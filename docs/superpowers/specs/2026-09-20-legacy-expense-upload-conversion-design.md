# Převod starých výdajových XLSX do upload struktury

## Cíl

Umožnit vložit staré výdajové bankovní výpisy ve formátu XLSX do bezpečné vstupní složky, převést jejich historickou strukturu na současný formát a připravit je pro upload na Google Drive.

Výstup musí obsahovat standardizované sloupce:

- `Kategorie`
- `Jistota kategorie`
- `Firma`
- `Radek`

Původní bankovní data včetně sloupce `Poznámka` se zachovají. Historicky zadané kategorie se nemají bezdůvodně měnit novým AI rozhodováním.

## Rozhodnutí

- Staré XLSX se nejdříve zpracují lokálně; raw soubory se nesmí nahrávat přímo na Drive.
- Doporučené vstupní místo pro raw soubory je `data/upload/incoming/`, aby je běžný uploader omylem nezpracoval jako hotové uploady.
- Připravené soubory se vytvoří odděleně jako upload-ready XLSX.
- Stávající `data/upload/*.xlsx` workflow zůstane kompatibilní s již připravenými soubory.
- Původní `Poznámka` zůstane zachovaná; slouží jako zdroj historického štítku nebo vodítko, ne jako jediná výsledná kategorie.
- Pro známé historické štítky a aliasy se použije deterministické mapování.
- `Radek` se vždy dopočítá přes `_radek_pro_kategorii(kategorie, objem, mena)`, aby respektoval znaménko částky a měnu.
- Drive naming se aplikuje až při uploadu přes existující `_drive_nazev`; lokální soubory se kvůli tomu nepřejmenovávají.

## Vstupní struktury

Převod musí podporovat minimálně:

1. Fio XLSX s kanonickými sloupci `Datum`, `Objem`, `Měna`, `Protiúčet`, `Poznámka`.
2. Starší Fio exporty s duplicitními sloupci `Poznámka`, `Poznámka_2` nebo jinými opakovanými hlavičkami.
3. Pokladní výpisy s aliasy `Datum platby`, `Příjem/Výdej`, `Popis`, `VS dokladu`.
4. Raiffeisenbank/Air Bank exporty s jinými názvy sloupců a kategorií uloženou ve starším textovém sloupci.

Hlavičky se normalizují bez ztráty originálních sloupců. Duplicitní názvy dostanou deterministické suffixy, aby bylo jasné, ze kterého sloupce historická hodnota pochází.

## Mapování kategorií

### Priorita zdrojů

1. Existující kanonická `Kategorie`, pokud je ve vstupu vyplněná.
2. Historický štítek z `Poznámka` podle explicitní mapovací tabulky.
3. Existující aliasy a deterministická pravidla projektu.
4. Textové/dodavatelské pravidlo pouze tehdy, pokud je pro stará data výslovně schválené.
5. Jinak `Neurčeno`.

Příklady historických hodnot, které vyžadují mapu nebo pravidlo:

- `Alza`
- `Jednatel`
- `Booking provize`
- `Tmobile`
- `Převod`
- `Nájem + Energie Vlhká 19`
- dlouhé hodnoty typu `Nákup: ...`

Tyto texty se nesmí slepě kopírovat do `Kategorie`: některé jsou skutečné štítky, jiné jsou pouze popis transakce.

### Jistota

- Přesná historická kategorie nebo explicitní alias: `100`.
- Deterministické pravidlo s jednoznačným výsledkem: `100`.
- Nejasný nebo nepřiřazený řádek: prázdná hodnota nebo nízká hodnota podle existujícího kontraktu, vždy s kontrolní poznámkou.

### Nejasné řádky

Nejasné hodnoty se nesmí násilně přiřadit do kategorie. Výsledek:

- `Kategorie = Neurčeno`
- `Radek = N00` pro výdajový účet, případně příslušný nenamapovaný příjmový řádek
- zachovaná původní `Poznámka`
- kontrolní poznámka s důvodem, proč mapování nebylo jisté

Tím se zachová auditovatelnost a nevzniknou tiché účetní změny.

## Výstup

Převod vytvoří upload-ready XLSX se standardizovanými sloupci a původními bankovními daty. Každý řádek musí mít:

- stejný počet transakcí jako vstup,
- vyplněné `Firma`,
- vyplněné `Kategorie`, minimálně `Neurčeno`,
- vyplněný `Radek`,
- žádné přetečení CSV/XLSX sloupců,
- zachovaný původní text `Poznámka`.

Výstupy se vytvoří do oddělené staging složky nebo s jednoznačným upload-ready názvem. Raw vstup se nepřepisuje.

## Workflow

```text
raw XLSX
  -> načtení a normalizace hlaviček
  -> výběr historického štítku
  -> deterministické mapování Kategorie
  -> výpočet Firma + Radek
  -> validační report
  -> upload-ready XLSX
  -> uv run nahraj-na-drive
  -> Drive název MM-YYYY-firma-zbytek
```

Před uploadem se zobrazí souhrn:

- počet vstupních a výstupních řádků,
- počet konkrétních kategorií,
- počet `Neurčeno`,
- počet řádků s `Radek = N00`,
- soubory s neznámými historickými štítky.

## Chyby a bezpečnost

- Chyba jednoho souboru nesmí zabránit zpracování ostatních souborů.
- Při chybě validace se upload-ready výstup pro daný soubor nevytvoří.
- Raw vstupní soubor se nemaže ani nepřepisuje.
- Upload na Drive je samostatný krok; převod sám nesmí volat Drive API.
- Převod bez explicitního přepínače nesmí spouštět Gemini recategorizaci.

## Testovací kontrakt

Ověřit minimálně:

1. Převod Fio XLSX s kategorií v `Poznámka`.
2. Duplicitní `Poznámka` a zachování všech původních sloupců.
3. Přesné aliasy a historické štítky.
4. Neznámý štítek → `Neurčeno` + nenamapovaný `Radek`.
5. Mapování `Radek` podle znaménka částky a měny.
6. Zachování počtu vstupních řádků.
7. Žádné přetečené hodnoty ani rozbité hlavičky.
8. Opakovaný převod vytvoří stejný výsledek.
9. Uploader použije správný Drive název bez přejmenování lokálního raw souboru.

## Mimo rozsah

- Automatické rozhodování nových kategorií Gemini pro historické řádky.
- Ruční oprava každého neznámého štítku bez uživatelského mapování.
- Mazání nebo přepis raw XLSX.
- Změna existujících lokálních výsledků bez explicitního příkazu.
- Změna Drive naming convention.

## Otevřené rozhodnutí před implementací

Je potřeba potvrdit finální mapu historických hodnot, které nejsou přesným názvem kategorie. Doporučený první krok je vygenerovat report unikátních hodnot z `Poznámka` a schválit jejich mapování před vytvořením upload-ready souborů.
