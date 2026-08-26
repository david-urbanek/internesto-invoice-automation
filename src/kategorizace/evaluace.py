"""
Evaluace kategorizace proti schváleným výpisům (data/<mesic>/*.xlsx).

Prožene každý výpis celou pipeline (deterministika → AI → přepisy, BEZ indexu
faktur) a porovná výsledek s lidskou kategorií z posledního sloupce
Poznámka/Poznámky v Excelu. Lidská kategorie se pipeline neposkytuje.

Použití:
    uv run evaluace              # všechny měsíce v data/
    uv run evaluace kveten       # jen jeden měsíc
    uv run evaluace kveten unor  # vybrané měsíce

Výstup:
  - tabulka úspěšnosti per soubor a per kategorie do konzole
  - CSV s neshodami do data/eval_neshody.csv (feedback k ručnímu projití)

Porovnání ignoruje:
  - řádky bez lidské kategorie (nejsou zkategorizované ani člověkem)
  - lidské štítky, které nejsou platnou kategorií ani aliasem (zkopírované
    popisy plateb, jména osob) – vypíšou se zvlášť jako "nehodnoceno"
  - rozdíl mezi "Převod" a jeho dřívějšími podkategoriemi (sloučeno)
"""

import csv
import glob
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import openpyxl
from dotenv import load_dotenv
from google import genai
from rich.console import Console
from rich.table import Table

from .ai import kategorizuj_transakce
from .config import ALIASY, KATEGORIE, KATEGORIE_PRIJMOVE
from .deterministika import aplikuj_deterministickou_kategorizaci
from .prepisy import (
    aplikuj_interni_prevod,
    aplikuj_jidlo_podle_provedl,
    aplikuj_jidlo_pokladna,
    aplikuj_jmena_pokladna,
    aplikuj_kotlarska_pronajem_bytu,
    aplikuj_pradlo_pokladna,
    aplikuj_prevod_zpetna_platba,
    aplikuj_telefony_nejvyssi_castka,
    aplikuj_vychozi_kategorii_ucet,
    aplikuj_vzdy_dodavatel,
    omezene_kategorie_pro_soubor,
)

load_dotenv()

DATA_SLOZKA = "data"
VYSTUP_NESHODY = os.path.join(DATA_SLOZKA, "eval_neshody.csv")
ZNAME_KATEGORIE = {k["nazev"] for k in KATEGORIE + KATEGORIE_PRIJMOVE}


# ---------------------------------------------------------------------------
# Načtení xlsx výpisů (různá schémata: Fio plný/zkrácený, RB, Air Bank, Pokladna)
# ---------------------------------------------------------------------------

def _bez_diakritiky(s) -> str:
    # Air Bank exporty mají rozbité kódování hlaviček -> porovnávej jen ASCII
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if c.isascii()).lower().strip()


def _najdi_sloupec(hdr: list, *varianty: str) -> int | None:
    for i, h in enumerate(hdr):
        if h is None:
            continue
        hn = _bez_diakritiky(h)
        for v in varianty:
            if hn == v or v in hn:
                return i
    return None


