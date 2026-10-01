# Raiffeisen categorization rules

## Goal

Classify the supplied RD Group transactions deterministically, preserve their allocation-form mappings, and recognize the two new Pokladna cleaning staff.

## Rules

- Text containing `PRICELABSINC*DYNAPRICE` is always `Previo systém`; its existing allocation mapping is `N45`.
- The exact Raiffeisen descriptions `Úrok z úvěru` and `Úrok z nevyčerpaného úvěru` are `Úrok`; its existing allocation mapping is `N49`.
- On Pokladna only, normalized whole-word names `nemcova` and `hoskova` are `Úklid`, alongside the existing cleaning staff names.
- Existing declarative account and text rules remain the source of truth for the other supplied transactions:
  - `2200973033` internal transfers are `Převod`.
  - contract marker `3699/24/021` is `B53`.
  - contract marker `1694/25/021` is `A43`.
  - the listed transfers therefore remain `Převod`.

## Design

Rules stay in the existing configuration dictionaries. PriceLabs uses the fixed-supplier rewrite, because card transaction merchant text is available only after the initial classification path. Interest descriptions use deterministic text markers, which run before account classification and prevent ambiguity caused by shared Raiffeisen loan accounts. The people map retains its existing Pokladna-only guard and normalized whole-word matching.

No account-wide Raiffeisen classifier or date/amount-specific exception is introduced.

## Verification

Add focused tests that assert category assignment for PriceLabs, both interest descriptions, the two loan-contract markers, the internal transfer account, and that the new people change a Pokladna transaction to `Úklid` but do not affect a non-Pokladna transaction. Assert the existing allocation mappings for `Previo systém` and `Úrok`.
