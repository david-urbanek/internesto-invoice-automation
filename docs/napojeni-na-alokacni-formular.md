# Napojení kategorizace na Alokační formulář

Analýza z 2. 8. 2026. Podklad k rozmyšlení, ne hotové zadání.

Cíl: transakce, které skript odkategorizuje, se mají samy propsat do
`data/2026 Alokační formulář.xlsx` (resp. do jeho verze v Google Sheets),
aby je klient nemusel přepisovat ručně.

---

## 1. Výchozí stav — co je na obou stranách

### Skript (tento repozitář)

| Věc | Kde | Poznámka |
|---|---|---|
| 58 kategorií | `src/kategorizace/config.py:80` a `:618` | `KATEGORIE` + `KATEGORIE_PRIJMY_A_MAJITEL` |
| ~60 aliasů | `config.py:568` | historické štítky → kanonický název |
| Deterministická pravidla | `config.py:697`–`:818`, `deterministika.py` | podle účtu, dodavatele, textu, částky |
| Výstup | `firmy/<Firma>/results/<Firma>-<vypis>.csv` | oddělovač `;`, kódování UTF-8 s BOM |

**Důležité, co se v diskuzi ztratilo: výstup není jeden CSV na firmu, ale
jeden CSV na bankovní účet.**

```
RD       → Příjmový 1, Výdajový 1, Výdajový 2, Ostatní   (4 soubory)
Nesty    → Ostatní                                        (1)
Casa     → Výdajový 1                                     (1)
Pokladna → Pokladna                                       (1)
```

To je ~7 souborů za měsíc, tedy **~84 CSV za rok**, ne 48.

**Hlavičky se liší soubor od souboru.** `uloz_csv()` bere sloupce z prvního
řádku dat (`pipeline.py:74`), takže:

- Fio výpisy: ~24 sloupců (`ID operace`, `Datum`, `Objem`, `Měna`, `Protiúčet`, …)
- Pokladna: úplně jiné schéma (`Číslo`, `Č. dokladu`, `Popis`, `Datum platby`,
  `Příjem/Výdej`, …) a **jeden sloupec má prázdný název** (je v něm měna)
- Názvy mají navíc mezery navíc (`"ID operace "`, `" Datum  "`)

Společné napříč všemi soubory jsou jen: `Datum`, `Objem`, `Poznámka`,
`Kategorie`, `Jistota`, `Faktura`, `Parovani`.

> **Důsledek:** slévání do jednoho listu musí sloupce normalizovat podle
> **jména**, ne podle pozice. Jinak se Pokladna posype.

### Formulář

17 listů ve třech vrstvách:

1. **Zdrojové listy entit** — `RD`, `Nesty`, `Casa`, `Pokladna`.
   Sem se dnes zadává ručně. Řádky = položky, sloupce C–N = leden–prosinec,
   O = roční součet. **Tohle je jediné místo, kde se bude něco měnit.**
2. **Měsíční listy** — `Leden` … `Prosinec`. Jen odkazy na listy entit.
3. **`Přehled`** — jen odkazy na měsíční listy.

Struktura řádků na listu entity (na všech čtyřech shodná), od 08/2026
doplněno o statický **ID sloupec `C`** (`P2`…`P18` příjmy, `N19`…`N73`
výdaje, `CELKEM_*`/`OSTATNI_*` pro souhrnné řádky) a měsíční sloupce
posunuté na `D`–`O` (`P` = roční součet):

