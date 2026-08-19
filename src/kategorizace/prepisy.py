"""
Deterministické přepisy kategorie po AI kategorizaci.

aplikuj_interni_prevod – transakce s protiúčtem patřícím některému z interních
účtů skupiny (FIREMNI_UCTY) je interní převod → "Převod". Výjimkou jsou
kategorie, které daný protiúčet explicitně deklarují v protiucty (Splátka,
Výplata majitele, Kotlářská, Rezervní…) – to jsou záměrně zvlášť sledované
interní toky a zůstávají.

aplikuj_jidlo_podle_provedl – u karetních nákupů jídla (kategorie "Jídlo")
na účtu Nesty Ostatní přepíše kategorii na osobní výdaj podle toho, kdo
transakci provedl (sloupec "Provedl" z Fio výpisu) – viz JIDLO_PODLE_PROVEDL
a UCET_NESTY_OSTATNI v config.py.

omezene_kategorie_pro_soubor – pozná, že výpis patří k účtu s uzavřeným
seznamem historicky možných kategorií (viz OMEZENE_KATEGORIE_PODLE_UCTU
v config.py) a vrátí tento seznam pro ai.kategorizuj_transakce, aby AI mohla
vybírat jen z něj místo z celého seznamu kategorií.

aplikuj_kotlarska_pronajem_bytu – na účtu RD Příjmový (UCET_RD_PRIJMOVY)
přepíše kategorii na "Kotlářská" u transakcí se štítkem "pronájem bytu"
v Poznámce, bez ohledu na to, co AI vybrala podle protiúčtu (často sdíleného
s Casa Libre Příjmový, což ji svádí k obecnému "Převod").

aplikuj_prevod_zpetna_platba – pokud se na stejném protiúčtu vrátí stejná
částka opačným směrem (typicky u protiúčtů kategorie "Splátka"), nejde
o splátku úvěru, ale o interní přesun peněz (např. půjčka/vratka společníka
tam a zpět) -> obě transakce se přepíšou na kategorii "Převod".

aplikuj_telefony_nejvyssi_castka – z plateb T-Mobile (účet UCET_TMOBILE)
v daném výpisu je "Telefony" jen ta s nejvyšší částkou, ostatní se přepíšou
na "Zvláštní výdaj".

aplikuj_vzdy_dodavatel – pro dodavatele z VZDY_DODAVATEL_KATEGORIE (config.py)
platí vždy stejná kategorie bez ohledu na znaménko částky (nákup i vratka).
Ne úplně bezpodmínečně – VYJIMKY_VZDY_DODAVATEL (config.py) definuje výjimky
podle dalšího klíčového slova v textu (např. "Alza" je vždy "Dekorace", ALE
"Alza" + "V24" v Poznámce je "V24"). Na výpisech s uzavřeným seznamem
kategorií (omezene_kategorie) se navíc neuplatní, pokud výsledná kategorie
do tohoto seznamu nepatří.
"""

import os
import re
from collections import defaultdict

from .config import (
    FIREMNI_UCTY,
    JIDLO_PODLE_PROVEDL,
    KATEGORIE,
    KATEGORIE_PREPIS_PODLE_PROVEDL,
    KATEGORIE_PRIJMOVE,
    KLICOVA_SLOVA_KOTLARSKA_RD_PRIJMOVY,
    MAPOVANI_NA_FORMULAR,
    OMEZENE_KATEGORIE_PODLE_UCTU,
    POKLADNA_JMENA_KATEGORIE,
    UCET_NESTY_OSTATNI,
    UCET_RD_PRIJMOVY,
    UCET_TMOBILE,
    VYJIMKY_VZDY_DODAVATEL,
    VZDY_DODAVATEL_KATEGORIE,
)

_KATEGORIE_PRIJMOVE_NAZVY = {k["nazev"] for k in KATEGORIE_PRIJMOVE}


