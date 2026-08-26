# Plán — nahrávání na Google Drive přes service account (klientovo prostředí)

Kontext: `drive.py` teď nahrává soubory přes OAuth pod **mým** osobním
Google účtem (viz hlavička `drive.py`) — funguje, ale soubory patří mně a
počítají se do mé osobní kvóty. Cíl: přepnout na **service account**, který
bude nahrávat přímo do klientova Google prostředí, bez závislosti na mém
účtu.

Klient zatím v Google Cloude nemá zařízeno vůbec nic — vše, co v repu je
teď (`credentials/testing-488518-*.json`), je z mého testovacího účtu a
před nasazením se to nahradí.

---

## Proč to není triviální — klíčové technické omezení

Service account **nemá vlastní úložnou kvótu** na běžném "Můj disk" —
upload by spadl na chybu `storageQuotaExceeded`. Service account umí
nahrávat jen do **Shared Drive** (sdíleného/týmového disku), kde kvóta
patří disku samotnému (organizaci), ne nahrávající identitě.

**Shared Drive vyžaduje Google Workspace.** Běžné osobní @gmail.com konto
sdílené disky vůbec nemá k dispozici — jen placená Workspace organizace
(Business Starter a výš).

→ Z toho plyne první a nejdůležitější otázka pro klienta (viz níže).

---

## Otázka pro klienta č. 1 — má vůbec Google Workspace?

Ptát se konkrétně: **"Máte pro firmu (Nesty/Casa/RD…) placený Google
Workspace (firemní e-maily na vlastní doméně, ne @gmail.com)?"**

- **Ano, má Workspace** → pokračovat podle plánu níže (service account +
  Shared Drive), toto je čistší a plně automatizovatelné řešení.
- **Ne, nemá / nechce platit Workspace** → service account nedává smysl.
  Alternativa: zůstat u OAuth (současný stav), ale přihlásit ho pod
  **klientovým** osobním Google účtem místo mého — soubory pak patří jemu
  a počítají se do jeho osobní kvóty na Disku. Nevýhoda: při expiraci
  OAuth tokenu nebo odhlášení bude potřeba znovu proklikat přihlašovací
  flow (nejde spustit čistě automatizovaně/na serveru bez zásahu).

Tahle odpověď určuje, jestli má smysl dělat cokoliv z kroků níže.

---

## Plán postupu (pokud klient Workspace má/pořídí)

### 1. Google Cloud projekt
- Klient buď založí nový GCP projekt pod svým Workspace účtem, nebo mě
  přidá jako **Editor/Owner** do existujícího projektu (pokud už nějaký
  GCP používá).
- Je potřeba mít u projektu aktivní **billing account** (napojenou platební
  kartu) — Drive API samotné je zdarma, ale GCP projekt bez billing účtu
  má omezené možnosti (a některá API ho vyžadují).

### 2. Povolit Google Drive API
- V GCP Console → APIs & Services → povolit "Google Drive API" pro daný
  projekt.

### 3. Vytvořit service account
- GCP Console → IAM & Admin → Service Accounts → vytvořit nový (např.
  `kategorizace-drive-upload`).
- Vygenerovat JSON klíč, ten mi bezpečně předat (ne e-mailem/Slackem v
  čistém textu — přes 1Password sdílení, šifrovaný kanál apod.).
- Zapsat si e-mail service accountu (tvar
  `xxx@<projekt>.iam.gserviceaccount.com`) — ten bude potřeba v kroku 5.

### 4. Vytvořit Shared Drive (sdílený disk)
- Na `drive.google.com` → "Sdílené disky" → nový disk, např. "Kategorizace
  — výstupy".
- Musí to založit někdo s Workspace účtem (klient nebo pověřená osoba u
  něj) — service account ani já sám o sobě Shared Drive založit nemůžeme
  bez existující Workspace organizace.

### 5. Přidat service account do Shared Drive
- V nastavení Shared Drive → Manage members → přidat e-mail service
  accountu z kroku 3, role **Content Manager** (stačí na nahrávání/přepis
  souborů, nemusí mít Manager).

### 6. Předat mi ID cílové složky
- Uvnitř Shared Drive vytvořit/označit podsložku pro výstupy (nebo použít
  kořen disku) a poslat mi její ID z URL (`.../folders/<ID>`).

### 7. Já dokončím technickou stranu
- Upravím `drive.py`: `service_account.Credentials.from_service_account_file()`
  místo OAuth flow, `supportsAllDrives=True` (a `includeItemsFromAllDrives=True`
  u listování) ve všech Drive API voláních.
- `.env`: `GOOGLE_DRIVE_FOLDER_ID` nastavím na ID z kroku 6, service
  account JSON uložím do `credentials/`, odpadají
  `GOOGLE_DRIVE_OAUTH_CLIENT_FILE`/`GOOGLE_DRIVE_TOKEN_FILE`.
- Otestuju upload zkusmým souborem, ověřím v UI Shared Drive, že se
  objevil a že ho jde znovu přepsat (ne duplicitně vytvořit).

---

## Shrnutí — kdo dělá co

| Krok | Kdo |
|---|---|
| Potvrdit, jestli má Workspace | **klient** (otázka č. 1) |
| Založit/zpřístupnit GCP projekt + billing | **klient** |
| Povolit Drive API | já (pokud mám přístup do projektu) nebo klient |
| Vytvořit service account + JSON klíč | já (v klientově projektu) |
| Bezpečně mi předat JSON klíč | já sám sobě, pokud jsem projekt založil; jinak klient mně |
| Založit Shared Drive | **klient** (nebo jeho IT/admin Workspace) |
| Přidat service account do Shared Drive | **klient** |
| Poslat mi ID cílové složky | **klient** |
| Upravit `drive.py`, `.env`, otestovat | já |

---

## Otázka pro klienta č. 2 (až bude Workspace/Shared Drive hotový)

Kdo bude mít ke Shared Drive přístup a v jaké roli (jen čtení výstupů /
možnost mazat a přesouvat)? Ovlivní to, jaké role přidat konkrétním lidem
vedle service accountu.
