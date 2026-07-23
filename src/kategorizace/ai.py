"""
Dvoustupňová AI kategorizace transakcí s využitím indexu faktur.

kategorizuj_transakce – hlavní funkce:
  1. Deterministické předpárování (faktura_index.predparuj) – VS, VS ve zprávě,
     účet+částka. Tyto shody AI nesmí přepsat.
  2. AI PÁROVÁNÍ (_paruj_faktury) – pro každou nespárovanou transakci se
     deterministicky sestaví shortlist kandidátů (faktura_index.kandidati_pro_transakci)
     a Gemini vybírá VÝHRADNĚ z nich. Výběr mimo kandidáty nebo s nízkou
     jistotou se zamítne → NENALEZENO. Transakce bez kandidátů do AI vůbec nejdou.
  3. AI KATEGORIZACE – druhý Gemini call přiřadí kategorie; faktury už jen čte
     jako vodítko (položky/dodavatel spárované faktury), neměni je.

Výstupní sloupce: Kategorie, Faktura, Poznamka, Jistota a Parovani
(jak byla faktura přiřazena: deterministicky / AI / zamítnuto / prázdné).
"""

import os

from google import genai
from google.genai import types
from pydantic import BaseModel

from .config import ALIASY, FIREMNI_UCTY, KATEGORIE, KATEGORIE_PRIJMY_A_MAJITEL, MODEL
from .faktura_index import kandidati_pro_transakci, predparuj

MIN_JISTOTA_PAROVANI = 50


class _Parovani(BaseModel):
    id: int
    faktura: str
    jistota: int


class _VysledekParovani(BaseModel):
    transakce: list[_Parovani]


class _Transakce(BaseModel):
    id: int
    kategorie: str
    poznamka: str
    jistota: int


class _Vysledek(BaseModel):
    transakce: list[_Transakce]


def _formatuj_kategorii(k: dict) -> str:
    parts = [f"- **{k['nazev']}**: {k['popis']}"]
    if k.get("dodavatele"):
        parts.append(f"  Dodavatelé: {', '.join(k['dodavatele'])}.")
    if k.get("protiucty"):
        parts.append(f"  Protiúčty: {', '.join(k['protiucty'])}.")
    if k.get("klicova_slova"):
        parts.append(f"  Klíčová slova: {', '.join(k['klicova_slova'])}.")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Krok 2: AI párování faktur (jen nespárované transakce, jen z kandidátů)
# ---------------------------------------------------------------------------

