# Checklist — probrat s klientem: Google Drive service account

Návazně na `plan-google-drive-service-account.md` (tam je technické proč/jak
do detailu). Tady jen odškrtávací seznam na call s klientem, ať se nic
nezapomene.

## 0. Předpoklad — má Workspace?

- [ ] Zjistit: **"Máte pro firmu (Nesty/Casa/RD…) placený Google Workspace
      na vlastní doméně (firemní e-maily, ne @gmail.com)?"** — tohle
      rozhoduje o všem ostatním. Service account nemá vlastní úložnou
      kvótu na běžném "Můj disk" (`storageQuotaExceeded`), umí nahrávat
      jen do **Shared Drive**, a Shared Drive existuje jen ve Workspace
      organizaci.
- [ ] Pokud nemá / nechce platit Workspace → service account nedává
      smysl. Alternativa: zůstat u OAuth, ale přihlásit ho pod **jeho**
      osobním Google účtem místo mého. Zbytek checklistu odpadá.

## 1. GCP projekt a přístup

- [ ] Domluvit, jestli klient založí nový GCP projekt, nebo mě přidá
      Editor/Owner do existujícího (pokud už nějaký GCP používá).
- [ ] Ověřit, že má/založí aktivní billing account (platební kartu)
      napojený na GCP projekt.
- [ ] Získat přístup do projektu (pokud zakládá on) nebo mu poslat, co
      potřebuju (pokud zakládám já).

## 2. Shared Drive

- [ ] Domluvit, kdo založí Shared Drive ("Sdílené disky") — musí to
      udělat někdo s Workspace účtem.
- [ ] Domluvit název a strukturu složek na Shared Drive (kam přesně se
      budou nahrávat výstupní CSV).
- [ ] Ujasnit, kdo bude mít k Shared Drive přístup a v jaké roli (jen
      čtení výstupů / možnost mazat a přesouvat).

## 3. Service account a napojení

- [ ] Vytvořit service account v GCP projektu a povolit Google Drive
      API.
- [ ] Bezpečně předat/uložit JSON klíč service accountu (ne holým
      textem přes e-mail/Slack — přes 1Password sdílení, šifrovaný
      kanál apod.).
- [ ] Nechat klienta přidat e-mail service accountu
      (`xxx@<projekt>.iam.gserviceaccount.com`) do Shared Drive jako
      **Content Manager**.
- [ ] Získat ID cílové složky z URL (`.../folders/<ID>`).

## 4. Dokončení a test

- [ ] Upravit `drive.py` na service account
      (`service_account.Credentials.from_service_account_file()`,
      `supportsAllDrives=True`) a `.env` (`GOOGLE_DRIVE_FOLDER_ID`).
- [ ] Otestovat upload zkusmým souborem a přepis existujícího souboru
      na Shared Drive.
- [ ] Domluvit s klientem finální název/konvenci souborů při nahrávání
      na Drive — teď se nahrává pod lokálním názvem
      (`RD-RD Výdajový 1 (1).csv`); plochá konvence
      `RRRR-MM_Firma_Ucet.csv` z `docs/napojeni-na-alokacni-formular.md`
      je zatím nerozhodnutá, stojí za to to probrat rovnou.
