"""
Deterministické přepisy kategorie po AI kategorizaci.

aplikuj_interni_prevod – transakce s protiúčtem patřícím některému z interních
účtů skupiny (FIREMNI_UCTY) je interní převod → "Převod". Výjimkou jsou
kategorie, které daný protiúčet explicitně deklarují v protiucty (Splátka,
Výplata majitele, Kotlářská, Rezervní…) – to jsou záměrně zvlášť sledované
interní toky a zůstávají.

aplikuj_jidlo_podle_provedl – u karetních nákupů jídla (kategorie "Jídlo")
na účtu Nesty Ostatní přepíše kategorii na osobní výdaj podle toho, kdo
transakci provedl (sloupec "Provedl" z Fio výpisu) – viz JIDLO_PODLE_PROVEDL
a UCET_NESTY_OSTATNI v config.py.

omezene_kategorie_pro_soubor – pozná uzavřený seznam kategorií pro daný
výpis ve dvou vrstvách: (1) konkrétní účet s historicky jedinou možnou
kategorií (OMEZENE_KATEGORIE_PODLE_UCTU v config.py), (2) když se výpis
podle účtu nenajde, podle rodičovské složky "Prijmove"/"Vydajove" (rozdělení
firmy/<Firma>/transactions/ zavedené 08/2026) – příjmová složka nabídne jen
KATEGORIE_PRIJMOVE, výdajová jen KATEGORIE. Soubory ležící přímo
v transactions/ (bez rozdělení) mají obojí, jako dřív.

aplikuj_vychozi_kategorii_ucet – na účtech s definovaným "vychozi" v
OMEZENE_KATEGORIE_PODLE_UCTU (Casa/Nesty Příjmový) je tahle kategorie
výchozí pro VŠECHNO, co na daném výpisu skončí jinak než "Převod" – ať už
AI vrátila kategorii mimo uzavřený seznam ("Neurčeno"), nebo nějaký dřívější
přepis přiřadil jinou kategorii. Musí běžet AŽ PO všech ostatních přepisech
(hlavně po aplikuj_interni_prevod), aby skutečné interní převody zůstaly
"Převod".

aplikuj_kotlarska_pronajem_bytu – na účtu RD Příjmový (UCET_RD_PRIJMOVY)
přepíše kategorii na "Kotlářská" u transakcí se štítkem "pronájem bytu"
v Poznámce, bez ohledu na to, co AI vybrala podle protiúčtu (často sdíleného
s Casa Libre Příjmový, což ji svádí k obecnému "Převod").

aplikuj_prostory_nesty_prijmovy – na účtu Nesty Příjmový přepíše příchozí
platbu na "Prostory Příjem", když protiúčet patří RD (RD_UCTY) A text zmiňuje
"prostor". Obě podmínky nutné: RD protiúčet nese i běžné převody, text
"prostor" se objevuje i u ubytování od externích hostů. Běží po
aplikuj_interni_prevod (ten je nejdřív označí "Převod").

aplikuj_prevod_zpetna_platba – pokud se na stejném protiúčtu vrátí stejná
částka opačným směrem (typicky u protiúčtů kategorie "Splátka"), nejde
o splátku úvěru, ale o interní přesun peněz (např. půjčka/vratka společníka
tam a zpět) -> obě transakce se přepíšou na kategorii "Převod".

aplikuj_telefony_nejvyssi_castka – z plateb T-Mobile (účet UCET_TMOBILE)
v daném výpisu je "Telefony" jen ta s nejvyšší částkou, ostatní se přepíšou
na "Zvláštní výdaj".

aplikuj_vzdy_dodavatel – pro dodavatele z VZDY_DODAVATEL_KATEGORIE (config.py)
platí vždy stejná kategorie bez ohledu na znaménko částky (nákup i vratka).
Ne úplně bezpodmínečně – VYJIMKY_VZDY_DODAVATEL (config.py) definuje výjimky
podle dalšího klíčového slova v textu (např. "Alza" je vždy "Dekorace", ALE
"Alza" + "V24" v Poznámce je "V24"). Na výpisech s uzavřeným seznamem
kategorií (omezene_kategorie) se navíc neuplatní, pokud výsledná kategorie
do tohoto seznamu nepatří.
"""

