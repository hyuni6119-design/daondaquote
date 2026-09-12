const { app, BrowserWindow, dialog, shell, ipcMain } = require("electron");
const path = require("path");

let mainWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1500,
    height: 950,
    title: "다온다자동차유리 견적서",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      spellcheck: false
    }
  });
  mainWindow.loadFile(path.join(__dirname, "index.html"));
}

// 폴더 선택 창을 띄우고 고른 폴더의 실제 경로를 돌려준다
ipcMain.handle("daonda:pickFolder", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "공유폴더 선택",
    properties: ["openDirectory"]
  });
  if (result.canceled || !result.filePaths.length) return null;
  return result.filePaths[0];
});

// 윈도우 탐색기로 해당 폴더를 연다. 실패하면 사유 문자열을 돌려준다
ipcMain.handle("daonda:openFolder", async (_event, target) => {
  if (typeof target !== "string" || !target.trim()) return "폴더 경로가 비어 있습니다.";
  return await shell.openPath(target);
});

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => app.quit());
