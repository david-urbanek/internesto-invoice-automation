"""
Statická konfigurace: kategorie výdajů, firemní účty a aliasy štítků.

Edituj tento soubor když:
  - přibude nová kategorie nebo dodavatel
  - Fio banka začne používat jiný název protistrany
  - přibude nový firemní účet (FIREMNI_UCTY)
  - uživatel ručně napsal jiný štítek než kanonický název (ALIASY)
"""

FIRMY_SLOZKA = "firmy"
CSV_SEPARATOR = ";"
MODEL = "gemini-2.5-flash"

# ---------------------------------------------------------------------------
# Aliasy názvů sloupců v CSV výpisech
# ---------------------------------------------------------------------------
# Kategorizace (ai.py) a přepisy (prepisy.py) čekají kanonické názvy sloupců
# z Fio bankovního výpisu (Datum, Objem, Poznámka, VS, Provedl…). Některé
# zdroje (např. pokladní kniha) mají stejný obsah, ale jiné názvy sloupců –
# tady se namapují na kanonický název, PŘIDÁ se jako nový klíč vedle
# původního (žádná data se neztratí, výstupní CSV má oba). Aplikuje se
# v io.nacti_csv pro každý řádek, jen pokud kanonický klíč ještě neexistuje.
ALIASY_SLOUPCU_CSV: dict[str, str] = {
    "Datum platby": "Datum",
    "Příjem/Výdej": "Objem",
    "Popis": "Poznámka",
    "VS dokladu": "VS",
    "Uživatel": "Provedl",
}

# Všechny interní účty skupiny (Fio, MONETA, Raiffeisen, Air Bank).
# Transakce s protiúčtem z tohoto seznamu je interní převod → kategorie
# "Převod", POKUD přiřazená kategorie daný protiúčet sama nedeklaruje
# v protiucty (Splátka, Výplata majitele, Kotlářská…) – viz
# aplikuj_interni_prevod() v prepisy.py.
FIREMNI_UCTY = {
    # RD Group s.r.o.
    "2200973033": "RD Group s.r.o. | Příjmový 1 CZK (Fio)",
    "2301780732": "RD Group s.r.o. | Příjmový 2 EUR (Fio)",
    "2901813198": "RD Group s.r.o. | Výdajový 1 CZK (Fio)",
    "2601728813": "RD Group s.r.o. | Výdajový 2 CZK (Fio)",
    "2901321222": "RD Group s.r.o. | Ostatní CZK (Fio)",
    "2203097403": "RD Group s.r.o. | Premier Fond (Fio)",
    "2402351507": "RD Group s.r.o. | Rezervní 1 (Fio)",
    "2102351505": "RD Group s.r.o. | Rezervní 2 (Fio)",
    "2602411244": "RD Group s.r.o. | Rezervní 3 (Fio)",
    "4877715":    "RD Group s.r.o. | Příjmový / úvěrový (Raiffeisen 5500)",
    "6102102232": "RD Group s.r.o. | Raiffeisen",
    "6430097786": "RD Group s.r.o. | Raiffeisen (úvěr)",
    "249102969":  "RD Group s.r.o. | MONETA (úvěr)",
    "249102977":  "RD Group s.r.o. | MONETA",
    "261119667":  "RD Group s.r.o. | MONETA",
    # Casa Libre s.r.o.
    "2201422348": "Casa Libre s.r.o. | Příjmový 1 CZK (Fio)",
    "2401780748": "Casa Libre s.r.o. | Příjmový 1 EUR (Fio)",
    "2601813209": "Casa Libre s.r.o. | Výdajový 1 CZK (Fio)",
    "2002351495": "Casa Libre s.r.o. | Rezervní 1 (Fio)",
    "2102351492": "Casa Libre s.r.o. | Rezervní 2 (Fio)",
    "249103128":  "Casa Libre s.r.o. | MONETA (úvěr)",
    "249103136":  "Casa Libre s.r.o. | MONETA",
    "276191995":  "Casa Libre s.r.o. | MONETA",
    # Nesty Services s.r.o.
    "2301240402": "Nesty Services s.r.o. | Příjmový 1 CZK (Fio)",
    "2201830907": "Nesty Services s.r.o. | Výdajový 1 CZK (Fio)",
    "2301780716": "Nesty Services s.r.o. | Ostatní CZK (Fio)",
    "2802351514": "Nesty Services s.r.o. | Rezervní 1 CZK (Fio)",
    "249099667":  "Nesty Services s.r.o. | MONETA (úvěr)",
    "249099739":  "Nesty Services s.r.o. | MONETA",
    # Fyzické osoby
    "2400860172": "Radek Danč | FO (Fio)",
    "1177419055": "Radek Danč | FO (Air Bank)",
    "1177419047": "Radek Danč | FO (Air Bank)",
    "1177419020": "Radek Danč | jednatel / společník (Air Bank)",
    "5845640002": "Ing. Radek Danč | společník",
    "2401715997": "Tomáš Opravil (Fio)",
    "2402543103": "Tomáš Opravil (Fio)",
}