def aplikuj_interni_prevod(transakce: list[dict]) -> list[dict]:
    """
    Přepíše kategorii na "Převod" u transakcí, jejichž protiúčet je interní
    účet skupiny (FIREMNI_UCTY).

    Výjimka: pokud AI přiřadila kategorii, která tento protiúčet sama
    deklaruje v configu (Splátka → úvěrové účty MONETA, Výplata majitele →
    účty Radka Danče, Kotlářská → Casa Příjmový…), kategorie zůstává –
    jde o záměrně zvlášť sledovaný interní tok, ne o obyčejný přesun peněz.
    """
    povolene_kategorie: dict[str, set[str]] = {}
    for k in KATEGORIE + KATEGORIE_PRIJMOVE:
        for ucet in k.get("protiucty") or []:
            povolene_kategorie.setdefault(ucet.strip(), set()).add(k["nazev"])

    for t in transakce:
        protiucet = (t.get("Číslo protiúčtu") or t.get("Protiúčet") or "").strip()
        if not protiucet or protiucet not in FIREMNI_UCTY:
            continue
        kategorie = t.get("Kategorie", "")
        if kategorie == "Převod" or kategorie in povolene_kategorie.get(protiucet, set()):
            continue
        puvodni_poznamka = t.get("Poznamka", "")
        t["Kategorie"] = "Převod"
        t["Poznamka"] = (
            f"{puvodni_poznamka} Přepsáno z '{kategorie}' na 'Převod' – protiúčet "
            f"{protiucet} je firemní účet ({FIREMNI_UCTY[protiucet]})."
        ).strip()

    return transakce


def _bez_diakritiky(s: str) -> str:
    return (
        s.lower()
        .replace("á", "a").replace("í", "i").replace("é", "e")
        .replace("ý", "y").replace("ř", "r").replace("š", "s")
        .replace("č", "c").replace("ž", "z").replace("ů", "u")
        .replace("ú", "u").replace("ň", "n").replace("ť", "t").replace("ď", "d")
    )


def _soubor_patri_uctu(nazev_souboru: str, cislo_uctu: str, klicove_slovo: str) -> bool:
    """
    Pozná výpis daného účtu z názvu souboru dvěma způsoby:
      1. Fio export obsahuje číslo účtu v názvu ("Vypis_z_uctu-<cislo_uctu>_...")
         -> porovná se s cislo_uctu.
      2. Soubor je ručně pojmenovaný popisně a obsahuje klicove_slovo
         (case-insensitive, bez diakritiky) -> např. "Nesty Ostatní.csv",
         "RD Ostatní (1).csv".
    """
    zaklad = os.path.basename(nazev_souboru)

    m = re.search(r"Vypis_z_uctu-(\d+)", zaklad)
    if m and cislo_uctu and m.group(1) == cislo_uctu:
        return True

    return klicove_slovo in _bez_diakritiky(zaklad)


def _je_ucet_ostatni(nazev_souboru: str) -> bool:
    return _soubor_patri_uctu(nazev_souboru, UCET_NESTY_OSTATNI, "ostatni")


def omezene_kategorie_pro_soubor(nazev_souboru: str) -> list[str] | None:
    """
    Pro výpisy s historicky omezenou nabídkou kategorií vrátí seznam, ze
    kterého má AI vybírat (pro ai.kategorizuj_transakce), jinak None.

    Prohledá OMEZENE_KATEGORIE_PODLE_UCTU (config.py) podle čísla účtu nebo
    klíčového slova v názvu souboru (viz _soubor_patri_uctu) – klíč slovníku
    je jen identifikátor záznamu, není potřeba znát firma_nazev. Každý
    záznam má buď "kategorie" (uzavřený POVOLOVACÍ seznam – AI smí vybrat
    jen z něj, např. RD Ostatní), nebo "vyloucene" (VYLUČOVACÍ seznam – AI
    smí vybrat cokoliv KROMĚ těchto kategorií, např. Pokladna, kde nikdy
    nesmí vyjít "Výdaje majitele").
    """
    for klic, zaznam in OMEZENE_KATEGORIE_PODLE_UCTU.items():
        if not _soubor_patri_uctu(nazev_souboru, klic, zaznam["klicove_slovo"]):
            continue
        if "kategorie" in zaznam:
            return zaznam["kategorie"]
        vyloucene = set(zaznam.get("vyloucene", []))
        vsechny_kategorie = [k["nazev"] for k in KATEGORIE + KATEGORIE_PRIJMOVE]
        return [n for n in vsechny_kategorie if n not in vyloucene]
    return None


