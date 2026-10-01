"""
Index metadat faktur: extrakce přes Gemini, cache v .index.json, deterministické předpárování.

Workflow:
  postav_index   – načte nebo vytvoří/aktualizuje .index.json ve složce invoices/
                   Gemini extrahuje: dodavatel, částka, datum, VS, čísla účtů, položky
                   Soubory se zpracují jen pokud chybí v indexu nebo se změnilo mtime.

  filtruj_faktury – z indexu vybere jen faktury datově relevantní pro daný výpis
                    (±TOLERANCE_DNI dní), aby Gemini nedostal zbytečně velký kontext

  predparuj      – deterministicky spáruje transakce PŘED odesláním do Gemini:
                   1. shoda variabilního symbolu (VS transakce = VS na faktuře)
                   2. VS / číslo faktury nalezené v textu zprávy pro příjemce
                   3. shoda základu čísla účtu + částky (s tolerancí ±1 Kč)
                   Kolize VS (víc faktur se stejným VS) se rozhodují částkou;
                   nejednoznačné případy se deterministicky nepárují a jdou do AI.
                   Takto spárované transakce Gemini nemůže přepsat (_predparovano).

  kandidati_pro_transakci – deterministický shortlist faktur pro AI párování
                   (částka, datové okno, dodavatel, VS) – AI pak vybírá jen
                   z tohoto úzkého seznamu místo celého indexu.
"""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from io import BytesIO

import fitz
from google import genai
from google.genai import types
from PIL import Image
from pydantic import BaseModel

from .config import MODEL
from .io import MIME_TYPY

INDEX_SOUBOR = ".index.json"
TOLERANCE_DNI = 45
# .bmp není mezi MIME_TYPY (Gemini image/bmp nepodporuje) – převádí se na PNG v _extrahuj
_EXT_PODPOROVANE = set(MIME_TYPY.keys()) | {".pdf", ".bmp"}


class _FakturaMetadata(BaseModel):
    dodavatel: str
    castka: float | None
    mena: str | None
    datum: str | None  # YYYY-MM-DD
    vs: str | None
    ucty: list[str]
    polozky: list[str]