KATEGORIE = [
    # =======================================================================
    # PROVOZ APARTMÁNŮ – nákupy a služby
    # =======================================================================
    {
        "nazev": "Dekorace",
        "popis": "Nákupy vybavení, nábytku a doplňků pro bytové jednotky.",
        "dodavatele": ["Alza", "Hornbach", "JYSK", "Mobelix", "IKEA", "Conrad",
                       "Datart", "SmartKey", "SIKO", "Bonami", "Pepco",
                       "Podlahový ráj", "Drogeo.cz"],
        "protiucty": ["2171532", "4228119399", "2531920104", "2000295311"],
        "klicova_slova": ["OBJEDNAVKA", "ALZA.CZ"],
    },
    {
        "nazev": "Drogerie",
        "popis": "Spotřební hygienické a čisticí potřeby pro provoz.",
        "dodavatele": ["Herout", "dm drogerie", "Drogeo.cz", "Drogerie Rabek",
                       "Rossmann", "DR. MAX"],
        "protiucty": ["27-5829880217"],
        "klicova_slova": ["FAKTURUJEME VAM ZBOZI"],
    },
    {
        "nazev": "Prádelna",
        "popis": "Praní prádla pro apartmány (Christof). Historicky štítkováno i 'Chrištof'.",
        "dodavatele": ["Christof"],
        "protiucty": ["306744731"],
    },
    {
        "nazev": "Technik",
        "popis": "Údržba a technické práce.",
        "dodavatele": ["Michal Říčánek", "Igor", "Igor Martof"],
        "protiucty": ["123-5811180247", "2002124604", "2300245551"],
        "klicova_slova": ["údržba"],
    },
    {
        "nazev": "Netflix a Spotify",
        "popis": "Předplatné streamovacích služeb v apartmánech pro hosty.",
        "dodavatele": ["Netflix", "Spotify"],
        "klicova_slova": ["NETFLIX.COM", "Spotify"],
    },
    {
        "nazev": "Taxi",
        "popis": "Doprava taxislužbou (Bolt) – služební cesty.",
        "dodavatele": ["Bolt"],
        "protiucty": ["2552940200"],
        "klicova_slova": ["BOLT.EU"],
    },
    {
        "nazev": "Google",
        "popis": "Google Cloud / Workspace – IT/provozní náklady.",
        "dodavatele": ["Google", "Google CLOUD"],
        "protiucty": ["2500900397"],
    },
    # POZN.: kategorie "Multisport" sloučena do "Ostatní služby" (07/2026)
    # – dodavatel i protiúčet 2104561127 tam už byly, viz ALIASY.
    {
        "nazev": "Ostatní služby",
        "popis": "Různé služby nezařaditelné jinam (callcentrum, pošta, drobné poplatky).",
        "dodavatele": ["Daktela", "AirWallet", "Česká pošta", "Multisport", "Coma Jurny", "Burda Design"],
        "protiucty": ["2078745001", "2104561127", "170158265"],
        "klicova_slova": ["FAKTURUJEME VAM ZA", "AIRWALLET", "Coma Jurny", "Burda Design"],
    },
    {
        "nazev": "Jídlo",
        "popis": "Potraviny a suroviny (snídaně pro hosty, provoz).",
        "dodavatele": ["Rohlik.cz", "Bidfood", "Lidl", "Tesco", "Nok Nok",
                       "La Formaggeria", "Matějovo pekařství"],
        "protiucty": ["8010-616742803", "86-883970237"],
        "klicova_slova": ["ROHLIK.CZ", "pečivo", "snídan"],
    },
    {
        "nazev": "Reprezentace",
        "popis": "Reprezentace – dárky, pohoštění, drobné občerstvení.",
        "dodavatele": ["Qerko", "Matějovo pekařství", "Pivnice", "J&T banka cafe"],
        "protiucty": ["2400406244"],
        "klicova_slova": ["dárek", "Reprezentace", "narozeniny", "teambuilding", "svátek"],
    },
    {
        "nazev": "Kancelář",
        "popis": "Kancelářské potřeby a tisk.",
        "dodavatele": ["Papír"],
        "klicova_slova": ["Kancelář", "tisk", "Papir"],
    },
    {
        "nazev": "Poplatek",
        "popis": "Pokuty a drobné poplatky (radary, ATM poplatky, správní pokuty). "
                 "POZOR: 'Poplatek z ubytovací kapacity' patří do Rezervní 1.",
        "dodavatele": [],
        "protiucty": [],
        "klicova_slova": ["Pokuta", "RADARY"],
    },
    {
        "nazev": "Banka",
        "popis": "Hotovostní operace s bankou z pokladny (odvod/vklad hotovosti do banky, "
                 "typicky Radek). Štítek 'Banka' nebo 'Radek - banka'.",
        "dodavatele": [],
        "protiucty": [],
        "klicova_slova": ["Radek - banka"],
    },

    # =======================================================================
    # MZDY A LIDÉ (dle přehledu mezd)
    # =======================================================================
    {
        "nazev": "Úklid",
        "popis": "Mzdy a odměny úklidového personálu + související (exekutor, úřad práce). Dle přehledu mezd.",
        "dodavatele": ["Beltsyk Olha", "Gavlas Radoslav", "Conkova Lucie",
                       "Sarayova Lucie", "Hejna Veronika", "Pospisilova Marie",
                       "Hlouskova Marcela", "Hadbavna Julia Sofia", "Podlouckova Katerina",
                       "Kuswitova Shabrina", "Necasova Lucie", "Bostik Zbynek",
                       "Marosova", "Dobos", "Soudni exekutor", "Urad prace",
                       "Drackova Michaela", "Hyzova Natalia", "Melichova Emma"],
        "protiucty": ["354003954", "6015-229761", "115-1648560267", "3055051183",
                      "3799998003", "129886578",
                      # doplněno z analýzy schválených výpisů leden–květen 2026
                      # (100% konzistentní, 3+ výskyty)
                      "2900681939", "2535398069", "4121512043", "330641230",
                      "254203430", "86-138790287", "1186374047", "1024086325",
                      "2800959278",
                      "1289314063"],  # Zelená Iva (od 05/2026)
    },
    {
        "nazev": "Recepční",
        "popis": "Mzdy a odměny recepčních. Dle přehledu mezd.",
        "dodavatele": ["Aneta Hrušková", "Petr Moravčík", "Pavlína Jadrná",
                       "Bartonova Katerina", "Zalkovska Lucie", "Rybarova Ema",
                       "Lipenska Sara", "Jezkova Eliska"],
        "protiucty": ["346775719", "35-1336730247", "23806170", "3020639163",
                      "2703187907", "1863183011"],
    },
    {
        "nazev": "Design",
        "popis": "Odměna za designové práce (Zuzana Dančová). Dle přehledu mezd.",
        "dodavatele": ["Dancova Zuzana"],
        "protiucty": ["1616038044"],
    },
    {
        "nazev": "Výplata majitele",
        "popis": "Opakující se výplata jednateli / společníkovi. Stanoveno finančním manažerem.",
        "dodavatele": ["Radek Danč", "Jednatel"],
        "protiucty": ["1177419020", "5845640002"],
        "klicova_slova": ["Jednatel"],
    },

    # =======================================================================
    # ODVODY STÁTU
    # =======================================================================
    {
        "nazev": "FU",
        "popis": "Platby finančnímu úřadu (daně ze závislé činnosti, daň z nemovitosti). "
                 "Dle přehledu mezd.",
        "dodavatele": [],
        "protiucty": ["7720-77628621", "713-77628621", "7755-77628621"],
        "klicova_slova": ["FU", "Dan z nemovitosti"],
    },
    {
        "nazev": "Socka",
        "popis": "Sociální pojištění – OSSZ. Dle přehledu mezd.",
        "dodavatele": ["OSSZ"],
        "protiucty": ["21012-7929621"],
    },
    {
        "nazev": "Zdravka",
        "popis": "Zdravotní pojištění zaměstnanců. Dle přehledu mezd.",
        "dodavatele": ["Zdravotni pojistovna ministerstva", "Revirni bratrska pokladna"],
        "protiucty": ["2115106031", "2130000761"],
    },
    {
        "nazev": "DPH",
        "popis": "Platba DPH finančnímu úřadu (RD i Nesty). Bez dokladu.",
        "dodavatele": [],
        # 2203097403 odstraněn – platby na Premier Fond jsou VŽDY "Premier"
        # (rozhodnutí uživatele 07/2026, viz UCET_VZDY_KATEGORIE)
        "protiucty": ["705-77628621"],
        "klicova_slova": ["DPH"],
    },

    # =======================================================================
    # PROVIZE A SYSTÉMY
    # =======================================================================
    {
        "nazev": "Booking",
        "popis": "Provize Booking.com. Dle FA.",
        "dodavatele": ["Booking"],
        "protiucty": ["4030400003"],
        "klicova_slova": ["Booking provize"],
    },
    {
        "nazev": "Previo systém",
        "popis": "Rezervační systém Previo. Dle FA.",
        "dodavatele": ["Previo"],
        "protiucty": ["5125975234"],
        "klicova_slova": ["Previo system"],
    },
    {
        "nazev": "Provize Previo",
        "popis": "Provize z prodeje přes Previo / Hotely.cz / Szallas. Dle FA.",
        "dodavatele": ["Hotely.cz", "Szallas", "Previo provize"],
        "protiucty": ["5125975234", "2534260105"],
        "klicova_slova": ["provize"],
    },

    # =======================================================================
    # IT / TELEKOMUNIKACE
    # =======================================================================
    {
        "nazev": "Internet",
        "popis": "Připojení k internetu pro objekty. Dle FA.",
        "dodavatele": ["Brnet", "Global internet", "Rywa"],
        "protiucty": ["23456799", "35-4387590217", "2701441318"],
    },
    {
        "nazev": "Telefony",
        "popis": "Mobilní a telekomunikační služby (T-Mobile). Dle FA.",
        "dodavatele": ["T-Mobile"],
        "protiucty": ["19-2235210247"],
        "klicova_slova": ["T-MOBILE"],
    },
    {
        "nazev": "Zvláštní výdaj",
        "popis": "Dodatečné T-Mobile položky / mimořádné výdaje nezařaditelné jinam. Dle FA.",
        "dodavatele": ["T-Mobile"],
        "protiucty": ["19-2235210247", "2132464033"],
        "klicova_slova": ["T-MOBILE INKASO"],
    },

    # =======================================================================
    # AUTO
    # =======================================================================
    {
        "nazev": "Arteon",
        "popis": "Výdaje na firemní auto VW Arteon – servis, STK, destičky, baterie.",
        "dodavatele": ["Arteon"],
        "protiucty": ["604646021"],
        "klicova_slova": ["Arteon"],
    },
    {
        "nazev": "Pojištění",
        "popis": "Pojištění vozidel (Arteon/Taigo) a Kooperativa. Dle FA.",
        "dodavatele": ["Kooperativa", "Pojištění Arteon", "Pojištění Taigo"],
        "protiucty": ["4503502", "40002-50404011"],
    },

    # =======================================================================
    # SPLÁTKY ÚVĚRŮ A ÚROKY
    # =======================================================================
    {
        "nazev": "Splátka",
        "popis": ("Splátky úvěrů a úroků (MONETA, Casa Libre). Fixně dle smlouvy. "
                  "POZOR: na úvěrové účty chodí i doplňování prostředků a interní "
                  "obraty – Splátka je JEN fixní měsíční částka (SPLATKY_UVERU), "
                  "jiné částky jsou 'Převod' – řeší deterministika.py."),
        "dodavatele": [],
        "protiucty": ["249102969", "249103128", "249099667"],
        "klicova_slova": ["splátku", "úvěr"],
    },
    {
        "nazev": "Úrok",
        "popis": "Bankovní úroky z úvěru a poplatky za vedení úvěrového účtu (Raiffeisen). Inkaso.",
        "dodavatele": [],
        "protiucty": ["6430097786"],
        "klicova_slova": ["Úrok", "Vedení účtu", "Souhrnná položka"],
    },

    # =======================================================================
    # NÁJMY / ENERGIE / JEDNOTKY (trvalé příkazy dle smlouvy)
    # =======================================================================
    {
        "nazev": "Šremer",
        "popis": "Nájemné Jan Šremer dle smlouvy z 1.7.2024.",
        "dodavatele": ["Jan Šremer"],
        "protiucty": ["4171718023"],
    },
    {
        "nazev": "V19",
        "popis": ("Nájem + energie objekt Vlhká 19. Dle smlouvy. "
                  "POZN.: účet 327457117 sdílí i Kotlářská a Garant – rozhoduje "
                  "primárně uživatelský štítek (Poznámka)/klíčové slovo, ne protiúčet sám."),
        "dodavatele": [],
        "protiucty": ["327457117", "10014-1703621"],
        "klicova_slova": ["Vlhká 19", "Vlhká"],
    },
    {
        "nazev": "Kotlářská",
        "popis": ("Nájem + energie objekt Kotlářská 12. Dle smlouvy. "
                  "POZN.: účet 327457117 sdílí i V19 a Garant – rozhoduje "
                  "primárně uživatelský štítek (Poznámka)/klíčové slovo, ne protiúčet sám."),
        "dodavatele": [],
        "protiucty": ["327457117", "2201422348"],
        "klicova_slova": ["Kotlářská"],
    },
    {
        "nazev": "Garant",
        "popis": ("Garantovaná platba (výplata garantovi nájmu/výnosu, typicky Radek Danč). "
                  "Účet 327457117 je sdílený s V19/Kotlářská – rozhoduj VÝHRADNĚ podle "
                  "uživatelského štítku (Poznámka) 'Garant', protiúčet sám o kategorii nerozhoduje."),
        "dodavatele": ["Radek Danč"],
        "protiucty": ["327457117"],
        "klicova_slova": ["Garant"],
    },
    {
        "nazev": "V14 nájem",
        "popis": "Nájemné objekt Veselá 14 (UniCredit / Nesty). Dle smlouvy.",
        "dodavatele": ["Nesty"],
        "protiucty": ["2110568392"],
        "klicova_slova": ["Nájem", "Nájemné"],
    },
    {
        "nazev": "V14 energie",
        "popis": "Zálohy / vyúčtování / nedoplatky energií (plyn E-on) objekt Veselá 14.",
        "dodavatele": ["E-on"],
        "protiucty": ["10014-1703621", "2110568392"],
        "klicova_slova": ["energie", "plyn", "V14", "nedoplatek"],
    },
    # POZN.: Prostory a Snídaně dřív deklarovaly protiúčet 2301240402 (Nesty
    # Příjmový). Dle rozhodnutí uživatele (07/2026) platby na interní účet
    # patří do "Převod" – protiúčet odstraněn, aby je aplikuj_interni_prevod
    # přepsal; kategorie zůstávají pro případy rozpoznané štítkem/klíč. slovem.
    {
        "nazev": "Prostory",
        "popis": "Nájem prostor sloužících podnikání (Nesty – X.01, E03, E09). Dle smlouvy.",
        "dodavatele": [],
        "protiucty": [],
        "klicova_slova": ["prostor", "Prostory"],
    },
    {
        "nazev": "Snídaně",
        "popis": "Náklady na snídaně pro hosty. Dle FA.",
        "dodavatele": [],
        "protiucty": [],
        "klicova_slova": ["Snidane", "snídan"],
    },
    {
        "nazev": "A43",
        "popis": "Energie/nájem jednotky – Cejl 79 (o.m. 361020403), č. 143, inkaso úvěru "
                 "jednotky (smlouva 1694/25/021). Trvalý příkaz.",
        "dodavatele": [],
        "protiucty": ["6102102232", "3342292", "2702901101"],
        "klicova_slova": ["361020403", "č. 143", "1694/25/021"],
    },
    {
        "nazev": "B53",
        "popis": "Energie/nájem jednotky – Cejl 79 (o.m. 361010303), č. 253 a 71, inkaso úvěru "
                 "jednotky (smlouva 3699/24/021). Trvalý příkaz.",
        "dodavatele": [],
        "protiucty": ["2702901101", "6430097786", "3342292"],
        "klicova_slova": ["361010303", "č. 253", "č. 71", "3699/24/021"],
    },
    {
        "nazev": "A63",
        "popis": "Měsíční nájemné včetně energií k jednotce č. 533/163. Trvalý příkaz.",
        "dodavatele": [],
        "protiucty": ["224131675"],
        "klicova_slova": ["533/163"],
    },
    {
        "nazev": "A73",
        "popis": "Měsíční nájemné včetně energií k jednotce č. 533/173. Trvalý příkaz.",
        "dodavatele": [],
        "protiucty": ["224131675"],
        "klicova_slova": ["533/173"],
    },
    {
        "nazev": "A82",
        "popis": "Měsíční nájemné včetně energií k jednotce č. 533/182. Trvalý příkaz.",
        "dodavatele": ["Martin Pencik"],
        "protiucty": ["107-2501400247"],
        "klicova_slova": ["533/182"],
    },
    {
        "nazev": "Rosi",
        "popis": "Pravidelné fakturované služby – Rosi (účetní/účetnictví). Dle FA.",
        "dodavatele": ["Rosi"],
        "protiucty": ["241879538", "3154606033"],
        "klicova_slova": ["FAKTURUJEME VAM SLUZBY"],
    },
    {
        "nazev": "Spilberk",
        "popis": "Mezifiremní fakturace ubytovacích služeb – Spilberk / Cejl 79 (C79). Dle FA.",
        "dodavatele": ["Spilberk"],
        "protiucty": ["2702904169", "2502904199"],
        "klicova_slova": ["UBYTOVACI SLUZBY", "C79", "Spilberk"],
    },

    # =======================================================================
    # PROJEKT V24 (vybavení/rekonstrukce jednotky V24)
    # =======================================================================
    {
        "nazev": "V24",
        "popis": ("Vybavení a rekonstrukce jednotky V24 – nábytek/dekorace označené V24. "
                  "POZN.: štítek se v datech používá i pro mezifiremní ubytovací fakturaci "
                  "(účet 2502904199) – ověřit při čištění."),
        "dodavatele": ["JYSK", "IKEA", "Mobelix", "Bonami", "Pepco", "Sinsay", "Beliani", "Alza"],
        "protiucty": ["2171532", "2000295311"],
        "klicova_slova": ["V24", "Spilberk C79"],
    },

    # =======================================================================
    # HOSTÉ – KAUCE A VRATKY (doklad v interním systému)
    # =======================================================================
    {
        "nazev": "Vratka",
        "popis": ("Vrácení plateb hostům/zákazníkům – VÝHRADNĚ odchozí platba (záporná částka) "
                  "směrem k zákazníkovi (na příkaz hosta, doklad v interním systému). "
                  "POZOR: příchozí refundace od dodavatelů (JYSK, Alza, IKEA…) NEJSOU Vratka – "
                  "patří do kategorie původního výdaje (např. Dekorace)."),
        "dodavatele": [],
        "klicova_slova": ["Vratka", "Vrácení", "rez."],
    },
    {
        "nazev": "Kauce",
        "popis": "Vratné kauce hostů (na příkaz hosta, doklad v interním systému).",
        "dodavatele": [],
        "klicova_slova": ["kauce", "Refundable", "deposit"],
    },

    # =======================================================================
    # INTERNÍ PŘEVODY A REZERVY (NEzahrnovat do výdajových součtů)
    # =======================================================================
    {
        "nazev": "Převod",
        "popis": ("Interní převody mezi firemními účty + výběry/vklady hotovosti z bankomatu "
                  "a půjčky/splátky společníka. Není to skutečný výdaj – jen přesun peněz. "
                  "Označit, ALE NEzahrnovat do výdajových součtů."),
        "dodavatele": [],
        # Dřívější samostatné kategorie "Převod Výdajový 1/2" sloučeny sem
        # (rozhodnutí uživatele 07/2026) – viz ALIASY.
        "protiucty": ["2200973033", "2901813198", "2601728813", "2301240402",
                      "2201422348", "2901321222", "1177419020", "5845640002",
                      # doplněno z analýzy schválených výpisů leden–květen 2026
                      "2107482336", "064450-6005980009"],
        "klicova_slova": ["Převod na Výdajový", "Převod na výdajový",
                          "První část na Výdajový", "Odklad", "Výběr z bankomatu",
                          "Vklad do bankomatu", "Půjčka společníka", "Splátka společníka",
                          "Mylná platba"],
    },
    {
        "nazev": "Premier",
        "popis": "Převod na účet Premier Fond (2203097403). Interní tok – přesun peněz, ne výdaj.",
        "dodavatele": [],
        "protiucty": ["2203097403"],
        "klicova_slova": ["Premier"],
    },
    {
        "nazev": "Rezervní 1",
        "popis": "Rezervní účet (2402351507) – ubytovací/místní poplatky, popelnice (FCC), parkování.",
        "dodavatele": ["FCC"],
        "protiucty": ["2402351507", "43-8206670217", "115-9579990277"],
        "klicova_slova": ["Poplatek z ubytovací kapacity", "Ubytovaci poplatky", "Popelnice"],
    },
    {
        "nazev": "Rezervní 2",
        "popis": "Rezervní účet (2102351505) na daň z příjmu – odklady daně. Přesun peněz, ne výdaj.",
        "dodavatele": [],
        "protiucty": ["2102351505"],
        "klicova_slova": ["Odklad na daň z příjmu", "daň z příjmu"],
    },
    {
        "nazev": "Rezervní 3",
        "popis": "Rezervní účet (2602411244) – převody a doplatky na Rezervní 3.",
        "dodavatele": [],
        "protiucty": ["2602411244"],
        "klicova_slova": ["Rezervní 3"],
    },
]

