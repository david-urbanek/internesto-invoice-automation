FIRMY_SLOZKA = "firmy"
CSV_SEPARATOR = ";"
MODEL = "gemini-2.5-flash"

FIREMNI_UCTY = {
    "2200973033": "RD Group s.r.o. | Příjmový 1",
    "2901813198": "RD Group s.r.o. | Výdajový 1",
    "2601728813": "RD Group s.r.o. | Výdajový 2",
    "2901321222": "RD Group s.r.o. | Ostatní",
    "2402351507": "RD Group s.r.o. | Rezervní 1 (poplatky)",
    "2102351505": "RD Group s.r.o. | Rezervní 2 (daň z příjmu)",
    "2602411244": "RD Group s.r.o. | Rezervní 3",
    "2203097403": "RD Group s.r.o. | Premier / odklady",
    "2301240402": "Nesty Services s.r.o. | Příjmový 1",
    "2201422348": "Casa Libre s.r.o. | Příjmový 1",
    "4877715":    "RD Group s.r.o. | úvěrový účet (Raiffeisen)",
    "1177419020": "Radek Danč (jednatel / společník – Air Bank)",
    "5845640002": "Ing. Radek Danč (společník)",
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
    {
        "nazev": "Multisport",
        "popis": "Karty Multisport pro zaměstnance.",
        "dodavatele": ["Multisport"],
        "protiucty": ["2104561127"],
    },
    {
        "nazev": "Ostatní služby",
        "popis": "Různé služby nezařaditelné jinam (callcentrum, pošta, drobné poplatky).",
        "dodavatele": ["Daktela", "AirWallet", "Česká pošta", "Multisport"],
        "protiucty": ["2078745001", "2104561127", "170158265"],
        "klicova_slova": ["FAKTURUJEME VAM ZA", "AIRWALLET"],
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
        "dodavatele": ["Qerko", "Matějovo pekařství", "Pivnice", "J&T banka cafe", "Alza"],
        "protiucty": ["2400406244"],
        "klicova_slova": ["dárek", "Reprezentace"],
    },
    {
        "nazev": "Kancelář",
        "popis": "Kancelářské potřeby a tisk.",
        "dodavatele": ["Papír"],
        "klicova_slova": ["Kancelář", "tisk", "Papir"],
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
                       "Marosova", "Dobos", "Soudni exekutor", "Urad prace"],
        "protiucty": ["354003954", "6015-229761", "115-1648560267", "3055051183",
                      "3799998003", "129886578"],
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
        "popis": "Platby finančnímu úřadu (daně ze závislé činnosti). Dle přehledu mezd.",
        "dodavatele": [],
        "protiucty": ["7720-77628621", "713-77628621"],
        "klicova_slova": ["FU"],
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
        "protiucty": ["705-77628621", "2203097403"],
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
        "protiucty": ["19-2235210247"],
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
        "popis": "Splátky úvěrů a úroků (MONETA, Casa Libre). Fixně dle smlouvy.",
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
        "popis": "Nájem + energie objekt Vlhká 19. Dle smlouvy.",
        "dodavatele": [],
        "protiucty": ["327457117", "10014-1703621"],
        "klicova_slova": ["Vlhká 19", "Vlhká"],
    },
    {
        "nazev": "Kotlářská",
        "popis": "Nájem + energie objekt Kotlářská 12. Dle smlouvy.",
        "dodavatele": [],
        "protiucty": ["327457117", "2201422348"],
        "klicova_slova": ["Kotlářská"],
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
    {
        "nazev": "Prostory",
        "popis": "Nájem prostor sloužících podnikání (Nesty – X.01, E03, E09). Dle smlouvy.",
        "dodavatele": [],
        "protiucty": ["2301240402"],
        "klicova_slova": ["prostor", "Prostory"],
    },
    {
        "nazev": "Snídaně",
        "popis": "Náklady na snídaně pro hosty. Dle FA.",
        "dodavatele": [],
        "protiucty": ["2301240402"],
        "klicova_slova": ["Snidane", "snídan"],
    },
    {
        "nazev": "A43",
        "popis": "Energie/nájem jednotky – Cejl 79 (o.m. 361020403), č. 143, inkaso úvěru jednotky. Trvalý příkaz.",
        "dodavatele": [],
        "protiucty": ["6102102232", "3342292", "2702901101"],
        "klicova_slova": ["361020403", "č. 143"],
    },
    {
        "nazev": "B53",
        "popis": "Energie/nájem jednotky – Cejl 79 (o.m. 361010303), č. 253 a 71, inkaso úvěru jednotky. Trvalý příkaz.",
        "dodavatele": [],
        "protiucty": ["2702901101", "6430097786", "3342292"],
        "klicova_slova": ["361010303", "č. 253", "č. 71"],
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
        "dodavatele": ["JYSK", "Alza", "IKEA", "Mobelix", "Bonami", "Pepco", "Sinsay", "Beliani"],
        "protiucty": ["2171532", "2000295311"],
        "klicova_slova": ["V24", "Spilberk C79"],
    },

    # =======================================================================
    # HOSTÉ – KAUCE A VRATKY (doklad v interním systému)
    # =======================================================================
    {
        "nazev": "Vratka",
        "popis": "Vrácení plateb hostům (na příkaz hosta, doklad v interním systému).",
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
        "protiucty": ["2200973033", "2901813198", "2301240402", "2201422348",
                      "2901321222", "1177419020", "5845640002"],
        "klicova_slova": ["Převod na Výdajový", "Odklad", "Výběr z bankomatu",
                          "Vklad do bankomatu", "Půjčka společníka", "Splátka společníka",
                          "Mylná platba"],
    },
    {
        "nazev": "Převod Výdajový 1",
        "popis": "Převod na účet Výdajový 1 (2901813198). Přesun peněz, ne výdaj.",
        "dodavatele": [],
        "protiucty": ["2901813198"],
        "klicova_slova": ["Převod na Výdajový 1", "První část na Výdajový"],
    },
    {
        "nazev": "Převod Výdajový 2",
        "popis": "Převod na účet Výdajový 2 (2601728813). Přesun peněz, ne výdaj.",
        "dodavatele": [],
        "protiucty": ["2601728813"],
        "klicova_slova": ["Převod na Výdajový 2", "Převod na výdajový"],
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
    "Převod", "Převod Výdajový 1", "Převod Výdajový 2",
    "Rezervní 1", "Rezervní 2", "Rezervní 3",
    # Hosté a příjmy
    "Kauce", "Vratka", "Airbnb", "Příjem energie",
    # Osobní výdaje majitele (nepatří do firemních výdajů)
    "Výdaje majitele", "Benzín",
}

ALIASY: dict[str, str] = {
    "Netflix": "Netflix a Spotify", "Spotify": "Netflix a Spotify",
    "Spotify a Netflix": "Netflix a Spotify",
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
    "převod": "Převod", "Výdajový 2": "Převod Výdajový 2", "RD Ostatní": "Převod",
    "DPH Nesty": "DPH", "DPH do plusu": "DPH",
    "vratka": "Vratka", "Vratka peněz": "Vratka",
    "Airbank": "Airbnb",
    "Přeplatek energie": "Příjem energie",
    "Ostatní": "Ostatní služby",
    "Alza": "Dekorace",
    "Benzín převod?": "Benzín",
    "Pokuta": "Poplatek",
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
        "popis": "Osobní nákupy majitele (Rohlik, Lidl, DR.MAX, pronájem bytu Fibingr). "
                 "Nepatří do firemních výdajů.",
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
