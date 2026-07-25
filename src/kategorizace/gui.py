"""
GUI runner: stejná pipeline jako `kategorizace`, ale výstup jako JSON Lines
na stdout – rozhraní pro Electron aplikaci (app/).

Každý řádek stdout je jeden JSON objekt {"event": ..., ...}:
  seznam        – přehled nalezených firem a jobů (režim --seznam, pak konec)
  chyba         – fatální chyba, běh končí
  start         – začátek běhu (počet firem a jobů)
  index_start   – začala indexace faktur firmy (celkem = počet nových souborů)
  index_krok    – zaindexován jeden soubor faktury
  index_hotovo  – indexace firmy dokončena
  job_start     – začalo zpracování výpisu
  job_stav      – průběžný stav výpisu (text)
  job_hotovo    – výpis dokončen (transakce, faktury, prazdny, vystup)
  job_chyba     – výpis selhal (text chyby)
  hotovo        – celý běh dokončen

Spuštění:  python -m kategorizace.gui --root <složka s podadresářem firmy/>
API klíč se čte z prostředí (GOOGLE_API_KEY) – Electron ho předá při spawnu.
"""

import argparse
import json
import os
import sys
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from google import genai

from .config import FIRMY_SLOZKA
from .faktura_index import postav_index
from .pipeline import zpracuj_job_core

_lock = threading.Lock()


def emit(event: str, **data) -> None:
    with _lock:
        print(json.dumps({"event": event, **data}, ensure_ascii=False), flush=True)


class _IndexProgress:
    """Adaptér s rozhraním rich.Progress (add_task/update) → JSONL eventy."""

    def __init__(self, firma: str):
        self.firma = firma
        self._celkem = 0
        self._hotovo = 0

    def add_task(self, description: str, total: int = 0):
        self._celkem = total
        emit("index_start", firma=self.firma, celkem=total)
        return 0

    def update(self, task_id, advance: int = 0, description: str | None = None, **_):
        if advance:
            self._hotovo += advance
            emit("index_krok", firma=self.firma, hotovo=self._hotovo, celkem=self._celkem)


def najdi_firmy() -> list[dict]:
    # Import až tady, aby chyba v cli.py nezablokovala emit("chyba")
    from .cli import najdi_firmy as _najdi
    return _najdi()


def main() -> None:
    parser = argparse.ArgumentParser(description="GUI runner kategorizace (JSONL výstup)")
    parser.add_argument("--root", help=f"složka obsahující podadresář '{FIRMY_SLOZKA}/'")
    parser.add_argument("--seznam", action="store_true", help="jen vypiš nalezené firmy a joby, nic nespouštěj")
    args = parser.parse_args()

    if args.root:
        try:
            os.chdir(args.root)
        except OSError as e:
            emit("chyba", text=f"Složku nelze otevřít: {e}")
            sys.exit(1)

    load_dotenv()

    firmy = najdi_firmy()
    if args.seznam:
        emit("seznam", firmy=[
            {"nazev": f["nazev"], "joby": [j["label"] for j in f["joby"]]} for f in firmy
        ])
        return

    if not os.environ.get("GOOGLE_API_KEY"):
        emit("chyba", text="Chybí API klíč (GOOGLE_API_KEY). Nastav ho v aplikaci.")
        sys.exit(1)
    if not firmy:
        emit("chyba", text=f"Žádné firmy nenalezeny ve složce '{FIRMY_SLOZKA}/'. "
                           f"Vyber složku, která obsahuje podadresář '{FIRMY_SLOZKA}'.")
        sys.exit(1)

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    celkem_jobu = sum(len(f["joby"]) for f in firmy)
    emit("start", firmy=[f["nazev"] for f in firmy], celkem_jobu=celkem_jobu,
         joby=[{"label": j["label"], "firma": f["nazev"]} for f in firmy for j in f["joby"]])

    # 1. Indexace faktur všech firem paralelně
    def _indexuj(firma: dict) -> None:
        firma["index"] = postav_index(firma["invoices"], client, _IndexProgress(firma["nazev"]))
        emit("index_hotovo", firma=firma["nazev"])

    with ThreadPoolExecutor(max_workers=len(firmy)) as pool:
        futures = {pool.submit(_indexuj, f): f for f in firmy}
        for future in as_completed(futures):
            firma = futures[future]
            try:
                future.result()
            except Exception as e:
                firma.setdefault("index", {})
                emit("job_chyba", label=f"Indexace {firma['nazev']}", text=str(e))

    # 2. Zpracování všech výpisů paralelně
    def _zpracuj(job: dict, firma: dict) -> None:
        emit("job_start", label=job["label"])
        try:
            vysledek = zpracuj_job_core(
                job, firma["invoices"], firma.get("index", {}), firma["nazev"], client,
                status=lambda msg: emit("job_stav", label=job["label"], text=msg),
            )
            emit("job_hotovo", label=job["label"], vystup=os.path.abspath(job["vystup"]), **vysledek)
        except Exception as e:
            emit("job_chyba", label=job["label"], text=str(e), detail=traceback.format_exc())

    vsechny = [(job, firma) for firma in firmy for job in firma["joby"]]
    with ThreadPoolExecutor(max_workers=max(1, len(vsechny))) as pool:
        futures = [pool.submit(_zpracuj, job, firma) for job, firma in vsechny]
        for future in as_completed(futures):
            future.result()

    emit("hotovo")


if __name__ == "__main__":
    main()
