"""
Hlavní CLI: orchestrace kategorizace pro všechny firmy paralelně.

Průběh:
  1. najdi_firmy()    – prohledá firmy/ a sestaví seznam jobů (firma → CSV → výstupní CSV)
  2. postav_index()   – pro každou firmu paralelně indexuje faktury přes Gemini
  3. zpracuj_job()    – načte CSV, filtruje faktury dle data, volá AI, uloží výsledek
  4. ThreadPoolExecutor – firmy i joby uvnitř firem běží paralelně

Výstup se ukládá do firmy/<Firma>/results/<Firma>-<nazev_vypisu>.csv
"""

import glob
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from google import genai
from pydantic import ValidationError
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .ai import kategorizuj_transakce
from .config import FIRMY_SLOZKA
from .deterministika import aplikuj_deterministickou_kategorizaci
from .faktura_index import filtruj_faktury, postav_index, rozsah_dat
from .io import najdi_faktury, nacti_csv, uloz_csv
from .prepisy import (
    aplikuj_interni_prevod,
    aplikuj_jidlo_podle_provedl,
    aplikuj_jidlo_pokladna,
    aplikuj_jmena_pokladna,
    aplikuj_kotlarska_pronajem_bytu,
    aplikuj_pradlo_pokladna,
    aplikuj_prevod_zpetna_platba,
    aplikuj_telefony_nejvyssi_castka,
    aplikuj_vzdy_dodavatel,
    omezene_kategorie_pro_soubor,
)

load_dotenv()


def najdi_firmy() -> list[dict]:
    firmy = []
    for firma_slozka in sorted(glob.glob(os.path.join(FIRMY_SLOZKA, "*"))):
        if not os.path.isdir(firma_slozka):
            continue
        firma_nazev = os.path.basename(firma_slozka)
        trans_slozka = os.path.join(firma_slozka, "transactions")
        if not os.path.isdir(trans_slozka):
            continue
        soubory = sorted(glob.glob(os.path.join(trans_slozka, "*.csv")))
        joby = []
        for soubor in soubory:
            nazev = os.path.splitext(os.path.basename(soubor))[0]
            joby.append({
                "csv": soubor,
                "label": f"{firma_nazev} / {nazev}",
                "vystup": os.path.join(firma_slozka, "results", f"{firma_nazev}-{nazev}.csv"),
            })
        if joby:
            firmy.append({
                "nazev": firma_nazev,
                "slozka": firma_slozka,
                "invoices": os.path.join(firma_slozka, "invoices"),
                "joby": joby,
            })
    return firmy


