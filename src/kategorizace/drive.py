"""
Nahraje výsledné CSV z `firmy/*/results/` do sdílené Google Drive složky.

Použití: `uv run nahraj-na-drive`

Přihlašuje se OAuth jako TVŮJ Google účet (ne service account – ten nemá na
běžném "Můj disk" žádnou úložnou kvótu, viz storageQuotaExceeded). Soubory
tak patří tobě a počítají se do tvé osobní kvóty.

Vyžaduje v `.env`:
  GOOGLE_DRIVE_OAUTH_CLIENT_FILE – cesta k OAuth client secret JSON
                                    (Cloud Console → Credentials →
                                    OAuth client ID → typ "Desktop app")
  GOOGLE_DRIVE_FOLDER_ID          – ID cílové složky (z URL)

Při prvním spuštění otevře prohlížeč pro přihlášení/souhlas a uloží token
do GOOGLE_DRIVE_TOKEN_FILE (výchozí `credentials/drive-token.json`) – další
spuštění ho jen obnoví, žádné opakované přihlašování.

Soubor stejného jména, který už ve složce existuje, se PŘEPÍŠE (aktualizuje
obsah pod stejným Drive ID) – nevytváří duplicity při opakovaném spuštění.

POZOR: nahrává se pod aktuálním lokálním názvem souboru
(`<Firma>-<vypis>.csv`, např. "RD-RD Výdajový 1 (1).csv"), NE podle finální
ploché konvence `RRRR-MM_Firma_Ucet.csv` navržené v
`docs/napojeni-na-alokacni-formular.md` – přejmenování je samostatný krok
(Fáze 2), zatím nerozhodnutý.
"""

import glob
import os

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from rich.console import Console

from .config import FIRMY_SLOZKA

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/drive"]


def _drive_service():
    token_soubor = os.environ.get("GOOGLE_DRIVE_TOKEN_FILE", "credentials/drive-token.json")
    client_soubor = os.environ.get("GOOGLE_DRIVE_OAUTH_CLIENT_FILE")
    if not client_soubor or not os.path.isfile(client_soubor):
        raise RuntimeError(
            f"GOOGLE_DRIVE_OAUTH_CLIENT_FILE nenastaveno nebo soubor neexistuje: {client_soubor!r}"
        )

    creds = None
    if os.path.isfile(token_soubor):
        creds = Credentials.from_authorized_user_file(token_soubor, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_soubor, SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(token_soubor) or ".", exist_ok=True)
        with open(token_soubor, "w") as f:
            f.write(creds.to_json())

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
        ).execute()
        for f in resp.get("files", []):
            existujici[f["name"]] = f["id"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return existujici


def _nahraj_soubor(service, cesta: str, nazev: str, folder_id: str, existujici: dict[str, str]) -> str:
    media = MediaFileUpload(cesta, mimetype="text/csv", resumable=True)
    if nazev in existujici:
        service.files().update(fileId=existujici[nazev], media_body=media).execute()
        return "aktualizováno"
    metadata = {"name": nazev, "parents": [folder_id]}
    service.files().create(body=metadata, media_body=media, fields="id").execute()
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

    soubory = sorted(glob.glob(os.path.join(FIRMY_SLOZKA, "*", "results", "*.csv")))
    if not soubory:
        console.print(f"[red]Žádné výsledky nenalezeny ve '{FIRMY_SLOZKA}/*/results/'.[/]")
        return

    try:
        existujici = _najdi_existujici(service, folder_id)
    except Exception as e:
        console.print(f"[red]CHYBA čtení cílové složky:[/] {e}")
        return
    console.print(f"Ve složce už je {len(existujici)} souborů.\n")

    ok, chyby = 0, 0
    for cesta in soubory:
        nazev = os.path.basename(cesta)
        try:
            stav = _nahraj_soubor(service, cesta, nazev, folder_id, existujici)
            console.print(f"[green]{stav.upper()}[/] {nazev}")
            ok += 1
        except Exception as e:
            console.print(f"[red]CHYBA[/] {nazev}: {e}")
            chyby += 1

    console.print(f"\n[bold]Hotovo.[/] {ok} nahráno/aktualizováno, {chyby} chyb.")


if __name__ == "__main__":
    main()
