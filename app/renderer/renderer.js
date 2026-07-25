/*
 * Renderer: obsluha UI. Komunikuje s hlavním procesem přes window.api (preload).
 * Eventy enginu (JSONL z kategorizace.gui) přicházejí přes onEngineEvent.
 */

const $ = (id) => document.getElementById(id);

let nastaveni = { apiKey: "", rootDir: "" };
let celkemJobu = 0;
let hotovoJobu = 0;
let bezi = false;

// ---------------------------------------------------------------------------
// Nastavení
// ---------------------------------------------------------------------------

async function init() {
  nastaveni = await window.api.nactiNastaveni();
  if (nastaveni.apiKey) {
    $("api-key").value = nastaveni.apiKey;
    $("klic-stav").textContent = "Klíč je uložený.";
    $("klic-stav").className = "hint ok";
  }
  if (nastaveni.rootDir) {
    $("slozka-cesta").textContent = nastaveni.rootDir;
    obnovNahled();
  }
  aktualizujTlacitka();
}

$("btn-uloz-klic").addEventListener("click", async () => {
  nastaveni.apiKey = $("api-key").value.trim();
  await window.api.ulozNastaveni(nastaveni);
  $("klic-stav").textContent = nastaveni.apiKey ? "Klíč uložen." : "Klíč smazán.";
  $("klic-stav").className = "hint ok";
  aktualizujTlacitka();
});

$("btn-vyber-slozku").addEventListener("click", async () => {
  const slozka = await window.api.vyberSlozku();
  if (!slozka) return;
  nastaveni.rootDir = slozka;
  await window.api.ulozNastaveni(nastaveni);
  $("slozka-cesta").textContent = slozka;
  aktualizujTlacitka();
  obnovNahled();
});

async function obnovNahled() {
  const wrap = $("nahled-wrap");
  const ul = $("nahled");
  ul.innerHTML = "<li>Načítám…</li>";
  wrap.hidden = false;
  const seznam = await window.api.seznam();
  ul.innerHTML = "";
  if (!seznam || !seznam.firmy.length) {
    ul.innerHTML = "<li>⚠ Ve složce nebyly nalezeny žádné firmy s výpisy. Zkontroluj, že obsahuje podadresář <strong>firmy</strong>.</li>";
    return;
  }
  for (const firma of seznam.firmy) {
    const li = document.createElement("li");
    const strong = document.createElement("strong");
    strong.textContent = firma.nazev;
    li.appendChild(strong);
    li.appendChild(document.createTextNode(` — ${firma.joby.length} výpis(ů)`));
    ul.appendChild(li);
  }
}

function aktualizujTlacitka() {
  $("btn-spustit").disabled = bezi || !nastaveni.apiKey || !nastaveni.rootDir;
}

// ---------------------------------------------------------------------------
// Běh enginu
// ---------------------------------------------------------------------------

$("btn-spustit").addEventListener("click", async () => {
  $("joby").innerHTML = "";
  $("log").textContent = "";
  $("log-wrap").hidden = false;
  $("progress-wrap").hidden = false;
  $("progress-fill").style.width = "0%";
  $("progress-text").textContent = "Spouštím…";
  celkemJobu = 0;
  hotovoJobu = 0;
  bezi = true;
  aktualizujTlacitka();
  $("btn-zastavit").hidden = false;
  await window.api.spustit();
});

$("btn-zastavit").addEventListener("click", async () => {
  await window.api.zastavit();
  $("progress-text").textContent = "Zastaveno uživatelem.";
  konecBehu();
});

function konecBehu() {
  bezi = false;
  $("btn-zastavit").hidden = true;
  aktualizujTlacitka();
}

function log(text) {
  const el = $("log");
  el.textContent += text.endsWith("\n") ? text : text + "\n";
  el.scrollTop = el.scrollHeight;
}

