"""
Samostatný příkaz: doplní/přepočítá sloupce `Firma` a `Radek` (ID řádku
Alokačního formuláře) ve už existujících výstupních CSV v `results/`,
BEZ opětovného volání AI.

Použití: `uv run radky`

Kdy se hodí:
  - staré výsledky vznikly před zavedením sloupců Firma/Radek
  - `MAPOVANI_NA_FORMULAR` v config.py se změnil (nová kategorie, oprava
    mapování) a staré CSV mají zastaralé/chybějící hodnoty v Radek

Přepíše KAŽDÝ soubor v `firmy/<Firma>/results/*.csv` na místě – sloupce
Firma/Radek se vždy přepočítají znovu podle aktuální Kategorie a Objem/Měna
v souboru, ostatní sloupce zůstávají beze změny.
"""

import csv
import glob
import os

from rich.console import Console

from .config import CSV_SEPARATOR, FIRMY_SLOZKA
from .prepisy import aplikuj_radek_formulare


def _nacti_results_csv(cesta: str) -> tuple[list[str], list[dict]]:
    with open(cesta, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=CSV_SEPARATOR)
        # Fio hlavičky mívají odsazení mezerami kolem ";" (např. "Datum  ").
        # Ořízni fieldnames STEJNĚ jako klíče v každém řádku níže, jinak si
        # DictWriter na konci nepozná svoje vlastní sloupce (a při zápisu
        # buď spadne, nebo v horším případě zapíše prázdný soubor).
        fieldnames = [h.strip() if h else h for h in (reader.fieldnames or [])]
        radky = []
        for row in reader:
            # None = restkey pro řádky s víc sloupci, než má hlavička
            # (ojedinělé u starších/ručně upravených CSV) – zahoď je, ať
            # se nezapisují jako neplatný sloupec.
            row.pop(None, None)
            radky.append({
                (k.strip() if k else k): (v.strip() if isinstance(v, str) else v)
                for k, v in row.items()
            })
    return fieldnames, radky


def _uloz_csv(cesta: str, fieldnames: list[str], radky: list[dict]) -> None:
    with open(cesta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=CSV_SEPARATOR)
        writer.writeheader()
        writer.writerows(radky)


def main():
    console = Console()
    console.print("=== Přiřazení řádků Alokačního formuláře ===\n")

    soubory = sorted(glob.glob(os.path.join(FIRMY_SLOZKA, "*", "results", "*.csv")))
    if not soubory:
        console.print(f"[red]Žádné výsledky nenalezeny ve '{FIRMY_SLOZKA}/*/results/'.[/]")
        return

    celkem_transakci = 0
    for cesta in soubory:
        # cesta = firmy/<Firma>/results/<vypis>.csv
        firma_nazev = cesta.split(os.sep)[-3]
        fieldnames, radky = _nacti_results_csv(cesta)
        if not radky:
            console.print(f"[yellow]Přeskakuji (prázdný soubor):[/] {cesta}")
            continue

        radky = aplikuj_radek_formulare(radky, firma_nazev)

        # Zachovej původní pořadí sloupců, nové (Firma, Radek) připoj na konec.
        for novy_sloupec in ("Firma", "Radek"):
            if novy_sloupec not in fieldnames:
                fieldnames.append(novy_sloupec)

        _uloz_csv(cesta, fieldnames, radky)
        nenamapovano = sum(1 for r in radky if r.get("Radek", "").endswith("00"))
        console.print(
            f"[green]OK[/] {cesta}  ({len(radky)} transakcí, "
            f"{nenamapovano} nenamapováno)"
        )
        celkem_transakci += len(radky)

    console.print(f"\n[bold]Hotovo.[/] Zpracováno {len(soubory)} souborů, {celkem_transakci} transakcí.")


if __name__ == "__main__":
    main()