import os
import re
from collections import defaultdict

from .config import (
    FIREMNI_UCTY,
    JIDLO_PODLE_PROVEDL,
    KATEGORIE,
    KATEGORIE_PREPIS_PODLE_PROVEDL,
    KATEGORIE_PREZIJI_INTERNI_PREVOD,
    KATEGORIE_PRIJMOVE,
    KLICOVA_SLOVA_KOTLARSKA_RD_PRIJMOVY,
    MAPOVANI_NA_FORMULAR,
    OMEZENE_KATEGORIE_PODLE_UCTU,
    POKLADNA_JMENA_KATEGORIE,
    RD_UCTY,
    UCET_NESTY_OSTATNI,
    UCET_NESTY_PRIJMOVY,
    UCET_RD_PRIJMOVY,
    UCET_TMOBILE,
    VYJIMKY_VZDY_DODAVATEL,
    VZDY_DODAVATEL_KATEGORIE,
)

_KATEGORIE_PRIJMOVE_NAZVY = {k["nazev"] for k in KATEGORIE_PRIJMOVE}

# Poznámka, kterou deterministika.py zapisuje u kategorizace podle ručního
# štítku. Slouží i jako signál pro aplikuj_interni_prevod, že kategorii určil
# explicitní lidský štítek (viz docstring tamtéž).
POZNAMKA_STITEK_PREFIX = "Deterministicky: štítek"


def _protiucet(t: dict) -> str:
    """Číslo protiúčtu bez kódu banky.

    RB/Air Bank/Raiffeisen exporty mívají protiúčet ve formátu
    „číslo/kód banky" (např. „2200973033/5500"). FIREMNI_UCTY i protiucty
    v configu jsou vedené jen holým číslem, takže se musí stejně jako
    v deterministika._protiucet odseknout vše za „/", jinak by se interní
    převod na firemní účet na takovém výpisu nerozpoznal.
    """
    ucet = str(t.get("Číslo protiúčtu") or t.get("Protiúčet") or "").strip()
    return ucet.split("/")[0].strip()


def aplikuj_interni_prevod(transakce: list[dict]) -> list[dict]:
    """
    Přepíše kategorii na "Převod" u transakcí, jejichž protiúčet je interní
    účet skupiny (FIREMNI_UCTY).

    Výjimky, kdy kategorie zůstává (nejde o obyčejný přesun peněz):
      - kategorie sama tento protiúčet deklaruje v configu (Splátka → úvěrové
        účty MONETA, Výplata majitele → účty Radka Danče, Kotlářská → Casa
        Příjmový…) – jde o záměrně zvlášť sledovaný interní tok;
      - kategorii určil explicitní ruční štítek (deterministika.py, poznámka
        začíná POZNAMKA_STITEK_PREFIX). Ruční štítek je nejspolehlivější signál,
        jaký máme, a má přednost i před firemním protiúčtem (rozhodnutí
        uživatele 10/2026) – např. tankování placené mezi vlastními účty se
        štítkem „Benzín" zůstává „Benzín", ne „Převod".
    """
    povolene_kategorie: dict[str, set[str]] = {}
    for k in KATEGORIE + KATEGORIE_PRIJMOVE:
        for ucet in k.get("protiucty") or []:
            povolene_kategorie.setdefault(ucet.strip(), set()).add(k["nazev"])

    for t in transakce:
        protiucet = _protiucet(t)
        if not protiucet or protiucet not in FIREMNI_UCTY:
            continue
        kategorie = t.get("Kategorie", "")
        puvodni_poznamka = t.get("Poznamka", "")
        if (
            kategorie == "Převod"
            or kategorie in povolene_kategorie.get(protiucet, set())
            or kategorie in KATEGORIE_PREZIJI_INTERNI_PREVOD
            or puvodni_poznamka.startswith(POZNAMKA_STITEK_PREFIX)
        ):
            continue
        t["Kategorie"] = "Převod"
        t["Poznamka"] = (
            f"{puvodni_poznamka} Přepsáno z '{kategorie}' na 'Převod' – protiúčet "
            f"{protiucet} je firemní účet ({FIREMNI_UCTY[protiucet]})."
        ).strip()

    return transakce


