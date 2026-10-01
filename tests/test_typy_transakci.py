from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from openpyxl import Workbook

from kategorizace.ai import kategorizuj_transakce
from kategorizace.config import MAPOVANI_NA_FORMULAR
from kategorizace.deterministika import aplikuj_deterministickou_kategorizaci
from kategorizace.io import nacti_xlsx
from kategorizace.prepisy import aplikuj_jmena_pokladna, aplikuj_vzdy_dodavatel


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
        rows = [
            {"Název protiúčtu": "Úrok z úvěru"},
            {"Název protiúčtu": "Úrok z nevyčerpaného úvěru"},
        ]

        result = aplikuj_deterministickou_kategorizaci(rows)

        self.assertEqual([row.get("Kategorie") for row in result], ["Úrok", "Úrok"])
        self.assertEqual(MAPOVANI_NA_FORMULAR["Úrok"], "N49")

    def test_pricelabs_merchant_is_previo_system(self):
        result = aplikuj_vzdy_dodavatel(
            [{"Název protiúčtu": "PRICELABSINC*DYNAPRICE"}]
        )

        self.assertEqual(result[0].get("Kategorie"), "Previo systém")
        self.assertEqual(MAPOVANI_NA_FORMULAR["Previo systém"], "N45")

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

if __name__ == "__main__":
    unittest.main()
