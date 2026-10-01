"""
Jádro zpracování jednoho jobu – sdílené mezi terminálovým CLI a GUI runnerem.

zpracuj_job_core() provede celou pipeline pro jeden CSV nebo XLSX výpis:
načtení, filtr faktur dle data, deterministickou kategorizaci, AI kategorizaci
a všechny přepisy, nakonec uloží výsledek jako CSV. Neví nic o terminálu ani GUI –
průběžný stav hlásí přes volitelný callback `status`.
"""

import os
from typing import Callable

from google import genai

from .ai import kategorizuj_transakce
from .deterministika import aplikuj_deterministickou_kategorizaci
from .faktura_index import filtruj_faktury, rozsah_dat
from .io import najdi_faktury, nacti_transakce, uloz_csv
from .prepisy import (
    aplikuj_interni_prevod,
    aplikuj_jidlo_podle_provedl,
    aplikuj_jidlo_pokladna,
    aplikuj_jmena_pokladna,
    aplikuj_kotlarska_pronajem_bytu,
    aplikuj_pradlo_pokladna,
    aplikuj_prevod_zpetna_platba,
    aplikuj_radek_formulare,
    aplikuj_telefony_nejvyssi_castka,
    aplikuj_vychozi_kategorii_ucet,
    aplikuj_vzdy_dodavatel,
    omezene_kategorie_pro_soubor,
)


# Sloupce, které pipeline dopočítá – pevné pořadí v CSV bez ohledu na to,
# v jakém pořadí je která vrstva (deterministika/AI) reálně naplnila.
VYSTUPNI_SLOUPCE = [
    "Kategorie", "Jistota kategorie", "Chyba v kategorii", "Poznamka",
    "Faktura", "Jistota faktura", "Check přiřazení faktury", "Špatně zvolená faktura",
]
# Sloupce pro Alokační formulář (prepisy.aplikuj_radek_formulare) – vždy až za VYSTUPNI_SLOUPCE.
FORMULAROVE_SLOUPCE = ["Firma", "Radek"]


def _serad_sloupce(radek: dict) -> list[str]:
    """Původní sloupce z výpisu beze změny, pak VYSTUPNI_SLOUPCE, pak FORMULAROVE_SLOUPCE."""
    special = set(VYSTUPNI_SLOUPCE) | set(FORMULAROVE_SLOUPCE)
    puvodni = [k for k in radek if k not in special]
    return (
        puvodni
        + [k for k in VYSTUPNI_SLOUPCE if k in radek]
        + [k for k in FORMULAROVE_SLOUPCE if k in radek]
    )


def zpracuj_job_core(
    job: dict,
    invoices_slozka: str,
    firma_index: dict,
    firma_nazev: str,
    client: genai.Client,
    status: Callable[[str], None] = lambda _: None,
) -> dict:
    """Zpracuje jeden výpis a vrátí {"transakce": n, "faktury": m, "prazdny": bool}."""
    transakce = nacti_transakce(job["vstup"])

    # Filtruj faktury podle datového rozsahu transakcí
    rozsah = rozsah_dat(transakce)
    if rozsah and firma_index:
        datum_od, datum_do = rozsah
        faktury = filtruj_faktury(firma_index, invoices_slozka, datum_od, datum_do)
    elif os.path.isdir(invoices_slozka):
        faktury = najdi_faktury(invoices_slozka)
    else:
        faktury = []

    status(f"Odesílám {len(transakce)} transakcí + {len(faktury)} faktur...")
    if not transakce:
        return {"transakce": 0, "faktury": len(faktury), "prazdny": True}

    omezene_kategorie = omezene_kategorie_pro_soubor(job["vstup"])
    # Jednoznačné transakce (štítek/protiúčet) zkategorizuj bez AI
    transakce = aplikuj_deterministickou_kategorizaci(transakce, omezene_kategorie)
    transakce = kategorizuj_transakce(
        transakce, faktury, client, firma_index=firma_index, omezene_kategorie=omezene_kategorie,
    )
    transakce = aplikuj_interni_prevod(transakce)
    transakce = aplikuj_kotlarska_pronajem_bytu(transakce, job["vstup"], firma_nazev)
    transakce = aplikuj_jidlo_podle_provedl(transakce, job["vstup"], firma_nazev)
    transakce = aplikuj_pradlo_pokladna(transakce, firma_nazev)
    transakce = aplikuj_jmena_pokladna(transakce, firma_nazev)
    transakce = aplikuj_jidlo_pokladna(transakce, firma_nazev)
    transakce = aplikuj_prevod_zpetna_platba(transakce)
    transakce = aplikuj_telefony_nejvyssi_castka(transakce)
    transakce = aplikuj_vzdy_dodavatel(transakce, omezene_kategorie=omezene_kategorie)
    transakce = aplikuj_vychozi_kategorii_ucet(transakce, job["vstup"])
    transakce = aplikuj_radek_formulare(transakce, firma_nazev)
    for t in transakce:
        t.setdefault("Chyba v kategorii", "")
        t.setdefault("Špatně zvolená faktura", "")
    os.makedirs(os.path.dirname(job["vystup"]), exist_ok=True)
    uloz_csv(job["vystup"], transakce, _serad_sloupce(transakce[0]))
    return {"transakce": len(transakce), "faktury": len(faktury), "prazdny": False}
