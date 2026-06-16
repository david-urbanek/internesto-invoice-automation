import csv
import glob
import os
import re
from collections import defaultdict

from rich import box
from rich.console import Console
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .config import FIRMY_SLOZKA, KATEGORIE_BEZ_FAKTURY


def _nacti_results(slozka: str) -> list[tuple[str, dict]]:
    radky = []
    for path in sorted(glob.glob(os.path.join(slozka, "results", "*.csv"))):
        label = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f, delimiter=";"):
                radky.append((label, {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}))
    return radky


def _parsuj_datum(s: str) -> str:
    s = s.strip()
    m = re.match(r"\d{4}-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(2)}.{m.group(1)}."
    m = re.match(r"(\d{2})\.(\d{2})\.\d{4}", s)
    if m:
        return f"{m.group(1)}.{m.group(2)}."
    return s


def _parsuj_label(label: str) -> tuple[str, str]:
    """Vrátí (firma, popis) z labelu výstupního souboru."""
    m = re.match(r"^(\w+)-Vypis_z_uctu-(\d+)_(\d{4})(\d{2})\d{2}-", label)
    if m:
        firma, ucet, rok, mesic = m.groups()
        return firma, f"{ucet}  ·  {mesic}/{rok}"
    # "Nesty-RD Výdajový 1" apod.
    parts = label.split("-", 1)
    return parts[0], parts[1].strip() if len(parts) > 1 else label


def _format_castka(s: str) -> Text:
    try:
        val = float(s.replace(",", ".").replace(" ", ""))
        formatted = f"{abs(val):,.0f}".replace(",", " ") + " Kč"
        if val < 0:
            return Text(f"−{formatted}", style="red")
        return Text(f"+{formatted}", style="green")
    except (ValueError, TypeError):
        return Text(s)


def _zkrat_popis(text: str) -> str:
    if text.lower().startswith("nákup:"):
        after = text[6:].strip()
        return after.split(",")[0].strip()
    return text[:70]


def _chybi_faktura(t: dict) -> bool:
    kat = t.get("Kategorie", "").strip()
    faktura = t.get("Faktura", "").strip()
    return (
        faktura == "NENALEZENO"
        and kat not in KATEGORIE_BEZ_FAKTURY
        and kat not in ("", "Neurčeno")
        and t.get("Datum", "").strip() != ""
    )


def main():
    console = Console()

    firmy_slozky = sorted(
        d for d in glob.glob(os.path.join(FIRMY_SLOZKA, "*")) if os.path.isdir(d)
    )
    if not firmy_slozky:
        console.print(f"[red]CHYBA:[/] Žádné firmy ve složce '{FIRMY_SLOZKA}/'")
        return

    chybejici: list[tuple[str, dict]] = []
    celkem_transakci = 0
    for slozka in firmy_slozky:
        vsechny = _nacti_results(slozka)
        celkem_transakci += len(vsechny)
        chybejici.extend((label, t) for label, t in vsechny if _chybi_faktura(t))

    console.print()
    console.print(Rule(
        f"[bold]Chybějící faktury[/bold]  [dim]{len(chybejici)} transakcí  ·  "
        f"z celkem {celkem_transakci} zpracovaných[/dim]",
        style="red",
    ))
    console.print()

    if not chybejici:
        console.print("[green]  Všechny transakce mají fakturu nebo ji nevyžadují.[/green]\n")
        return

    skupiny: dict[str, list[dict]] = defaultdict(list)
    for label, t in chybejici:
        skupiny[label].append(t)

    celkova_suma = 0.0

    for label, transakce in skupiny.items():
        firma, popis_uctu = _parsuj_label(label)

        # Sekční hlavička
        console.print(
            f"  [bold white]{firma}[/bold white]"
            f"  [dim]›[/dim]  [dim]{popis_uctu}[/dim]"
            f"  [dim]({len(transakce)} položek)[/dim]"
        )
        console.print(f"  [dim italic]{label}.csv[/dim italic]")
        console.print()

        table = Table(
            box=box.SIMPLE_HEAD,
            show_footer=False,
            header_style="bold dim",
            show_edge=False,
            padding=(0, 1),
        )
        table.add_column("Datum", no_wrap=True, min_width=7)
        table.add_column("Objem", justify="right", no_wrap=True, min_width=12)
        table.add_column("Kategorie", style="cyan", no_wrap=True)
        table.add_column("VS", no_wrap=True, style="dim")
        table.add_column("Popis", no_wrap=True)

        sekce_suma = 0.0
        for t in transakce:
            poznamka = t.get("Poznámka", "").strip()
            zprava = t.get("Zpráva pro příjemce", "").strip()
            protistrana = t.get("Název protiúčtu", "").strip()
            popis = _zkrat_popis(poznamka or zprava or protistrana)

            objem_str = t.get("Objem", "").strip()
            try:
                sekce_suma += float(objem_str.replace(",", ".").replace(" ", ""))
            except (ValueError, TypeError):
                pass

            table.add_row(
                _parsuj_datum(t.get("Datum", "")),
                _format_castka(objem_str),
                t.get("Kategorie", "").strip(),
                t.get("VS", "").strip(),
                popis,
            )

        console.print(table)

        # Subtotál sekce
        celkova_suma += sekce_suma
        subtotal = _format_castka(str(sekce_suma))
        console.print(f"  [dim]Součet:[/dim] {subtotal}")
        console.print()

    # Grand total
    console.print(Rule(style="dim"))
    console.print(
        f"  [bold]Celkem chybějících:[/bold]  {_format_castka(str(celkova_suma))}"
        f"  [dim]({len(chybejici)} transakcí)[/dim]"
    )
    console.print()
