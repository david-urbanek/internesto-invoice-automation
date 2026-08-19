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

## 2. `V24` — řádek 31? Podezření na kolizi jako u `Booking`/`Premier`

Řádek 31 se doslova jmenuje "Nájem Fond - Vlhká 24 včetně energií" (nájem),
ale kategorie `V24` v `config.py` je popsaná jako "Vybavení a rekonstrukce
jednotky V24 – nábytek/dekorace" (dodavatelé JYSK, IKEA, Mobelix, Alza) —
to je nákup nábytku, ne nájem.

1. Existuje pro nájem Vlhká 24 vůbec samostatná kategorie ve skriptu (jako
   `V19`, `Kotlářská`, `Šremer` mají svoje), nebo se dosud kategorizovalo
   špatně/vůbec?
2. Kam má jít nákup nábytku (dnešní `V24`) — nový řádek, nebo pod `N63`
   "Drobný majetek + dekorace + opravy + lékárna" (tam by svým obsahem
   sedělo líp)?

## 3. `Výdaj Premier` (fond) — kam patří ve formuláři, pokud vůbec?

Skript zná (protiúčet `2203097403`, interní přesun do Premier Fondu),
formulář na to nemá řádek.

## 4. `Spilberk`, `Prostory` — kam patří ve formuláři?

Obě kategorie skript zná (mezifiremní fakturace Spilberk/Cejl 79, nájem
prostor Nesty), formulář na ně nemá řádek.

## 5. `Kauce` — má se ve formuláři vůbec objevit?

Nebo je to průběžná položka mimo formulář (vratná kauce hosta, ne skutečný
příjem/výdaj firmy)?

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

## 10. `Příjem energie` — chybí mu řádek

Ve viditelných příjmových řádcích (2–18) není nic se slovem "energie".
Kam patří (nejbližší kandidát: `P16` "Ostatní příjmy")?