def _overeni_extrakce(meta: dict, text: str | None) -> None:
    """
    Ověří, že extrahovaný VS a částka se skutečně vyskytují v textu PDF.

    Chrání deterministické párování před halucinacemi extrakce: neověřená
    hodnota se v predparuj používá jen s dodatečným potvrzením (viz tam).
    U obrázků a skenů bez textové vrstvy není co ověřovat – extrakci věříme.
    """
    if not text or len(text.strip()) < 50:
        return
    bez_mezer = re.sub(r"\s", "", text)

    vs = re.sub(r"\D", "", str(meta.get("vs") or ""))
    if vs:
        meta["vs_overen"] = vs in bez_mezer

    castka = meta.get("castka")
    if castka is not None:
        c = round(float(castka), 2)
        varianty = {
            f"{c:.2f}",
            f"{c:.2f}".replace(".", ","),
            f"{c:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        }
        if c == int(c):
            varianty.add(str(int(c)))
        meta["castka_overena"] = any(v in bez_mezer for v in varianty)


def _extrahuj(cesta: str, client: genai.Client) -> dict:
    """Pošle fakturu do Gemini a vrátí extrahovaná metadata. PDF i obrázky se posílají jako bytes;
    z PDF se navíc přes PyMuPDF vytáhne text pro zpětné ověření extrakce. Gemini nepodporuje
    image/bmp přímo, proto se .bmp v paměti převede na PNG před odesláním."""
    ext = os.path.splitext(cesta)[1].lower()
    parts = []
    text_pdf = None

    if ext in MIME_TYPY:
        with open(cesta, "rb") as f:
            parts.append(types.Part.from_bytes(data=f.read(), mime_type=MIME_TYPY[ext]))
        if ext == ".pdf":
            try:
                doc = fitz.open(cesta)
                text_pdf = "\n".join(p.get_text() for p in doc)
                doc.close()
            except Exception:
                text_pdf = None
    elif ext == ".bmp":
        buf = BytesIO()
        Image.open(cesta).convert("RGB").save(buf, "PNG")
        parts.append(types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png"))
    else:
        return {}

    parts.append(types.Part.from_text(text=(
        "Z tohoto dokladu extrahuj:\n"
        "- dodavatel: název dodavatele (NE odběratele — ignoruj RD Group, Nesty, Casa Libre)\n"
        "- castka: celková částka k úhradě PŘESNĚ tak, jak je uvedená na dokladu — "
        "NEPŘEPOČÍTÁVEJ na CZK, i když je doklad v cizí měně (USD, EUR...); "
        "desetinné číslo bez mezer\n"
        "- mena: měna částky jako ISO 4217 kód (CZK, USD, EUR...); pokud doklad "
        "měnu neuvádí, použij CZK\n"
        "- datum: datum vystavení nebo DUZP ve formátu YYYY-MM-DD\n"
        "- vs: variabilní symbol (pouze číslice, bez mezer)\n"
        "- ucty: čísla bankovních účtů dodavatele ve formátu základ/kód (např. '306744731/100')\n"
        "- polozky: stručný seznam položek faktury (max 5, např. ['čisticí prostředky', 'papírové ručníky'])\n"
        "Pokud hodnotu nelze určit, použij null."
    )))

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=parts,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_FakturaMetadata,
            ),
        )
        d = response.parsed
        meta = {
            "dodavatel": d.dodavatel,
            "castka": d.castka,
            "mena": (d.mena or "CZK").strip().upper(),
            "datum": d.datum,
            "vs": d.vs,
            "ucty": d.ucty or [],
            "polozky": d.polozky or [],
            "mtime": os.path.getmtime(cesta),
        }
        _overeni_extrakce(meta, text_pdf)
        return meta
    except Exception:
        return {"error": True, "mtime": os.path.getmtime(cesta)}


def postav_index(slozka: str, client: genai.Client, progress=None) -> dict:
    """Načte nebo vytvoří/aktualizuje index metadat faktur v dané složce."""
    if not os.path.isdir(slozka):
        return {}

    index_cesta = os.path.join(slozka, INDEX_SOUBOR)
    index: dict = {}
    if os.path.exists(index_cesta):
        with open(index_cesta, encoding="utf-8") as f:
            index = json.load(f)

    soubory = [
        f for f in os.listdir(slozka)
        if os.path.splitext(f)[1].lower() in _EXT_PODPOROVANE
    ]
    # Zpracuj soubory které nejsou v indexu nebo se změnily (jiné mtime)
    ke_zpracovani = [
        f for f in soubory
        if f not in index
        or (not index[f].get("error") and abs(index[f].get("mtime", 0) - os.path.getmtime(os.path.join(slozka, f))) > 1)
    ]

    if ke_zpracovani:
        nazev = os.path.basename(slozka)
        task_id = None
        if progress:
            task_id = progress.add_task(f"[cyan]{nazev}[/cyan]", total=len(ke_zpracovani))

        def _zpracuj(fname: str) -> tuple[str, dict]:
            return fname, _extrahuj(os.path.join(slozka, fname), client)

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(_zpracuj, f): f for f in ke_zpracovani}
            for future in as_completed(futures):
                fname, meta = future.result()
                index[fname] = meta
                if progress and task_id is not None:
                    progress.update(task_id, advance=1)

        if progress and task_id is not None:
            progress.update(task_id, description=f"[green]✓ {nazev}[/green]")

        tmp = index_cesta + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        os.replace(tmp, index_cesta)

    return index


# ---------------------------------------------------------------------------
# Filtrování faktur dle data transakcí
# ---------------------------------------------------------------------------

