# transactions/

CSV výpisy z Fio banky. Jeden soubor = jeden výpis z účtu.

Export z Fio: Účty → Historie → Export → CSV (UTF-8).
Název souboru zachovej tak, jak ho Fio vygeneruje.

## Rozdělení Prijmove/ vs Vydajove/ (08/2026)

Výpisy patří do podsložky podle typu účtu (viz `FIREMNI_UCTY` v
`src/kategorizace/config.py`) – zúží to nabídku kategorií pro AI
a sníží riziko špatného zařazení. Soubor ponechaný přímo v `transactions/`
(bez podsložky) se zpracuje jako dřív, bez zúžení.

- **Prijmove/** – Příjmový 1 CZK (`2201422348`), Příjmový 1 EUR (`2401780748`)
- **Vydajove/** – Výdajový 1 CZK (`2601813209`), Rezervní 1 (`2002351495`),
  Rezervní 2 (`2102351492`), MONETA