def _bez_diakritiky(s: str) -> str:
    return (
        s.lower()
        .replace("á", "a").replace("í", "i").replace("é", "e").replace("ě", "e")
        .replace("ý", "y").replace("ř", "r").replace("š", "s")
        .replace("č", "c").replace("ž", "z").replace("ů", "u")
        .replace("ú", "u").replace("ň", "n").replace("ť", "t").replace("ď", "d")
    )


def _soubor_patri_uctu(nazev_souboru: str, cislo_uctu: str, klicove_slovo: str) -> bool:
    """
    Pozná výpis daného účtu z názvu souboru dvěma způsoby:
      1. Fio export obsahuje číslo účtu v názvu ("Vypis_z_uctu-<cislo_uctu>_...")
         -> porovná se s cislo_uctu.
      2. Soubor je ručně pojmenovaný popisně a obsahuje klicove_slovo
         (case-insensitive, bez diakritiky) -> např. "Nesty Ostatní.csv",
         "RD Ostatní (1).csv".
    """
    zaklad = os.path.basename(nazev_souboru)

    m = re.search(r"Vypis_z_uctu-(\d+)", zaklad)
    if m and cislo_uctu and m.group(1) == cislo_uctu:
        return True

    # Oddělovače (-, _, .) sjednotit na mezeru, aby klíčové slovo "casa prijmovy"
    # trefilo i názvy jako "09-2026-casa-prijmovy-1" (backtest / data/<mesic>/).
    text = _bez_diakritiky(zaklad).replace("-", " ").replace("_", " ").replace(".", " ")
    return klicove_slovo in text


def _je_ucet_ostatni(nazev_souboru: str) -> bool:
    return _soubor_patri_uctu(nazev_souboru, UCET_NESTY_OSTATNI, "ostatni")


def _slozka_prijem_vydaj(nazev_souboru: str) -> str | None:
    """
    Pozná směr výpisu "prijmove" / "vydajove" / None:
      1. podle rodičovské složky transactions/Prijmove nebo /Vydajove,
      2. jako záloha podle názvu souboru (token "prijmov"/"vydajov"), když výpis
         leží ploše (např. backtest data/<mesic>/09-2026-rd-vydajovy-1.xlsx).
    """
    slozka = _bez_diakritiky(os.path.basename(os.path.dirname(nazev_souboru)))
    if slozka == "prijmove":
        return "prijmove"
    if slozka == "vydajove":
        return "vydajove"
    zaklad = _bez_diakritiky(os.path.basename(nazev_souboru))
    if "vydajov" in zaklad:
        return "vydajove"
    if "prijmov" in zaklad:
        return "prijmove"
    return None