def _parsuj_datum(s: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y", "%m/%d/%Y", "%-m/%-d/%Y", "%m/%d/%y", "%d.%m.%y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            pass
    return None


def rozsah_dat(transakce: list[dict]) -> tuple[datetime, datetime] | None:
    datumy = [d for t in transakce if (d := _parsuj_datum(str(t.get("Datum", "") or "")))]
    return (min(datumy), max(datumy)) if datumy else None


def filtruj_faktury(index: dict, slozka: str, datum_od: datetime, datum_do: datetime) -> list[str]:
    """Vrátí cesty k fakturám relevantním pro dané období ± TOLERANCE_DNI."""
    od = datum_od - timedelta(days=TOLERANCE_DNI)
    do = datum_do + timedelta(days=TOLERANCE_DNI)
    cesty = []
    for fname, meta in index.items():
        if meta.get("error"):
            continue
        datum_str = meta.get("datum")
        if datum_str:
            try:
                d = datetime.fromisoformat(datum_str)
                if od <= d <= do:
                    cesty.append(os.path.join(slozka, fname))
            except ValueError:
                cesty.append(os.path.join(slozka, fname))
        else:
            cesty.append(os.path.join(slozka, fname))
    return cesty


# ---------------------------------------------------------------------------
# Deterministické předpárování
# ---------------------------------------------------------------------------

TOLERANCE_CASTKY = 1.0  # Kč – zaokrouhlení a drobné odchylky


def _je_cizi_mena(meta: dict) -> bool:
    """True, pokud faktura není v CZK – částku pak nelze přímo srovnávat s Kč na výpisu
    (kurz + poplatky banky vždy udělají jiné číslo)."""
    return str(meta.get("mena") or "CZK").strip().upper() not in ("CZK", "KČ", "KC")


def _normalizuj_ucet(ucet: str) -> str:
    """Základní číslo účtu bez bankovního kódu a mezer."""
    ucet = re.sub(r"\s", "", ucet)
    # Odstraň případný prefix (např. "27-5829880217" → ponechat celé, jen strip kódu za lomítkem)
    return ucet.split("/")[0]


def _normalizuj_vs(vs) -> str:
    """VS jako čisté číslice bez vedoucích nul."""
    return re.sub(r"\D", "", str(vs or "")).lstrip("0")


def _castka_transakce(t: dict) -> float | None:
    """Absolutní částka transakce ze sloupce Objem, nebo None."""
    try:
        return round(abs(float(str(t.get("Objem", "")).replace(" ", "").replace(",", "."))), 2)
    except (ValueError, TypeError):
        return None


def predparuj(transakce: list[dict], index: dict) -> list[dict]:
    """
    Deterministicky spáruje transakce s fakturami před odesláním do Gemini.

    Pořadí priorit:
      1. VS transakce = VS faktury
      2. VS / číslo faktury nalezené v textu zprávy pro příjemce (vyžaduje shodu částky)
      3. Základ čísla protiúčtu + částka s tolerancí ±TOLERANCE_CASTKY

    Ochrany proti chybnému párování:
      - kolize VS (víc faktur se stejným VS) rozhoduje shoda částky; nejednoznačné
        případy se nepárují a rozhodne o nich AI z kandidátního shortlistu
      - známe-li částku faktury i transakce a nesedí, VS shoda nestačí
      - VS neověřený v textu PDF (vs_overen=False) vyžaduje shodu částky
      - neověřená částka faktury (castka_overena=False) se nepoužije pro tier 3
      - jednou spárovaná faktura se deterministicky nepřiřadí druhé transakci

    Spárované transakce dostanou _predparovano=<důvod> — Gemini je nesmí přepsat.
    Příznak se odstraní z výstupu v ai.kategorizuj_transakce po dokončení.
    """
    vs_mapa: dict[str, list[str]] = {}              # vs → [fname, ...]
    ucet_mapa: dict[str, list[tuple[float, str]]] = {}  # zaklad_uctu → [(castka, fname), ...]

    for fname, meta in index.items():
        if meta.get("error"):
            continue
        vs = _normalizuj_vs(meta.get("vs"))
        if vs:
            vs_mapa.setdefault(vs, []).append(fname)

        castka = meta.get("castka")
        if castka is not None and meta.get("castka_overena", True) and not _je_cizi_mena(meta):
            castka_r = round(float(castka), 2)
            for ucet in meta.get("ucty") or []:
                zaklad = _normalizuj_ucet(str(ucet))
                if zaklad:
                    ucet_mapa.setdefault(zaklad, []).append((castka_r, fname))

    pouzite: set[str] = set()

    def _vyber_vs(kandidati: list[str], castka: float | None, vyzaduj_castku: bool, datum: datetime | None = None) -> str | None:
        """Z faktur se shodným VS vybere jednoznačnou; kolize rozhoduje částka."""
        zuzeni: list[tuple[str, bool]] = []
        for fname in dict.fromkeys(kandidati):
            if fname in pouzite:
                continue
            meta = index[fname]
            fc = meta.get("castka")
            fc = round(float(fc), 2) if fc is not None and not _je_cizi_mena(meta) else None
            castka_sedi = castka is not None and fc is not None and abs(fc - castka) <= TOLERANCE_CASTKY
            if not castka_sedi:
                if vyzaduj_castku:
                    continue
                if fc is not None and castka is not None:
                    continue  # obě částky známe a nesedí → nech na AI
                if not meta.get("vs_overen", True):
                    continue  # částku nelze porovnat a VS není ověřen v textu PDF
            zuzeni.append((fname, castka_sedi))
        if len(zuzeni) == 1:
            return zuzeni[0][0]
        se_shodou = [f for f, sedi in zuzeni if sedi]
        if len(se_shodou) == 1:
            return se_shodou[0]
        if len(se_shodou) > 1:
            # Víc kandidátů se stejným VS i sedící částkou: pokud jde o duplicitní
            # dokumentaci téže platby (stejný dodavatel, prakticky stejná částka –
            # typicky zálohová faktura + daňový doklad k ní), rozhodne datum:
            # vezme se ten, jehož datum na faktuře je nejblíž datu transakce.
            # Bez použitelného data (chybí u faktur/transakce) padá na první.
            prvni = index[se_shodou[0]]
            castka0 = round(float(prvni.get("castka")), 2)
            dodavatel0 = str(prvni.get("dodavatel") or "").strip().lower()
            duplikaty = all(
                str(index[f].get("dodavatel") or "").strip().lower() == dodavatel0
                and abs(round(float(index[f].get("castka")), 2) - castka0) <= TOLERANCE_CASTKY
                for f in se_shodou
            )
            if duplikaty:
                if datum:
                    s_datem = []
                    for f in se_shodou:
                        try:
                            datum_f = datetime.fromisoformat(index[f]["datum"])
                        except (KeyError, TypeError, ValueError):
                            continue
                        s_datem.append((abs((datum - datum_f).days), f))
                    if s_datem:
                        s_datem.sort(key=lambda x: x[0])
                        return s_datem[0][1]
                return se_shodou[0]
        return None

    for t in transakce:
        if t.get("Faktura"):
            continue
        castka = _castka_transakce(t)
        datum_t = _parsuj_datum(str(t.get("Datum", "") or ""))

        # 1. VS pole transakce
        vs_t = _normalizuj_vs(t.get("VS"))
        if vs_t and vs_t in vs_mapa:
            hit = _vyber_vs(vs_mapa[vs_t], castka, vyzaduj_castku=False, datum=datum_t)
            if hit:
                t["Faktura"] = hit
                t["_predparovano"] = "VS"
                pouzite.add(hit)
                continue

        # 2. VS / číslo faktury v textu zprávy (banka VS pole nevyplnila)
        texty = " ".join(str(t.get(k) or "") for k in ("Zpráva pro příjemce", "Poznámka"))
        hit = None
        for seq in re.findall(r"\d{4,10}", texty):
            seq_n = seq.lstrip("0")
            if seq_n and seq_n != vs_t and seq_n in vs_mapa:
                hit = _vyber_vs(vs_mapa[seq_n], castka, vyzaduj_castku=True, datum=datum_t)
                if hit:
                    break
        if hit:
            t["Faktura"] = hit
            t["_predparovano"] = "VS ve zprávě"
            pouzite.add(hit)
            continue

        # 3. Protiúčet + částka s tolerancí
        protiucet_raw = str(t.get("Číslo protiúčtu", t.get("Protiúčet", "")) or "")
        zaklad = _normalizuj_ucet(protiucet_raw)
        if zaklad and castka is not None:
            kand = list(dict.fromkeys(
                f for fc, f in ucet_mapa.get(zaklad, [])
                if abs(fc - castka) <= TOLERANCE_CASTKY and f not in pouzite
            ))
            if len(kand) == 1:
                t["Faktura"] = kand[0]
                t["_predparovano"] = "účet+částka"
                pouzite.add(kand[0])

    return transakce


# ---------------------------------------------------------------------------
# Kandidáti pro AI párování
# ---------------------------------------------------------------------------

_GENERICKA_SLOVA = {"sro", "spol", "czech", "republic", "company", "group",
                    "servis", "service", "services", "praha", "brno"}


def _dodavatel_v_textu(dodavatel: str, text: str) -> bool:
    """Hrubá shoda jména dodavatele s textem transakce (tokeny ≥ 4 znaky)."""
    for tok in re.split(r"[^\w]+", dodavatel.lower()):
        if len(tok) >= 4 and tok not in _GENERICKA_SLOVA and tok in text:
            return True
    return False


def kandidati_pro_transakci(
    t: dict,
    index: dict,
    povolene: set[str] | None = None,
    max_kandidatu: int = 6,
) -> list[dict]:
    """
    Deterministický shortlist faktur, ze kterého smí AI pro danou transakci vybírat.

    Faktura se stane kandidátem jen když projde datovým oknem (vystavena max
    60 dní před platbou a max 14 dní po ní) a získá skóre ≥ 2 z těchto signálů:
      - částka sedí (±1 Kč: +3) nebo přibližně sedí (±2 %: +2) — jen pro faktury v CZK;
        cizí měna (USD, EUR...) se s Kč na výpisu nesrovnává (kurz + poplatky)
      - shoda VS (+3), VS v názvu souboru nebo VS faktury ve zprávě (+2)
      - jméno dodavatele se vyskytuje v textu transakce (+2)

    Vrací max_kandidatu nejlépe skórujících záznamů s metadaty a důvody.
    """
    castka = _castka_transakce(t)
    datum_t = _parsuj_datum(str(t.get("Datum", "") or ""))
    vs_t = _normalizuj_vs(t.get("VS"))
    text = " ".join(
        str(t.get(k) or "")
        for k in ("Název protiúčtu", "Poznámka", "Zpráva pro příjemce")
    ).lower()
    cisla_ve_zprave = {s.lstrip("0") for s in re.findall(r"\d{4,10}", text)} - {vs_t, ""}

    vysledky = []
    for fname, meta in index.items():
        if meta.get("error"):
            continue
        if povolene is not None and fname not in povolene:
            continue

        datum_f = None
        if meta.get("datum"):
            try:
                datum_f = datetime.fromisoformat(meta["datum"])
            except ValueError:
                pass
        if datum_t and datum_f and not (-14 <= (datum_t - datum_f).days <= 60):
            continue

        skore = 0
        duvody = []

        if datum_t and datum_f:
            dny = abs((datum_t - datum_f).days)
            if dny <= 2:
                skore += 2
                duvody.append("datum sedí (±2 dny)")
            elif dny <= 7:
                skore += 1
                duvody.append("datum blízko (±7 dní)")

        fc = meta.get("castka")
        fc = round(float(fc), 2) if fc is not None else None
        cizi_mena = _je_cizi_mena(meta)
        if castka is not None and fc is not None and not cizi_mena:
            if abs(fc - castka) <= TOLERANCE_CASTKY:
                skore += 3
                duvody.append("částka sedí")
            elif abs(fc - castka) <= 0.02 * max(fc, castka):
                skore += 2
                duvody.append("částka přibližně sedí")
        elif cizi_mena:
            duvody.append(f"zahraniční faktura ({meta.get('mena')}) – částka nesrovnatelná s Kč")

        vs_f = _normalizuj_vs(meta.get("vs"))
        if vs_t and vs_f and (
            vs_t == vs_f
            or (len(min(vs_t, vs_f, key=len)) >= 5 and (vs_t in vs_f or vs_f in vs_t))
        ):
            skore += 3
            duvody.append("shoda VS")
        elif vs_t and len(vs_t) >= 5 and vs_t in re.sub(r"\D", "", fname):
            skore += 2
            duvody.append("VS v názvu souboru")
        elif vs_f and vs_f in cisla_ve_zprave:
            skore += 2
            duvody.append("VS ve zprávě")

        dodavatel = str(meta.get("dodavatel") or "")
        if dodavatel and _dodavatel_v_textu(dodavatel, text):
            skore += 2
            duvody.append("dodavatel se shoduje")

        if skore >= 2:
            vysledky.append({
                "soubor": fname,
                "dodavatel": dodavatel,
                "castka": fc,
                "mena": meta.get("mena") or "CZK",
                "datum": meta.get("datum"),
                "vs": meta.get("vs"),
                "polozky": meta.get("polozky") or [],
                "duvody": duvody,
                "skore": skore,
            })

    vysledky.sort(key=lambda k: -k["skore"])
    return vysledky[:max_kandidatu]


# ---------------------------------------------------------------------------
# Zpětné ověření přiřazení (deterministicky i po AI)
# ---------------------------------------------------------------------------

def over_prirazeni(transakce: list[dict], index: dict) -> list[dict]:
    """
    Poslední pojistka: po přiřazení faktury (deterministicky i AI) ověří, že
    přiřazení nekoliduje s tvrdými signály z indexu (VS, protiúčet, částka).

    Nejde o to, že by chyběl signál (kartové platby VS/účet nemají – to je
    normální a nic to neznamená) – jde o to, že DOSTUPNÝ signál JEDNOZNAČNĚ
    NESEDÍ. To je silný náznak, že přiřazení je chybné (VS kolize bez
    kontroly částky, halucinace AI, špatně přečtená faktura…) – ale může mít
    i legitimní vysvětlení (např. částečná platba), proto se přiřazení
    nemaže, jen se označí varováním do "Check přiřazení faktury" k ruční
    kontrole.
    """
    for t in transakce:
        fname = t.get("Faktura")
        if not fname or fname == "NENALEZENO":
            t["Check přiřazení faktury"] = ""
            continue
        meta = index.get(fname)
        if not meta or meta.get("error"):
            t["Check přiřazení faktury"] = "⚠ faktura není v indexu"
            continue

        problemy = []

        vs_t = _normalizuj_vs(t.get("VS"))
        vs_f = _normalizuj_vs(meta.get("vs"))
        if vs_t and vs_f and vs_t != vs_f:
            problemy.append(f"VS transakce ({vs_t}) ≠ VS faktury ({vs_f})")

        protiucet_raw = str(t.get("Číslo protiúčtu", t.get("Protiúčet", "")) or "")
        zaklad_t = _normalizuj_ucet(protiucet_raw)
        ucty_f = [_normalizuj_ucet(str(u)) for u in (meta.get("ucty") or [])]
        if zaklad_t and ucty_f and zaklad_t not in ucty_f:
            problemy.append(f"účet transakce ({zaklad_t}) není mezi účty faktury ({', '.join(ucty_f)})")

        castka_t = _castka_transakce(t)
        castka_f = meta.get("castka")
        if castka_t is not None and castka_f is not None and not _je_cizi_mena(meta):
            castka_f = round(float(castka_f), 2)
            odchylka = abs(castka_f - castka_t)
            if odchylka > max(TOLERANCE_CASTKY * 5, 0.05 * max(castka_f, castka_t)):
                problemy.append(f"částka transakce ({castka_t}) ≠ částka faktury ({castka_f})")

        t["Check přiřazení faktury"] = ("⚠ " + "; ".join(problemy)) if problemy else ""

    return transakce
