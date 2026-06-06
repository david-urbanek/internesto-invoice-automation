"""
Kategorizace bankovních transakcí pomocí Gemini API
----------------------------------------------------
Použití:
  pip install google-generativeai
  export GOOGLE_API_KEY=AIza...
  python kategorizace.py

Vstup:
  transactions/transakce.csv  - export z banky (Datum;Castka;Mena;Popis;Protistrana;VS)
  faktury/                    - složka s PDF fakturami

Výstup:
  transakce_kategorizovane.csv - stejné CSV + sloupce Kategorie, Faktura, Poznamka
"""

import base64
import csv
import glob
import json
import os
import tempfile
from collections import Counter

from PIL import Image

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ─── Konfigurace ────────────────────────────────────────────────────────────

CSV_VSTUP = "transactions/transakce.csv"
CSV_VYSTUP = "transakce_kategorizovane.csv"
SLOZKA_FAKTUR = "faktury"
CSV_SEPARATOR = ","
MODEL = "gemini-3.5-flash"

KATEGORIE = [
    {
        "nazev": "Dekorace",
        "popis": "Nákupy vybavení, nábytku a doplňků pro bytové jednotky.",
        "dodavatele": ["IKEA", "Hornbach", "Alza", "Pepco", "JYSK", "Nábytek Žák", "Jurny", "Zamečnictví", "SmartKey"],
    },
    {
        "nazev": "Drogerie",
        "popis": "Spotřební hygienické a čisticí potřeby pro provoz.",
        "dodavatele": ["Drogerie Herout", "dm drogerie", "Drogeo.cz"],
    },
    {
        "nazev": "Prádelna",
        "popis": "Platby za praní prádla pro apartmány.",
        "dodavatele": ["Christof"],
    },
    {
        "nazev": "Technik",
        "popis": "Platby za údržbu a technické práce.",
        "dodavatele": ["Michal Říčánek", "Igor"],
    },
    {
        "nazev": "Netflix a Spotify",
        "popis": "Předplatné streamovacích služeb provozovaných v apartmánech pro hosty.",
        "dodavatele": ["Netflix", "Spotify"],
    },
    {
        "nazev": "Převod",
        "popis": "Interní převody mezi firemními účty (Příjmový 1 → Výdajový 2, Rezervní 1 atd.) a výběry z bankomatu. Nejedná se o skutečný výdaj — jen přesun peněz mezi účty firmy. Tyto transakce označ ale nezahrnuj do výdajových součtů.",
        "dodavatele": [],
    },
    {
        "nazev": "Rezervní 1",
        "popis": "Výdaje hrazené primárně z rezervního účtu — parkování, servis auta.",
        "dodavatele": [],
    },
    {
        "nazev": "Arteon",
        "popis": "Výdaje na firemní auto VW Arteon — servis, STK, destičky, baterie.",
        "dodavatele": [],
    },
    {
        "nazev": "Taxi",
        "popis": "Doprava taxislužbou — pravděpodobně služební cesty.",
        "dodavatele": ["Bolt"],
    },
    {
        "nazev": "Google",
        "popis": "Google Cloud / Google Workspace předplatné — IT/provozní náklady.",
        "dodavatele": ["Google"],
    },
    {
        "nazev": "Ostatní služby",
        "popis": "Různé služby, které nespadají jinam.",
        "dodavatele": ["Česká pošta"],
    },
    {
        "nazev": "Reprezentace",
        "popis": "Nákupy reprezentačního charakteru.",
        "dodavatele": ["Alza"],
    },
]

# ─── Pomocné funkce ──────────────────────────────────────────────────────────


def nacti_csv(cesta: str) -> list[dict]:
    with open(cesta, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=CSV_SEPARATOR)
        raw_headers = next(reader)
        headers = []
        seen: dict[str, int] = {}
        for h in raw_headers:
            h = h.strip() if h else h
            if h in seen:
                seen[h] += 1
                headers.append(f"{h}_{seen[h]}")
            else:
                seen[h] = 1
                headers.append(h)
        return [
            {k: v.strip() if isinstance(v, str) else v for k, v in zip(headers, row)}
            for row in reader
        ]


def uloz_csv(cesta: str, radky: list[dict], fieldnames: list[str]):
    with open(cesta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames,
                                delimiter=CSV_SEPARATOR)
        writer.writeheader()
        writer.writerows(radky)


MIME_TYPY = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

EXTENSIONS_VSECHNY = list(MIME_TYPY.keys()) + [".bmp", ".tiff", ".tif", ".webp", ".gif"]