def omezene_kategorie_pro_soubor(nazev_souboru: str) -> list[str] | None:
    """
    Pro výpisy s historicky omezenou nabídkou kategorií vrátí seznam, ze
    kterého má AI vybírat (pro ai.kategorizuj_transakce), jinak None.

    Prohledá nejdřív OMEZENE_KATEGORIE_PODLE_UCTU (config.py) podle čísla
    účtu nebo klíčového slova v názvu souboru (viz _soubor_patri_uctu) –
    klíč slovníku je jen identifikátor záznamu, není potřeba znát
    firma_nazev. Každý záznam má buď "kategorie" (uzavřený POVOLOVACÍ
    seznam – AI smí vybrat jen z něj, např. RD Ostatní), nebo "vyloucene"
    (VYLUČOVACÍ seznam – AI smí vybrat cokoliv KROMĚ těchto kategorií,
    např. Pokladna, kde nikdy nesmí vyjít "Výdaje majitele"). Volitelný
    klíč "vychozi" (viz aplikuj_vychozi_kategorii_ucet) navíc určuje
    kategorii, na kterou se na konci pipeline přepíše úplně všechno na
    tomto účtu, co skončí jinak než "Převod".

    Když nic z toho nesedí, spadne na rozdělení podle složky (viz
    _slozka_prijem_vydaj) – transactions/Prijmove/ dostane jen
    KATEGORIE_PRIJMOVE, transactions/Vydajove/ jen KATEGORIE.
    """
    for klic, zaznam in OMEZENE_KATEGORIE_PODLE_UCTU.items():
        if not _soubor_patri_uctu(nazev_souboru, klic, zaznam["klicove_slovo"]):
            continue
        if "kategorie" in zaznam:
            return zaznam["kategorie"]
        vyloucene = set(zaznam.get("vyloucene", []))
        vsechny_kategorie = [k["nazev"] for k in KATEGORIE + KATEGORIE_PRIJMOVE]
        return [n for n in vsechny_kategorie if n not in vyloucene]

    smer = _slozka_prijem_vydaj(nazev_souboru)
    if smer == "prijmove":
        return [k["nazev"] for k in KATEGORIE_PRIJMOVE]
    if smer == "vydajove":
        return [k["nazev"] for k in KATEGORIE]
    return None


def aplikuj_vychozi_kategorii_ucet(
    transakce: list[dict],
    nazev_souboru: str,
) -> list[dict]:
    """
    Na účtech s definovaným "vychozi" v OMEZENE_KATEGORIE_PODLE_UCTU
    (rozhodnutí uživatele 08/2026: Casa a Nesty Příjmový nemají historicky
    žádný jiný příjem než ubytování mimo OTA kanály) přepíše kategorii na
    tuhle výchozí hodnotu u KAŽDÉ transakce, jejíž finální kategorie není
    "Převod" – bez ohledu na to, co k ní AI nebo dřívější přepisy došly
    (Neurčeno mimo uzavřený seznam, chybně odhadnutá jiná příjmová
    kategorie…). Musí běžet AŽ PO všech ostatních přepisech (hlavně
    aplikuj_interni_prevod), jinak by přepsal i skutečné interní převody.
    """
    for klic, zaznam in OMEZENE_KATEGORIE_PODLE_UCTU.items():
        vychozi = zaznam.get("vychozi")
        if not vychozi:
            continue
        if not _soubor_patri_uctu(nazev_souboru, klic, zaznam["klicove_slovo"]):
            continue
        povolene = set(zaznam.get("kategorie") or [])
        for t in transakce:
            kategorie = t.get("Kategorie", "")
            # Nepřepisovat kategorie legitimně povolené pro tento účet
            # (zaznam["kategorie"] – např. Airbnb, Snídaně Příjem, Mamka nájem,
            # Úrok, Vratka), "Převod" (nepřepisuje se ani tam, kde v seznamu
            # není – Nesty), ani kategorie přežívající interní převod (Prostory
            # Příjem). vychozi je jen pro Neurčeno / zbytkové chyby.
            if (
                kategorie in (vychozi, "Převod")
                or kategorie in povolene
                or kategorie in KATEGORIE_PREZIJI_INTERNI_PREVOD
            ):
                continue
            puvodni_poznamka = t.get("Poznamka", "")
            t["Kategorie"] = vychozi
            t["Poznamka"] = (
                f"{puvodni_poznamka} Přepsáno z '{kategorie}' na výchozí kategorii "
                f"'{vychozi}' – na tomto účtu je to jediná příjmová kategorie pro "
                f"vše, co není Převod."
            ).strip()
        break

    return transakce