def aplikuj_kotlarska_pronajem_bytu(
    transakce: list[dict],
    nazev_souboru: str,
    firma_nazev: str,
) -> list[dict]:
    """
    Na účtu RD Příjmový přepíše kategorii na "Kotlářská" u transakcí se
    štítkem "pronájem bytu" v Poznámce – bez ohledu na to, co AI vybrala
    podle protiúčtu (často sdíleného s Casa Libre Příjmový, což ji svádí
    k obecnému "Převod").
    """
    if firma_nazev != "RD" or not _soubor_patri_uctu(nazev_souboru, UCET_RD_PRIJMOVY, "prijmovy"):
        return transakce

    for t in transakce:
        text = _bez_diakritiky(_text_transakce(t))
        if not any(klic in text for klic in KLICOVA_SLOVA_KOTLARSKA_RD_PRIJMOVY):
            continue
        if t.get("Kategorie") != "Kotlářská":
            puvodni_poznamka = t.get("Poznamka", "")
            puvodni_kategorie = t.get("Kategorie")
            t["Kategorie"] = "Kotlářská"
            t["Poznamka"] = (
                f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na 'Kotlářská' – "
                f"účet RD Příjmový a štítek 'pronájem bytu' vždy patří k nájmu Kotlářská."
            ).strip()

    return transakce


def aplikuj_jidlo_podle_provedl(
    transakce: list[dict],
    nazev_souboru: str,
    firma_nazev: str,
) -> list[dict]:
    """
    Přepíše kategorii "Jídlo" na osobní výdaj podle karty, kterou byl nákup proveden.

    Platí VÝHRADNĚ pro firmu Nesty a účet Ostatní – poznaný buď podle čísla účtu
    (UCET_NESTY_OSTATNI v config.py), nebo podle slova "ostatní" v názvu souboru
    (viz _je_ucet_ostatni). Bez ani jedné shody se pravidlo neaplikuje vůbec
    (žádný fallback na celou firmu) – riskovali bychom přepsání legitimních
    firemních nákupů jídla na jiných účtech.
    """
    if firma_nazev != "Nesty" or not _je_ucet_ostatni(nazev_souboru):
        return transakce

    for t in transakce:
        puvodni_kategorie = t.get("Kategorie")
        if puvodni_kategorie not in KATEGORIE_PREPIS_PODLE_PROVEDL:
            continue
        provedl = (t.get("Provedl") or "").lower()
        for jmeno, nova_kategorie in JIDLO_PODLE_PROVEDL.items():
            if jmeno in provedl:
                puvodni_poznamka = t.get("Poznamka", "")
                t["Kategorie"] = nova_kategorie
                t["Poznamka"] = (
                    f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na "
                    f"'{nova_kategorie}' podle karty ({t.get('Provedl', '')})."
                ).strip()
                break

    return transakce


def aplikuj_pradlo_pokladna(transakce: list[dict], firma_nazev: str) -> list[dict]:
    """
    Na Pokladně popisek obsahující "prádlo" (např. "Petr prádlo", "ostatní
    Petr výplata prádlo") vždy patří do kategorie "Recepční" – jde o odměnu
    recepční/recepčnímu za vyprané prádlo v hotovosti, ne o platbu externí
    prádelně (ta se řeší fakturou od Christofa, kategorie "Prádelna").
    """
    if firma_nazev != "Pokladna":
        return transakce

    for t in transakce:
        text = _bez_diakritiky(_text_transakce(t))
        if "pradlo" not in text or t.get("Kategorie") == "Recepční":
            continue
        puvodni_poznamka = t.get("Poznamka", "")
        puvodni_kategorie = t.get("Kategorie")
        t["Kategorie"] = "Recepční"
        t["Poznamka"] = (
            f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na 'Recepční' – "
            f"na Pokladně popisek 'prádlo' je odměna recepční, ne externí prádelna."
        ).strip()

    return transakce


def aplikuj_jmena_pokladna(transakce: list[dict], firma_nazev: str) -> list[dict]:
    """
    Na Pokladně popisek se jménem z POKLADNA_JMENA_KATEGORIE (celé slovo,
    bez diakritiky) je hotovostní výplata/odměna dané osoby → její kategorie
    (Petr → Recepční, Vendula/Iva → Úklid). Ověřeno na schválené historii.
    """
    if firma_nazev != "Pokladna":
        return transakce

    for t in transakce:
        text = _bez_diakritiky(_text_transakce(t))
        slova = set(re.findall(r"[a-z]+", text))
        for jmeno, nova_kategorie in POKLADNA_JMENA_KATEGORIE.items():
            if jmeno not in slova or t.get("Kategorie") == nova_kategorie:
                continue
            puvodni_poznamka = t.get("Poznamka", "")
            puvodni_kategorie = t.get("Kategorie")
            t["Kategorie"] = nova_kategorie
            t["Poznamka"] = (
                f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na '{nova_kategorie}' – "
                f"hotovostní výplata/odměna ({jmeno.capitalize()}) na Pokladně."
            ).strip()
            break

    return transakce


