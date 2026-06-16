"""
Příkaz `konfigurace`: vypíše tabulku všech definovaných kategorií z config.py.
Slouží k rychlé orientaci v tom, co AI kategorizace zná a jaký model používá.
"""

from rich.console import Console
from rich.table import Table

from .config import FIRMY_SLOZKA, KATEGORIE, MODEL


def main():
    console = Console()
    console.print(f"\n[bold]Model:[/bold] {MODEL}")
    console.print(f"[bold]Složka firem:[/bold] {FIRMY_SLOZKA}\n")

    table = Table(title="Kategorie", show_lines=True)
    table.add_column("Název", style="cyan", no_wrap=True)
    table.add_column("Popis")
    table.add_column("Typičtí dodavatelé", style="dim")

    for k in KATEGORIE:
        table.add_row(
            k["nazev"],
            k["popis"],
            ", ".join(k["dodavatele"]) if k["dodavatele"] else "—",
        )

    console.print(table)