def aplikuj_kotlarska_pronajem_bytu(
    transakce: list[dict],
    nazev_souboru: str,
    firma_nazev: str,
) -> list[dict]:
    """
    Na účtu RD Příjmový přepíše kategorii na "Kotlářská" u transakcí se
    štítkem "pronájem bytu" v Poznámce – bez ohledu na to, co AI vybrala
    podle protiúčtu (často sdíleného s Casa Libre Příjmový, což ji svádí
    k obecnému "Převod").
    """
    if firma_nazev != "RD" or not _soubor_patri_uctu(nazev_souboru, UCET_RD_PRIJMOVY, "prijmovy"):
        return transakce

    for t in transakce:
        text = _bez_diakritiky(_text_transakce(t))
        if not any(klic in text for klic in KLICOVA_SLOVA_KOTLARSKA_RD_PRIJMOVY):
            continue
        if t.get("Kategorie") != "Kotlářská":
            puvodni_poznamka = t.get("Poznamka", "")
            puvodni_kategorie = t.get("Kategorie")
            t["Kategorie"] = "Kotlářská"
            t["Poznamka"] = (
                f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na 'Kotlářská' – "
                f"účet RD Příjmový a štítek 'pronájem bytu' vždy patří k nájmu Kotlářská."
            ).strip()

    return transakce


def aplikuj_prostory_nesty_prijmovy(
    transakce: list[dict],
    nazev_souboru: str,
    firma_nazev: str,
) -> list[dict]:
    """
    Na účtu Nesty Příjmový přepíše příchozí platbu na "Prostory Příjem", když
    protiúčet patří firmě RD (RD_UCTY) A text zmiňuje "prostor" (nájem prostor
    X.01/E03/E09). Musí běžet AŽ PO aplikuj_interni_prevod – ten tyhle platby
    (firemní protiúčet) nejdřív označí "Převod", tohle je přepíše zpátky.

    Obě podmínky jsou nutné: samotný RD protiúčet nese i běžné interní převody
    (RD Příjmový → Nesty) bez nájmu prostor, a samotný text "prostor" se
    objevuje i u nájmu ubytování od externích hostů (jiný protiúčet).
    """
    if firma_nazev != "Nesty" or not _soubor_patri_uctu(
        nazev_souboru, UCET_NESTY_PRIJMOVY, "nesty prijmov"
    ):
        return transakce

    for t in transakce:
        if _protiucet(t) not in RD_UCTY:
            continue
        if "prostor" not in _bez_diakritiky(_text_transakce(t)):
            continue
        castka = _parsuj_castku(t.get("Objem", ""))
        if castka is None or castka <= 0:
            continue  # Prostory Příjem je příjem – odchozí platby ignoruj
        if t.get("Kategorie") != "Prostory Příjem":
            puvodni_poznamka = t.get("Poznamka", "")
            puvodni_kategorie = t.get("Kategorie")
            t["Kategorie"] = "Prostory Příjem"
            t["Jistota kategorie"] = 100
            t["Poznamka"] = (
                f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na "
                f"'Prostory Příjem' – Nesty Příjmový, protiúčet z RD a text "
                f"'prostor' (nájem prostor sloužících podnikání)."
            ).strip()

    return transakce


def aplikuj_jidlo_podle_provedl(
    transakce: list[dict],
    nazev_souboru: str,
    firma_nazev: str,
) -> list[dict]:
    """
    Přepíše kategorii "Jídlo" na osobní výdaj podle karty, kterou byl nákup proveden.

    Platí VÝHRADNĚ pro firmu Nesty a účet Ostatní – poznaný buď podle čísla účtu
    (UCET_NESTY_OSTATNI v config.py), nebo podle slova "ostatní" v názvu souboru
    (viz _je_ucet_ostatni). Bez ani jedné shody se pravidlo neaplikuje vůbec
    (žádný fallback na celou firmu) – riskovali bychom přepsání legitimních
    firemních nákupů jídla na jiných účtech.
    """
    if firma_nazev != "Nesty" or not _je_ucet_ostatni(nazev_souboru):
        return transakce

    for t in transakce:
        puvodni_kategorie = t.get("Kategorie")
        if puvodni_kategorie not in KATEGORIE_PREPIS_PODLE_PROVEDL:
            continue
        provedl = (t.get("Provedl") or "").lower()
        for jmeno, nova_kategorie in JIDLO_PODLE_PROVEDL.items():
            if jmeno in provedl:
                puvodni_poznamka = t.get("Poznamka", "")
                t["Kategorie"] = nova_kategorie
                t["Poznamka"] = (
                    f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na "
                    f"'{nova_kategorie}' podle karty ({t.get('Provedl', '')})."
                ).strip()
                break

    return transakce