# Kategorie kde faktura objektivně neexistuje nebo není vyžadována.
# Transakce v těchto kategoriích se nezobrazí v reportu chybějících faktur.
KATEGORIE_BEZ_FAKTURY: set[str] = {
    # Mzdy a odvody – dle přehledu mezd
    "Úklid", "Recepční", "Design", "Výplata majitele",
    "FU", "Socka", "Zdravka", "DPH",
    # Nájmy a trvalé příkazy dle smlouvy
    "V14 nájem", "V14 energie", "V19", "Kotlářská", "Šremer",
    "Prostory", "Snídaně", "A43", "B53", "A63", "A73", "A82",
    # Splátky úvěrů
    "Splátka", "Úrok",
    # Interní převody a rezervy
    "Převod", "Premier",
    "Rezervní 1", "Rezervní 2", "Rezervní 3",
    # Hosté a příjmy
    "Kauce", "Vratka", "Airbnb", "Příjem energie",
    # Osobní výdaje majitele (nepatří do firemních výdajů)
    "Výdaje majitele", "Benzín",
    # Pokuty, poplatky a hotovostní operace pokladny
    "Poplatek", "Banka",
}

ALIASY: dict[str, str] = {
    "Spotify a Netflix": "Netflix a Spotify",
    "Netflix": "Netflix a Spotify", "Spotify": "Netflix a Spotify",
    # sloučení dřívějších podkategorií převodů (07/2026)
    "Převod Výdajový 1": "Převod", "Převod Výdajový 2": "Převod",
    "Převod na Výdajový 1": "Převod", "Převod na Výdajový 2": "Převod",
    "Převod na Výdajový 2 (Druhá část)": "Převod",
    "Převod na výdajový 2 (První část)": "Převod",
    "První část na Výdajový 1": "Převod",
    "Kooperativa, pojistovna, a.s.": "Pojištění",
    "Pojištění Taigo": "Pojištění",
    "Bidfood": "Jídlo",
    "Chrištof": "Prádelna",
    "Uklid": "Úklid",
    "Telefon": "Telefony",
    "Zvlšátní výdaj": "Zvláštní výdaj",
    "Rezevní 2": "Rezervní 2",
    "Kancelá": "Kancelář",
    "Kooperativa": "Pojištění",
    "Energie Veselá": "V14 energie", "Energie Veselá 14": "V14 energie",
    "Veselá energie": "V14 energie", "Veselá 14 energie": "V14 energie",
    "Energie": "V14 energie", "Plyn nedoplatek": "V14 energie",
    "Nájem": "V14 nájem", "Nájem Veselá 14": "V14 nájem", "Veselá nájem": "V14 nájem",
    "Veselá 14 Nájem": "V14 nájem", "Nájemné únor": "V14 nájem",
    "Nájemné březen": "V14 nájem", "V14": "V14 nájem", "Nájemné únor ": "V14 nájem",
    "Vlhká 19": "V19", "Nájem a energie Vlhká 19": "V19", "Nájem Vlhká 19": "V19",
    "Kotlářská 12": "Kotlářská", "nájem Kotlářská": "Kotlářská",
    "energie Kotlářská": "Kotlářská", "K12": "Kotlářská",
    "Previo provize": "Provize Previo", "Provize Hotely.cz": "Provize Previo",
    "Provize R+": "Provize Previo",
    "Previo": "Previo systém", "Previo piny": "Previo systém",
    "Vlhká 24 léto": "V24", "Vlhká 24": "V24", "V24 únor": "V24", "V24 bžezen": "V24",
    "Dekorace 2": "Dekorace",
    "C79 únor": "Spilberk", "C79 březen": "Spilberk", "C79": "Spilberk",
    "Účetní únor": "Rosi", "Účetní březen": "Rosi",
    "převod": "Převod", "Výdajový 2": "Převod", "RD Ostatní": "Převod",
    "DPH Nesty": "DPH", "DPH do plusu": "DPH",
    "vratka": "Vratka", "Vratka peněz": "Vratka",
    "Airbank": "Airbnb",
    "Přeplatek energie": "Příjem energie",
    "Ostatní": "Ostatní služby",
    "Multisport": "Ostatní služby",
    "Alza": "Dekorace",
    "Benzín převod?": "Benzín",
    "Pokuta": "Poplatek",
    # vratka omylem poslané platby je vždy interní přesun, i když protiúčet
    # patří konkrétní kategorii (Spilberk apod.)
    "Mylná platba": "Převod",
}

