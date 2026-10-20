"""
Deterministická kategorizace PŘED voláním AI.

Postaveno na analýze schválených výpisů (leden–květen 2026, 2 492 transakcí):
zhruba 60 % transakcí má jednoznačný signál, u kterého AI nemá co rozhodovat.
Transakce zkategorizované tady dostanou Jistota kategorie 100 a AI kategorizace
(ai.kategorizuj_transakce) je přeskočí – řeší jen zbytek.

Pravidla v pořadí priority:
  1. ÚČET S PEVNOU KATEGORIÍ (UCET_VZDY_KATEGORIE) – Premier Fond a rezervní
     účty mají svou kategorii VŽDY, přebíjí i uživatelský štítek.
  2. ŠTÍTEK – uživatelův štítek (Poznámka) po normalizaci přes ALIASY přesně
     odpovídá názvu kategorie. Uživatelův ručně psaný štítek je nejspolehlivější
     signál, jaký máme.
  3. TEXTOVÝ MARKER (VZDY_TEXT_KATEGORIE) – jednoznačný identifikátor v textu
     (odběrná místa, čísla úvěrových smluv, Comgate).
  4. ÚVĚROVÝ ÚČET (SPLATKY_UVERU) – na úvěrové účty MONETA je "Splátka" jen
     fixní měsíční částka dle smlouvy; jiné částky jsou doplňování prostředků
     a interní obraty → "Převod". Neznámá částka s textem "splátk" jde do AI
     (možná refixace úroku).
  5. PROTIÚČET – protiúčet deklaruje v configu právě JEDNA kategorie.
     Sdílené protiúčty (V19/Kotlářská/Garant, Telefony/Zvláštní výdaj…)
     zůstávají na AI + přepisech.
  6. FIREMNÍ ÚČET – protiúčet je interní účet skupiny bez jiného signálu
     → "Převod" (stejná logika jako prepisy.aplikuj_interni_prevod, jen dopředu).

Respektuje omezene_kategorie (uzavřené seznamy per účet) – kategorie mimo
povolený seznam se deterministicky nepřiřadí a transakce jde do AI.
"""

from .config import (
    ALIASY,
    FIREMNI_UCTY,
    KATEGORIE,
    KATEGORIE_PRIJMOVE,
    SPLATKY_UVERU,
    UCET_VZDY_KATEGORIE,
    VZDY_TEXT_KATEGORIE,
)
from .prepisy import POZNAMKA_STITEK_PREFIX, _parsuj_castku, _protiucet


def _mapy_pravidel() -> tuple[dict[str, str], dict[str, str], set[str]]:
    """
    Vrátí (štítek→kategorie, protiúčet→kategorie s právě jednou deklarací,
    množina všech deklarovaných protiúčtů).
    """
    podle_stitku: dict[str, str] = {}
    for k in KATEGORIE + KATEGORIE_PRIJMOVE:
        podle_stitku[k["nazev"].strip().casefold()] = k["nazev"]
    for alias, kanonicky in ALIASY.items():
        podle_stitku.setdefault(alias.strip().casefold(), kanonicky)

    deklarace: dict[str, set[str]] = {}
    for k in KATEGORIE + KATEGORIE_PRIJMOVE:
        for ucet in k.get("protiucty") or []:
            deklarace.setdefault(ucet.strip(), set()).add(k["nazev"])
    podle_uctu = {u: next(iter(kat)) for u, kat in deklarace.items() if len(kat) == 1}
    return podle_stitku, podle_uctu, set(deklarace)


def aplikuj_deterministickou_kategorizaci(
    transakce: list[dict],
    omezene_kategorie: list[str] | None = None,
) -> list[dict]:
    """
    Přiřadí Kategorie + Jistota kategorie=100 transakcím s jednoznačným signálem.
    Ostatní nechá beze změny (Kategorie nenastaví) – ty půjdou do AI.
    """
    podle_stitku, podle_uctu, deklarovane_ucty = _mapy_pravidel()

    def povolena(kategorie: str) -> bool:
        return omezene_kategorie is None or kategorie in omezene_kategorie

    for t in transakce:
        if t.get("Kategorie"):
            continue

        ucet = _protiucet(t)

        kategorie = UCET_VZDY_KATEGORIE.get(ucet)
        if kategorie and povolena(kategorie):
            t["Kategorie"] = kategorie
            t["Jistota kategorie"] = 100
            t["Poznamka"] = (
                f"Deterministicky: protiúčet {ucet} má vždy kategorii "
                f"'{kategorie}' bez ohledu na štítek."
            )
            continue

        stitek = (t.get("Poznámka") or "").strip().casefold()
        kategorie = podle_stitku.get(stitek) if stitek else None
        if kategorie and povolena(kategorie):
            t["Kategorie"] = kategorie
            t["Jistota kategorie"] = 100
            t["Poznamka"] = f"{POZNAMKA_STITEK_PREFIX} '{t.get('Poznámka', '').strip()}'."
            continue

        text = " ".join(
            str(t.get(k) or "")
            for k in ("Poznámka", "Zpráva pro příjemce", "Název protiúčtu")
        ).casefold()
        for marker, kat_marker in VZDY_TEXT_KATEGORIE.items():
            if marker in text and povolena(kat_marker):
                t["Kategorie"] = kat_marker
                t["Jistota kategorie"] = 100
                t["Poznamka"] = f"Deterministicky: text obsahuje '{marker}'."
                break
        if t.get("Kategorie"):
            continue

        if not ucet:
            continue

        if ucet in SPLATKY_UVERU:
            castka = _parsuj_castku(t.get("Objem", ""))
            text = " ".join(
                str(t.get(k) or "") for k in ("Poznámka", "Zpráva pro příjemce")
            ).lower()
            if castka is None:
                continue  # bez částky nechej na AI
            if any(abs(abs(castka) - fixni) < 0.01 for fixni in SPLATKY_UVERU[ucet]):
                if povolena("Splátka"):
                    t["Kategorie"] = "Splátka"
                    t["Jistota kategorie"] = 100
                    t["Poznamka"] = (
                        f"Deterministicky: fixní splátka úvěru {abs(castka):.2f} "
                        f"na účet {ucet}."
                    )
                continue
            if "splátk" in text or "splatk" in text:
                continue  # neznámá částka se zmínkou o splátce – možná refixace, do AI
            if povolena("Převod"):
                t["Kategorie"] = "Převod"
                t["Jistota kategorie"] = 100
                t["Poznamka"] = (
                    f"Deterministicky: částka {castka} na úvěrový účet {ucet} "
                    f"neodpovídá fixní splátce → interní přesun peněz."
                )
            continue

        kategorie = podle_uctu.get(ucet)
        if kategorie and povolena(kategorie):
            t["Kategorie"] = kategorie
            t["Jistota kategorie"] = 100
            t["Poznamka"] = f"Deterministicky: protiúčet {ucet} patří jednoznačně kategorii."
            continue

        # Firemní účet deklarovaný nějakou kategorií (Výplata majitele, DPH,
        # Premier, Splátka…) musí rozhodnout AI – tady jen nedeklarované.
        if ucet in FIREMNI_UCTY and ucet not in deklarovane_ucty and povolena("Převod"):
            t["Kategorie"] = "Převod"
            t["Jistota kategorie"] = 100
            t["Poznamka"] = (
                f"Deterministicky: protiúčet {ucet} je firemní účet "
                f"({FIREMNI_UCTY[ucet]}) bez jiného signálu → Převod."
            )

    return transakce
