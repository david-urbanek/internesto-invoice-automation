# Internesto Invoice Automation

Kategorizace bankovních transakcí pomocí Gemini AI.

## Požadavky

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Google API klíč s přístupem ke Gemini

## Instalace

```bash
uv sync
```

## Konfigurace

Vytvoř `.env` soubor v kořeni projektu:

```
GOOGLE_API_KEY=tvuj_klic
```

## Struktura složek

Každá firma musí mít tuto strukturu:

```
firmy/
  NazevFirmy/
    transactions/     ← CSV výpisy z banky (jeden soubor = jeden výpis)
    invoices/         ← faktury (PDF, PNG, JPG, ...)
    results/          ← výsledné CSV (generuje se automaticky)
```

## Spuštění

```bash
# Kategorizace transakcí
uv run kategorizace

# Zobrazení dostupných kategorií
uv run konfigurace
```

## Co se děje při spuštění

1. **Indexování faktur** — Gemini přečte každou fakturu a uloží metadata (dodavatel, částka, datum, VS, číslo účtu) do `.index.json` ve složce `invoices/`. Faktury, které se nezměnily, se znovu nezpracovávají.
2. **Deterministické předpárování** — transakce s jasnou shodou (VS nebo číslo účtu + částka) se spárují s fakturami bez AI.
3. **Kategorizace** — Gemini dostane tabulku transakcí + přehled faktur z indexu a ke každé transakci přiřadí kategorii, fakturu a skóre jistoty.
4. **Výsledky** — uloží se do `firmy/NazevFirmy/results/` jako CSV.

## Přidání nové firmy

1. Vytvoř složku `firmy/NazevFirmy/`
2. Přidej podsložky `transactions/` a `invoices/`
3. Vlož CSV výpisy a faktury
4. Spusť `uv run kategorizace`

## Úprava kategorií

Kategorie, aliasy a firemní účty jsou definovány v `src/kategorizace/config.py`.