def aplikuj_pradlo_pokladna(transakce: list[dict], firma_nazev: str) -> list[dict]:
    """
    Na Pokladně popisek obsahující "prádlo" (např. "Petr prádlo", "ostatní
    Petr výplata prádlo") vždy patří do kategorie "Recepční" – jde o odměnu
    recepční/recepčnímu za vyprané prádlo v hotovosti, ne o platbu externí
    prádelně (ta se řeší fakturou od Christofa, kategorie "Prádelna").
    """
    if firma_nazev != "Pokladna":
        return transakce

    for t in transakce:
        text = _bez_diakritiky(_text_transakce(t))
        if "pradlo" not in text or t.get("Kategorie") == "Recepční":
            continue
        puvodni_poznamka = t.get("Poznamka", "")
        puvodni_kategorie = t.get("Kategorie")
        t["Kategorie"] = "Recepční"
        t["Poznamka"] = (
            f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na 'Recepční' – "
            f"na Pokladně popisek 'prádlo' je odměna recepční, ne externí prádelna."
        ).strip()

    return transakce


def aplikuj_jmena_pokladna(transakce: list[dict], firma_nazev: str) -> list[dict]:
    """
    Na Pokladně popisek se jménem z POKLADNA_JMENA_KATEGORIE (celé slovo,
    bez diakritiky) je hotovostní výplata/odměna dané osoby → její kategorie
    (Petr → Recepční, Vendula/Iva → Úklid). Ověřeno na schválené historii.
    """
    if firma_nazev != "Pokladna":
        return transakce

    for t in transakce:
        text = _bez_diakritiky(_text_transakce(t))
        slova = set(re.findall(r"[a-z]+", text))
        for jmeno, nova_kategorie in POKLADNA_JMENA_KATEGORIE.items():
            if jmeno not in slova or t.get("Kategorie") == nova_kategorie:
                continue
            puvodni_poznamka = t.get("Poznamka", "")
            puvodni_kategorie = t.get("Kategorie")
            t["Kategorie"] = nova_kategorie
            t["Poznamka"] = (
                f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na '{nova_kategorie}' – "
                f"hotovostní výplata/odměna ({jmeno.capitalize()}) na Pokladně."
            ).strip()
            break

    return transakce


def aplikuj_jidlo_pokladna(transakce: list[dict], firma_nazev: str) -> list[dict]:
    """
    Na Pokladně hotovostní nákupy pečiva/snídaní ("Ostatní - pečivo, snídaně")
    patří do "Jídlo", ne "Snídaně Výdaj" – rozhodnutí uživatele 07/2026. Kategorie
    "Snídaně Výdaj" je pro fakturované snídaně, ne drobné hotovostní nákupy.
    """
    if firma_nazev != "Pokladna":
        return transakce

    for t in transakce:
        text = _bez_diakritiky(_text_transakce(t))
        if ("pecivo" not in text and "snidan" not in text) or t.get("Kategorie") == "Jídlo":
            continue
        puvodni_poznamka = t.get("Poznamka", "")
        puvodni_kategorie = t.get("Kategorie")
        t["Kategorie"] = "Jídlo"
        t["Poznamka"]
        (
            f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na 'Jídlo' – "
            f"hotovostní nákup pečiva/snídaně na Pokladně je Jídlo."
        ).strip()

    return transakce


