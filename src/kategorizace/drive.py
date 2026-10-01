"""
Nahraje výsledná CSV z `firmy/*/results/` a normalizované výpisy z
`data/upload/*.xlsx` (výstup `zpracuj-upload`) do sdílené Google Drive složky
jako nativní Google Sheet (ne binární soubor).

Použití: `uv run nahraj-na-drive`

Přihlašuje se přes service account (ne OAuth) – soubory patří klientově
Google Workspace organizaci, ne osobnímu účtu. Service account nemá na
běžném "Můj disk" žádnou úložnou kvótu (storageQuotaExceeded), proto musí
cílová složka ležet na Shared Drive (sdíleném disku) a service account
musí být do něj přidaný jako člen (Content Manager).

Vyžaduje v `.env`:
  GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE – cesta k JSON klíči service accountu
                                       (Cloud Console → IAM & Admin →
                                       Service Accounts → Keys)
  GOOGLE_DRIVE_FOLDER_ID            – ID cílové složky na Shared Drive
                                       (z URL)

Sheet stejného jména, který už ve složce existuje, se PŘEPÍŠE (aktualizuje
obsah pod stejným Drive ID) – nevytváří duplicity při opakovaném spuštění.

Název v Drive: `MM-firma-zbytek` (měsíc odvozený jako majoritní měsíc
transakcí ve sloupci Datum, lowercase, bez diakritiky, bez přípony – viz
`_drive_nazev`). Lokální soubor v `results/` zůstává beze změny.
"""

import csv
import glob
import os
import re
import tempfile
import unicodedata
from collections import Counter
from datetime import datetime
import openpyxl
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from rich.console import Console

