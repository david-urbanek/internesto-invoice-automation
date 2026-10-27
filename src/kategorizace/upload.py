"""
Samostatný příkaz: doplní do ručně odkategorizovaných výpisů v ``data/upload``
sloupce ``Kategorie``, ``Radek`` (ID řádku Alokačního formuláře) a ``Firma``,
BEZ volání AI. Kategorii bere z toho, co už klient napsal ručně, řádek dopočítá
přes stávající mapování ``MAPOVANI_NA_FORMULAR``.

Použití: ``uv run zpracuj-upload``

Chování (dohodnuto s klientem):

* **Staré měsíce (leden–květen) + Pokladna červen** – kategorie je v POSLEDNÍM
  sloupci listu (hlavička kolísá mezi ``Poznámka`` a ``Poznámky`` a je
  duplicitní, proto se bere podle pozice, ne podle jména). Hodnoty se ověří
  proti slovníku kategorií + ``ALIASY``; pokud poslední sloupec kategoriím
  neodpovídá, soubor se NEZPRACUJE a jen se nahlásí.
* **Červen (výstup pipeline)** – už má reálný sloupec ``Kategorie``. Ten se
  nechá být, doplní se jen ``Radek`` a ``Firma``. Pokud má list DRUHÝ, řídký
  sloupec ``Kategorie`` s ručními opravami klienta, má pro daný řádek přednost
  (rozhodnutí klienta) – pokud v něm je rozpoznatelná kategorie; komentáře a
  nesmysly spadnou zpět na primární pipeline kategorii a vypíšou se v reportu.
* Při kopírování do ``Kategorie`` a při výpočtu řádku se aplikují ``ALIASY``
  (``DPH Nesty`` → ``DPH``, ``Převod Výdajový 1`` → ``Převod`` …),
  case-insensitive (``TELEFONY`` → ``Telefony``). Štítky, které i tak skončí na
  ``N00``/``P00``, se vypíšou v reportu.

Soubory se přepisují NA MÍSTĚ v ``data/upload`` (rozhodnutí klienta). Opakované
spuštění je bezpečné: soubor, který už sloupce má, se jen PŘEPOČÍTÁ podle
aktuálního ``MAPOVANI_NA_FORMULAR`` (Kategorie zůstává, přepíše se Radek/Firma).
"""

import glob
import os
from collections import Counter

from openpyxl import load_workbook
from rich.console import Console

from .config import (
    ALIASY,
    KATEGORIE,
    KATEGORIE_PRIJMOVE,
    MAPOVANI_NA_FORMULAR,
)
from .prepisy import _radek_pro_kategorii

UPLOAD_SLOZKA = os.path.join("data", "upload")

# Kanonické názvy kategorií (to, na co se dá mapovat řádek formuláře).
_KANON: set[str] = (
    {k["nazev"] for k in KATEGORIE}
    | {k["nazev"] for k in KATEGORIE_PRIJMOVE}
    | set(MAPOVANI_NA_FORMULAR.keys())
    | set(ALIASY.values())
)

# Case-insensitive lookup: lower(štítek) → kanonický název. Aliasy mají přednost
# před shodou s kanonickým názvem (proto se přidávají jako poslední).
_LOWER: dict[str, str] = {}
for _name in _KANON:
    _LOWER.setdefault(_name.lower(), _name)
for _k, _v in ALIASY.items():
    _LOWER[_k.lower()] = _v

# Podíl řádků s rozpoznanou kategorií, pod kterým prohlásíme, že poslední
# sloupec kategoriím neodpovídá a soubor přeskočíme.
PRAH_ROZPOZNANI = 0.5


def _s(hodnota) -> str:
    return "" if hodnota is None else str(hodnota).strip()


def firma_z_nazvu(nazev_souboru: str) -> str:
    low = nazev_souboru.lower()
    if "nesty" in low:
        return "Nesty"
    if "casa" in low:
        return "Casa"
    if "pokladna" in low:
        return "Pokladna"
    # RD, RB RD, Airbank RD, RD Premier, RD RB, Airbank Radek, Radek FO FIO …
    return "RD"


def _resoluj(surova: str) -> tuple[str, bool]:
    """Vrátí (kanonická kategorie, rozpoznáno?). Aplikuje ALIASY case-insensitive."""
    if not surova:
        return "", False
    if surova in ALIASY:
        return ALIASY[surova], True
    if surova in _KANON:
        return surova, True
    low = surova.lower()
    if low in _LOWER:
        return _LOWER[low], True
    return surova, False


