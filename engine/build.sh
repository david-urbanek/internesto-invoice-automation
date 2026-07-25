#!/usr/bin/env bash
# Zabalí Python engine (kategorizace.gui) do samostatného spustitelného souboru
# přes PyInstaller. Výstup: engine/dist/kategorizace-gui
# Ten pak electron-builder přibalí do aplikace jako resources/engine/.
#
# Spuštění (z kořene repozitáře):  bash engine/build.sh
set -euo pipefail

cd "$(dirname "$0")/.."

# PyInstaller nainstaluj do venv, pokud chybí
.venv/bin/python -m pip show pyinstaller >/dev/null 2>&1 || .venv/bin/python -m pip install pyinstaller

.venv/bin/python -m PyInstaller \
  --onefile \
  --name kategorizace-gui \
  --distpath engine/dist \
  --workpath engine/build \
  --specpath engine \
  --paths src \
  --hidden-import kategorizace \
  --collect-all google.genai \
  --collect-all pymupdf \
  engine/entry.py

echo "Hotovo: engine/dist/kategorizace-gui"