from .config import CSV_SEPARATOR, FIRMY_SLOZKA

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/drive"]
SHEET_MIMETYPE = "application/vnd.google-apps.spreadsheet"
XLSX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _drive_service():
    keyfile = os.environ.get("GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE")
    if not keyfile or not os.path.isfile(keyfile):
        raise RuntimeError(
            f"GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE nenastaveno nebo soubor neexistuje: {keyfile!r}"
        )

    creds = service_account.Credentials.from_service_account_file(keyfile, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def _najdi_existujici(service, folder_id: str) -> dict[str, str]:
    """Vrátí {nazev_souboru: drive_id} pro soubory už ve složce (bez smazaných)."""
    existujici: dict[str, str] = {}
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken, files(id, name)",
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            corpora="allDrives",
        ).execute()
        for f in resp.get("files", []):
            existujici[f["name"]] = f["id"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return existujici


def _slug(text: str) -> str:
    """Lowercase, bez diakritiky, jen [a-z0-9-]."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text


# Formáty dat napříč zdroji výsledkových CSV – Fio (`dd.mm.yyyy`), pokladna
# (`dd.mm.yyyy HH:MM`), starší evaluační export (`m/d/yy`). Stejný seznam
# (bez pokladního formátu s časem) používá `faktura_index._parsuj_datum`.
DATUM_FORMATY = (
    "%d.%m.%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d.%m.%y",
)


def _parsuj_datum(s: str) -> datetime | None:
    s = s.strip()
    for fmt in DATUM_FORMATY:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _urci_mesic_rok(cesta: str) -> str | None:
    """Majoritní `MM-YYYY` ze sloupce Datum v datech – robustní vůči pár řádkům na přelomu měsíce/roku."""
    obdobi = Counter()
    with open(cesta, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=CSV_SEPARATOR)
        fieldnames = {(name or "").strip(): name for name in (reader.fieldnames or [])}
        sloupec = fieldnames.get("Datum")
        if not sloupec:
            return None
        for row in reader:
            d = _parsuj_datum(str(row.get(sloupec, "")))
            if d:
                obdobi[f"{d.month:02d}-{d.year}"] += 1
    return obdobi.most_common(1)[0][0] if obdobi else None


def _urci_mesic_rok_xlsx(cesta: str) -> str | None:
    workbook = openpyxl.load_workbook(cesta, read_only=True, data_only=True)
    values = list(workbook.worksheets[0].iter_rows(values_only=True))
    if not values:
        return None
    headers = [str(value).strip() if value is not None else "" for value in values[0]]
    stem = os.path.basename(cesta).lower()
    fallback_index = 0 if "airbank" in stem else 7
    date_index = next(
        (headers.index(name) for name in ("Datum", "Datum zaúčtování", "Datum provedení") if name in headers),
        fallback_index,
    )
    obdobi = Counter()
    for row in values[1:]:
        value = row[date_index] if date_index < len(row) else None
        if isinstance(value, datetime):
            obdobi[f"{value.month:02d}-{value.year}"] += 1
        elif value:
            datum = _parsuj_datum(str(value))
            if datum:
                obdobi[f"{datum.month:02d}-{datum.year}"] += 1
    return obdobi.most_common(1)[0][0] if obdobi else None

def _xlsx_drive_nazev(cesta: str) -> str:
    zaklad = os.path.splitext(os.path.basename(cesta))[0]
    dily = zaklad.split()
    firma = dily[0] if dily else zaklad
    zbytek = " ".join(dily[1:])
    mesic_rok = _urci_mesic_rok_xlsx(cesta)
    casti = ([*mesic_rok.split("-")] if mesic_rok else []) + [_slug(firma), _slug(zbytek)]
    return "-".join(cast for cast in casti if cast)
def _drive_nazev(cesta: str) -> str:
    """Odvodí název pro Drive z CSV cesty."""
    zaklad = os.path.splitext(os.path.basename(cesta))[0]
    firma, _, zbytek = zaklad.partition("-")
    if zbytek.lower().startswith(firma.lower()):
        zbytek = zbytek[len(firma):].lstrip(" -")
    dily = [_slug(firma), _slug(zbytek)]
    mesic_rok = _urci_mesic_rok(cesta)
    if mesic_rok:
        dily = mesic_rok.split("-") + dily
    return "-".join(d for d in dily if d)


def _nahraj_soubor(service, cesta: str, nazev: str, folder_id: str, existujici: dict[str, str]) -> str:
    media = MediaFileUpload(cesta, mimetype="text/csv", resumable=True)
    if nazev in existujici:
        service.files().update(
            fileId=existujici[nazev], media_body=media, supportsAllDrives=True
        ).execute()
        return "aktualizováno"
    metadata = {"name": nazev, "parents": [folder_id], "mimeType": SHEET_MIMETYPE}
    service.files().create(
        body=metadata, media_body=media, fields="id", supportsAllDrives=True
    ).execute()
    return "nahráno"


def _nahraj_xlsx_soubor(
    service, cesta: str, nazev: str, folder_id: str, existujici: dict[str, str]
) -> str:
    media = MediaFileUpload(cesta, mimetype=XLSX_MIMETYPE, resumable=True)
    if nazev in existujici:
        service.files().update(
            fileId=existujici[nazev],
            media_body=media,
            supportsAllDrives=True,
        ).execute()
        return "aktualizováno"
    metadata = {"name": nazev, "parents": [folder_id], "mimeType": SHEET_MIMETYPE}
    service.files().create(
        body=metadata,
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return "nahráno"


def main():
    console = Console()
    console.print("=== Nahrání výsledků na Google Drive ===\n")

    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    if not folder_id:
        console.print("[red]CHYBA:[/] Nastav GOOGLE_DRIVE_FOLDER_ID v .env")
        return

    try:
        service = _drive_service()
    except Exception as e:
        console.print(f"[red]CHYBA přihlášení:[/] {e}")
        return

    csv_soubory = sorted(glob.glob(os.path.join(FIRMY_SLOZKA, "*", "results", "*.csv")))
    xlsx_soubory = sorted(glob.glob(os.path.join("data", "upload", "*.xlsx")))
    if not csv_soubory and not xlsx_soubory:
        console.print("[red]Žádné CSV ani XLSX soubory nenalezeny.[/]")
        return

    try:
        existujici = _najdi_existujici(service, folder_id)
    except Exception as e:
        console.print(f"[red]CHYBA čtení cílové složky:[/] {e}")
        return
    console.print(f"Ve složce už je {len(existujici)} souborů.\n")

    ok, chyby = 0, 0
    for cesta in csv_soubory:
        nazev = _drive_nazev(cesta)
        try:
            stav = _nahraj_soubor(service, cesta, nazev, folder_id, existujici)
            console.print(f"[green]{stav.upper()}[/] {nazev}")
            ok += 1
        except Exception as e:
            console.print(f"[red]CHYBA[/] {nazev}: {e}")
            chyby += 1

    for cesta in xlsx_soubory:
        # Soubory z data/upload jsou už normalizované příkazem `zpracuj-upload`
        # (Kategorie/Radek/Firma), nahráváme je tedy tak, jak jsou.
        nazev = _xlsx_drive_nazev(cesta)
        try:
            stav = _nahraj_xlsx_soubor(service, cesta, nazev, folder_id, existujici)
            console.print(f"[green]{stav.upper()}[/] {nazev}")
            ok += 1
        except Exception as e:
            console.print(f"[red]CHYBA[/] {nazev}: {e}")
            chyby += 1

    console.print(f"\n[bold]Hotovo.[/] {ok} nahráno/aktualizováno, {chyby} chyb.")


if __name__ == "__main__":
    main()
