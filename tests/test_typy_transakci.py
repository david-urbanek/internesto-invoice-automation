from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from openpyxl import Workbook

from kategorizace.ai import kategorizuj_transakce
from kategorizace.config import KATEGORIE, KATEGORIE_PRIJMOVE, MAPOVANI_NA_FORMULAR
from kategorizace.deterministika import aplikuj_deterministickou_kategorizaci
from kategorizace.io import nacti_xlsx
from kategorizace.prepisy import (
    aplikuj_interni_prevod,
    aplikuj_jmena_pokladna,
    aplikuj_prostory_nesty_prijmovy,
    aplikuj_vzdy_dodavatel,
)


class _FakeClient:
    class _Models:
        @staticmethod
        def generate_content(**_kwargs):
            return SimpleNamespace(parsed=SimpleNamespace(transakce=[]), candidates=[])

    models = _Models()


class TransactionValueTypeTests(unittest.TestCase):
    def test_xlsx_transaction_values_are_normalized_to_text(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "vypis.xlsx"
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.append(["Datum", "Objem", "Protiúčet", "Poznámka"])
            worksheet.append([datetime(2026, 4, 1), 123.45, 2601813209, None])
            workbook.save(path)

            row = nacti_xlsx(str(path))[0]

        self.assertEqual(row["Datum"], "2026-04-01 00:00:00")
        self.assertEqual(row["Objem"], "123.45")
        self.assertEqual(row["Protiúčet"], "2601813209")
        self.assertEqual(row["Poznámka"], "")

    def test_deterministic_categorization_accepts_numeric_account(self):
        rows = [{"Protiúčet": 2601813209, "Poznámka": None}]

        result = aplikuj_deterministickou_kategorizaci(rows)

        self.assertEqual(len(result), 1)

    def test_ai_prompt_accepts_missing_transaction_fields(self):
        rows = [
            {
                "Datum": None,
                "Objem": None,
                "Číslo protiúčtu": None,
                "Název protiúčtu": None,
                "Poznámka": None,
                "Zpráva pro příjemce": None,
                "VS": None,
            }
        ]

        result = kategorizuj_transakce(rows, [], _FakeClient())

        self.assertEqual(result[0]["Kategorie"], "Neurčeno")
        self.assertEqual(result[0]["Faktura"], "NENALEZENO")

    def test_xlsx_missing_values_are_empty_strings_in_pipeline(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "vypis.xlsx"
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.append(["Poznámka", "VS", "Název protiúčtu"])
            worksheet.append(["poznámka", None, None])
            workbook.save(path)

            row = nacti_xlsx(str(path))[0]

        self.assertEqual(row["Poznámka"], "poznámka")
        self.assertEqual(row["VS"], "")
        self.assertEqual(row["Název protiúčtu"], "")

    def test_raiffeisen_interest_descriptions_are_deterministic(self):
        # Raiffeisen dává popis do sloupce "Typ transakce" (ne "Poznámka"),
        # takže marker "úrok z úvěru" musí hledat i tam. Regrese z 10/2026:
        # dřív se pole neprohledávalo a úroky končily jako "Neurčeno".
        rows = [
            {"Typ transakce": "Úrok z úvěru", "Poznámka": "Úrok 09/2026"},
            {"Typ transakce": "Úrok z nevyčerpaného úvěru", "Poznámka": "Úrok 09/2026"},
        ]

        result = aplikuj_deterministickou_kategorizaci(rows)

        self.assertEqual([row.get("Kategorie") for row in result], ["Úrok", "Úrok"])
        self.assertEqual([row.get("Jistota kategorie") for row in result], [100, 100])
        self.assertEqual(MAPOVANI_NA_FORMULAR["Úrok"], "N49")

    def test_text_markers_respect_account_restriction(self):
        # Marker se nesmí vnutit, když kategorie není v povoleném seznamu účtu:
        # jinak by "comgate" (±1 Kč identifikace → Převod) přebil velké Booking
        # výplaty přes Comgate na příjmovém účtu. Takový řádek jde do AI.
        prijmove = [k["nazev"] for k in KATEGORIE_PRIJMOVE]
        self.assertNotIn("Převod", prijmove)
        rows = [{"Poznámka": "Comgate a.s.", "Objem": "115865,58"}]

        aplikuj_deterministickou_kategorizaci(rows, omezene_kategorie=prijmove)

        self.assertIsNone(rows[0].get("Kategorie"))

    def test_prostory_nesty_requires_rd_account_and_prostor_text(self):
        # "Prostory Příjem" jen na Nesty Příjmový a jen když je protiúčet z RD
        # A text zmiňuje "prostor". RD protiúčet bez textu = běžný převod;
        # "prostor" od externího hosta (jiný protiúčet) = ubytování.
        rows = [
            {"Protiúčet": "2901813198", "Objem": "24200",
             "Zpráva pro příjemce": "Nájem - prostor sloužící podnikání", "Kategorie": "Převod"},
            {"Protiúčet": "2200973033", "Objem": "115920",
             "Zpráva pro příjemce": "", "Kategorie": "Převod"},
            {"Protiúčet": "123-9105550237", "Objem": "14116",
             "Zpráva pro příjemce": "Pronajem prostor", "Kategorie": "Ostatní ubytování CZK"},
            {"Protiúčet": "2901813198", "Objem": "-5000",
             "Zpráva pro příjemce": "prostor", "Kategorie": "Převod"},
        ]

        aplikuj_prostory_nesty_prijmovy(rows, "09-2026-nesty-prijmovy-1.xlsx", "Nesty")

        self.assertEqual(
            [r["Kategorie"] for r in rows],
            ["Prostory Příjem", "Převod", "Ostatní ubytování CZK", "Převod"],
        )
        self.assertEqual(MAPOVANI_NA_FORMULAR["Prostory Příjem"], "P4")

    def test_prostory_nesty_skips_other_accounts(self):
        rows = [{"Protiúčet": "2901813198", "Objem": "24200",
                 "Zpráva pro příjemce": "prostor", "Kategorie": "Převod"}]
        aplikuj_prostory_nesty_prijmovy(rows, "09-2026-nesty-vydajovy-1.xlsx", "Nesty")
        self.assertEqual(rows[0]["Kategorie"], "Převod")

    def test_pricelabs_merchant_has_own_category_and_row(self):
        result = aplikuj_vzdy_dodavatel(
            [{"Název protiúčtu": "PRICELABSINC*DYNAPRICE"}]
        )

        self.assertEqual(result[0].get("Kategorie"), "Pricelabs")
        self.assertEqual(MAPOVANI_NA_FORMULAR["Pricelabs"], "N74")

    def test_split_service_vendors_have_own_category_and_row(self):
        # Daktela/Appsatori/BE-A dostaly 10/2026 vlastní kategorii i řádek
        # místo sběrného "Ostatní služby"/nenamapováno. Protiúčet je
        # deterministický signál, štítek jen potvrzuje.
        cases = [
            ("2078745001", "Daktela", "N75"),
            ("20356362", "Appsatori", "N76"),
            ("12173742", "BE-A", "N77"),
        ]
        for protiucet, kategorie, radek in cases:
            with self.subTest(kategorie=kategorie):
                rows = [{"Číslo protiúčtu": protiucet, "Poznámka": ""}]
                aplikuj_deterministickou_kategorizaci(rows)
                self.assertEqual(rows[0].get("Kategorie"), kategorie)
                self.assertEqual(MAPOVANI_NA_FORMULAR[kategorie], radek)

    def test_daktela_removed_from_ostatni_sluzby(self):
        # Protiúčet Daktely se nesmí zároveň hlásit k "Ostatní služby",
        # jinak by deterministika měla dvě kategorie a signál by zahodila.
        ostatni = next(k for k in KATEGORIE if k["nazev"] == "Ostatní služby")
        self.assertNotIn("2078745001", ostatni.get("protiucty", []))
        self.assertNotIn("Daktela", ostatni.get("dodavatele", []))

    def test_new_cleaning_people_apply_only_to_pokladna(self):
        pokladna = [
            {"Poznámka": "Výplata Němcová Tereza"},
            {"Poznámka": "Výplata Hošková Eva"},
        ]
        banka = [{"Poznámka": "Výplata Hošková Eva"}]

        aplikuj_jmena_pokladna(pokladna, "Pokladna")
        aplikuj_jmena_pokladna(banka, "RD Group s.r.o.")

        self.assertEqual(
            [row.get("Kategorie") for row in pokladna],
            ["Úklid", "Úklid"],
        )
        self.assertIsNone(banka[0].get("Kategorie"))

    def test_supplied_raiffeisen_signatures_keep_existing_categories(self):
        rows = [
            {"Číslo protiúčtu": "2200973033/2010", "Objem": "-80000"},
            {"Název protiúčtu": "771619 INKASO 3699/24/021/SME/PRP"},
            {"Název protiúčtu": "772022 INKASO 1694/25/021/SME/PRP"},
        ]

        result = aplikuj_deterministickou_kategorizaci(rows)

        self.assertEqual(
            [row.get("Kategorie") for row in result],
            ["Převod", "B53", "A43"],
        )

    def test_internal_transfer_with_bank_code_on_income_statement(self):
        # Příjmový výpis: uzavřený seznam kategorií neobsahuje "Převod", takže
        # deterministika ani AI ho přiřadit nesmí – interní převod na firemní
        # účet musí dorovnat až aplikuj_interni_prevod. Na Raiffeisen výpisu
        # má protiúčet příponu "/kód banky"; override ji musí normalizovat,
        # jinak řádek zůstane "Neurčeno" (regrese z 10/2026).
        prijmove = [k["nazev"] for k in KATEGORIE_PRIJMOVE]
        self.assertNotIn("Převod", prijmove)
        rows = [{"Číslo protiúčtu": "2200973033/2010", "Objem": "15000"}]

        aplikuj_deterministickou_kategorizaci(rows, prijmove)
        self.assertIsNone(rows[0].get("Kategorie"))  # na příjmovém výpisu nesahá

        rows[0]["Kategorie"] = "Neurčeno"  # stav po AI omezené na příjmové kategorie
        aplikuj_interni_prevod(rows)

        self.assertEqual(rows[0].get("Kategorie"), "Převod")

    def test_manual_label_keeps_category_over_internal_transfer(self):
        # Ruční štítek je nejspolehlivější signál a má přednost i před firemním
        # protiúčtem (rozhodnutí uživatele 10/2026). Tankování placené mezi
        # vlastními účty se štítkem „Benzín" musí zůstat „Benzín", ne „Převod".
        stitek = [{"Poznámka": "Benzín", "Číslo protiúčtu": "2200973033", "Objem": "-3100"}]
        aplikuj_deterministickou_kategorizaci(stitek)
        self.assertEqual(stitek[0]["Kategorie"], "Benzín")
        aplikuj_interni_prevod(stitek)
        self.assertEqual(stitek[0]["Kategorie"], "Benzín")

        # Kontrola: kategorie od AI (bez štítkové poznámky) se stále přepíše.
        ai = [{
            "Číslo protiúčtu": "2200973033",
            "Kategorie": "Benzín",
            "Poznamka": "AI: tankování",
        }]
        aplikuj_interni_prevod(ai)
        self.assertEqual(ai[0]["Kategorie"], "Převod")


if __name__ == "__main__":
    unittest.main()
