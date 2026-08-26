# transactions/

CSV výpisy hotovostní pokladny. Jeden soubor = jeden výpis.

## Rozdělení Prijmove/ (08/2026)

Pokladní kniha (obecný výpis se smíšenými příjmy/výdaji, jako
`Pokladna-1.csv`) zůstává přímo v `transactions/` beze změny – má
vlastní uzavřený seznam kategorií (`OMEZENE_KATEGORIE_PODLE_UCTU`,
klíč `POKLADNA_HOTOVOST`), zúžení podle Prijmove/Vydajove tam nedává
smysl (jeden soubor obsahuje obojí).

- **Prijmove/** – vyhrazeno pro budoucí SAMOSTATNÝ příjmový výpis
  pokladny (pokud se od pokladní knihy oddělí) – veškeré příjmy tam
  patří do jediné kategorie „Hotovost" (`OMEZENE_KATEGORIE_PODLE_UCTU`,
  klíč `POKLADNA_PRIJMOVY`) → řádek P11 v alokačním formuláři.