def soubor_na_base64(cesta: str) -> str:
    with open(cesta, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def konvertuj_na_pdf(cesta: str) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    Image.open(cesta).convert("RGB").save(tmp.name, "PDF")
    return tmp.name


def najdi_faktury(slozka: str) -> list[str]:
    cesty = []
    for ext in EXTENSIONS_VSECHNY:
        cesty.extend(glob.glob(os.path.join(slozka, f"*{ext}")))
    return cesty


# ─── Hlavní logika ───────────────────────────────────────────────────────────

def kategorizuj_transakce(transakce: list[dict], faktury_cesty: list[str]) -> list[dict]:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel(MODEL)

    tmp_soubory = []
    parts = []
    for cesta in faktury_cesty:
        ext = os.path.splitext(cesta)[1].lower()
        if ext not in MIME_TYPY:
            cesta = konvertuj_na_pdf(cesta)
            tmp_soubory.append(cesta)
            ext = ".pdf"
        parts.append({
            "inline_data": {
                "mime_type": MIME_TYPY[ext],
                "data": soubor_na_base64(cesta),
            }
        })

    # Seznam transakcí jako text
    radky = [
        f"{'ID':<4} {'Datum':<12} {'Objem':>10} {'Protistrana':<30} {'Pozn.':<20} {'Zpráva':<35} {'VS':<12}"]
    radky.append("-" * 135)
    for i, t in enumerate(transakce):
        radky.append(
            f"{i:<4} "
            f"{t.get('Datum', ''):<12} "
            f"{t.get('Objem', ''):>10} "
            f"{t.get('Název protiúčtu', ''):<30} "
            f"{t.get('Poznámka', ''):<20} "
            f"{t.get('Zpráva pro příjemce', ''):<35} "
            f"{t.get('VS', ''):<12}"
        )

    def _formatuj_kategorii(k: dict) -> str:
        radek = f"- {k['nazev']}: {k['popis']}"
        if k["dodavatele"]:
            radek += f" Typičtí dodavatelé: {', '.join(k['dodavatele'])}."
        return radek

    prompt = f"""Jsi asistent pro kategorizaci účetních transakcí.

Dostaneš seznam bankovních transakcí a PDF faktury. Tvým úkolem je:
1. Přiřadit každé transakci kategorii ze seznamu níže.
2. Pokud transakce odpovídá některé faktuře (podle VS, částky, názvu protistrany nebo datumu), uveď název souboru faktury.
3. Kategorie urči primárně z obsahu faktury a kontextu transakce. Uvedení typičtí dodavatelé u každé kategorie slouží jako nápověda, ale nejsou závazní — stejný dodavatel může spadat do jiné kategorie podle účelu nákupu.
4. Uveď pravděpodobnost jistoty jako číslo 0–100.
5. Pokud kategorii nelze určit, použij "Neurčeno".

DOSTUPNÉ KATEGORIE:
{chr(10).join(_formatuj_kategorii(k) for k in KATEGORIE)}

TRANSAKCE K ZATEGORIZOVÁNÍ:
{chr(10).join(radky)}

Odpověz POUZE validním JSON polem, žádný jiný text. Formát:
[
  {{
    "id": 0,
    "kategorie": "název kategorie",
    "faktura": "název souboru faktury nebo prázdný string",
    "poznamka": "krátká poznámka proč tato kategorie",
    "jistota": 85
  }},
  ...
]

Vrať záznam pro každou transakci (celkem {len(transakce)} záznamů), ve stejném pořadí jako vstup."""

    parts.append({"text": prompt})

    print(
        f"  Odesílám {len(transakce)} transakcí + {len(faktury_cesty)} faktur do Gemini API...")

    response = model.generate_content(parts)
    odpoved_text = response.text.strip()

    # Odstraní případné markdown bloky
    if odpoved_text.startswith("```"):
        odpoved_text = odpoved_text.split("```")[1]
        if odpoved_text.startswith("json"):
            odpoved_text = odpoved_text[4:]
        odpoved_text = odpoved_text.strip()

    vysledky = json.loads(odpoved_text)

    for tmp in tmp_soubory:
        os.unlink(tmp)

    for vysledek in vysledky:
        idx = vysledek["id"]
        transakce[idx]["Kategorie"] = vysledek.get("kategorie", "Neurčeno")
        transakce[idx]["Faktura"] = vysledek.get("faktura", "")
        transakce[idx]["Poznamka"] = vysledek.get("poznamka", "")
        transakce[idx]["Jistota"] = vysledek.get("jistota", "")

    return transakce


# ─── Spuštění ────────────────────────────────────────────────────────────────

def main():
    print("=== Kategorizace transakcí (Gemini) ===\n")

    if not os.environ.get("GOOGLE_API_KEY"):
        print("CHYBA: Nastav proměnnou GOOGLE_API_KEY")
        print("  export GOOGLE_API_KEY=AIza...")
        return

    if not os.path.exists(CSV_VSTUP):
        print(f"CHYBA: Soubor {CSV_VSTUP} nenalezen")
        return

    transakce = nacti_csv(CSV_VSTUP)
    print(f"Načteno {len(transakce)} transakcí z {CSV_VSTUP}")

    faktury = najdi_faktury(SLOZKA_FAKTUR)
    if faktury:
        print(
            f"Nalezeno {len(faktury)} faktur: {[os.path.basename(f) for f in faktury]}")
    else:
        print("Žádné PDF faktury nenalezeny — kategorizace proběhne bez párování faktur")

    print()

    try:
        transakce = kategorizuj_transakce(transakce, faktury)
    except json.JSONDecodeError as e:
        print(f"CHYBA: Gemini nevrátil validní JSON: {e}")
        return
    except Exception as e:
        print(f"CHYBA: {e}")
        return

    fieldnames = list(transakce[0].keys())
    uloz_csv(CSV_VYSTUP, transakce, fieldnames)

    print(f"\nHotovo! Výsledek uložen do {CSV_VYSTUP}")
    print("\nPřehled kategorií:")
    pocty = Counter(t["Kategorie"] for t in transakce)
    for kat, pocet in pocty.most_common():
        print(f"  {kat:<30} {pocet}x")


if __name__ == "__main__":
    main()
