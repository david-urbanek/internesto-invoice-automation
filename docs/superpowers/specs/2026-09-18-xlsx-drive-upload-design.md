# XLSX upload do Google Sheets

## Cíl

Umožnit nahrát všech 13 souborů z `data/upload/*.xlsx` do cílové Google Drive složky jako nativní Google Sheets, aby je Apps Script načetl přes `MimeType.GOOGLE_SHEETS`.

## Chování

- Uploader načte Excel soubory z `data/upload/`.
- Každý soubor musí mít hlavičky `Datum`, `Objem`, `Měna`, `Kategorie`, `Jistota kategorie`, `Firma` a `Radek`.
- Název cílového souboru vznikne podle existující konvence: většinový měsíc/rok ze sloupce `Datum`, firma a zbytek názvu; odstraní se diakritika, použije lowercase a bez přípony.
- Upload použije Drive API konverzi do MIME typu Google Spreadsheet.
- Při shodě názvu se aktualizuje existující soubor; jinak se vytvoří nový.
- Zdrojové XLSX soubory zůstanou nezměněné.
- Po zpracování se vypíše počet řádků, počet nových/aktualizovaných souborů a chyby. Soubor s chybějící povinnou hlavičkou se nenahraje.

## Kompatibilita s Apps Scriptem

Výstupní Google Sheets zachovají první řádek jako hlavičky a datové řádky. Apps Script následně čte povinné sloupce podle jména, přeskočí zcela prázdné řádky a doplní měsíc z názvu, pokud datum nepůjde rozpoznat.

## Ověření

- Kontrola povinných hlaviček všech 13 vstupů.
- Kontrola parsování dat a generovaných názvů.
- Skutečný upload/aktualizace do cílové složky.
- Kontrola výsledného počtu souborů a nahlášených chyb.