function jobElement(label) {
  const id = "job-" + label.replace(/[^a-zA-Z0-9]/g, "_");
  let li = $(id);
  if (!li) {
    li = document.createElement("li");
    li.id = id;
    li.innerHTML = `<span class="ikona"></span><span class="label"></span><span class="stav"></span>`;
    li.querySelector(".label").textContent = label;
    $("joby").appendChild(li);
  }
  return li;
}

function aktualizujProgress() {
  if (!celkemJobu) return;
  const pct = Math.round((hotovoJobu / celkemJobu) * 100);
  $("progress-fill").style.width = pct + "%";
  $("progress-text").textContent = `Hotovo ${hotovoJobu} z ${celkemJobu} výpisů`;
}

window.api.onEngineEvent((ev) => {
  switch (ev.event) {
    case "chyba": {
      $("progress-text").textContent = "❌ " + ev.text;
      log("CHYBA: " + ev.text);
      break;
    }
    case "start": {
      celkemJobu = ev.celkem_jobu;
      $("progress-text").textContent = `Nalezeno ${ev.firmy.length} firem, ${celkemJobu} výpisů. Indexuji faktury…`;
      for (const job of ev.joby) {
        const li = jobElement(job.label);
        li.querySelector(".ikona").innerHTML = "·";
        li.querySelector(".stav").textContent = "Čeká…";
      }
      log(`Start: firmy ${ev.firmy.join(", ")}`);
      break;
    }
    case "index_start":
      log(`Indexace faktur ${ev.firma}: ${ev.celkem} nových souborů`);
      break;
    case "index_krok":
      $("progress-text").textContent = `Indexuji faktury ${ev.firma} (${ev.hotovo}/${ev.celkem})…`;
      break;
    case "index_hotovo":
      log(`Indexace faktur ${ev.firma} hotova`);
      break;
    case "job_start": {
      const li = jobElement(ev.label);
      li.querySelector(".ikona").innerHTML = '<span class="spinner"></span>';
      li.querySelector(".stav").textContent = "Zpracovávám…";
      break;
    }
    case "job_stav": {
      const li = jobElement(ev.label);
      li.querySelector(".stav").textContent = ev.text;
      break;
    }
    case "job_hotovo": {
      hotovoJobu++;
      const li = jobElement(ev.label);
      if (ev.prazdny) {
        li.className = "warn";
        li.querySelector(".ikona").textContent = "⚠";
        li.querySelector(".stav").textContent = "Prázdný CSV soubor";
      } else {
        li.className = "ok";
        li.querySelector(".ikona").textContent = "✓";
        li.querySelector(".stav").textContent = `Hotovo (${ev.transakce} transakcí, ${ev.faktury} faktur)`;
        if (!li.querySelector("button")) {
          const btn = document.createElement("button");
          btn.className = "mini";
          btn.textContent = "Zobrazit výsledek";
          btn.addEventListener("click", () => window.api.otevriCestu(ev.vystup));
          li.appendChild(btn);
        }
      }
      aktualizujProgress();
      log(`✓ ${ev.label}`);
      break;
    }
    case "job_chyba": {
      hotovoJobu++;
      const li = jobElement(ev.label);
      li.className = "err";
      li.querySelector(".ikona").textContent = "✗";
      li.querySelector(".stav").textContent = "CHYBA: " + ev.text;
      aktualizujProgress();
      log(`✗ ${ev.label}: ${ev.text}\n${ev.detail || ""}`);
      break;
    }
    case "hotovo": {
      $("progress-fill").style.width = "100%";
      $("progress-text").textContent = `✅ Vše hotovo (${hotovoJobu} výpisů).`;
      break;
    }
    case "log":
      log(ev.text);
      break;
  }
});

window.api.onEngineExit((code) => {
  if (bezi && code !== 0 && code !== null) {
    $("progress-text").textContent += "  (engine skončil s chybou)";
  }
  konecBehu();
});

init();