KATEGORIE_PRIJMY_A_MAJITEL = [
    {
        "nazev": "Airbnb",
        "popis": "Příchozí výplaty z Airbnb (přes Citibank). PŘÍJEM. "
                 "POZOR: část byla štítkována chybně jako 'Airbank'.",
        "dodavatele": [],
        "protiucty": ["4000230103"],
        "klicova_slova": ["G-", "/ROC/", "CITIBANK"],
    },
    {
        "nazev": "Výdaje majitele",
        "popis": "Osobní nákupy majitele – potraviny, drogerie, lékárna, hobbymarkety "
                 "(OBI, zahradnictví), e-shopy, pronájem bytu Fibingr. Nepatří do "
                 "firemních výdajů. Na účtu RD Ostatní (2901321222) sem patří KAŽDÝ "
                 "karetní nákup u obchodníka, který není tankování (Benzín).",
        "dodavatele": ["Lidl", "Rohlik.cz", "DR. MAX", "Fairhotel"],
        "protiucty": ["670100-2200894925"],
        "klicova_slova": [],
    },
    {
        "nazev": "Benzín",
        "popis": "PHM – tankování (SILMET, ZEROGAS). Vázáno na osobní/auto účty.",
        "dodavatele": ["SILMET", "ZEROGAS", "CS Silmet"],
        "protiucty": [],
        "klicova_slova": [],
    },
    {
        "nazev": "Příjem energie",
        "popis": "Příjmy/přeplatky energií (L.D.Energy, Mixová Věra). PŘÍJEM.",
        "dodavatele": [],
        "protiucty": ["3342292", "2110568392"],
        "klicova_slova": [],
    },
]

