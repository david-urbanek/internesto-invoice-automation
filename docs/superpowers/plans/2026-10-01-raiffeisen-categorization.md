# Raiffeisen Categorization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deterministically categorize the supplied PriceLabs, interest, loan, transfer, and Pokladna-cleaning transactions while retaining their allocation-form mappings.

**Architecture:** Extend the existing declarative configuration dictionaries rather than adding a Raiffeisen-specific classifier. Deterministic text markers classify exact interest descriptions before ambiguous counter-account rules; the fixed-supplier rewrite classifies PriceLabs merchant text after initial categorization; the existing Pokladna-only name rewrite supplies the new cleaning staff scope.

**Tech Stack:** Python 3.12, unittest, existing `kategorizace` package.

## Global Constraints

- Keep categorization data declarative in `src/kategorizace/config.py`.
- PriceLabs merchant text must categorize as `Previo systém` and map to `N45`.
- Exact descriptions `Úrok z úvěru` and `Úrok z nevyčerpaného úvěru` must categorize as `Úrok` and map to `N49`.
- `nemcova` and `hoskova` must produce `Úklid` only when `firma_nazev == "Pokladna"`.
- Existing `Převod`, `A43`, and `B53` account/contract rules remain unchanged.

---

### Task 1: Add failing categorization-contract tests

**Files:**
- Modify: `tests/test_typy_transakci.py`

**Interfaces:**
- Consumes: `aplikuj_deterministickou_kategorizaci(transakce, omezene_kategorie=None) -> list[dict]`.
- Consumes: `aplikuj_vzdy_dodavatel(transakce, omezene_kategorie=None) -> list[dict]` and `aplikuj_jmena_pokladna(transakce, firma_nazev) -> list[dict]`.
- Consumes: `MAPOVANI_NA_FORMULAR: dict[str, str | dict | None]`.
- Produces: regression tests for all supplied rule signatures.

- [ ] **Step 1: Add imports and deterministic-rule tests**

```python
from kategorizace.config import MAPOVANI_NA_FORMULAR
from kategorizace.prepisy import aplikuj_jmena_pokladna, aplikuj_vzdy_dodavatel


def test_raiffeisen_interest_descriptions_are_deterministic(self):
    rows = [
        {"Název protiúčtu": "Úrok z úvěru"},
        {"Název protiúčtu": "Úrok z nevyčerpaného úvěru"},
    ]

    result = aplikuj_deterministickou_kategorizaci(rows)

    self.assertEqual([row["Kategorie"] for row in result], ["Úrok", "Úrok"])
    self.assertEqual(MAPOVANI_NA_FORMULAR["Úrok"], "N49")
```

Add equivalent tests where the counter-account and transaction text identify `3699/24/021` as `B53`, `1694/25/021` as `A43`, and `2200973033/2010` as `Převod`. Assert `MAPOVANI_NA_FORMULAR["Previo systém"] == "N45"`.

- [ ] **Step 2: Add failing PriceLabs and Pokladna-scope tests**

```python
def test_pricelabs_merchant_is_previo_system(self):
    rows = [{"Název protiúčtu": "PRICELABSINC*DYNAPRICE"}]

    result = aplikuj_vzdy_dodavatel(rows)

    self.assertEqual(result[0]["Kategorie"], "Previo systém")


def test_new_cleaning_people_apply_only_to_pokladna(self):
    pokladna = [{"Poznámka": "Výplata Němcová Tereza"}]
    banka = [{"Poznámka": "Výplata Hošková Eva"}]

    aplikuj_jmena_pokladna(pokladna, "Pokladna")
    aplikuj_jmena_pokladna(banka, "RD Group s.r.o.")

    self.assertEqual(pokladna[0]["Kategorie"], "Úklid")
    self.assertIsNone(banka[0].get("Kategorie"))
```

- [ ] **Step 3: Run the targeted tests and confirm the new assertions fail**

Run: `python -m unittest tests.test_typy_transakci -v`

Expected: failures for unconfigured PriceLabs, interest markers, and new names.

### Task 2: Extend declarative categorization configuration

**Files:**
- Modify: `src/kategorizace/config.py:870-876`
- Modify: `src/kategorizace/config.py:900-907`
- Modify: `src/kategorizace/config.py:932-939`

**Interfaces:**
- Consumes: `POKLADNA_JMENA_KATEGORIE`, normalized by `aplikuj_jmena_pokladna`.
- Consumes: `VZDY_TEXT_KATEGORIE`, scanned in insertion order by `aplikuj_deterministickou_kategorizaci`.
- Consumes: `VZDY_DODAVATEL_KATEGORIE`, scanned by `aplikuj_vzdy_dodavatel`.
- Produces: category configuration for the new rule signatures; no API changes.

- [ ] **Step 1: Add exact markers and names**

```python
POKLADNA_JMENA_KATEGORIE: dict[str, str] = {
    "vendula": "Úklid",
    "venda": "Úklid",
    "vendy": "Úklid",
    "iva": "Úklid",
    "nemcova": "Úklid",
    "hoskova": "Úklid",
    "petr": "Recepční",
}

VZDY_TEXT_KATEGORIE: dict[str, str] = {
    "úrok z nevyčerpaného úvěru": "Úrok",
    "úrok z úvěru": "Úrok",
    "361020403": "A43",
    "1694/25/021": "A43",
    "361010303": "B53",
    "3699/24/021": "B53",
    "comgate": "Převod",
    "dobr0": "Vratka",
}

VZDY_DODAVATEL_KATEGORIE: dict[str, str] = {
    "pricelabsinc*dynaprice": "Previo systém",
    "alza": "Dekorace",
    "silmet": "Benzín",
    "zerogas": "Benzín",
    "nestle": "Dekorace",
}
```

Do not change `MAPOVANI_NA_FORMULAR`, loan-account declarations, or existing transfer/account mappings: they already represent the approved allocation and categories.

- [ ] **Step 2: Run focused tests and verify they pass**

Run: `python -m unittest tests.test_typy_transakci -v`

Expected: all tests pass, including the new deterministic category and scope assertions.

- [ ] **Step 3: Commit the implementation**

```bash
git add src/kategorizace/config.py tests/test_typy_transakci.py
git commit -m "feat: add Raiffeisen categorization rules"
```

### Task 3: Exercise the complete supplied-rule flow

**Files:**
- Modify: `tests/test_typy_transakci.py`

**Interfaces:**
- Consumes: category configuration and the three existing categorization/rewrite functions.
- Produces: an end-to-end in-memory regression test for each supplied signature.

- [ ] **Step 1: Add an integration-style transaction fixture**

```python
def test_supplied_transaction_signatures_keep_their_categories(self):
    deterministic_rows = [
        {"Číslo protiúčtu": "2200973033/2010", "Objem": "-80000"},
        {"Název protiúčtu": "771619 INKASO 3699/24/021/SME/PRP"},
        {"Název protiúčtu": "772022 INKASO 1694/25/021/SME/PRP"},
    ]

    result = aplikuj_deterministickou_kategorizaci(deterministic_rows)

    self.assertEqual([row["Kategorie"] for row in result], ["Převod", "B53", "A43"])
```

Keep the PriceLabs, interest, and Pokladna fixtures in their appropriate functions, because their real pipeline phases differ.

- [ ] **Step 2: Run the complete targeted suite**

Run: `python -m unittest tests.test_typy_transakci -v`

Expected: all existing and newly added tests pass.

- [ ] **Step 3: Commit verification coverage**

```bash
git add tests/test_typy_transakci.py
git commit -m "test: cover Raiffeisen categorization signatures"
```
