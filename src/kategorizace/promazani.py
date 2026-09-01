"""
Samostatný příkaz: promaže obsah `transactions/Prijmove` a `transactions/Vydajove`
u VŠECH firem – tj. zpracované bankovní výpisy, které jsi tam nahrál/a.

Použití: `uv run promazat-vypisy`

Maže POUZE vstupní výpisy (transactions/), NIKDY `results/` ani `invoices/` –
ty je potřeba mazat ručně, pokud je to skutečně záměr. Složky samotné
(Prijmove/, Vydajove/) i jejich `.gitkeep` zůstávají – jen se z nich vysype
obsah, aby struktura zůstala verzovaná v gitu.

Před smazáním vypíše seznam souborů a vyžádá si potvrzení (lze přeskočit
přepínačem `-y`/`--force`).
"""

import glob
import os
import sys

from rich.console import Console
from rich.prompt import Confirm

from .config import FIRMY_SLOZKA

PODSLOZKY = ("Prijmove", "Vydajove")


def _najdi_soubory() -> list[str]:
    soubory = []
    for podslozka in PODSLOZKY:
        vzor = os.path.join(FIRMY_SLOZKA, "*", "transactions", podslozka, "*")
        for cesta in sorted(glob.glob(vzor)):
            if os.path.isfile(cesta) and os.path.basename(cesta) != ".gitkeep":
                soubory.append(cesta)
    return soubory


def main():
    console = Console()
    console.print("=== Promazání zpracovaných výpisů (transactions/) ===\n")

    soubory = _najdi_soubory()
    if not soubory:
        console.print("[green]Nic k promazání – Prijmove/Vydajove jsou už prázdné.[/]")
        return

    console.print(f"[yellow]Ke smazání ({len(soubory)}):[/]")
    for cesta in soubory:
        console.print(f"  {cesta}")

    force = "-y" in sys.argv or "--force" in sys.argv
    if not force and not Confirm.ask(f"\nSmazat {len(soubory)} souborů?", default=False):
        console.print("[red]Zrušeno.[/]")
        return

    for cesta in soubory:
        os.remove(cesta)

    console.print(f"\n[green]Hotovo.[/] Smazáno {len(soubory)} souborů.")


if __name__ == "__main__":
    main()
