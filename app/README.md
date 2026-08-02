# Kategorizace transakcí – desktopová aplikace

Electron obal nad Python enginem (`kategorizace.gui`). Zákazník si vybere
složku s daty, vloží API klíč a jedním tlačítkem spustí kategorizaci –
průběh vidí živě v okně, výsledné CSV otevře přímo z aplikace.

## Architektura

```
app/                  Electron (GUI)
  main.js             hlavní proces – spawnuje Python engine, streamuje JSONL eventy
  preload.js          bezpečný IPC most do rendereru
  renderer/           UI (HTML/CSS/JS, česky)

engine/               balení Python enginu
  entry.py            vstupní bod pro PyInstaller
  build.sh            vytvoří engine/dist/kategorizace-gui (onefile binárka)

src/kategorizace/gui.py   JSONL runner – stejná pipeline jako CLI `kategorizace`
```

Komunikace: engine píše na stdout JSON Lines eventy (`start`, `index_krok`,
`job_stav`, `job_hotovo`, `hotovo`, `chyba`…), Electron je parsuje a
zobrazuje. API klíč se předává přes proměnnou prostředí `GOOGLE_API_KEY`.

## Vývoj

```bash
cd app
npm install
npm start          # použije ../.venv/bin/python -m kategorizace.gui
```

## Sestavení distribuce (.dmg / .exe)

```bash
# 1. zabal Python engine (na cílové platformě!)
bash engine/build.sh

# 2. zabal Electron aplikaci (přibalí engine/dist/ jako resources/engine/)
cd app
npm run dist       # výstup v app/dist/
```

Výstup: `app/dist/Kategorizace.app` (dvojklikem spustitelná) a `.dmg`.
Rychlejší build jen pro vlastní architekturu: `npx electron-builder --mac dmg --arm64`.

Pozn.: PyInstaller nedělá cross-compile – macOS binárku sestavíš na Macu
(arm64/x64 zvlášť), Windows `.exe` na Windows.

### Dvě macOS specialitky, na které nešahat

1. **`build.productName` musí být bez diakritiky** (`Kategorizace`). macOS ukládá
   názvy složek v Unicode NFD, ale `Info.plist` v NFC – s „í“ v názvu pak Chromium
   nenajde helper aplikace (`… Helper (GPU).app`) a aplikace spadne hned po startu
   na `SIGTRAP`, bez jediné hlášky. Český název se uživateli zobrazuje přes
   `CFBundleDisplayName` v `mac.extendInfo`.

2. **Ad-hoc podpis přes `afterPack.js`.** Bez Developer ID certifikátu
   electron-builder podpis přeskočí, jenže na Apple Siliconu se nepodepsaný bundle
   vůbec nespustí. `afterPack.js` podepíše bundle zevnitř ven (`codesign --deep`
   u Electronu nefunguje). Pro cizí Macy to nenahrazuje notarizaci – Gatekeeper
   si při prvním spuštění vyžádá pravý klik → Otevřít.

## Nastavení uživatele

Ukládá se do `userData/settings.json` (macOS:
`~/Library/Application Support/Kategorizace transakcí/`):

- `apiKey` – Gemini API klíč
- `rootDir` – složka obsahující podadresář `firmy/`