def _paruj_faktury(
    transakce: list[dict],
    firma_index: dict,
    povolene: set[str],
    client: genai.Client,
) -> None:
    """
    AI páruje nespárované transakce s fakturami – výběr POUZE z deterministických
    kandidátů. Vše ostatní končí jako NENALEZENO. Zapisuje Faktura a Parovani.
    """
    kandidati_mapa: dict[int, list[dict]] = {}
    for i, t in enumerate(transakce):
        if t.get("Faktura"):
            continue
        kand = kandidati_pro_transakci(t, firma_index, povolene=povolene)
        if kand:
            kandidati_mapa[i] = kand
        else:
            t["Faktura"] = "NENALEZENO"
            t["Parovani"] = ""

    if not kandidati_mapa:
        return

    bloky = []
    for i, kand in sorted(kandidati_mapa.items()):
        t = transakce[i]
        radky_k = []
        for k in kand:
            radek = (
                f"  - {k['soubor']} | {k['dodavatel']} | "
                f"{k['castka'] if k['castka'] is not None else '?'} CZK | "
                f"{k['datum'] or '?'} | VS {k['vs'] or '-'} | "
                f"signály: {', '.join(k['duvody'])}"
            )
            if k["polozky"]:
                radek += f" | položky: {', '.join(k['polozky'][:3])}"
            radky_k.append(radek)
        bloky.append(
            f"### Transakce {i}\n"
            f"Datum: {t.get('Datum', '')} | Objem: {t.get('Objem', '')} | "
            f"Protistrana: {t.get('Název protiúčtu', '')} | "
            f"Protiúčet: {t.get('Číslo protiúčtu', t.get('Protiúčet', ''))} | "
            f"VS: {t.get('VS', '')} | Už.štítek: {t.get('Poznámka', '')} | "
            f"Zpráva: {t.get('Zpráva pro příjemce', '')}\n"
            f"Kandidáti:\n" + "\n".join(radky_k)
        )

    prompt = f"""Jsi asistent pro párování bankovních transakcí s fakturami.

Pro každou transakci níže rozhodni, která z JEJÍCH kandidátních faktur k ní patří.

Pravidla:
1. Vybírej VÝHRADNĚ ze seznamu kandidátů dané transakce. Pokud žádný kandidát nesedí, vrať prázdný řetězec "".
2. Síla signálů: shoda VS > shoda částky + dodavatele > shoda samotné částky.
3. Karetní platby nemají VS – páruj podle dodavatele a částky; datum faktury bývá do několika dní od data platby.
4. Jedna faktura patří typicky k jedné transakci – pokud stejný kandidát sedí na víc transakcí, přiřaď ho té s nejsilnějšími signály a u ostatních vrať "".
5. jistota 0–100. Pod {MIN_JISTOTA_PAROVANI} znamená, že si nejsi jistý – v tom případě raději vrať "".

{chr(10).join(bloky)}

Vrať záznam pro každou transakci (celkem {len(kandidati_mapa)} záznamů)."""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_VysledekParovani,
        ),
    )
    if response.parsed is None:
        # Párování selhalo – transakce zůstanou NENALEZENO, kategorizace proběhne dál
        for i in kandidati_mapa:
            transakce[i]["Faktura"] = "NENALEZENO"
            transakce[i]["Parovani"] = "AI párování selhalo"
        return

    vysledky = {v.id: v for v in response.parsed.transakce}
    for i, kand in kandidati_mapa.items():
        v = vysledky.get(i)
        jmena = {k["soubor"] for k in kand}
        if v and v.faktura and v.faktura in jmena and v.jistota >= MIN_JISTOTA_PAROVANI:
            transakce[i]["Faktura"] = v.faktura
            transakce[i]["Parovani"] = f"AI ({v.jistota} %)"
        else:
            transakce[i]["Faktura"] = "NENALEZENO"
            if v and v.faktura and v.faktura not in jmena:
                transakce[i]["Parovani"] = "AI zamítnuto ověřením (mimo kandidáty)"
            elif v and v.faktura:
                transakce[i]["Parovani"] = f"AI zamítnuto (jistota {v.jistota} %)"
            else:
                transakce[i]["Parovani"] = ""


# ---------------------------------------------------------------------------
# Krok 3: AI kategorizace (faktury už jsou přiřazené)
# ---------------------------------------------------------------------------