# ---------------------------------------------------------------------------
# Přepis kategorie 'Jídlo' podle karty (sloupec "Provedl") – účet Nesty Ostatní
# ---------------------------------------------------------------------------
# Karetní nákupy jídla (Lidl, Rohlik.cz apod.) na tomto účtu jsou ve skutečnosti
# osobní útraty konkrétní osoby, ne firemní provozní výdaj. AI je zařadí do
# kategorie "Jídlo" – aplikuj_jidlo_podle_provedl() v prepisy.py to pak přepíše
# podle toho, kdo transakci provedl.
#
UCET_NESTY_OSTATNI = "2301780716"

# Kategorie, u kterých se na účtu Nesty Ostatní přepisuje podle karty.
# Ověřeno na schválené historii: karetní nákupy Danče v těchto kategoriích
# jsou VŽDY osobní útrata. Benzín a Reprezentace se NEpřepisují – tam má
# Danč i legitimní firemní/vlastní kategorie (tankování, pohoštění).
KATEGORIE_PREPIS_PODLE_PROVEDL: set[str] = {"Jídlo", "Drogerie", "Snídaně"}

# Podřetězec ve sloupci "Provedl" (hledá se case-insensitive) → nová kategorie.
# Aplikuje se JEN pokud AI transakci nejdřív zařadila do některé z kategorií
# KATEGORIE_PREPIS_PODLE_PROVEDL.
JIDLO_PODLE_PROVEDL: dict[str, str] = {
    "danč": "Výdaje majitele",
    "danc": "Výdaje majitele",
    "gardášová": "Recepční",
    "gardasova": "Recepční",
}

