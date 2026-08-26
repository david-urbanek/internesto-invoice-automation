# transactions/

CSV výpisy z Fio banky. Jeden soubor = jeden výpis z účtu.

Export z Fio: Účty → Historie → Export → CSV (UTF-8).
Název souboru zachovej tak, jak ho Fio vygeneruje.

## Rozdělení Prijmove/ vs Vydajove/ (08/2026)

Výpisy patří do podsložky podle typu účtu (viz `FIREMNI_UCTY` v
`src/kategorizace/config.py`) – zúží to nabídku kategorií pro AI
a sníží riziko špatného zařazení. Soubor ponechaný přímo v `transactions/`
(bez podsložky) se zpracuje jako dřív, bez zúžení.

- **Prijmove/** – Příjmový 1 CZK (`2200973033`), Příjmový 2 EUR (`2301780732`)
- **Vydajove/** – Výdajový 1 CZK (`2901813198`), Výdajový 2 CZK (`2601728813`),
  Ostatní CZK (`2901321222`), Premier Fond (`2203097403`),
  Rezervní 1/2/3, Raiffeisen, MONETA