def _parsuj_castku(s: str) -> float | None:
    s = (s or "").strip().replace(" ", "").replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def aplikuj_prevod_zpetna_platba(transakce: list[dict]) -> list[dict]:
    """
    Přepíše kategorii "Splátka" na "Převod", pokud na stejném protiúčtu existuje
    jiná transakce se stejnou absolutní částkou a opačným znaménkem (peníze se
    tam a zpět jen přesunuly, nešlo o skutečnou splátku úvěru).
    """
    skupiny_podle_uctu: dict[str, list[dict]] = defaultdict(list)
    for t in transakce:
        protiucet = _protiucet(t)
        if protiucet:
            skupiny_podle_uctu[protiucet].append(t)

    spareno: set[int] = set()
    for protiucet, skupina in skupiny_podle_uctu.items():
        for t in skupina:
            if t.get("Kategorie") != "Splátka" or id(t) in spareno:
                continue
            castka = _parsuj_castku(t.get("Objem", ""))
            if castka is None:
                continue
            for druhy in skupina:
                if druhy is t or id(druhy) in spareno:
                    continue
                druha_castka = _parsuj_castku(druhy.get("Objem", ""))
                if druha_castka is not None and abs(druha_castka + castka) < 0.01:
                    for radek in (t, druhy):
                        if radek.get("Kategorie") == "Splátka":
                            puvodni_poznamka = radek.get("Poznamka", "")
                            radek["Kategorie"] = "Převod"
                            radek["Poznamka"] = (
                                f"{puvodni_poznamka} Přepsáno z 'Splátka' na 'Převod' – "
                                f"částka se na protiúčtu {protiucet} vrátila zpět."
                            ).strip()
                        spareno.add(id(radek))
                    break

    return transakce


def aplikuj_telefony_nejvyssi_castka(transakce: list[dict]) -> list[dict]:
    """
    Z plateb na účtu T-Mobile (UCET_TMOBILE) je "Telefony" jen ta s nejvyšší
    absolutní částkou v daném výpisu, ostatní se přepíšou na "Zvláštní výdaj".
    """
    tmobile = [
        t for t in transakce
        if _protiucet(t) == UCET_TMOBILE
        and t.get("Kategorie") in ("Telefony", "Zvláštní výdaj")
    ]

    castky = [(abs(c), t) for t in tmobile if (c := _parsuj_castku(t.get("Objem", ""))) is not None]
    if len(castky) < 2:
        return transakce

    nejvyssi_t = max(castky, key=lambda x: x[0])[1]

    for _, t in castky:
        nova_kategorie = "Telefony" if t is nejvyssi_t else "Zvláštní výdaj"
        if t.get("Kategorie") != nova_kategorie:
            puvodni_poznamka = t.get("Poznamka", "")
            puvodni_kategorie = t.get("Kategorie")
            t["Kategorie"] = nova_kategorie
            t["Poznamka"] = (
                f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na '{nova_kategorie}' "
                f"– {'nejvyšší' if nova_kategorie == 'Telefony' else 'není nejvyšší'} platba T-Mobile ve výpisu."
            ).strip()

    return transakce


def _text_transakce(t: dict) -> str:
    casti = [
        t.get("Název protiúčtu", ""),
        t.get("Poznámka", ""),
        t.get("Zpráva pro příjemce", ""),
    ]
    return " ".join(c for c in casti if c).lower()


def aplikuj_vzdy_dodavatel(
    transakce: list[dict],
    omezene_kategorie: list[str] | None = None,
) -> list[dict]:
    """
    Pro dodavatele z VZDY_DODAVATEL_KATEGORIE je kategorie vždy stejná bez
    ohledu na znaménko částky (nákup i vratka/refundace) – s výjimkami
    z VYJIMKY_VZDY_DODAVATEL podle dalšího klíčového slova v textu (např.
    "Alza" + "V24" je "V24", ne obecné "Dekorace").

    Pokud má výpis uzavřený seznam kategorií (omezene_kategorie – viz
    prepisy.omezene_kategorie_pro_soubor), pravidlo se NEUPLATNÍ, pokud
    výsledná kategorie do tohoto seznamu nepatří – jinak by přepsalo správně
    omezenou AI kategorizaci (např. "alza" → "Dekorace" na účtu RD Ostatní,
    kde smí být jen Benzín / Výdaje majitele / Převod).
    """
    for t in transakce:
        text = _text_transakce(t)
        for klic, obecna_kategorie in VZDY_DODAVATEL_KATEGORIE.items():
            if klic not in text:
                continue

            nova_kategorie = obecna_kategorie
            vyjimecne_slovo = None
            for extra_slovo, vyjimecna_kategorie in VYJIMKY_VZDY_DODAVATEL.get(klic, []):
                if extra_slovo in text:
                    nova_kategorie = vyjimecna_kategorie
                    vyjimecne_slovo = extra_slovo
                    break

            if omezene_kategorie is not None and nova_kategorie not in omezene_kategorie:
                break
            if t.get("Kategorie") != nova_kategorie:
                puvodni_poznamka = t.get("Poznamka", "")
                puvodni_kategorie = t.get("Kategorie")
                t["Kategorie"] = nova_kategorie
                if vyjimecne_slovo:
                    t["Poznamka"] = (
                        f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na '{nova_kategorie}' "
                        f"– dodavatel '{klic}' je obvykle '{obecna_kategorie}', ale text obsahuje "
                        f"'{vyjimecne_slovo}' → výjimka na '{nova_kategorie}'."
                    ).strip()
                else:
                    t["Poznamka"] = (
                        f"{puvodni_poznamka} Přepsáno z '{puvodni_kategorie}' na '{nova_kategorie}' "
                        f"– dodavatel '{klic}' je vždy tato kategorie bez ohledu na znaménko částky."
                    ).strip()
            break

    return transakce