# ---------------------------------------------------------------------------
# Omezená nabídka kategorií pro konkrétní účty/zdroje
# ---------------------------------------------------------------------------
# Pro výpisy, kde historicky platí jen omezená podmnožina kategorií (nebo
# naopak jedna konkrétní kategorie tam NIKDY nepatří), se AI
# (ai.kategorizuj_transakce) pošle upravená nabídka místo celého seznamu
# KATEGORIE – viz omezene_kategorie_pro_soubor() v prepisy.py.
#
# Klíč slovníku je číslo účtu, pokud existuje (jedinečné přes všechny firmy,
# viz FIREMNI_UCTY), jinak jen popisný identifikátor záznamu (u zdrojů bez
# bankovního účtu, např. hotovostní pokladna). "klicove_slovo" se použije
# k rozpoznání výpisu podle názvu souboru, když soubor nemá číslo účtu
# v názvu (např. ručně přejmenované "RD Ostatní (1).csv") – viz
# _soubor_patri_uctu() v prepisy.py.
#
# Každý záznam má buď:
#   "kategorie"  – uzavřený POVOLOVACÍ seznam, AI smí vybrat jen z něj
#   "vyloucene"  – VYLUČOVACÍ seznam, AI smí vybrat cokoliv KROMĚ těchto
OMEZENE_KATEGORIE_PODLE_UCTU: dict[str, dict] = {
    "2901321222": {  # RD Group s.r.o. | Ostatní CZK (Fio)
        # POZOR: klíčové slovo musí obsahovat i firmu – samotné "ostatni" by
        # chytalo i "Nesty Ostatní", který uzavřený seznam mít nesmí.
        "klicove_slovo": "rd ostatni",
        "kategorie": ["Benzín", "Výdaje majitele", "Převod"],
    },
    "POKLADNA_HOTOVOST": {  # hotovostní pokladna – bez čísla účtu
        "klicove_slovo": "pokladna",
        # Zpětná analýza historicky schválených výpisů: hotovostní výběry/dary
        # pro Radka Danče ("Party - Anet", "Radek osobni") byly vždy "Převod",
        # nikdy "Výdaje majitele" – ten je vázaný na jeho osobní bankovní účet
        # (670100-2200894925), ne na sdílenou pokladnu s personálem.
        "vyloucene": ["Výdaje majitele"],
    },
}

