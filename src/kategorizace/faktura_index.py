"""
Index metadat faktur: extrakce přes Gemini, cache v .index.json, deterministické předpárování.

Workflow:
  postav_index   – načte nebo vytvoří/aktualizuje .index.json ve složce invoices/
                   Gemini extrahuje: dodavatel, částka, datum, VS, čísla účtů, položky
                   Soubory se zpracují jen pokud chybí v indexu nebo se změnilo mtime.

  filtruj_faktury – z indexu vybere jen faktury datově relevantní pro daný výpis
                    (±TOLERANCE_DNI dní), aby Gemini nedostal zbytečně velký kontext

  predparuj      – deterministicky spáruje transakce PŘED odesláním do Gemini:
                   1. shoda variabilního symbolu (VS transakce = VS na faktuře)
                   2. shoda základu čísla účtu + přesné částky
                   Takto spárované transakce Gemini nemůže přepsat (_predparovano=True).
"""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import fitz
from google import genai
from google.genai import types
from pydantic import BaseModel

from .config import MODEL
from .io import MIME_TYPY

INDEX_SOUBOR = ".index.json"
TOLERANCE_DNI = 45
_EXT_PODPOROVANE = set(MIME_TYPY.keys()) | {".pdf"}


class _FakturaMetadata(BaseModel):
    dodavatel: str
    castka: float | None
    datum: str | None  # YYYY-MM-DD
    vs: str | None
    ucty: list[str]
    polozky: list[str]


def _extrahuj(cesta: str, client: genai.Client) -> dict:
    """Pošle fakturu do Gemini a vrátí extrahovaná metadata. PDF se čte přes PyMuPDF jako text; obrázky se pošlou přímo jako bytes."""
    ext = os.path.splitext(cesta)[1].lower()
    parts = []

    if ext in MIME_TYPY:
        with open(cesta, "rb") as f:
            parts.append(types.Part.from_bytes(data=f.read(), mime_type=MIME_TYPY[ext]))
    elif ext == ".pdf":
        try:
            doc = fitz.open(cesta)
            text = "\n".join(p.get_text() for p in doc)[:4000]
            doc.close()
        except Exception:
            return {}
        parts.append(types.Part.from_text(text=text))
    else:
        return {}

    parts.append(types.Part.from_text(text=(
        "Z tohoto dokladu extrahuj:\n"
        "- dodavatel: název dodavatele (NE odběratele — ignoruj RD Group, Nesty, Casa Libre)\n"
        "- castka: celková částka k úhradě v CZK jako desetinné číslo bez mezer\n"
        "- datum: datum vystavení nebo DUZP ve formátu YYYY-MM-DD\n"
        "- vs: variabilní symbol (pouze číslice, bez mezer)\n"
        "- ucty: čísla bankovních účtů dodavatele ve formátu základ/kód (např. '306744731/100')\n"
        "- polozky: stručný seznam položek faktury (max 5, např. ['čisticí prostředky', 'papírové ručníky'])\n"
        "Pokud hodnotu nelze určit, použij null."
    )))

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=parts,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_FakturaMetadata,
            ),
        )
        d = response.parsed
        return {
            "dodavatel": d.dodavatel,
            "castka": d.castka,
            "datum": d.datum,
            "vs": d.vs,
            "ucty": d.ucty or [],
            "polozky": d.polozky or [],
            "mtime": os.path.getmtime(cesta),
        }
    except Exception:
        return {"error": True, "mtime": os.path.getmtime(cesta)}


def postav_index(slozka: str, client: genai.Client, progress=None) -> dict:
    """Načte nebo vytvoří/aktualizuje index metadat faktur v dané složce."""
    if not os.path.isdir(slozka):
        return {}

    index_cesta = os.path.join(slozka, INDEX_SOUBOR)
    index: dict = {}
    if os.path.exists(index_cesta):
        with open(index_cesta, encoding="utf-8") as f:
            index = json.load(f)

    soubory = [
        f for f in os.listdir(slozka)
        if os.path.splitext(f)[1].lower() in _EXT_PODPOROVANE
    ]
    # Zpracuj soubory které nejsou v indexu nebo se změnily (jiné mtime)
    ke_zpracovani = [
        f for f in soubory
        if f not in index
        or (not index[f].get("error") and abs(index[f].get("mtime", 0) - os.path.getmtime(os.path.join(slozka, f))) > 1)
    ]

    if ke_zpracovani:
        nazev = os.path.basename(slozka)
        task_id = None
        if progress:
            task_id = progress.add_task(f"[cyan]{nazev}[/cyan]", total=len(ke_zpracovani))

        def _zpracuj(fname: str) -> tuple[str, dict]:
            return fname, _extrahuj(os.path.join(slozka, fname), client)

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(_zpracuj, f): f for f in ke_zpracovani}
            for future in as_completed(futures):
                fname, meta = future.result()
                index[fname] = meta
                if progress and task_id is not None:
                    progress.update(task_id, advance=1)

        if progress and task_id is not None:
            progress.update(task_id, description=f"[green]✓ {nazev}[/green]")

        tmp = index_cesta + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        os.replace(tmp, index_cesta)

    return index