# Suffix řádku, který signalizuje "člověk MUSÍ doplnit ručně" (kategorie
# mimo MAPOVANI_NA_FORMULAR – Neurčeno, prázdná, neznámý štítek). Odlišuje
# je od vědomě nenamapovaných interních toků (None v mapě → čisté P00/N00).
RADEK_RUCNI_SUFFIX = "*"
_CHYBI_V_MAPE = object()


def _radek_pro_kategorii(kategorie: str, objem: str | None, mena: str | None) -> str:
    """
    Namapuje kategorii na ID řádku Alokačního formuláře (config.MAPOVANI_NA_FORMULAR).

    "P<n>" = příjmový řádek, "N<n>" = výdajový řádek.

    Dvě různé "nenamapované" situace se ODLIŠUJÍ, ať člověk ví, co dořešit:
      - kategorie NENÍ v MAPOVANI_NA_FORMULAR vůbec (Neurčeno, prázdná,
        neznámý štítek) → "P00*"/"N00*" s hvězdičkou: AI/štítek nestačily,
        řádek MUSÍ doplnit člověk ručně;
      - kategorie je v mapě s hodnotou None (vědomě bez řádku – interní tok
        jako Převod/Kauce/Rezervní nebo čeká na klienta, viz
        docs/otazky-pro-klienta.md) → "P00"/"N00" BEZ hvězdičky: je to
        záměrné, nic se nedoplňuje.
    Peníze se tak nikdy neztratí potichu a ruční práce je na první pohled vidět.
    """
    prefix = "P" if kategorie in _KATEGORIE_PRIJMOVE_NAZVY else "N"
    nenamapovano = f"{prefix}00"
    rucni = nenamapovano + RADEK_RUCNI_SUFFIX
    cil = MAPOVANI_NA_FORMULAR.get(kategorie, _CHYBI_V_MAPE)
    if cil is _CHYBI_V_MAPE:
        return rucni
    if cil is None:
        return nenamapovano
    if isinstance(cil, str):
        return cil
    if "+" in cil or "-" in cil:
        castka = _parsuj_castku(objem) or 0.0
        return cil.get("+" if castka >= 0 else "-", rucni)
    # currency-keyed dict, např. {"CZK": "P4", "EUR": "P6"}
    return cil.get((mena or "CZK").strip().upper(), rucni)

def aplikuj_radek_formulare(transakce: list[dict], firma_nazev: str) -> list[dict]:
    """
    Doplní ke každé transakci sloupce "Firma" (název firmy dle složky) a
    "Radek" (ID řádku Alokačního formuláře, viz _radek_pro_kategorii výš).
    Musí běžet AŽ PO všech ostatních přepisech, protože se řídí finální
    kategorií transakce.
    """
    for t in transakce:
        t["Firma"] = firma_nazev
        t["Radek"] = _radek_pro_kategorii(t.get("Kategorie", ""), t.get("Objem"), t.get("Měna"))
    return transakce
