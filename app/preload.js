const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("api", {
  nactiNastaveni: () => ipcRenderer.invoke("nacti-nastaveni"),
  ulozNastaveni: (s) => ipcRenderer.invoke("uloz-nastaveni", s),
  vyberSlozku: () => ipcRenderer.invoke("vyber-slozku"),
  otevriCestu: (cesta) => ipcRenderer.invoke("otevri-cestu", cesta),
  seznam: () => ipcRenderer.invoke("seznam"),
  spustit: () => ipcRenderer.invoke("spustit"),
  zastavit: () => ipcRenderer.invoke("zastavit"),
  onEngineEvent: (cb) => ipcRenderer.on("engine-event", (_e, ev) => cb(ev)),
  onEngineExit: (cb) => ipcRenderer.on("engine-exit", (_e, code) => cb(code)),
});
