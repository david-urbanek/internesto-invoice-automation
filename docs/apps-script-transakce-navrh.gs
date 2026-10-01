/**
 * Slije všechny CSV->Sheet výstupy z Drive složky (GOOGLE_DRIVE_FOLDER_ID)
 * do listu `Transakce` v tomto sešitu. Spouští se ručně z menu — nikdy
 * automaticky (aby refresh nepřepsal data v okamžiku, kdy do listu
 * někdo kouká přes Zobrazení filtru).
 *
 * Předpoklad: soubory ve složce jsou Google Sheety (drive.py je tak
 * nahrává, SHEET_MIMETYPE), název "MM-YYYY-firma-zbytek" (drive.py:_drive_nazev).
 */

const CONFIG = {
  // stejné ID jako GOOGLE_DRIVE_FOLDER_ID v .env Python skriptu
  FOLDER_ID: 'DOPLNIT_ID_SLOZKY',
  TARGET_SHEET: 'Transakce',
  EUR_KURZ_CZK: 24.30,
  HEADER: ['Datum', 'Firma', 'Ucet', 'Radek', 'Kategorie', 'Objem', 'Mesic', 'Mena', 'Jistota', 'Zdroj'],
  // Tyto sloupce musí existovat. Starší AI exporty mohou mít `Jistota`
  // místo `Jistota kategorie`; Firma a Radek se doplní z názvu/defaultu.
  POVINNE_SLOUPCE: ['Datum', 'Objem', 'Měna', 'Kategorie'],
};

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Kategorizace')
    .addItem('Aktualizovat transakce', 'aktualizujTransakce')
    .addToUi();
}

function aktualizujTransakce() {
  const folder = DriveApp.getFolderById(CONFIG.FOLDER_ID);
  const soubory = folder.getFilesByType(MimeType.GOOGLE_SHEETS);

  const vsechnyRadky = [];
  const chyby = [];
  let pocetSouboru = 0;

  while (soubory.hasNext()) {
    const file = soubory.next();
    pocetSouboru++;
    try {
      vsechnyRadky.push(...nactiSoubor(file));
    } catch (e) {
      chyby.push(`${file.getName()}: ${e.message}`);
    }
  }

  zapisDoTransakce(vsechnyRadky);

  const nenamapovano = vsechnyRadky.filter(r => String(r.Radek || '').endsWith('00')).length;
  const mesicFallback = vsechnyRadky.filter(r => r._mesicZNazvu).length;
  const zprava = [
    `Souborů zpracováno: ${pocetSouboru}`,
    `Transakcí celkem: ${vsechnyRadky.length}`,
    `Nenamapováno na řádek formuláře (R00): ${nenamapovano}`,
    `Mesic dopočítán z názvu souboru (nešlo parsovat Datum): ${mesicFallback}`,
    chyby.length ? `\nCHYBY (soubor přeskočen, zbytek pokračoval):\n${chyby.join('\n')}` : 'Bez chyb.',
  ].join('\n');

  SpreadsheetApp.getUi().alert(zprava);
}

/** Vytáhne měsíc/rok/firmu/účet z názvu "MM-YYYY-firma-zbytek". */
function parsujNazevSouboru(nazev) {
  const dily = nazev.split('-');
  const [mesic, rok, firma, ...zbytek] = dily;
  return {
    mesic: Number(mesic),
    rok: Number(rok),
    firma: firma ? firma.toUpperCase() : '',
    ucet: zbytek.join('-'),
  };
}

/**
 * Měsíc z hodnoty buňky Datum. Sheets ji při importu CSV někdy rozpozná
 * jako Date, jindy (mix formátů, prázdné řádky u pokladny) zůstane text —
 * zkusíme oboje, stejné formáty jako drive.py:DATUM_FORMATY. Když se
 * nepovede nic, vrátí null a volající spadne zpět na měsíc z názvu souboru.
 */
function mesicZDatumu(hodnota) {
  if (hodnota instanceof Date && !isNaN(hodnota)) return hodnota.getMonth() + 1;
  const s = String(hodnota || '').trim();
  if (!s) return null;
  let m = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})/); // dd.mm.yyyy[ HH:MM]
  if (m) return Number(m[2]);
  m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/); // yyyy-mm-dd[ HH:MM:SS]
  if (m) return Number(m[2]);
  m = s.match(/^(\d{1,2})\/(\d{1,2})\/\d{2,4}$/); // m/d/yy (starší export)
  if (m) return Number(m[1]);
  return null;
}


function nactiSoubor(file) {
  const meta = parsujNazevSouboru(file.getName());
  const ss = SpreadsheetApp.openById(file.getId());
  const sheet = ss.getSheets()[0];
  const data = sheet.getDataRange().getValues();
  if (data.length < 2) return [];

  // Hlavičky podle JMÉNA, ne pozice — soubory mají různé sloupce
  // (Pokladna != Fio výpisy), viz docs/napojeni-na-alokacni-formular.md.
  const hlavicky = data[0].map(h => String(h).trim());
  const idx = {};
  hlavicky.forEach((h, i) => { idx[h] = i; });

  for (const sl of CONFIG.POVINNE_SLOUPCE) {
    if (!(sl in idx)) {
      throw new Error(`chybí sloupec „${sl}“ (má: ${hlavicky.join(', ')})`);
    }
  }
  const jistotaSloupec = 'Jistota kategorie' in idx
    ? 'Jistota kategorie'
    : ('Jistota' in idx ? 'Jistota' : null);
  if (!jistotaSloupec) {
    throw new Error('chybí sloupec „Jistota kategorie“ nebo „Jistota“');
  }

  const radky = [];
  for (let r = 1; r < data.length; r++) {
    const radek = data[r];
    if (radek.every(v => v === '' || v === null)) continue; // prázdný řádek na konci

    const datumHodnota = radek[idx['Datum']];
    const mesicZDatumuHodnoty = mesicZDatumu(datumHodnota);

    const objem = Number(radek[idx['Objem']]) || 0;
    const mena = String(radek[idx['Měna']] || '').trim().toUpperCase();
    const objemCzk = mena === 'EUR' ? objem * CONFIG.EUR_KURZ_CZK : objem;

    radky.push({
      Datum: datumHodnota,
      Firma: radek[idx['Firma']] || meta.firma,
      Ucet: meta.ucet,
      Radek: radek[idx['Radek']] || 'R00',
      Kategorie: radek[idx['Kategorie']],
      Objem: objemCzk,
      Mesic: mesicZDatumuHodnoty !== null ? mesicZDatumuHodnoty : meta.mesic,
      Mena: 'CZK',
      Jistota: radek[idx[jistotaSloupec]],
      Zdroj: file.getName(),
      _mesicZNazvu: mesicZDatumuHodnoty === null, // pro hlášku, nezapisuje se (mimo HEADER)
    });
  }
  return radky;
}

function zapisDoTransakce(radky) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(CONFIG.TARGET_SHEET);
  if (!sheet) sheet = ss.insertSheet(CONFIG.TARGET_SHEET);

  // Přepis NAČISTO — do tohoto listu se nikdy nepíše ručně, refresh ho maže.
  sheet.clearContents();
  sheet.getRange(1, 1, 1, CONFIG.HEADER.length).setValues([CONFIG.HEADER]);

  if (radky.length === 0) return;

  // Jeden batch setValues, ne cyklus po buňkách — 84 souborů × stovky
  // řádků by po jedné buňce bylo pomalé a narazí na kvóty.
  const matice = radky.map(r => CONFIG.HEADER.map(h => r[h]));
  sheet.getRange(2, 1, matice.length, CONFIG.HEADER.length).setValues(matice);
}
