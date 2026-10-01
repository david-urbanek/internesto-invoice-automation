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

from .config import FIRMY_SLOZKA
from .faktura_index import postav_index
from .pipeline import zpracuj_job_core

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
        # Rozdělení na Prijmove/Vydajove (08/2026) zúží nabídku kategorií
        # pro AI/deterministiku (viz omezene_kategorie_pro_soubor v prepisy.py).
        # Soubory ležící volně v transactions/ (bez rozdělení) se pořád
        # zpracují, jen bez tohoto zúžení – přechodné období.
        kandidati = (
            glob.glob(os.path.join(trans_slozka, "*"))
            + glob.glob(os.path.join(trans_slozka, "Prijmove", "*"))
            + glob.glob(os.path.join(trans_slozka, "Vydajove", "*"))
        )
        soubory = sorted(
            cesta for cesta in kandidati
            if os.path.isfile(cesta) and os.path.splitext(cesta)[1].lower() in {".csv", ".xlsx"}
        )
        joby = []
        for soubor in soubory:
            nazev = os.path.splitext(os.path.basename(soubor))[0]
            joby.append({
                "vstup": soubor,
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
        vysledek = zpracuj_job_core(
            job, invoices_slozka, firma_index, firma_nazev, client,
            status=lambda msg: progress.update(task_id, description=f"[cyan]{job['label']}[/cyan]  {msg}"),
        )
        if vysledek["prazdny"]:
            progress.update(task_id, completed=1, description=f"[yellow]⚠ {job['label']}[/yellow]  Prázdný CSV soubor")
            return
        progress.update(
            task_id,
            completed=1,
            description=f"[green]✓ {job['label']}[/green]  Hotovo ({vysledek['transakce']} transakcí, {vysledek['faktury']} faktur)",
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
