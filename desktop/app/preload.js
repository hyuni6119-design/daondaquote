const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("daondaDesktop", {
  pickFolder: () => ipcRenderer.invoke("daonda:pickFolder"),
  openFolder: target => ipcRenderer.invoke("daonda:openFolder", target)
});