def _index_hlavicky(ws) -> int | None:
    """Číslo prvního neprázdného řádku (řádek s hlavičkou)."""
    for r in range(1, ws.max_row + 1):
        if any(ws.cell(row=r, column=c).value not in (None, "")
               for c in range(1, ws.max_column + 1)):
            return r
    return None


def _sloupec_ma_data(ws, col: int, prvni_datovy: int) -> bool:
    return any(_s(ws.cell(row=r, column=col).value)
              for r in range(prvni_datovy, ws.max_row + 1))


def _objem_a_mena_sloupce(ws, hlavicka_radek: int) -> tuple[int | None, int | None]:
    objem = pri_vydej = mena = None
    for c in range(1, ws.max_column + 1):
        nazev = _s(ws.cell(row=hlavicka_radek, column=c).value)
        if nazev == "Objem" and objem is None:
            objem = c
        elif nazev == "Příjem/Výdej" and pri_vydej is None:
            pri_vydej = c
        elif nazev == "Měna" and mena is None:
            mena = c
    return (objem if objem is not None else pri_vydej), mena


def _skore_sloupce(ws, col: int, prvni_datovy: int) -> int:
    """Počet řádků, kde hodnota ve sloupci je rozpoznatelná kategorie."""
    return sum(
        1 for r in range(prvni_datovy, ws.max_row + 1)
        if _resoluj(_s(ws.cell(row=r, column=col).value))[1]
    )


def _kategorie_sloupce(ws, hlavicka_radek: int, prvni_datovy: int) -> tuple[list[int], bool]:
    """Vrátí (seznam sloupců s kategorií zleva doprava, je_cerven).

    Červen: sloupce ``Kategorie`` s daty (první = pipeline, další = ruční opravy
    klienta). Staré měsíce: sloupec s NEJVÍCE rozpoznanými kategoriemi (robustní
    napříč formáty Fio i Air Bank, kde kategorie není nutně poslední sloupec –
    Air Bank má za ní ještě další pojmenované sloupce). Při shodě vyhraje
    pravější sloupec (klient kategorii píše doprava)."""
    kat = [
        c for c in range(1, ws.max_column + 1)
        if _s(ws.cell(row=hlavicka_radek, column=c).value) == "Kategorie"
        and _sloupec_ma_data(ws, c, prvni_datovy)
    ]
    if kat:
        return kat, True
    kandidati = [
        c for c in range(1, ws.max_column + 1)
        if _s(ws.cell(row=hlavicka_radek, column=c).value)
    ]
    nejlepsi = max(kandidati, key=lambda c: (_skore_sloupce(ws, c, prvni_datovy), c))
    return [nejlepsi], False


def _ma_radek_sloupec(ws, hlavicka_radek: int) -> bool:
    return any(_s(ws.cell(row=hlavicka_radek, column=c).value) == "Radek"
               for c in range(1, ws.max_column + 1))


def _index_sloupce(ws, hlavicka_radek: int, nazev: str) -> int | None:
    for c in range(1, ws.max_column + 1):
        if _s(ws.cell(row=hlavicka_radek, column=c).value) == nazev:
            return c
    return None


