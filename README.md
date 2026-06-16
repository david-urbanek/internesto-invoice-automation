# Internesto Invoice Automation

Nástroj pro automatickou kategorizaci bankovních transakcí pomocí Gemini AI. Načte CSV výpisy z Fio banky, přiřadí ke každé transakci účetní kategorii a spáruje ji s fakturou ze složky `invoices/`.

## Co to umí

- **Kategorizace transakcí** — Gemini přečte výpis z banky a ke každé transakci přiřadí kategorii (Úklid, Booking, Nájem, DPH, Převod…), skóre jistoty 0–100 a poznámku
- **Párování faktur** — deterministicky spáruje transakce s fakturami přes VS nebo číslo účtu + částku; pro zbytek se ptá AI
- **Indexování faktur** — při prvním spuštění Gemini přečte každou fakturu (PDF/PNG/JPG) a uloží metadata do `.index.json`; při dalším spuštění přečte jen nové nebo změněné soubory
- **Report chybějících faktur** — samostatný příkaz ukáže transakce, kde fakturu nenašel a kde ji podle kategorie očekáváme
- **Přehled kategorií** — příkaz pro výpis všech definovaných kategorií a jejich popisů

## Požadavky

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) — správce prostředí a závislostí
- Google API klíč s přístupem ke Gemini 2.5 Flash

## Setup od nuly

### 1. Nainstaluj závislosti

```bash
uv sync
```

### 2. Nastav API klíč

Zkopíruj `.env.example` a doplň svůj klíč:

```bash
cp .env.example .env
```

```
GOOGLE_API_KEY=tvuj_klic
```

Klíč získáš na [aistudio.google.com](https://aistudio.google.com/) → Get API key.

### 3. Připrav strukturu složek

Pro každou firmu vytvoř tuto strukturu pod `firmy/`:

```
firmy/
  NazevFirmy/
    transactions/     ← CSV výpisy z banky (Fio: Účty → Export)
    invoices/         ← faktury jako PDF, PNG nebo JPG
    results/          ← sem se ukládají výsledky (generuje se automaticky)
```

Příklad pro více firem:

```
firmy/
  RD/
    transactions/
      Vypis_z_uctu-2901813198_20260101-20260131.csv
    invoices/
      faktura-001.pdf
      faktura-002.jpg
    results/
  Nesty/
    transactions/
      ...
    invoices/
      ...
```

### 4. Spusť kategorizaci

```bash
uv run kategorizace
```

## Příkazy

| Příkaz | Co dělá |
|---|---|
| `uv run kategorizace` | Spustí kategorizaci všech firem a uloží výsledky do `results/` |
| `uv run report` | Zobrazí transakce bez spárované faktury (kde se faktura očekává) |
| `uv run konfigurace` | Vypíše tabulku všech kategorií s popisem a typickými dodavateli |

## Co se děje při spuštění kategorizace

1. **Indexování faktur** — Gemini přečte každou fakturu ze složky `invoices/` a extrahuje dodavatele, částku, datum, variabilní symbol a čísla účtů. Výsledek uloží do `.index.json` ve složce `invoices/`. Faktury, které se nezměnily, se příště přeskočí.

2. **Deterministické předpárování** — transakce s jednoznačnou shodou (VS, nebo číslo účtu + přesná částka) se spárují s fakturami bez AI. Tato přiřazení Gemini nemůže přepsat.

3. **Kategorizace přes Gemini** — pro každý CSV výpis odešle Gemini tabulku transakcí + přehled faktur z indexu + seznam kategorií. Ke každé transakci vrátí: kategorii, název souboru faktury, skóre jistoty (0–100) a poznámku.

4. **Uložení výsledků** — výsledné CSV se uloží do `firmy/NazevFirmy/results/` se stejným názvem jako vstupní soubor.

## Výstupní CSV

Výsledný soubor obsahuje všechny původní sloupce z bankovního výpisu a navíc:

| Sloupec | Popis |
|---|---|
| `Kategorie` | Přiřazená účetní kategorie |
| `Faktura` | Název souboru faktury nebo `NENALEZENO` |
| `Poznamka` | Vysvětlení kategorizace od AI |
| `Jistota` | Skóre 0–100 (100 = absolutně jisté) |

## Kategorie a konfigurace

Všechny kategorie, aliasy a čísla firemních účtů jsou v `src/kategorizace/config.py`. Každá kategorie má:
- `nazev` — název použitý ve výstupu
- `popis` — popis pro AI
- `dodavatele` — typická jména protistrany
- `protiucty` — čísla bankovních účtů dodavatele
- `klicova_slova` — text hledaný v popisu nebo zprávě

Kategorie bez faktury (mzdy, odvody, nájmy dle smlouvy, interní převody) jsou v seznamu `KATEGORIE_BEZ_FAKTURY` a nezobrazují se v reportu chybějících faktur.

## Přidání nové firmy

1. Vytvoř složku `firmy/NazevFirmy/`
2. Přidej podsložky `transactions/` a `invoices/`
3. Vlož CSV výpisy a faktury
4. Spusť `uv run kategorizace`
