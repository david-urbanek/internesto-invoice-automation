import os

from google import genai
from google.genai import types
from pydantic import BaseModel

from .config import ALIASY, FIREMNI_UCTY, KATEGORIE, KATEGORIE_PRIJMY_A_MAJITEL, MODEL
from .faktura_index import predparuj


class _Transakce(BaseModel):
    id: int
    kategorie: str
    faktura: str
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


def kategorizuj_transakce(
    transakce: list[dict],
    faktury_cesty: list[str],
    client: genai.Client,
    firma_index: dict | None = None,
) -> list[dict]:
    if firma_index:
        transakce = predparuj(transakce, firma_index)

    jmena_faktur = [os.path.basename(c) for c in faktury_cesty]
    platne_faktury = set(jmena_faktur)

    radky = [
        f"{'ID':<4} {'Datum':<12} {'Objem':>10} {'Protiúčet':<18} {'Protistrana':<26} "
        f"{'Pozn.':<18} {'Zpráva':<28} {'VS':<12} {'Faktura (det.)':<30}"
    ]
    radky.append("-" * 155)
    for i, t in enumerate(transakce):
        predparovana = t.get("Faktura") if t.get("_predparovano") else ""
        radky.append(
            f"{i:<4} "
            f"{t.get('Datum', ''):<12} "
            f"{t.get('Objem', ''):>10} "
            f"{t.get('Číslo protiúčtu', t.get('Protiúčet', '')):<18} "
            f"{t.get('Název protiúčtu', ''):<26} "
            f"{t.get('Poznámka', ''):<18} "
            f"{t.get('Zpráva pro příjemce', ''):<28} "
            f"{t.get('VS', ''):<12} "
            f"{predparovana:<30}"
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
    aliasy_text = "\n".join(
        f"  \"{s}\" → \"{k}\"" for s, k in ALIASY.items()
    )

    prompt = f"""Jsi asistent pro kategorizaci účetních transakcí české firmy provozující apartmány.

## Firemní účty
Tyto protiúčty patří vlastním účtům firmy – transakce na ně jsou interní převody:
{firemni_ucty_text}

## Instrukce
1. Přiřaď každé transakci kategorii ze seznamu níže.
2. Shoda na protiúčtu nebo klíčovém slově má přednost před jménem dodavatele.
3. Pokud „Poznámka" obsahuje starý/chybný štítek ze ALIASŮ, použij kanonický název.
4. Přiřazení faktury — pravidla v pořadí priority:
   a) Sloupec „Faktura (det.)" je neprázdný → tato faktura byla deterministicky ověřena, NEMĚŇ ji.
   b) Shoda VS transakce s VS nebo názvem souboru faktury.
   c) Karetní transakce bez VS: shoda přesné částky + jména dodavatele z PŘEHLEDU FAKTUR.
   d) Shoda data + částky.
   Používej VÝHRADNĚ názvy ze seznamu DOSTUPNÉ FAKTURY — nic nevymýšlej.
5. Uveď pravděpodobnost jistoty 0–100.
6. Pokud kategorii nelze určit, použij „Neurčeno".

## Aliasy
{aliasy_text}

## Přehled faktur (pro párování dle částky a dodavatele)
{chr(10).join(prehled_radky)}

## Dostupné kategorie
### Firemní výdaje a interní převody
{chr(10).join(_formatuj_kategorii(k) for k in KATEGORIE)}

### Příjmy a osobní výdaje majitele
{chr(10).join(_formatuj_kategorii(k) for k in KATEGORIE_PRIJMY_A_MAJITEL)}

## Transakce k zategorizování
{chr(10).join(radky)}

Vrať záznam pro každou transakci (celkem {len(transakce)} záznamů), ve stejném pořadí."""

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
            f"Pravděpodobně příliš velký kontext ({len(transakce)} transakcí)."
        )
    vysledky = response.parsed.transakce

    for v in vysledky:
        if not (0 <= v.id < len(transakce)):
            continue
        transakce[v.id]["Kategorie"] = v.kategorie
        transakce[v.id]["Poznamka"] = v.poznamka
        transakce[v.id]["Jistota"] = v.jistota

        if transakce[v.id].get("_predparovano"):
            pass
        else:
            faktura = v.faktura or ""
            transakce[v.id]["Faktura"] = faktura if faktura in platne_faktury else "NENALEZENO"

    for t in transakce:
        t.pop("_predparovano", None)

    return transakce
