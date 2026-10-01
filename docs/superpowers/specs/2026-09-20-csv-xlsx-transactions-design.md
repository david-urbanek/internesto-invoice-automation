# Podpora CSV a XLSX transakcí

## Cíl

Kategorizace načte bankovní výpisy ve složce `firmy/*/transactions/` ve formátu CSV i XLSX. Oba formáty projdou stejnou existující pipeline. Výstup zůstává vždy CSV.

## Rozhodnutí

- CSV se načítá stávající implementací.
- XLSX se načítá přes již používaný `openpyxl`.
- Společný loader vybírá parser podle přípony.
- XLSX se čte z prvního worksheetu; první vhodný neprázdný řádek je hlavička.
- Řádky se převedou na stejný `list[dict]` jako u CSV.
- Na oba formáty se aplikuje stejná normalizace aliasů.
- Výsledky z CSV i XLSX se zapisují do `results/<Firma>-<název>.csv`.
- Přípony při hledání vstupů jsou case-insensitive.

## Architektura

### `src/kategorizace/io.py`

Doplní se XLSX parser a společný loader `nacti_transakce(cesta)`. XLSX parser otevře workbook přes `openpyxl.load_workbook(..., read_only=True, data_only=True)`, vybere první worksheet, najde první řádek s použitelnými hlavičkami, odstraní prázdné trailing řádky, převede hodnoty a použije společnou normalizaci aliasů.

Datumové hodnoty musí zůstat rozpoznatelné funkcí pro rozsah dat. Číselné hodnoty musí zůstat použitelné pro částky a deterministická pravidla.

### `src/kategorizace/cli.py`

Vyhledávají se `*.csv` i `*.xlsx` v `transactions/`, `transactions/Prijmove/` a `transactions/Vydajove/`. Job odkazuje na obecný vstupní soubor, ale původní cesta zůstává dostupná pravidlům používajícím název výpisu.

### `src/kategorizace/pipeline.py`

Pipeline použije společný loader místo přímého CSV parseru. Ostatní kroky zůstanou stejné. Výstupní serializer zůstane `uloz_csv`.

## Chyby

Poškozený nebo nečitelný XLSX selže pouze u daného jobu; CLI pokračuje dalšími joby. Prázdný XLSX má stejný stav jako prázdný CSV a nevytvoří částečný výstup.

## Testovací kontrakt

Ověří se zachování CSV, načtení XLSX, aliasy, datumy a částky, discovery obou přípon ve všech složkách, CSV výstup pro XLSX, prázdný a poškozený XLSX.

## Mimo rozsah

Generování XLSX výstupu, změny AI promptů/kategorizace, změna CSV výsledku, pandas a změny Google Drive uploadu.
