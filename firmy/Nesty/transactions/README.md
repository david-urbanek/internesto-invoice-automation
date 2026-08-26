# transactions/

CSV výpisy z Fio banky. Jeden soubor = jeden výpis z účtu.

Export z Fio: Účty → Historie → Export → CSV (UTF-8).
Název souboru zachovej tak, jak ho Fio vygeneruje.

## Rozdělení Prijmove/ vs Vydajove/ (08/2026)

Výpisy patří do podsložky podle typu účtu (viz `FIREMNI_UCTY` v
`src/kategorizace/config.py`) – zúží to nabídku kategorií pro AI
a sníží riziko špatného zařazení. Soubor ponechaný přímo v `transactions/`
(bez podsložky) se zpracuje jako dřív, bez zúžení.

- **Prijmove/** – Příjmový 1 CZK (`2301240402`)
- **Vydajove/** – Výdajový 1 CZK (`2201830907`), Ostatní CZK (`2301780716`),
  Rezervní 1 CZK (`2802351514`), MONETA