def zpracuj_soubor(cesta: str, nenamapovane_globalne: Counter) -> str:
    """Zpracuje jeden xlsx na místě. Vrací krátký stav pro report."""
    nazev = os.path.basename(cesta)
    firma = firma_z_nazvu(nazev)
    wb = load_workbook(cesta)
    try:
        ws = wb.active
        hlavicka_radek = _index_hlavicky(ws)
        if hlavicka_radek is None:
            return f"[yellow]PŘESKOČENO (prázdný list):[/] {nazev}"
        prepocet = _ma_radek_sloupec(ws, hlavicka_radek)

        prvni_datovy = hlavicka_radek + 1
        kat_cols, je_cerven = _kategorie_sloupce(ws, hlavicka_radek, prvni_datovy)
        primarni = kat_cols[0]
        opravy = kat_cols[1:]  # jen u června, ruční opravy klienta
        objem_col, mena_col = _objem_a_mena_sloupce(ws, hlavicka_radek)

        radky_idx = [
            r for r in range(prvni_datovy, ws.max_row + 1)
            if any(_s(ws.cell(row=r, column=c).value)
                   for c in range(1, ws.max_column + 1))
        ]

        rozpoznano = s_kategorii = prepsano = 0
        nepouzite_opravy: list[str] = []
        nenamapovane_lokalne: Counter = Counter()
        vysledky: list[tuple[int, str, str]] = []  # (řádek xlsx, kategorie, řádek formuláře)
        for r in radky_idx:
            surova = _s(ws.cell(row=r, column=primarni).value)
            kategorie, rozp = _resoluj(surova)
            if surova:
                s_kategorii += 1
                if rozp:
                    rozpoznano += 1
            # Ruční oprava klienta (červen): nejpravější rozpoznaná vyhrává.
            for oc in reversed(opravy):
                surova_o = _s(ws.cell(row=r, column=oc).value)
                if not surova_o:
                    continue
                kan_o, rozp_o = _resoluj(surova_o)
                if rozp_o:
                    kategorie = kan_o
                    prepsano += 1
                    break
                nepouzite_opravy.append(surova_o)

            objem = _s(ws.cell(row=r, column=objem_col).value) if objem_col else ""
            mena = _s(ws.cell(row=r, column=mena_col).value) if mena_col else ""
            radek_formulare = _radek_pro_kategorii(kategorie, objem, mena)
            vysledky.append((r, kategorie, radek_formulare))
            if radek_formulare.rstrip("*").endswith("00") and kategorie:
                nenamapovane_lokalne[kategorie] += 1

        # Validace starých výpisů: má vybraný sloupec opravdu kategorie?
        if not je_cerven and s_kategorii and rozpoznano / s_kategorii < PRAH_ROZPOZNANI:
            return (f"[red]NEZPRACOVÁNO (žádný sloupec neodpovídá kategoriím, "
                    f"rozpoznáno {rozpoznano}/{s_kategorii}):[/] {nazev}")

        if prepocet:
            # Soubor už zpracovaný – jen přepočítej Radek/Firma na místě podle
            # aktuálního mapování (Kategorie nechávám beze změny).
            radek_col = _index_sloupce(ws, hlavicka_radek, "Radek")
            firma_col = _index_sloupce(ws, hlavicka_radek, "Firma")
            for (r, _kategorie, radek_formulare) in vysledky:
                ws.cell(row=r, column=radek_col, value=radek_formulare)
                if firma_col:
                    ws.cell(row=r, column=firma_col, value=firma)
        else:
            # Připoj nové sloupce na konec. U června už Kategorie existuje.
            nove = ["Radek", "Firma"] if je_cerven else ["Kategorie", "Radek", "Firma"]
            zacatek = ws.max_column + 1
            for i, jmeno in enumerate(nove):
                ws.cell(row=hlavicka_radek, column=zacatek + i, value=jmeno)
            for (r, kategorie, radek_formulare) in vysledky:
                hodnoty = {"Kategorie": kategorie, "Radek": radek_formulare, "Firma": firma}
                for i, jmeno in enumerate(nove):
                    ws.cell(row=r, column=zacatek + i, value=hodnoty[jmeno])

        wb.save(cesta)
        nenamapovane_globalne.update(nenamapovane_lokalne)

        nenamapovano = sum(1 for _, _, rf in vysledky if rf.rstrip("*").endswith("00"))
        detaily = []
        if not prepocet and je_cerven:
            detaily.append("červen")
        detaily.append(f"{len(vysledky)} transakcí")
        detaily.append(f"{nenamapovano} nenamapováno")
        if prepsano:
            detaily.append(f"{prepsano} ručních oprav")
        if nepouzite_opravy:
            detaily.append(f"{len(nepouzite_opravy)} oprav nepoužito")
        stav = "PŘEPOČÍTÁNO" if prepocet else "OK"
        return f"[green]{stav}[/] {nazev}  ({', '.join(detaily)}, firma={firma})"
    finally:
        wb.close()


def main():
    console = Console()
    console.print("=== Zpracování ručně odkategorizovaných výpisů (data/upload) ===\n")

    soubory = sorted(glob.glob(os.path.join(UPLOAD_SLOZKA, "*.xlsx")))
    if not soubory:
        console.print(f"[red]Žádné xlsx nenalezeny v '{UPLOAD_SLOZKA}'.[/]")
        return

    nenamapovane_globalne: Counter = Counter()
    for cesta in soubory:
        console.print(zpracuj_soubor(cesta, nenamapovane_globalne))

    console.print(f"\n[bold]Hotovo.[/] Zpracováno {len(soubory)} souborů.")
    if nenamapovane_globalne:
        console.print("\n[bold yellow]Štítky bez řádku ve formuláři (N00/P00):[/]")
        for stitek, pocet in nenamapovane_globalne.most_common():
            console.print(f"  {stitek!r}: {pocet}×")


if __name__ == "__main__":
    main()
