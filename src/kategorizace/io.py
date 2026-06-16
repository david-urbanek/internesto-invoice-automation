import csv
import glob
import os
import tempfile

from PIL import Image

from .config import CSV_SEPARATOR

MIME_TYPY = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

EXTENSIONS_VSECHNY = list(MIME_TYPY.keys()) + [".bmp", ".tiff", ".tif", ".webp", ".gif"]


def nacti_csv(cesta: str) -> list[dict]:
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
        return [
            {k: v.strip() if isinstance(v, str) else v for k, v in zip(headers, row)}
            for row in reader
        ]


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
