# Návrh mapování kategorií na formulář — k odsouhlasení s klientem

Vzniklo z rozhodovací session nad `napojeni-na-alokacni-formular.md`. Tohle
jsou konkrétní návrhy nových/přejmenovaných kategorií a jejich cílových
řádků formuláře. **Nic z tohohle není zavedené v kódu** — čeká to na tvoje
schválení, případně na probrání s klientem u bodů označených ⚠️.

ID řádků: `P<číslo>` = příjmový řádek (2–18), `N<číslo>` = výdajový řádek
(19–72). Číslo je původní pozice řádku ve formuláři `RD` (ostatní 3 listy
mají stejnou strukturu).

---

## 1. Přejmenování kolidujících kategorií

Dvě jména už v `config.py` existují jako **výdajové/interní** kategorie,
ale ve výpisech se stejné slovo objevuje i na **příjmové** straně
v jiném významu. Aby se to nepletlo, obě přejmenováváme a přidáváme nový
příjmový protějšek:

| Původní jméno | Nové jméno (výdaj) | Nová kategorie (příjem) | Poznámka |
|---|---|---|---|
| `Booking` (`config.py:261`, protiúčet `4030400003`) | `Výdaj Booking` | `Příjem Booking` | provize (výdaj) vs. tržba (příjem) — different protiúčty |
| `Premier` (`config.py:517`, protiúčet `2203097403`) | `Výdaj Premier` | `Příjem Premier` | převod do Premier Fondu (výdaj) vs. služby PremierHost (příjem, protiúčet `2401715997`) |

Historické štítkování zůstává funkční přes `ALIASY["Booking"] = "Výdaj Booking"`
(ověřeno proti `scratch_dataset.json` — historicky se `Booking` nikdy nepoužil
pro příjmovou transakci, takže alias nic nerozbije).

---

## 2. Nové příjmové kategorie (`KATEGORIE_PRIJMOVE`)

| Kategorie | Rozlišovací signál | Cílový řádek |
|---|---|---|
| `Příjem Booking` | protiúčty `2550840118` (Booking.com přímo), `55550309` (Global Payments), `115-1391640287` (GoPay) | **P3** „Platební terminál" |
| `Ostatní ubytování/služby` (CZK) | protiúčty typu Melvil (`7323607001`), Apartino (`276654216`), UCEEB — přímé platby CZ institucí za ubytování mimo OTA kanály | **P4** |
| `Ostatní ubytování EUR` | zahraniční platby (SK/jiné IBAN) na EUR účet firmy, rozhoduje klíčové slovo "Ubytování" — protiúčet se neopakuje, plátci jsou různí (např. zahraniční školy) | **P6** |
| `Ostatní příjmy` | drobné příchozí refundace od dodavatelů (např. Alza, protiúčet `2531920104`) | **P16** |
| `Příjem Premier` | protiúčet `2401715997` (Tomáš, "Příjmový Vlhká 9") | **P8** „PLUS zvláštní příjem \| Služby PremierHost" |

Plus stávající `Airbnb` a `Příjem energie` zůstávají beze změny (řádky
P2, resp. bez explicitního řádku v seznamu — ověřit přesné číslo).

---

## 3. Rozpad `Rezervní 1`

Stávající kategorie `Rezervní 1` (`config.py:524`, protiúčet `2402351507`
+ dva vedlejší protiúčty) mísí tři různé účely. Navrhujeme rozdělit na
čtyři kategorie:

| Nová kategorie | Rozlišovací signál | Cílový řádek |
|---|---|---|
| `Parkování` | protiúčet `2402351507` + klíčové slovo „parkování" | **N33** „Parkování" |
| `Popelnice` | protiúčet `2402351507` + klíčové slovo „popelnice", dodavatel `FCC` | **N61** „Popelnice" |
| `Ubytovací poplatky` | protiúčty `43-8206670217`, `115-9579990277` (vždy) NEBO `2402351507` + klíčové slovo „ubytovací"/„kapacity" | **N37** „Ubytovací a rekreační poplatky" |
| `Rezervní 1` (ponecháno jako zbytek) | protiúčet `2402351507`, nesedí žádné klíčové slovo výše | **žádný** — spadne do `N00` (nenamapováno), viditelně v kontrolním řádku |

⚠️ **Otevřeno:** v historii je i transakce "Převod na auto" z tohohle účtu,
která nesedí do žádné ze tří adresných kategorií. Zatím spadne do zbytkové
`Rezervní 1` → `N00`. Je to v pořádku, nebo to má vlastní řádek/kategorii?

---

## 4. Poplatkový uzel (dřív "nejhorší uzel" dokumentu)

| Kategorie | Cílový řádek |
|---|---|
| `Poplatek` (pokuty, ATM poplatky) | **N38** „Ostatní poplatky + DPPO + Havárie + Popelnice" |
| `Úrok` (bankovní úrok z úvěru, Raiffeisen) | **N49** „Jiné poplatky + úroky" |
| `Banka` (hotovostní odvod/vklad pokladna↔banka) | **žádný** — `None`, jde mimo formulář stejně jako `Převod` |

---

## 5. Nové jméno pro sloučený seznam kategorií

`KATEGORIE_PRIJMY_A_MAJITEL` → rozdělit na dvě čistá jména:

- `KATEGORIE` (výdajové) — beze změny, jen přibydou `Výdaje majitele` a `Benzín` (přesun z původního smíšeného seznamu)
- `KATEGORIE_PRIJMOVE` (nová) — jen skutečně příjmové: `Airbnb`, `Příjem energie`, `Příjem Booking`, `Ostatní ubytování/služby`, `Ostatní ubytování EUR`, `Ostatní příjmy`, `Příjem Premier`

Hlavička AI promptu (`ai.py:281`) se přejmenuje z "Firemní výdaje a interní
převody" na obecnější "Výdajové kategorie", protože `Výdaje majitele` není
firemní výdaj.

---

## 6. Vyřešeno v této session (bez zásahu klienta)

- ✅ **`Reprezentace` → N35.** Ověřeno v `.xlsx`: řádek 35 se doslova jmenuje
  "Vzdělávání + reprezentace" — je to jeden spojený řádek, ne konflikt 1:N.
- ✅ **`Šremer` → N26**, firma **RD** (výhradně na `RD Výdajový 1.xlsx`,
  10/10 nalezených transakcí v eval datasetu). Řádek 26 se doslova jmenuje
  "Nájem - Vlhká Honza včetně energie" — "Honza" je zdrobnělina "Jan",
  sedí na "Jan Šremer".

## 7. Otevřené otázky pro klienta

Přesunuto do samostatného souboru `docs/otazky-pro-klienta.md` (jen to,
co musí rozhodnout/potvrdit klient, odděleně od technického návrhu výše).