# ---------------------------------------------------------------------------
# Filtrování faktur dle data transakcí
# ---------------------------------------------------------------------------

def _parsuj_datum(s: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y", "%m/%d/%Y", "%-m/%-d/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            pass
    return None


def rozsah_dat(transakce: list[dict]) -> tuple[datetime, datetime] | None:
    datumy = [d for t in transakce if (d := _parsuj_datum(str(t.get("Datum", "") or "")))]
    return (min(datumy), max(datumy)) if datumy else None


def filtruj_faktury(index: dict, slozka: str, datum_od: datetime, datum_do: datetime) -> list[str]:
    """Vrátí cesty k fakturám relevantním pro dané období ± TOLERANCE_DNI."""
    od = datum_od - timedelta(days=TOLERANCE_DNI)
    do = datum_do + timedelta(days=TOLERANCE_DNI)
    cesty = []
    for fname, meta in index.items():
        if meta.get("error"):
            continue
        datum_str = meta.get("datum")
        if datum_str:
            try:
                d = datetime.fromisoformat(datum_str)
                if od <= d <= do:
                    cesty.append(os.path.join(slozka, fname))
            except ValueError:
                cesty.append(os.path.join(slozka, fname))
        else:
            cesty.append(os.path.join(slozka, fname))
    return cesty


# ---------------------------------------------------------------------------
# Deterministické předpárování
# ---------------------------------------------------------------------------

def _normalizuj_ucet(ucet: str) -> str:
    """Základní číslo účtu bez bankovního kódu a mezer."""
    ucet = re.sub(r"\s", "", ucet)
    # Odstraň případný prefix (např. "27-5829880217" → ponechat celé, jen strip kódu za lomítkem)
    return ucet.split("/")[0]


def predparuj(transakce: list[dict], index: dict) -> list[dict]:
    """
    Deterministicky spáruje transakce s fakturami před odesláním do Gemini.

    Pořadí priorit:
      1. VS transakce = VS faktury (po oříznutí vedoucích nul)
      2. Základ čísla protiúčtu + přesná částka = základ účtu faktury + částka

    Spárované transakce dostanou _predparovano=True — Gemini je nesmí přepsat.
    Příznak se odstraní z výstupu v ai.kategorizuj_transakce po dokončení.
    """
    # Sestavení vyhledávacích map z indexu
    vs_mapa: dict[str, str] = {}           # vs → fname
    ucet_castka_mapa: dict[tuple, str] = {}  # (zaklad_uctu, castka) → fname

    for fname, meta in index.items():
        if meta.get("error"):
            continue
        vs = str(meta.get("vs") or "").strip().lstrip("0") or None
        if vs:
            vs_mapa[vs] = fname
            vs_mapa[str(meta["vs"]).strip()] = fname  # také s původními nulami

        castka = meta.get("castka")
        if castka is not None:
            castka_r = round(float(castka), 2)
            for ucet in meta.get("ucty") or []:
                zaklad = _normalizuj_ucet(str(ucet))
                if zaklad:
                    ucet_castka_mapa[(zaklad, castka_r)] = fname

    for t in transakce:
        if t.get("Faktura"):
            continue

        # 1. VS shoda
        vs_raw = str(t.get("VS", "") or "").strip()
        if vs_raw:
            hit = vs_mapa.get(vs_raw) or vs_mapa.get(vs_raw.lstrip("0"))
            if hit:
                t["Faktura"] = hit
                t["_predparovano"] = True
                continue

        # 2. Protiúčet + přesná částka
        protiucet_raw = str(t.get("Číslo protiúčtu", t.get("Protiúčet", "")) or "")
        zaklad = _normalizuj_ucet(protiucet_raw)
        try:
            castka = round(abs(float(str(t.get("Objem", 0)).replace(",", "."))), 2)
        except (ValueError, TypeError):
            castka = None

        if zaklad and castka:
            hit = ucet_castka_mapa.get((zaklad, castka))
            if hit:
                t["Faktura"] = hit
                t["_predparovano"] = True

    return transakce