# ---------------------------------------------------------------------------
# Deterministický přepis podle Poznámky na účtu RD Příjmový
# ---------------------------------------------------------------------------
# Na tomto účtu (RD Group s.r.o. | Příjmový 1, FIREMNI_UCTY["2200973033"])
# transakce se štítkem (Poznámka) "pronájem bytu" vždy patří k nájmu objektu
# Kotlářská – i když protiúčet bývá sdílený s Casa Libre Příjmový a AI ho
# proto mate s obecným interním převodem. Viz
# aplikuj_kotlarska_pronajem_bytu() v prepisy.py.
UCET_RD_PRIJMOVY = "2200973033"
KLICOVA_SLOVA_KOTLARSKA_RD_PRIJMOVY: list[str] = ["pronajem bytu"]

# ---------------------------------------------------------------------------
# Přepis kategorie 'Telefony' – jen nejvyšší platba T-Mobile je "Telefony"
# ---------------------------------------------------------------------------
# Na účtu T-Mobile bývá víc plateb (pravidelný paušál + dodatečné položky).
# Kategorie "Telefony" patří jen platbě s nejvyšší částkou v daném výpisu,
# všechny ostatní platby T-Mobile jsou "Zvláštní výdaj" – viz
# aplikuj_telefony_nejvyssi_castka() v prepisy.py.
UCET_TMOBILE = "19-2235210247"

