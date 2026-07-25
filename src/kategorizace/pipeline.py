"""
Jádro zpracování jednoho jobu – sdílené mezi terminálovým CLI a GUI runnerem.

zpracuj_job_core() provede celou pipeline pro jeden CSV výpis:
načtení, filtr faktur dle data, deterministickou kategorizaci, AI kategorizaci
a všechny přepisy, nakonec uloží výsledek. Neví nic o terminálu ani GUI –
průběžný stav hlásí přes volitelný callback `status`.
"""

import os
from typing import Callable

from google import genai

from .ai import kategorizuj_transakce
from .deterministika import aplikuj_deterministickou_kategorizaci
from .faktura_index import filtruj_faktury, rozsah_dat
from .io import najdi_faktury, nacti_csv, uloz_csv
from .prepisy import (
    aplikuj_interni_prevod,
    aplikuj_jidlo_podle_provedl,
    aplikuj_jidlo_pokladna,
    aplikuj_jmena_pokladna,
    aplikuj_kotlarska_pronajem_bytu,
    aplikuj_pradlo_pokladna,
    aplikuj_prevod_zpetna_platba,
    aplikuj_telefony_nejvyssi_castka,
    aplikuj_vzdy_dodavatel,
    omezene_kategorie_pro_soubor,
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
    transakce = nacti_csv(job["csv"])

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

    omezene_kategorie = omezene_kategorie_pro_soubor(job["csv"])
    # Jednoznačné transakce (štítek/protiúčet) zkategorizuj bez AI
    transakce = aplikuj_deterministickou_kategorizaci(transakce, omezene_kategorie)
    transakce = kategorizuj_transakce(
        transakce, faktury, client, firma_index=firma_index, omezene_kategorie=omezene_kategorie,
    )
    transakce = aplikuj_interni_prevod(transakce)
    transakce = aplikuj_kotlarska_pronajem_bytu(transakce, job["csv"], firma_nazev)
    transakce = aplikuj_jidlo_podle_provedl(transakce, job["csv"], firma_nazev)
    transakce = aplikuj_pradlo_pokladna(transakce, firma_nazev)
    transakce = aplikuj_jmena_pokladna(transakce, firma_nazev)
    transakce = aplikuj_jidlo_pokladna(transakce, firma_nazev)
    transakce = aplikuj_prevod_zpetna_platba(transakce)
    transakce = aplikuj_telefony_nejvyssi_castka(transakce)
    transakce = aplikuj_vzdy_dodavatel(transakce, omezene_kategorie=omezene_kategorie)
    os.makedirs(os.path.dirname(job["vystup"]), exist_ok=True)
    uloz_csv(job["vystup"], transakce, list(transakce[0].keys()))
    return {"transakce": len(transakce), "faktury": len(faktury), "prazdny": False}
