# Otázky pro klienta — mapování kategorií na Alokační formulář

Vzešlo z rozhodovací session nad `napojeni-na-alokacni-formular.md` a
`navrh-mapovani-kategorii-na-formular.md`. Technické detaily/rozhodnutí,
která už padla, jsou v `navrh-mapovani-kategorii-na-formular.md` — tady je
jen to, co musí potvrdit nebo rozhodnout klient.

---

## 1. `A43` — řádek 28, nebo 32?

Ověřeno přímo v `.xlsx` na všech čtyřech listech:

| List | Řádek 28 | Řádek 32 |
|---|---|---|
| RD | "Nájem Gábi - A63 a **A73** včetně energií a DPH" | "Nájem (splátka) - B53 + **A43**..." |
| Nesty, Casa, Pokladna | "Nájem Gábi - **A43** a A63 včetně energií" | "Nájem (splátka) - B53 + **A43**..." |

Na listu RD je na řádku 28 "A73" místo "A43", a A43 je navíc na všech
čtyřech listech i na řádku 32. Je to překlep na listu RD, nebo A43
skutečně patří na obě místa (a jak se to pak nemá sečíst dvakrát)?

## 2. `V24` — vyřešeno, mapuje na N31 (⚠️ obsahový nesoulad zůstává)

Rozhodnutí uživatele (08/2026): kategorie `V24` míří na řádek 31 „Nájem
Fond - Vlhká 24 včetně energií" (`config.py`, `MAPOVANI_NA_FORMULAR["V24"] = "N31"`).

⚠️ Riziko ponechané vědomě otevřené: popis kategorie `V24` v `config.py`
(`KATEGORIE`) zní na nábytek/dekoraci (dodavatelé JYSK, IKEA, Mobelix,
Alza), ne na nájem. Deterministická pravidla i AI budou dál řadit nákupy
nábytku do `V24`, a ty teď poputují na řádek 31 „Nájem" místo výdajového
řádku za vybavení. Pokud je to nechtěné, potřeba buď přejmenovat/rozdělit
kategorii, nebo řádek 31 opravdu obsahuje i vybavení jednotky (ověřit
u klienta, co přesně řádek 31 sčítá).

## 3. `Výdaj Premier` (fond) — kam patří ve formuláři, pokud vůbec?

Skript zná (protiúčet `2203097403`, interní přesun do Premier Fondu),
formulář na to nemá řádek.

## 4. `Prostory` — kam patří ve formuláři?

Skript zná kategorii (nájem prostor Nesty), formulář na ni nemá řádek.

✅ Vyřešeno: `Spilberk` přejmenováno na `C79`, namapováno na `N30`
„Nájem Fond - A24-A83 včetně energií" (rozhodnutí uživatele, 08/2026).

## 5. `Kauce` — má se ve formuláři vůbec objevit?

✅ Vyřešeno: ne, `Kauce` do formuláře nepatří (`MAPOVANI_NA_FORMULAR["Kauce"] = None`)
— je to vratná kauce hosta, ne skutečný příjem/výdaj firmy (rozhodnutí
uživatele, 08/2026).

## 6. "Převod na auto" (nalezeno v `Rezervní 1`)

Ojedinělá transakce v datech, nesedí do žádné z rozpadlých kategorií
`Parkování`/`Popelnice`/`Ubytovací poplatky`. Kam patří?

## 7. Kde běží ostrá verze Sheets a kdo v ní pracuje?

Nutné vědět před nasazením Apps Scriptu, aby se nezačalo upravovat
odpojenou kopii `.xlsx` v repu místo živého souboru na Drive.

## 8. `Pojištění` → `N48` (auto) potvrzeno, nemovitost chybí

Vyřešeno: ověřeno v eval datasetu, všech 19 historických výskytů má
protiúčet `4503502` a štítek "Pojištění Taigo"/"Pojištění Arteon" (auta) —
kategorie tedy míří na `N48` "Pojištění auto". Druhý deklarovaný protiúčet
v configu (`40002-50404011`, možná nemovitostní pojistka) se v 5 měsících
dat ani jednou neobjevil. Otázka: platí se pojištění nemovitosti vůbec
z účtu, který skript vidí? Pokud ano, bude potřeba nová kategorie — pozor,
řádek 34 "Pojištění nemovitosti" je sloučený s řádkem 33 (`N33`), takže by
nová kategorie musela mířit tam, ne na vlastní řádek.

## 9. `Splátka` → N42 "Splátky Moneta", ale co N43 "Splátky Raiffeisen"?

Kategorie `Splátka` deklaruje jen tři protiúčty (RD Group, Casa Libre,
Nesty Services), všechny vypadají jako Moneta. Nenašel jsem žádnou
kategorii, která by jasně patřila na řádek 43 "Splátky Raiffeisen" —
nejbližší kandidát (`B53`/`Úrok`, oba na účtu `6430097786` u
Raiffeisenbank) už je mapovaný jinam (N32, resp. N49). Existuje samostatná
raiffeisenská splátka jistiny, kterou skript zatím nerozezná?

## 10. `Příjem energie` — vyřešeno

Rozhodnutí uživatele (08/2026): `Příjem energie` patří na `P16`
"Ostatní příjmy" (`config.py`, `MAPOVANI_NA_FORMULAR`).