def zpracuj_job(
    job: dict,
    invoices_slozka: str,
    firma_index: dict,
    firma_nazev: str,
    progress: Progress,
    console: Console,
    client: genai.Client,
) -> None:
    task_id = progress.add_task(f"[cyan]{job['label']}[/cyan]  Načítám...", total=1)
    try:
        transakce = nacti_csv(job["csv"])

        # Filtruj faktury podle datového rozsahu transakcí
        rozsah = rozsah_dat(transakce)
        if rozsah and firma_index:
            datum_od, datum_do = rozsah
            faktury = filtruj_faktury(firma_index, invoices_slozka, datum_od, datum_do)
        elif os.path.isdir(invoices_slozka):
            faktury = najdi_faktury(invoices_slozka)
        else:
            faktury = []

        progress.update(
            task_id,
            description=f"[cyan]{job['label']}[/cyan]  Odesílám {len(transakce)} transakcí + {len(faktury)} faktur...",
        )
        if not transakce:
            progress.update(task_id, completed=1, description=f"[yellow]⚠ {job['label']}[/yellow]  Prázdný CSV soubor")
            return
        omezene_kategorie = omezene_kategorie_pro_soubor(job["csv"])
        # Jednoznačné transakce (štítek/protiúčet) zkategorizuj bez AI
        transakce = aplikuj_deterministickou_kategorizaci(transakce, omezene_kategorie)
        transakce = kategorizuj_transakce(
            transakce, faktury, client, firma_index=firma_index, omezene_kategorie=omezene_kategorie,
        )
        transakce = aplikuj_interni_prevod(transakce)
        transakce = aplikuj_kotlarska_pronajem_bytu(transakce, job["csv"], firma_nazev)
        transakce = aplikuj_jidlo_podle_provedl(transakce, job["csv"], firma_nazev)
        transakce = aplikuj_pradlo_pokladna(transakce, firma_nazev)
        transakce = aplikuj_jmena_pokladna(transakce, firma_nazev)
        transakce = aplikuj_jidlo_pokladna(transakce, firma_nazev)
        transakce = aplikuj_prevod_zpetna_platba(transakce)
        transakce = aplikuj_telefony_nejvyssi_castka(transakce)
        transakce = aplikuj_vzdy_dodavatel(transakce, omezene_kategorie=omezene_kategorie)
        os.makedirs(os.path.dirname(job["vystup"]), exist_ok=True)
        uloz_csv(job["vystup"], transakce, list(transakce[0].keys()))
        progress.update(
            task_id,
            completed=1,
            description=f"[green]✓ {job['label']}[/green]  Hotovo ({len(transakce)} transakcí, {len(faktury)} faktur)",
        )
    except ValidationError:
        progress.update(task_id, completed=1, description=f"[red]✗ {job['label']}[/red]  Gemini vrátil neočekávanou strukturu.")
        console.print_exception()
    except Exception as e:
        progress.update(task_id, completed=1, description=f"[red]✗ {job['label']}[/red]  CHYBA: {e}")
        console.print_exception()


def main():
    console = Console()
    console.print("=== Kategorizace transakcí (Gemini) ===\n")

    if not os.environ.get("GOOGLE_API_KEY"):
        console.print("[red]CHYBA:[/] Nastav proměnnou GOOGLE_API_KEY")
        return

    firmy = najdi_firmy()
    if not firmy:
        console.print(f"[red]CHYBA:[/] Žádné firmy nenalezeny ve složce '{FIRMY_SLOZKA}/'")
        return

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    # Sestav indexy faktur pro všechny firmy před spuštěním jobů
    console.print("[bold]Indexuji faktury...[/bold]")
    with Progress(
        SpinnerColumn("dots"),
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as idx_progress:
        def _indexuj_firmu(firma: dict) -> None:
            firma["index"] = postav_index(firma["invoices"], client, idx_progress)

        with ThreadPoolExecutor(max_workers=len(firmy)) as pool:
            futures = {pool.submit(_indexuj_firmu, firma): firma for firma in firmy}
            for future in as_completed(futures):
                firma = futures[future]
                try:
                    future.result()
                except Exception as e:
                    console.print(f"[red]CHYBA indexování [{firma['nazev']}]:[/] {e}")
    console.print()

    vsechny_joby = [
        (job, firma["invoices"], firma["index"], firma["nazev"])
        for firma in firmy
        for job in firma["joby"]
    ]
    celkem_jobu = len(vsechny_joby)
    console.print(f"Nalezeno {len(firmy)} firem, {celkem_jobu} souborů k zpracování\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(bar_width=None),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        celkovy_task = progress.add_task("[bold]Celkem[/bold]", total=celkem_jobu)
        with ThreadPoolExecutor(max_workers=celkem_jobu) as executor:
            futures = {
                executor.submit(zpracuj_job, job, inv_slozka, inv_index, firma_nazev, progress, console, client): job
                for job, inv_slozka, inv_index, firma_nazev in vsechny_joby
            }
            for future in as_completed(futures):
                job = futures[future]
                try:
                    future.result()
                except Exception as e:
                    console.print(f"[red]CHYBA [{job['label']}]:[/] {e}")
                finally:
                    progress.advance(celkovy_task)

    console.print("\n[green]Všechno hotovo![/]")