def aplikuj_jidlo_pokladna(transakce: list[dict], firma_nazev: str) -> list[dict]:
    """
    Na Pokladně hotovostní nákupy pečiva/snídaní ("Ostatní - pečivo, snídaně")
    patří do "Jídlo", ne "Snídaně" – rozhodnutí uživatele 07/2026. Kategorie
    "Snídaně" je pro fakturované snídaně, ne drobné hotovostní nákupy.
    """
    if firma_nazev != "Pokladna":
        return transakce

    for t in transakce:
        text = _bez_diakritiky(_text_transakce(t))
        if ("pecivo" not in text and "snidan" not in text) or t.get("Kategorie") == "Jídlo":
            continue
        puvodni_poznamka = t.get("Poznamka", "")
        puvodni_kategorie = t.get("Kategorie")
        t["Kategorie"] = "Jídlo"
        t["Poznamka"] = (
            f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na 'Jídlo' – "
            f"hotovostní nákup pečiva/snídaně na Pokladně je Jídlo."
        ).strip()

    return transakce


def _parsuj_castku(s: str) -> float | None:
    s = (s or "").strip().replace(" ", "").replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def aplikuj_prevod_zpetna_platba(transakce: list[dict]) -> list[dict]:
    """
    Přepíše kategorii "Splátka" na "Převod", pokud na stejném protiúčtu existuje
    jiná transakce se stejnou absolutní částkou a opačným znaménkem (peníze se
    tam a zpět jen přesunuly, nešlo o skutečnou splátku úvěru).
    """
    skupiny_podle_uctu: dict[str, list[dict]] = defaultdict(list)
    for t in transakce:
        protiucet = (t.get("Číslo protiúčtu") or t.get("Protiúčet") or "").strip()
        if protiucet:
            skupiny_podle_uctu[protiucet].append(t)

    spareno: set[int] = set()
    for protiucet, skupina in skupiny_podle_uctu.items():
        for t in skupina:
            if t.get("Kategorie") != "Splátka" or id(t) in spareno:
                continue
            castka = _parsuj_castku(t.get("Objem", ""))
            if castka is None:
                continue
            for druhy in skupina:
                if druhy is t or id(druhy) in spareno:
                    continue
                druha_castka = _parsuj_castku(druhy.get("Objem", ""))
                if druha_castka is not None and abs(druha_castka + castka) < 0.01:
                    for radek in (t, druhy):
                        if radek.get("Kategorie") == "Splátka":
                            puvodni_poznamka = radek.get("Poznamka", "")
                            radek["Kategorie"] = "Převod"
                            radek["Poznamka"] = (
                                f"{puvodni_poznamka} Přepsáno z 'Splátka' na 'Převod' – "
                                f"částka se na protiúčtu {protiucet} vrátila zpět."
                            ).strip()
                        spareno.add(id(radek))
                    break

    return transakce


def aplikuj_telefony_nejvyssi_castka(transakce: list[dict]) -> list[dict]:
    """
    Z plateb na účtu T-Mobile (UCET_TMOBILE) je "Telefony" jen ta s nejvyšší
    absolutní částkou v daném výpisu, ostatní se přepíšou na "Zvláštní výdaj".
    """
    tmobile = [
        t for t in transakce
        if (t.get("Číslo protiúčtu") or t.get("Protiúčet") or "").strip() == UCET_TMOBILE
        and t.get("Kategorie") in ("Telefony", "Zvláštní výdaj")
    ]

    castky = [(abs(c), t) for t in tmobile if (c := _parsuj_castku(t.get("Objem", ""))) is not None]
    if len(castky) < 2:
        return transakce

    nejvyssi_t = max(castky, key=lambda x: x[0])[1]

    for _, t in castky:
        nova_kategorie = "Telefony" if t is nejvyssi_t else "Zvláštní výdaj"
        if t.get("Kategorie") != nova_kategorie:
            puvodni_poznamka = t.get("Poznamka", "")
            puvodni_kategorie = t.get("Kategorie")
            t["Kategorie"] = nova_kategorie
            t["Poznamka"] = (
                f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na '{nova_kategorie}' "
                f"– {'nejvyšší' if nova_kategorie == 'Telefony' else 'není nejvyšší'} platba T-Mobile ve výpisu."
            ).strip()

    return transakce


def _text_transakce(t: dict) -> str:
    casti = [
        t.get("Název protiúčtu", ""),
        t.get("Poznámka", ""),
        t.get("Zpráva pro příjemce", ""),
    ]
    return " ".join(c for c in casti if c).lower()