def nacti_vypis_xlsx(cesta: str) -> tuple[list[dict], list[str]]:
    """
    Vrátí (transakce ve formátu pro pipeline, lidské kategorie per řádek).
    Kategorie = POSLEDNÍ sloupec s hlavičkou Poznámka/Poznámky, pipeline
    ji nikdy nedostane.
    """
    wb = openpyxl.load_workbook(cesta, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    hdr = list(next(rows))

    poznamky = [
        i for i, h in enumerate(hdr)
        if h is not None and _bez_diakritiky(h) in ("poznamka", "poznamky", "poznmka", "poznmky")
    ]
    if not poznamky:
        wb.close()
        raise ValueError(f"nenalezen sloupec kategorie (Poznámka): {hdr}")
    kat_idx = poznamky[-1]
    i_stitek = poznamky[0] if len(poznamky) > 1 else None

    # varianty "uslo kttu…"/"sstka…"/"nszev…" jsou Air Bank hlavičky
    # s rozbitým kódováním po ASCII-foldu (viz _bez_diakritiky)
    i_protiucet = _najdi_sloupec(hdr, "protiucet", "cislo uctu protistrany", "cislo protiuctu",
                                 "uslo kttu protistrany")
    i_nazev = _najdi_sloupec(hdr, "nazev protiuctu", "nazev protistrany", "prijato od",
                             "nszev protistrany")
    i_objem = _najdi_sloupec(hdr, "objem", "zauctovana castka", "castka v mene uctu",
                             "prijem/vydej", "sstka v mznz")
    i_zprava = _najdi_sloupec(hdr, "zprava pro prijemce", "zprava", "popis")
    i_datum = _najdi_sloupec(hdr, "datum")
    i_vs = _najdi_sloupec(hdr, "vs")
    i_provedl = _najdi_sloupec(hdr, "provedl", "uzivatel", "uivatel")

    transakce, lidske = [], []
    for row in rows:
        if row is None or all(v is None for v in row):
            continue

        def g(i):
            if i is None or i >= len(row) or row[i] is None:
                return ""
            return re.sub(r"\.0$", "", str(row[i]).strip())

        # souhrnné/legendové řádky na konci Excelu (jen kategorie bez dat)
        if not g(i_objem) and not g(i_protiucet) and not g(i_zprava) and not g(i_stitek):
            continue
        transakce.append({
            "Datum": g(i_datum),
            "Objem": g(i_objem),
            "Protiúčet": g(i_protiucet).split("/")[0],
            "Název protiúčtu": g(i_nazev),
            "Zpráva pro příjemce": g(i_zprava),
            "Poznámka": g(i_stitek),
            "VS": g(i_vs),
            "Provedl": g(i_provedl),
        })
        lidske.append(g(kat_idx))
    wb.close()
    return transakce, lidske


def firma_ze_souboru(nazev: str) -> str:
    n = _bez_diakritiky(nazev)
    if n.startswith("nesty"):
        return "Nesty"
    if n.startswith("casa"):
        return "Casa"
    if n.startswith("pokladna"):
        return "Pokladna"
    return "RD"  # RD, RB RD, Airbank, Radek FO


# ---------------------------------------------------------------------------
# Vyhodnocení jednoho výpisu
# ---------------------------------------------------------------------------

def normalizuj_lidskou(k: str) -> str | None:
    """Kanonická kategorie z lidského štítku, None pokud to kategorie není."""
    k = ALIASY.get(k.strip(), k.strip())
    if k.startswith("Převod"):
        k = "Převod"
    return k if k in ZNAME_KATEGORIE else None


def vyhodnot_vypis(cesta: str, mesic: str, client: genai.Client) -> dict:
    nazev = os.path.basename(cesta)
    firma = firma_ze_souboru(nazev)
    transakce, lidske = nacti_vypis_xlsx(cesta)
    vysledek = {
        "mesic": mesic, "soubor": nazev, "transakci": len(transakce),
        "det": 0, "ok": 0, "spatne": 0, "nehodnoceno": 0,
        "neshody": [], "per_kategorie": Counter(), "per_kategorie_ok": Counter(),
    }
    if not transakce:
        return vysledek

    omezene = omezene_kategorie_pro_soubor(nazev)
    aplikuj_deterministickou_kategorizaci(transakce, omezene)
    vysledek["det"] = sum(1 for t in transakce if t.get("Kategorie"))
    kategorizuj_transakce(transakce, [], client, firma_index=None, omezene_kategorie=omezene)
    aplikuj_interni_prevod(transakce)
    aplikuj_kotlarska_pronajem_bytu(transakce, nazev, firma)
    aplikuj_jidlo_podle_provedl(transakce, nazev, firma)
    aplikuj_pradlo_pokladna(transakce, firma)
    aplikuj_jmena_pokladna(transakce, firma)
    aplikuj_jidlo_pokladna(transakce, firma)
    aplikuj_prevod_zpetna_platba(transakce)
    aplikuj_telefony_nejvyssi_castka(transakce)
    aplikuj_vzdy_dodavatel(transakce, omezene_kategorie=omezene)
    aplikuj_vychozi_kategorii_ucet(transakce, nazev)

    for t, lidska in zip(transakce, lidske):
        truth = normalizuj_lidskou(lidska) if lidska.strip() else None
        if truth is None:
            vysledek["nehodnoceno"] += 1
            continue
        pred = t.get("Kategorie", "Neurčeno")
        pred_srovnani = "Převod" if pred.startswith("Převod") else pred
        vysledek["per_kategorie"][truth] += 1
        if pred_srovnani == truth:
            vysledek["ok"] += 1
            vysledek["per_kategorie_ok"][truth] += 1
        else:
            vysledek["spatne"] += 1
            vysledek["neshody"].append({
                "mesic": mesic, "soubor": nazev,
                "datum": str(t.get("Datum", ""))[:10],
                "objem": t.get("Objem", ""),
                "protiucet": t.get("Protiúčet", ""),
                "stitek": t.get("Poznámka", ""),
                "zprava": t.get("Zpráva pro příjemce", ""),
                "pipeline": pred,
                "clovek": truth,
                "jistota": t.get("Jistota", ""),
                "poznamka_ai": t.get("Poznamka", ""),
            })
    return vysledek


# ---------------------------------------------------------------------------
# Hlavní běh + report
# ---------------------------------------------------------------------------

def main() -> None:
    console = Console()
    if not os.environ.get("GOOGLE_API_KEY"):
        console.print("[red]CHYBA:[/] Nastav proměnnou GOOGLE_API_KEY")
        return

    mesice = sys.argv[1:] or sorted(
        os.path.basename(p) for p in glob.glob(os.path.join(DATA_SLOZKA, "*")) if os.path.isdir(p)
    )
    soubory = [
        (os.path.basename(os.path.dirname(c)), c)
        for m in mesice
        for c in sorted(glob.glob(os.path.join(DATA_SLOZKA, m, "*.xlsx")))
    ]
    if not soubory:
        console.print(f"[red]CHYBA:[/] Žádné xlsx v {DATA_SLOZKA}/{{{','.join(mesice)}}}/")
        return

    console.print(f"[bold]Evaluace {len(soubory)} výpisů ({', '.join(mesice)})[/bold]\n")
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    vysledky = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(vyhodnot_vypis, c, m, client): (m, c) for m, c in soubory}
        for future in as_completed(futures):
            m, c = futures[future]
            try:
                v = future.result()
                vysledky.append(v)
                hodnoceno = v["ok"] + v["spatne"]
                pct = f"{v['ok'] / hodnoceno:.0%}" if hodnoceno else "–"
                console.print(f"  [green]✓[/] {m}/{v['soubor']}: {pct} ({v['ok']}/{hodnoceno})")
            except Exception as e:
                console.print(f"  [red]✗[/] {m}/{os.path.basename(c)}: {e}")

    vysledky.sort(key=lambda v: (v["mesic"], v["soubor"]))

    # --- tabulka per soubor -------------------------------------------------
    tab = Table(title="Úspěšnost per výpis")
    for sloupec in ("Měsíc", "Soubor", "Tx", "Determ.", "Shoda", "Úspěšnost"):
        tab.add_column(sloupec)
    for v in vysledky:
        hodnoceno = v["ok"] + v["spatne"]
        pct = f"{v['ok'] / hodnoceno:.0%}" if hodnoceno else "–"
        tab.add_row(v["mesic"], v["soubor"], str(v["transakci"]),
                    str(v["det"]), f"{v['ok']}/{hodnoceno}", pct)
    console.print(tab)

    # --- tabulka per kategorie ----------------------------------------------
    per_kat, per_kat_ok = Counter(), Counter()
    for v in vysledky:
        per_kat.update(v["per_kategorie"])
        per_kat_ok.update(v["per_kategorie_ok"])
    tab2 = Table(title="Úspěšnost per kategorie (dle lidského označení)")
    for sloupec in ("Kategorie", "Transakcí", "Shoda", "Úspěšnost"):
        tab2.add_column(sloupec)
    for kat, n in per_kat.most_common():
        ok = per_kat_ok[kat]
        tab2.add_row(kat, str(n), str(ok), f"{ok / n:.0%}")
    console.print(tab2)

    # --- celkový souhrn -----------------------------------------------------
    ok = sum(v["ok"] for v in vysledky)
    spatne = sum(v["spatne"] for v in vysledky)
    det = sum(v["det"] for v in vysledky)
    tx = sum(v["transakci"] for v in vysledky)
    nehodnoceno = sum(v["nehodnoceno"] for v in vysledky)
    console.print(
        f"\n[bold]CELKEM: {ok}/{ok + spatne} shoda ({ok / (ok + spatne):.1%})[/bold] | "
        f"deterministicky {det}/{tx} ({det / tx:.0%}) | "
        f"nehodnoceno {nehodnoceno} (bez/neplatné lidské kategorie)"
    )

    # --- CSV s neshodami ----------------------------------------------------
    neshody = [n for v in vysledky for n in v["neshody"]]
    if neshody:
        with open(VYSTUP_NESHODY, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(neshody[0].keys()), delimiter=";")
            writer.writeheader()
            writer.writerows(neshody)
        console.print(f"\n{len(neshody)} neshod zapsáno do [bold]{VYSTUP_NESHODY}[/bold]")


if __name__ == "__main__":
    main()