| Řádky | Blok |
|---|---|
| 2–18 | Příjmy |
| 19–73 | Výdaje (73 = nově přidaný „Nájem prostor – Nesty", ID `N73`) |
| 74–78 | CELKEM (součty) |
| 80–83 | Ostatní (Rezervní 2, Rezervní 3, Jiný příjem, Jiná vratka) |

Celkem **73 datových řádků**. Měsíční listy se na entity listy odkazují
přes `INDEX/MATCH` podle ID sloupce `C`, ne pevným číslem řádku/sloupce –
nové řádky lze přidávat kamkoli do bloku, aniž by se rozbily vzorce
v měsíčních listech (jen je nutné dohlídnout SUM rozsahy v řádcích 74–78
a sloučené buňky).

---

## 2. Hlavní problém: kategorie ≠ řádky formuláře

Kategorie skriptu a řádky formuláře vznikaly nezávisle. Nesedí na sebe
jménem ani počtem.

### Doporučení: NEstandardizovat kategorie, ale přidat mapovací vrstvu

Přejmenovat 58 kategorií na názvy řádků vypadá jako čisté řešení, ale rozbilo
by to:

- deterministická pravidla vázaná na názvy (`VZDY_DODAVATEL_KATEGORIE`,
  `UCET_VZDY_KATEGORIE`, `SPLATKY_UVERU`, `OMEZENE_KATEGORIE_PODLE_UCTU`)
- celý slovník `ALIASY` — historii, jak klient štítkoval v minulých letech
- zlatý dataset pro evaluaci (`scratch_dataset.json`, `evaluace.py`) —
  přišel bys o možnost měřit, jestli se přesnost zlepšuje, nebo zhoršuje

Zaplatil bys přesností kategorizace za kosmetiku.

**Místo toho:**

```python
# config.py
MAPOVANI_NA_FORMULAR: dict[str, str] = {
    "V14 nájem":   "R24",
    "V14 energie": "R24",
    "Kotlářská":   "R25",
    "Jídlo":       "R62",
    "Převod":      None,   # interní přesun — do formuláře nepatří
    ...
}
```

Skript pak do výstupního CSV přidá sloupec `Radek` s hodnotou `R24`, `R62`…

Proč takhle:

- **mapování žije na jednom místě**, ve verzovaném Pythonu, ne rozprostřené
  mezi configem a nějakým číselníkem v Sheets
- Sheets dělá hloupý SUMIFS a nemusí nic vědět o kategoriích
- kód řádku = číslo řádku, takže vzorec může být úplně stejný pro celou
  mřížku:

```
=SUMIFS(Transakce!$F:$F; Transakce!$B:$B; $B$1; Transakce!$D:$D; "R"&ROW(); Transakce!$G:$G; C$1)
        └ částka         └ firma (z buňky)              └ řádek         └ měsíc (z hlavičky)
```

Jeden vzorec, roztažený přes celou mřížku C2:N82, na všech čtyřech listech.

---

## 3. Mapování — jak to sedí

### 3a) Sedí 1:1 (~34 řádků) — žádná práce

| Skript | Řádek | Skript | Řádek |
|---|---|---|---|
| Booking | 22 | Socka | 56 |
| Kotlářská | 25 | Zdravka | 57 |
| V19 | 27 | FU (srážková daň) | 58 |
| A82 | 29 | Snídaně | 59 |
| V24 | 31 | Taxi | 60 |
| Arteon (auto leasing) | 39 | Jídlo | 62 |
| Benzín | 40 | Dekorace | 63 |
| Výdaje majitele | 41 | Drogerie | 64 |
| Internet | 44 | Kancelář | 65 |
| Previo systém | 45 | Technik | 66 |
| Google | 46 | Prádelna | 68 |
| Telefony | 47 | Ostatní služby | 70 |
| Recepční | 50 | Netflix a Spotify | 71 |
| Úklid | 51 | Rezervní 2 | 79 |
| Design | 52 | Rezervní 3 | 80 |
| Výplata majitele | 53 | | |
| Rosi (faktura účetní) | 54 | | |
| Garant | 55 | | |

> Pozor na dvojici `Výdaje majitele` (ř. 41) vs. `Výplata majitele` (ř. 53).
> Skoro stejný název, úplně jiný význam.

### 3b) N:1 — víc kategorií do jednoho řádku (v pořádku, SUMIFS to umí)

| Kategorie | Řádek | Poznámka |
|---|---|---|
| `V14 nájem` + `V14 energie` | 24 | „Nájem Veselá + energie" |
| `Šremer` | 26 | ověřit, jestli je to opravdu „Vlhká Honza" |
| `B53` + `A43` | 32 | „Nájem (splátka) – B53 + A43" |

### 3c) 1:N — jedna kategorie do víc řádků. **Tady je práce.**

Skript to sám nerozhodne, protože tu informaci nemá.

| Kategorie | Řádky | Jak to řešit |
|---|---|---|
| `Pojištění` | 34 nemovitost / 48 auto | rozdělit na 2 kategorie v configu — dodavatel a protiúčet to odliší |
| `Splátka`, `Úrok` | 42 Moneta / 43 Raiffeisen | `SPLATKY_UVERU` (`config.py:788`) už banky rozlišuje, jde z toho odvodit |
| `DPH` | 17 PLUS / 19 MÍNUS | podle znaménka `Objem` — řeší se až v Apps Scriptu |
| `Zvláštní výdaj` | 18 PLUS / 20 MÍNUS | totéž |
| `Reprezentace` | 35 Vzdělávání / 72 Osobní + dárky | **automaticky nerozhodnutelné** — buď nová kategorie, nebo natvrdo do jednoho řádku |
| `Poplatek`, `Banka`, `Úrok`, `Rezervní 1` | N37 / N38 / N49 / N61 (+ N33 Parkování) | **nejhorší uzel — částečně rozklíčováno, ještě nepotvrzeno klientem:** skutečné popisky řádků: N37 „Ubytovací a rekreační poplatky", N38 „Ostatní poplatky + DPPO + Havárie + Popelnice", N49 „Jiné poplatky + úroky", N61 „Popelnice". Navrhováno: `Poplatek→N38`, `Úrok→N49` (bankovní úrok z úvěru). `Rezervní 1` (config.py:524, protiúčty `2402351507`/`43-8206670217`/`115-9579990277`) je sama o sobě 1:N — podle textu v `zprava`/`stitek` (ověřeno v `scratch_dataset.json`) se rozpadá na "parkování"→N33, "popelnice"→N61, "ubytovací poplatky" (i pevně podle protiúčtů `43-8206670217`/`115-9579990277`)→N37. **Nevyřešeno:** nalezen i případ "Převod na auto" v `Rezervní 1`, který nesedí do žádného z těchto tří — kam patří? `Banka` (hotovostní odvod/vklad z pokladny) zatím navrženo jako `None` (nejde do formuláře, jako `Převod`) — potvrdit. |

### 3d) Řádky formuláře bez protějšku ve skriptu (~20)

**Skoro celý příjmový blok:**

| Řádek | Název |
|---|---|
| 3 | Platební terminál |
| 4 | Ostatní ubytování/služby CZK |
| 6 | Ostatní ubytování EUR |
| 7 | Dotace od státu |
| 9–10 | Faktura Casa VV CZK / EUR |
| 11–12 | Faktura Hotově CZK / EUR |
| 13–14 | Poukaz Hotově CZK / EUR |
| 15 | Hotovost/Poukaz Ostatní |
| 16 | Ostatní příjmy |

Z příjmů skript zná jen `Airbnb` (ř. 2), `Příjem energie` (od 08/2026
namapováno na ř. 16, sdílí s `Ostatní příjmy`), `Kauce`, `Vratka`.

Dále chybí: 30 (Nájem Fond A24-A83), 33 (Parkování), 36 (Nemoc),
67 (Jiná propagace), 69 (Služby spojené s hostem).

> ### ➜ Otázka č. 1 na klienta
> **Má skript kategorizovat i příjmy?**
> Pokud ne, řádky 2–18 zůstávají ruční a formulář bude hybridní —
> část automaticky, část ručně. To je legitimní volba, ale musí být
> vědomá, ne překvapení po nasazení.

### 3e) Kategorie skriptu bez protějšku ve formuláři

`Převod`, `Rezervní 1`, `Spilberk`, `Kauce` — `Prostory` má od 08/2026
řádek `N73` (viz `MAPOVANI_NA_FORMULAR` v `config.py`).

---

## 4. Další úskalí

### 4.1 `Převod` nesmí do formuláře

Interní přesuny mezi vlastními účty skupiny (`aplikuj_interni_prevod`,
`FIREMNI_UCTY`). Když se dostanou do sumy, **počítá se všechno dvakrát** —
jednou jako odchozí, jednou jako příchozí.

Potřebuje explicitní „zahodit" (`None` v mapovacím dictu), ne řádek ve
formuláři.

### 4.2 Měny — tichá past

Formulář má **oddělené CZK a EUR řádky**: 4/6, 9/10, 11/12, 13/14.

Ale `Objem` je jedno číslo a měna je vedle — a v Pokladně dokonce ve
**sloupci s prázdným názvem**:

```
Popis;Datum platby;Příjem/Výdej;;Zůstatek;_2
                                ^ tady je "EUR"/"CZK"
```

Klíč pro mapování tedy nesmí být jen kategorie, ale **(kategorie, měna)**.
Jinak se sečtou koruny s eury do jednoho čísla a nikdo si toho nevšimne.

### 4.3 Řádek 28 se jmenuje na každém listu jinak

| List | Popisek ř. 28 |
|---|---|
| RD | Nájem Gábi – **A63 a A73** |
| Nesty, Casa, Pokladna | Nájem Gábi – **A43 a A63** |

A `A43` je zároveň na řádku 32 („B53 + A43") na **všech** listech.

To je rozpor v datovém modelu samotného formuláře. Dokud tam je, patří
`A43` do dvou řádků současně a mapování nejde jednoznačně napsat.

> ### ➜ Otázka č. 2 na klienta
> Kam patří A43 — do řádku 28, nebo 32? A je popisek na listu RD (A73)
> správně, nebo je to překlep?

### 4.4 Formulář sám počítá špatně — ověřeno

Spot-check na listu `Leden` (openpyxl, čtení vzorců):

| Buňka | Aktuálně | Má být |
|---|---|---|
| `G46` | `0` natvrdo | `=Nesty!C33` |
| `I46` | `=I42-G46` | `=I45-G46` (přeskakuje ř. 43–45) |
| `J46` | `=Casa!I33` | `=Casa!C33` (odkaz na **duben** místo ledna) |
| `M46` | `=Pokladna!L33` | `=Pokladna!C33` (odkaz na **říjen**) |
| `F100` | `=F98-D100` | `=F99-D100` (vynechává ř. 99) |
| `I100`, `L100`, `O100` | totéž | totéž |
| `D111` | `40000` natvrdo | `=D110*0.6` |
| `D112` | `10000` natvrdo | `=D110*0.4` |
| `G111`, `J111`, `M111` | `=G110*0.7` | popisek říká **60 %**, vzorec počítá **70 %** |
| `D99` | `0` natvrdo | odkaz na list entity |

Kontrolováno na listu `Leden`. Ostatní měsíce vznikly kopií, takže tam ty
chyby budou pravděpodobně taky — neověřeno.

> **Tohle bych opravil dřív, než se na formulář napojí automatický vstup.**
> Jinak budeš ladit skript proti tabulce, která sama počítá špatně,
> a nepoznáš, čí je chyba.

### 4.5 Sloupec `Jistota` — vezmi ho s sebou

Skript u každé transakce vrací skóre jistoty. Když ho protáhneš až do listu
`Transakce`, klient si vyfiltruje „ukaž jen to pod 80" a nemusí kontrolovat
všech ~1500 řádků.

Je to zadarmo (sloupec už existuje) a je to pravděpodobně největší úspora
času v celém workflow.

---

## 5. Struktura složek na Drive

### Jak to vypadá dnes

```
2026/
  1) Leden/
  2) Únor/
  ...
  8) Srpen/
  Benefit/            ← tematické složky
  RB 2 úvěry/            na stejné úrovni
  Flatio faktury/        jako měsíce
  Airbnb/
  Airwallet/
  Netflix a Spotify/

  1) Leden/
    Podklady/
      RD/  Nesty/  Pokladna/  Casa/   ← tady jsou odkategorizovaná CSV
```

Parsovat to podle názvu je křehké: prefix `8) `, diakritika, mezery,
a tematické složky by se musely aktivně vyfiltrovat.

### Návrh: nechat jeho strukturu být a přidat plochou výstupní složku

Struktura pro účtenky mu funguje, není důvod ji měnit. Ale výstup skriptu
patří jinam:

```
2026/
  _Transakce_vystup/
    2026-01_RD_Vydajovy1.csv
    2026-01_RD_Prijmovy1.csv
    2026-01_Nesty_Ostatni.csv
    2026-01_Pokladna.csv
    2026-02_RD_Vydajovy1.csv
    ...
```

- měsíc i firma jsou v **názvu souboru** → Apps Script nepotřebuje
  procházet strom, stačí `getFoldersByName("_Transakce_vystup")`
- žádná diakritika, žádné mezery, žádné prefixy
- **konvenci vynutí Python skript**, ne klient — název generuje kód,
  takže se nemůže rozejít

---

## 6. Cílová architektura

```
Fio výpisy + faktury
        ↓
   Python skript (tento repo)
        ↓
   CSV se sloupci: Datum, Firma, Ucet, Popis, Kategorie, Radek, Mena, Objem, Jistota, Faktura
        ↓
   Drive: 2026/_Transakce_vystup/2026-01_RD_Vydajovy1.csv
        ↓
   Apps Script (tlačítko v menu Sheets)
     - normalizuje hlavičky (podle jména, ne pozice)
     - slije všechny CSV do listu Transakce
     - přepíše list NAČISTO (žádné duplicity, jedno kolikrát to spustíš)
        ↓
   List Transakce  (jediné místo v sešitu, kde leží data)
        ↓
   SUMIFS v RD / Nesty / Casa / Pokladna
        ↓
   Měsíční listy → Přehled   (beze změny, fungují jak fungují)
```

### Struktura listu `Transakce`

| Sloupec | Obsah |
|---|---|
| A | Datum |
| B | Firma (RD / Nesty / Casa / Pokladna) |
| C | Účet (Výdajový 1, Ostatní, …) |
| D | Řádek formuláře (`R24`, `R62`, `R00` = nenamapováno) |
| E | Kategorie (text — jen pro čtení při kontrole) |
| F | Objem |
| G | Měsíc (1–12, z názvu souboru) |
| H | Měna |
| I | Jistota |
| J | Zdrojový soubor |

### Kontrolní mechanismy

1. **`R00` = nenamapováno.** Všechno, co nemá řádek, spadne sem —
   nezmizí to potichu. Na listu entity kontrolní řádek, který ukáže, kolik
   peněz nikam nespadlo.
2. **Součet transakcí vs. součet formuláře.** Musí sedět na korunu.
   Když nesedí, něco se ztratilo nebo započítalo dvakrát.

### Pravidla, která z toho plynou

- Do listu `Transakce` **se nesmí psát ručně** — refresh to smaže.
- Ruční opravy kategorií musí proběhnout **před importem** (v CSV, nebo
  ve skriptu jako nový alias/pravidlo).
- Filtrovat přes **„Zobrazení filtru"**, ne obyčejný filtr — obyčejný
  filtr vidí všichni ostatní v dokumentu a schová jim řádky pod rukama.

---

## 7. Co je potřeba rozhodnout, než se začne

1. **Příjmy — ano, nebo ne?** (viz 3d) Pokud ano, přibude ~10 kategorií
   a bude potřeba vymyslet, jak skript pozná platební terminál od
   ostatního ubytování.
2. **Uzel poplatků 37 / 38 / 49 / 61.** (viz 3c) Co přesně patří kam?
3. **A43: řádek 28, nebo 32?** (viz 4.3)
4. **`Reprezentace`: vzdělávání, nebo osobní/dárky?** Nebo rozdělit?
5. **Kde běží Sheets a kdo do něj sahá?** Jestli je ostrá verze už na
   Drive a někdo v ní pracuje, nemá smysl přestavovat tenhle `.xlsx` —
   změny se budou muset zanést do té ostré.

---

## 8. Navržené pořadí prací

| # | Krok | Kde | Blokuje to něco? |
|---|---|---|---|
| 1 | Opravit vzorce ve formuláři (12 měsíců × ~6 míst) | xlsx | ne — dá se začít hned |
| 2 | Rozhodnout body ze sekce 7 | klient | blokuje krok 3 |
| 3 | Mapovací dict `KATEGORIE → řádek` | `config.py` | |
| 4 | Nové sloupce `Radek`, `Mena`, `Firma`, `Ucet` ve výstupu | `io.py`, `pipeline.py` | |
| 5 | Ploché názvy výstupních souborů | `cli.py` | |
| 6 | Apps Script — normalizace + slití do `Transakce` | Sheets | potřebuje 4 a 5 |
| 7 | SUMIFS mřížka + kontrolní řádky | Sheets | potřebuje 3 a 6 |

Kroky 1, 3, 4, 5 jsou v tomto repu. Krok 2 potřebuje klienta.
Kroky 6 a 7 se dělají až v Google Sheets — Apps Script půjde dodat jako
text k vložení do `Rozšíření → Apps Script`.

---

## Poznámky k dohledání

- `Šremer` → řádek 26 „Nájem Vlhká Honza"? Neověřeno, jen odhad podle názvu.
- `Prostory` — kam patří ve formuláři? (`Premier` vyřešeno → P8 "PLUS zvláštní příjem | Služby PremierHost"; `Rezervní 1` viz sekce 3c — částečně vyřešeno, případ "Převod na auto" otevřený; `Spilberk` přejmenováno na `C79` → N30 "Nájem Fond - A24-A83 včetně energií", vyřešeno)
- Ověřit, jestli rozbité vzorce (4.4) jsou i v ostatních 11 měsících.
- `Kauce` — vyřešeno: do formuláře nepatří, viz `docs/otazky-pro-klienta.md` bod 5.
