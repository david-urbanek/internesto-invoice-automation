/*
 * Hlavní proces Electronu.
 *
 * Zodpovídá za:
 *  - okno aplikace (renderer/)
 *  - ukládání nastavení (API klíč, složka s daty) do userData/settings.json
 *  - spouštění Python enginu (kategorizace.gui) jako subprocess a streamování
 *    jeho JSONL výstupu do rendereru přes IPC kanál "engine-event"
 *
 * Engine se hledá:
 *  - v zabalené aplikaci: resources/engine/kategorizace-gui(.exe)  (PyInstaller)
 *  - ve vývoji: ../.venv/bin/python -m kategorizace.gui  (repo venv)
 */

const { app, BrowserWindow, ipcMain, dialog, shell } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

let win = null;
let engineProcess = null;

const settingsPath = () => path.join(app.getPath("userData"), "settings.json");

function loadSettings() {
  try {
    return JSON.parse(fs.readFileSync(settingsPath(), "utf-8"));
  } catch {
    return { apiKey: "", rootDir: "" };
  }
}

function saveSettings(settings) {
  fs.writeFileSync(settingsPath(), JSON.stringify(settings, null, 2));
}

function engineCommand() {
  if (app.isPackaged) {
    const bin = process.platform === "win32" ? "kategorizace-gui.exe" : "kategorizace-gui";
    return { cmd: path.join(process.resourcesPath, "engine", bin), baseArgs: [] };
  }
  // Vývoj: použij venv v kořeni repozitáře
  const repoRoot = path.join(__dirname, "..");
  const python = process.platform === "win32"
    ? path.join(repoRoot, ".venv", "Scripts", "python.exe")
    : path.join(repoRoot, ".venv", "bin", "python");
  return { cmd: python, baseArgs: ["-m", "kategorizace.gui"], cwd: repoRoot };
}

function spawnEngine(extraArgs, settings, onLine, onExit) {
  const { cmd, baseArgs, cwd } = engineCommand();
  if (!fs.existsSync(cmd)) {
    onLine({ event: "chyba", text: `Engine nenalezen: ${cmd}` });
    onExit(1);
    return null;
  }
  const child = spawn(cmd, [...baseArgs, ...extraArgs], {
    cwd: cwd || undefined,
    env: {
      ...process.env,
      GOOGLE_API_KEY: settings.apiKey || process.env.GOOGLE_API_KEY || "",
      PYTHONUNBUFFERED: "1",
    },
  });

  let buffer = "";
  child.stdout.on("data", (chunk) => {
    buffer += chunk.toString();
    let idx;
    while ((idx = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 1);
      if (!line) continue;
      try {
        onLine(JSON.parse(line));
      } catch {
        onLine({ event: "log", text: line });
      }
    }
  });
  child.stderr.on("data", (chunk) => {
    onLine({ event: "log", text: chunk.toString() });
  });
  child.on("close", (code) => onExit(code));
  return child;
}

function createWindow() {
  win = new BrowserWindow({
    width: 980,
    height: 720,
    minWidth: 720,
    minHeight: 520,
    title: "Kategorizace transakcí",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadFile(path.join(__dirname, "renderer", "index.html"));
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (engineProcess) engineProcess.kill();
});

// ---------------------------------------------------------------------------
// IPC
// ---------------------------------------------------------------------------

ipcMain.handle("nacti-nastaveni", () => loadSettings());

ipcMain.handle("uloz-nastaveni", (_e, settings) => {
  saveSettings(settings);
  return true;
});

ipcMain.handle("vyber-slozku", async () => {
  const result = await dialog.showOpenDialog(win, {
    title: "Vyber složku s daty (musí obsahovat podadresář „firmy“)",
    properties: ["openDirectory"],
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle("otevri-cestu", (_e, cesta) => {
  if (fs.existsSync(cesta)) {
    if (fs.statSync(cesta).isDirectory()) shell.openPath(cesta);
    else shell.showItemInFolder(cesta);
  }
});

// Rychlý náhled: jaké firmy a výpisy engine vidí ve zvolené složce
ipcMain.handle("seznam", (_e) => {
  const settings = loadSettings();
  return new Promise((resolve) => {
    let seznam = null;
    spawnEngine(
      ["--root", settings.rootDir, "--seznam"],
      settings,
      (ev) => { if (ev.event === "seznam") seznam = ev; },
      () => resolve(seznam),
    );
  });
});

ipcMain.handle("spustit", (_e) => {
  if (engineProcess) return false;
  const settings = loadSettings();
  engineProcess = spawnEngine(
    ["--root", settings.rootDir],
    settings,
    (ev) => win && win.webContents.send("engine-event", ev),
    (code) => {
      engineProcess = null;
      if (win) win.webContents.send("engine-exit", code);
    },
  );
  return engineProcess !== null;
});

ipcMain.handle("zastavit", () => {
  if (engineProcess) {
    engineProcess.kill();
    engineProcess = null;
    return true;
  }
  return false;
});