def aplikuj_vzdy_dodavatel(
    transakce: list[dict],
    omezene_kategorie: list[str] | None = None,
) -> list[dict]:
    """
    Pro dodavatele z VZDY_DODAVATEL_KATEGORIE je kategorie vždy stejná bez
    ohledu na znaménko částky (nákup i vratka/refundace) – s výjimkami
    z VYJIMKY_VZDY_DODAVATEL podle dalšího klíčového slova v textu (např.
    "Alza" + "V24" je "V24", ne obecné "Dekorace").

    Pokud má výpis uzavřený seznam kategorií (omezene_kategorie – viz
    prepisy.omezene_kategorie_pro_soubor), pravidlo se NEUPLATNÍ, pokud
    výsledná kategorie do tohoto seznamu nepatří – jinak by přepsalo správně
    omezenou AI kategorizaci (např. "alza" → "Dekorace" na účtu RD Ostatní,
    kde smí být jen Benzín / Výdaje majitele / Převod).
    """
    for t in transakce:
        text = _text_transakce(t)
        for klic, obecna_kategorie in VZDY_DODAVATEL_KATEGORIE.items():
            if klic not in text:
                continue

            nova_kategorie = obecna_kategorie
            vyjimecne_slovo = None
            for extra_slovo, vyjimecna_kategorie in VYJIMKY_VZDY_DODAVATEL.get(klic, []):
                if extra_slovo in text:
                    nova_kategorie = vyjimecna_kategorie
                    vyjimecne_slovo = extra_slovo
                    break

            if omezene_kategorie is not None and nova_kategorie not in omezene_kategorie:
                break
            if t.get("Kategorie") != nova_kategorie:
                puvodni_poznamka = t.get("Poznamka", "")
                puvodni_kategorie = t.get("Kategorie")
                t["Kategorie"] = nova_kategorie
                if vyjimecne_slovo:
                    t["Poznamka"] = (
                        f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na '{nova_kategorie}' "
                        f"– dodavatel '{klic}' je obvykle '{obecna_kategorie}', ale text obsahuje "
                        f"'{vyjimecne_slovo}' → výjimka na '{nova_kategorie}'."
                    ).strip()
                else:
                    t["Poznamka"] = (
                        f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na '{nova_kategorie}' "
                        f"– dodavatel '{klic}' je vždy tato kategorie bez ohledu na znaménko částky."
                    ).strip()
            break

    return transakce


def _radek_pro_kategorii(kategorie: str, objem: str | None, mena: str | None) -> str:
    """
    Namapuje kategorii na ID řádku Alokačního formuláře (config.MAPOVANI_NA_FORMULAR).

    "P<n>" = příjmový řádek, "N<n>" = výdajový řádek. Kategorie, které nejsou
    v MAPOVANI_NA_FORMULAR vůbec, nebo mají hodnotu None (vědomě bez řádku /
    čeká na klienta – viz docs/otazky-pro-klienta.md), dostanou "P00"/"N00"
    podle toho, zda kategorie patří mezi příjmové, nebo výdajové – peníze se
    tak nikdy neztratí potichu, jen se objeví jako nenamapované.
    """
    prefix = "P" if kategorie in _KATEGORIE_PRIJMOVE_NAZVY else "N"
    nenamapovano = f"{prefix}00"
    cil = MAPOVANI_NA_FORMULAR.get(kategorie)
    if cil is None:
        return nenamapovano
    if isinstance(cil, str):
        return cil
    if "+" in cil or "-" in cil:
        castka = _parsuj_castku(objem) or 0.0
        return cil.get("+" if castka >= 0 else "-", nenamapovano)
    # currency-keyed dict, např. {"CZK": "P4", "EUR": "P6"}
    return cil.get((mena or "CZK").strip().upper(), nenamapovano)


def aplikuj_radek_formulare(transakce: list[dict], firma_nazev: str) -> list[dict]:
    """
    Doplní ke každé transakci sloupce "Firma" (název firmy dle složky) a
    "Radek" (ID řádku Alokačního formuláře, viz _radek_pro_kategorii výš).
    Musí běžet AŽ PO všech ostatních přepisech, protože se řídí finální
    kategorií transakce.
    """
    for t in transakce:
        t["Firma"] = firma_nazev
        t["Radek"] = _radek_pro_kategorii(t.get("Kategorie", ""), t.get("Objem"), t.get("Měna"))
    return transakce
