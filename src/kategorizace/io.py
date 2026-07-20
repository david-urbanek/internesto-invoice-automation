"""
Čtení a zápis souborů: CSV výpisy z Fio banky a vyhledávání faktur.

nacti_csv    – přeskočí metadata hlavičky Fio banky, auto-detekuje oddělovač
uloz_csv     – zapíše výsledek ve formátu s BOM (kompatibilita s Excel)
najdi_faktury – rekurzivní glob přes všechny podporované formáty dokladů
konvertuj_na_pdf – převod obrázku na PDF pro Gemini (který preferuje PDF)
"""

import csv
import glob
import os
import tempfile

from PIL import Image

from .config import ALIASY_SLOUPCU_CSV, CSV_SEPARATOR

MIME_TYPY = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

EXTENSIONS_VSECHNY = list(MIME_TYPY.keys()) + [".bmp", ".tiff", ".tif", ".webp", ".gif"]


def nacti_csv(cesta: str) -> list[dict]:
    """Načte CSV výpis z Fio banky. Přeskočí metadata řádky před záhlavím (Fio exportuje ~9 řádků před sloupci)."""
    with open(cesta, encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;").delimiter
        except csv.Error:
            delimiter = CSV_SEPARATOR
        reader = csv.reader(f, delimiter=delimiter)
        # Přeskočí metadatové řádky (Fio banka exportuje ~9 řádků před záhlavím sloupců)
        raw_headers = None
        for row in reader:
            if len(row) >= 5:
                raw_headers = row
                break
        if raw_headers is None:
            return []
        headers = []
        seen: dict[str, int] = {}
        for h in raw_headers:
            h = h.strip() if h else h
            if h in seen:
                seen[h] += 1
                headers.append(f"{h}_{seen[h]}")
            else:
                seen[h] = 1
                headers.append(h)
        radky = [
            {k: v.strip() if isinstance(v, str) else v for k, v in zip(headers, row)}
            for row in reader
        ]
        return _normalizuj_sloupce(radky)


def _normalizuj_sloupce(radky: list[dict]) -> list[dict]:
    """
    Doplní ke sloupcům s odlišným názvem (ALIASY_SLOUPCU_CSV, config.py) i
    kanonický název, který čekají ai.py/prepisy.py (Datum, Objem, Poznámka…).
    Nemaže originální sloupec, jen přidává alias vedle něj – použije se JEN
    pokud kanonický sloupec ještě není v řádku přítomný (aby se nepřepsaly
    skutečné Fio sloupce, které se jmenují stejně jako kanonický název).
    """
    for radek in radky:
        for puvodni, kanonicky in ALIASY_SLOUPCU_CSV.items():
            if kanonicky not in radek and puvodni in radek:
                radek[kanonicky] = radek[puvodni]
    return radky


def uloz_csv(cesta: str, radky: list[dict], fieldnames: list[str]):
    with open(cesta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=CSV_SEPARATOR)
        writer.writeheader()
        writer.writerows(radky)


def konvertuj_na_pdf(cesta: str) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    Image.open(cesta).convert("RGB").save(tmp.name, "PDF")
    return tmp.name


def najdi_faktury(slozka: str) -> list[str]:
    cesty = []
    for ext in EXTENSIONS_VSECHNY:
        cesty.extend(glob.glob(os.path.join(slozka, f"*{ext}")))
    return cesty