def kategorizuj_transakce(
    transakce: list[dict],
    faktury_cesty: list[str],
    client: genai.Client,
    firma_index: dict | None = None,
    omezene_kategorie: list[str] | None = None,
) -> list[dict]:
    """
    Kategorizuje transakce pomocí Gemini a vrátí je zpět s doplněnými sloupci.

    Args:
        transakce: řádky z CSV výpisu (list dictů z nacti_csv)
        faktury_cesty: cesty k fakturám relevantním pro toto období
        client: inicializovaný Gemini client
        firma_index: výstup postav_index — pokud je zadán, spustí deterministické
            předpárování a AI párování z kandidátů
        omezene_kategorie: pokud je zadán (viz prepisy.omezene_kategorie_pro_soubor),
            AI dostane místo celého seznamu kategorií jen tento uzavřený výběr —
            u výpisů, kde historicky připadají v úvahu jen konkrétní kategorie
            (např. účet RD Ostatní). Kategorie vrácená mimo tento seznam se
            neuplatní, transakce zůstane „Neurčeno" s poznámkou k ruční kontrole.

    Returns:
        Stejný list dictů s přidanými klíči: Kategorie, Faktura, Poznamka,
        Jistota, Parovani. Faktura je název souboru nebo "NENALEZENO".

    Raises:
        ValidationError: Gemini vrátil neočekávanou strukturu (handled v cli.py)
        ValueError: Gemini vrátil prázdnou odpověď — příliš velký kontext
    """
    jmena_faktur = [os.path.basename(c) for c in faktury_cesty]
    povolene = set(jmena_faktur)

    if firma_index:
        transakce = predparuj(transakce, firma_index)
        for t in transakce:
            if t.get("_predparovano"):
                t["Parovani"] = f"deterministicky ({t['_predparovano']})"
        _paruj_faktury(transakce, firma_index, povolene, client)
    else:
        # Bez indexu nelze sestavit kandidáty – párování se přeskočí
        for t in transakce:
            if not t.get("Faktura"):
                t["Faktura"] = "NENALEZENO"
                t["Parovani"] = "bez indexu faktur"

    # Transakce už zkategorizované deterministickou vrstvou
    # (deterministika.aplikuj_deterministickou_kategorizaci) do AI neposílej.
    k_ai = [i for i, t in enumerate(transakce) if not t.get("Kategorie")]
    if not k_ai:
        return _doplneno(transakce)

    radky = [
        f"{'ID':<4} {'Datum':<12} {'Objem':>10} {'Protiúčet':<18} {'Protistrana':<26} "
        f"{'Už.štítek':<20} {'Zpráva':<28} {'VS':<12} {'Faktura':<30}"
    ]
    radky.append("-" * 157)
    for i in k_ai:
        t = transakce[i]
        faktura = t.get("Faktura", "")
        radky.append(
            f"{i:<4} "
            f"{t.get('Datum', ''):<12} "
            f"{t.get('Objem', ''):>10} "
            f"{t.get('Číslo protiúčtu', t.get('Protiúčet', '')):<18} "
            f"{t.get('Název protiúčtu', ''):<26} "
            f"{t.get('Poznámka', ''):<20} "
            f"{t.get('Zpráva pro příjemce', ''):<28} "
            f"{t.get('VS', ''):<12} "
            f"{faktura:<30}"
        )

    prehled_radky = [f"{'Soubor':<55} {'Dodavatel':<30} {'CZK':>10} {'Datum':<12} {'Položky'}"]
    prehled_radky.append("-" * 140)
    index_mapa = firma_index or {}
    for fname in jmena_faktur:
        m = index_mapa.get(fname, {})
        polozky = ", ".join(m.get("polozky") or [])
        prehled_radky.append(
            f"{fname:<55} "
            f"{str(m.get('dodavatel') or ''):<30} "
            f"{str(m.get('castka') or '?'):>10} "
            f"{str(m.get('datum') or '?'):<12} "
            f"{polozky}"
        )

    firemni_ucty_text = "\n".join(
        f"  {c} → {n}" for c, n in FIREMNI_UCTY.items()
    )
    # Na výpisech s uzavřeným seznamem kategorií posílej jen aliasy, jejichž
    # cíl je v seznamu – jinak prompt obsahuje protichůdné instrukce (např.
    # "Alza" → "Dekorace" na účtu, kde Dekorace není povolená) a AI vrací
    # kategorie, které se pak zahazují na "Neurčeno".
    aliasy_text = "\n".join(
        f"  \"{s}\" → \"{k}\"" for s, k in ALIASY.items()
        if omezene_kategorie is None or k in omezene_kategorie
    )

    omezovaci_instrukce = ""
    if omezene_kategorie:
        vsechny_kategorie = {k["nazev"]: k for k in KATEGORIE + KATEGORIE_PRIJMY_A_MAJITEL}
        kategorie_sekce = (
            "## Dostupné kategorie (uzavřený výběr pro tento výpis)\n"
            + "\n".join(
                _formatuj_kategorii(vsechny_kategorie[n])
                for n in omezene_kategorie if n in vsechny_kategorie
            )
        )
        omezovaci_instrukce = (
            f"\n0. TENTO VÝPIS MÁ UZAVŘENÝ SEZNAM KATEGORIÍ: kategorie musí být VÝHRADNĚ jedna "
            f"z {', '.join(omezene_kategorie)}. Nepoužívej žádnou jinou kategorii ani pro "
            f"transakce, které by jinde patřily jinam."
        )
    else:
        kategorie_sekce = (
            "## Dostupné kategorie\n"
            "### Firemní výdaje a interní převody\n"
            f"{chr(10).join(_formatuj_kategorii(k) for k in KATEGORIE)}\n\n"
            "### Příjmy a osobní výdaje majitele\n"
            f"{chr(10).join(_formatuj_kategorii(k) for k in KATEGORIE_PRIJMY_A_MAJITEL)}"
        )

    prompt = f"""Jsi asistent pro kategorizaci účetních transakcí české firmy provozující apartmány.

## Firemní účty
Tyto protiúčty patří vlastním účtům firmy – transakce na ně jsou interní převody:
{firemni_ucty_text}

## Instrukce
1. Přiřaď každé transakci kategorii ze seznamu níže.
2. Shoda na protiúčtu nebo klíčovém slově má přednost před jménem dodavatele.
3. Sloupec „Už.štítek" je uživatelův vlastní ručně zapsaný popis transakce v internetbankingu —
   jedná se o nejspolehlivější vodítko ke kategorii. Pokud obsahuje starý/chybný štítek ze ALIASŮ,
   použij kanonický název.
4. Sloupec „Faktura" obsahuje již spárovanou fakturu (párování NEMĚNÍŠ). Pokud je vyplněná,
   použij dodavatele a položky této faktury z PŘEHLEDU FAKTUR jako silné vodítko ke kategorii.
5. Karetní platby (Zpráva/štítek začíná „Nákup:", chybí protiúčet) jsou nákupy u obchodníka –
   NIKDY to není interní „Převod", ani když „Název protiúčtu" obsahuje název vlastní firmy
   (u karetních plateb tam banka vyplňuje název VLASTNÍHO účtu, ne protistrany).
6. Uveď pravděpodobnost jistoty 0–100.
7. Pokud kategorii nelze určit, použij „Neurčeno".{omezovaci_instrukce}

## Aliasy
{aliasy_text}

## Přehled faktur (dodavatelé a položky spárovaných faktur)
{chr(10).join(prehled_radky)}

{kategorie_sekce}

## Transakce k zategorizování
{chr(10).join(radky)}

Vrať záznam pro každou transakci (celkem {len(k_ai)} záznamů), ve stejném pořadí.
Použij ID transakce přesně tak, jak je uvedeno v prvním sloupci."""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_Vysledek,
        ),
    )
    if response.parsed is None:
        finish = None
        if response.candidates:
            finish = response.candidates[0].finish_reason
        raise ValueError(
            f"Gemini vrátil prázdnou odpověď (finish_reason={finish}). "
            f"Pravděpodobně příliš velký kontext ({len(k_ai)} transakcí)."
        )
    vysledky = response.parsed.transakce

    k_ai_mnozina = set(k_ai)
    for v in vysledky:
        # Chybné ID mimo rozsah nebo na deterministicky zkategorizovaný řádek ignoruj
        if v.id not in k_ai_mnozina:
            continue
        kategorie, poznamka = v.kategorie, v.poznamka
        if omezene_kategorie and kategorie not in omezene_kategorie:
            poznamka = (
                f"{poznamka} POZOR: AI vrátila kategorii '{kategorie}' mimo uzavřený "
                f"seznam pro tento účet ({', '.join(omezene_kategorie)}) – zkontroluj ručně."
            ).strip()
            kategorie = "Neurčeno"
        transakce[v.id]["Kategorie"] = kategorie
        transakce[v.id]["Poznamka"] = poznamka
        transakce[v.id]["Jistota"] = v.jistota

    return _doplneno(transakce)


def _doplneno(transakce: list[dict]) -> list[dict]:
    for t in transakce:
        t.pop("_predparovano", None)
        # Každý řádek musí mít všechny výstupní sloupce (DictWriter v uloz_csv)
        t.setdefault("Kategorie", "Neurčeno")
        t.setdefault("Faktura", "NENALEZENO")
        t.setdefault("Poznamka", "")
        t.setdefault("Jistota", "")
        t.setdefault("Parovani", "")
    return transakce