# ---------------------------------------------------------------------------
# Hotovostní výplaty na Pokladně podle jména (aplikuj_jmena_pokladna)
# ---------------------------------------------------------------------------
# Jméno v popisu hotovostní transakce → kategorie (mzda/odměna v hotovosti).
# Ověřeno na schválených výpisech: Petr 7/7 Recepční, Vendula/Iva Úklid.
# Hledá se jako celé slovo (case-insensitive, bez diakritiky), jen na Pokladně.
POKLADNA_JMENA_KATEGORIE: dict[str, str] = {
    "vendula": "Úklid",
    "venda": "Úklid",
    "vendy": "Úklid",   # skloňovaný tvar ("Výplata Vendy M.")
    "iva": "Úklid",
    "petr": "Recepční",
}

# ---------------------------------------------------------------------------
# Protiúčty s pevnou kategorií bez ohledu na štítek a částku
# ---------------------------------------------------------------------------
# Nejsilnější deterministické pravidlo (deterministika.py) – přebíjí i
# uživatelský štítek. Rozhodnutí uživatele 07/2026: platby na Premier Fond
# jsou VŽDY "Premier" a platby na rezervní účty VŽDY příslušná "Rezervní N",
# i když štítek říká jen "Převod"/"Doplatek".
UCET_VZDY_KATEGORIE: dict[str, str] = {
    "2203097403": "Premier",
    "2402351507": "Rezervní 1",
    "2102351505": "Rezervní 2",
    "2602411244": "Rezervní 3",
}

# ---------------------------------------------------------------------------
# Textové markery s pevnou kategorií (deterministika.py)
# ---------------------------------------------------------------------------
# Jednoznačné identifikátory v textu transakce (štítek/zpráva/protistrana,
# hledá se case-insensitive) – čísla odběrných míst, čísla úvěrových smluv,
# technické platby. Ověřeno na schválených výpisech leden–květen 2026.
VZDY_TEXT_KATEGORIE: dict[str, str] = {
    "361020403": "A43",     # odběrné místo Cejl 79
    "1694/25/021": "A43",   # úvěrová smlouva jednotky
    "361010303": "B53",     # odběrné místo Cejl 79
    "3699/24/021": "B53",   # úvěrová smlouva jednotky
    "comgate": "Převod",    # identifikační platby ±1 Kč a jejich vratky
    "dobr0": "Vratka",      # čísla dobropisů z pokladny ("Platba dokladu č. 2026DOBR0471")
}

# ---------------------------------------------------------------------------
# Fixní měsíční splátky úvěrů podle úvěrového účtu (MONETA)
# ---------------------------------------------------------------------------
# Ověřeno na schválených výpisech leden–květen 2026: na úvěrové účty chodí
# kromě splátky i doplňování prostředků (−25k/−30k) a interní obraty (±40k),
# které patří do "Převod". Skutečná splátka je jen fixní částka dle smlouvy.
# Deterministické pravidlo (deterministika.py):
#   |částka| = některá z fixních splátek  → "Splátka"
#   jiná částka, ale text obsahuje "splátk" → nechat na AI (možná refixace
#     úroku – po změně výše splátky aktualizuj tento slovník)
#   jiná částka                            → "Převod"
SPLATKY_UVERU: dict[str, list[float]] = {
    "249102969": [6605.76, 7515.33],  # RD Group – splátka a úrok / splátka a úvěr
    "249103128": [6605.76],           # Casa Libre
    "249099667": [6290.42],           # Nesty Services
}

# ---------------------------------------------------------------------------
# Dodavatelé s pevnou kategorií bez ohledu na znaménko částky
# ---------------------------------------------------------------------------
# Podřetězec v textu transakce (protistrana/poznámka/zpráva, hledá se
# case-insensitive) → kategorie, která platí VŽDY – ať jde o nákup (mínus),
# nebo vratku/refundaci (plus). Viz aplikuj_vzdy_dodavatel() v prepisy.py.
VZDY_DODAVATEL_KATEGORIE: dict[str, str] = {
    "alza": "Dekorace",
    "silmet": "Benzín",
    "zerogas": "Benzín",
    # Nestlé automat "Mezi vodami" – doplňky do apartmánů, ne jídlo
    # (schválená historie: 7/7 Dekorace)
    "nestle": "Dekorace",
}

# ---------------------------------------------------------------------------
# Výjimky z VZDY_DODAVATEL_KATEGORIE podle dalšího klíčového slova v textu
# ---------------------------------------------------------------------------
# Pravidlo výše NENÍ úplně bezpodmínečné: pokud text obsahuje i tohle další
# klíčové slovo, použije se místo pevné kategorie dodavatele tahle
# specifičtější kategorie. Např. "Alza" je vždy "Dekorace", ALE pokud
# Poznámka obsahuje i "V24" (nákup vybavení pro jednotku V24), je to "V24".
# Kontroluje se JEN u dodavatele, který výjimku má – klíč musí odpovídat
# klíči ve VZDY_DODAVATEL_KATEGORIE. Viz aplikuj_vzdy_dodavatel() v prepisy.py.
VYJIMKY_VZDY_DODAVATEL: dict[str, list[tuple[str, str]]] = {
    "alza": [("v24", "V24")],
}
