'use strict';
const { app, BrowserWindow, ipcMain, dialog, shell, screen, Menu, Tray, nativeImage } = require('electron');
const fs = require('fs');
const path = require('path');
const os = require('os');
const C = require('./backend/core');
const S = require('./backend/server');
const G = require('./backend/game');
const I = require('./backend/install');
const A = require('./backend/accounts');
const V = require('./backend/settings');
const U = require('./backend/updates');

app.setName('openDC Launcher');
if (!app.requestSingleInstanceLock()) { app.quit(); process.exit(0); }

let win = null;
let busy = null;
let lastCheck = null;
let pendingImport = null;  // the export file picked for import, until it is imported      // the last update check (what update() installs)          // 'install' | 'update' | 'start' | null
let quitting = false;

const res = (...p) => (app.isPackaged ? path.join(process.resourcesPath, ...p) : path.join(__dirname, ...p));

function osInfo() {
  if (C.IS_WIN) {
    const [maj, min, build] = os.release().split('.').map(Number);
    let name = 'Windows';
    if (maj === 10) name = build >= 22000 ? 'Windows 11' : 'Windows 10';
    else if (maj === 6) name = { 1: 'Windows 7', 2: 'Windows 8', 3: 'Windows 8.1' }[min] || 'Windows';
    return { name, linux: false, old: maj < 10 };
  }
  let name = 'Linux';
  try {
    const t = fs.readFileSync('/etc/os-release', 'utf8');
    const m = t.match(/^PRETTY_NAME="?([^"\n]+)"?/m) || t.match(/^NAME="?([^"\n]+)"?/m);
    if (m) name = m[1];
  } catch { /* no os-release */ }
  if (!/linux/i.test(name)) name += ' (Linux)';
  return { name, linux: true, old: false };
}

async function state() {
  const cfg = C.config();
  return {
    installed: I.installed(), root: cfg.root, client: cfg.client, cfg, os: osInfo(), busy,
    server: S.serverRunning(), db: I.installed() && fs.existsSync(C.P().pyExe) ? await S.dbRunning().catch(() => false) : false,
    screen: (() => { const d = screen.getPrimaryDisplay(); const k = d.scaleFactor; return { w: Math.round(d.size.width * k), h: Math.round(d.size.height * k), ww: Math.round(d.workArea.width * k), wh: Math.round(d.workArea.height * k) }; })(),
    proton: (() => { try { return G.currentProton(); } catch { return null; } })(), game: G.gameRunning(), launching: G.gameLaunching(), version: app.getVersion(), port: S.emuConfig() ? S.emuConfig().authPort : null,
  };
}

function send(ch, data) { if (win && !win.isDestroyed()) win.webContents.send(ch, data); }
C.bus.on('log', (l) => send('log', l));
C.bus.on('state', async () => send('state', await state()));
C.bus.on('game', (g) => send('game', g));

async function guard(kind, fn) {
  if (busy) throw new Error('busy:' + busy);
  busy = kind; send('state', await state());
  try { return await fn(); }
  finally { busy = null; send('state', await state()); }
}

// The database and the server stay on while the launcher is open (closing the game doesn't stop them).
// When the game opens, the launcher gets out of the way (cfg.onGame: 'tray' | 'minimize' | 'none');
// when the game closes, it comes back.
let tray = null;
function showWindow() {
  if (!win) return;
  if (tray) { tray.destroy(); tray = null; }
  win.setSkipTaskbar(false);
  if (win.isMinimized()) win.restore();
  win.show(); win.focus();
}
function makeTray() {
  if (tray) return true;
  try {
    tray = new Tray(nativeImage.createFromPath(path.join(__dirname, 'ui', 'assets', 'icon.png')).resize({ width: 24, height: 24 }));
    tray.setToolTip('openDC Launcher');
    const L = { pt: ['Abrir o launcher', 'Fechar tudo'], en: ['Open the launcher', 'Close everything'], ru: ['Открыть лаунчер', 'Закрыть всё'] }[C.config().lang] || ['Abrir o launcher', 'Fechar tudo'];
    tray.setContextMenu(Menu.buildFromTemplate([{ label: L[0], click: showWindow }, { type: 'separator' }, { label: L[1], click: () => quitAll() }]));
    tray.on('click', showWindow);
    return true;
  } catch (e) { C.log('tray:', e.message); tray = null; return false; }
}
let tucked = false;
function onGameEvent(g) {
  if (!win) return;
  const mode = C.config().onGame || 'tray';
  if (g.running && !tucked) {
    tucked = true;
    if (mode === 'tray' && makeTray()) { win.setSkipTaskbar(true); win.hide(); }
    else if (mode !== 'none') win.minimize();
  } else if (!g.running && tucked) {
    tucked = false;
    showWindow();
  }
}
function gameClosed() { send('state', null); }

// close the launcher = close the game, the server and the database
async function quitAll() {
  if (quitting) return;
  quitting = true;
  C.log('launcher closing: game, server and database');
  if (tray) { tray.destroy(); tray = null; }
  if (win) win.hide();
  await G.killGame().catch(() => {});
  await S.stopAll().catch((e) => C.log('stop:', e.message));
  app.exit(0);
}

const api = {
  state,
  async install(client) {
    return guard('install', () => I.install(client, (p) => send('progress', Object.assign({ job: 'install' }, p))));
  },
  async play() {
    return guard('start', async () => {
      const cfg = C.config();
      if (cfg.serverMode === 'remote' && cfg.remoteIp) {
        await S.preparePython().catch(() => {});
        G.setServerAddress(cfg.remoteIp);
      } else {
        send('progress', { job: 'start', step: 0, n: 2, name: 'server', frac: 0.3 });
        await S.startAll();
        G.setServerAddress('127.0.0.1', S.emuConfig().authPort);
        send('progress', { job: 'start', step: 1, n: 2, name: 'game', frac: 0.6 });
      }
      await G.launch(gameClosed);
    });
  },
  async serverStart() { return guard('start', () => S.startAll()); },
  async serverStop() { return S.stopAll(); },
  async checkUpdate() { lastCheck = await U.checkAll(app.getVersion()); return lastCheck; },
  async update() {
    let restart = null;
    await guard('update', async () => {
      const u = lastCheck || await U.checkAll(app.getVersion());
      const list = [];
      if (u.emulator.available) list.push('check', 'download', 'restart');
      if (u.client.available) list.push('client', 'extract', 'tables');
      if (u.launcher.available) list.push('launcher');
      const rep = (name, frac, extra) => send('progress', { job: 'update', step: Math.max(0, list.indexOf(name)), n: list.length || 1, name, frac: frac || 0, extra });
      if (u.emulator.available) await I.update((o) => rep(o.name, o.frac, o.extra));
      if (u.client.available) {
        const wasOn = S.serverRunning();
        await U.updateClient(rep);
        if (wasOn && !S.serverRunning()) await S.startServer();
      }
      if (u.launcher.available) restart = await U.updateLauncher(u.launcher, rep);
      lastCheck = null;
    });
    if (restart) {
      // quit into the new launcher (the server and the database stop with this one)
      setTimeout(async () => {
        quitting = true;
        await S.stopAll().catch(() => {});
        if (restart.run) restart.run();
        else app.relaunch({ execPath: restart.execPath, args: process.argv.slice(1) });
        app.exit(0);
      }, 1200);
      return { restarting: true };
    }
    return { restarting: false };
  },
  async commits() { return I.commits(40); },
  // accounts
  accList: () => A.list(), accGet: (id) => A.get(id), accCreate: (id, pw, gm) => A.create(id, pw, gm),
  accPassword: (id, pw) => A.password(id, pw), accGm: (id, on) => A.gm(id, on), accBan: (id, on) => A.ban(id, on),
  accCoin: (id, n) => A.coin(id, n), accDelete: (id) => A.remove(id), charGet: (id, cid) => A.char(id, cid),
  charRename: (id, cid, name) => A.rename(id, cid, name), charDelete: (id, cid) => A.charDelete(id, cid),
  charMito: (id, cid, n) => A.mito(id, cid, n), charLevel: (name, lv) => A.level(name, lv),
  giveCar: (name, car) => A.giveCar(name, car), giveItem: (name, item, n) => A.giveItem(name, item, n),
  // settings
  video: () => V.readVideo(), videoSave: (v) => V.writeVideo(v), videoRestore: () => V.restoreVideo(),
  saveConfig: (patch) => C.saveConfig(patch),
  // export an account (all its characters) or one character to a .json file; import one back
  async accExport(id, cid, name) {
    const data = await A.exportData(id, cid);
    const base = cid ? `${name || 'corredor'}.opendc-corredor.json` : `${id}.opendc-conta.json`;
    const r = await dialog.showSaveDialog(win, { defaultPath: path.join(app.getPath('documents'), base), filters: [{ name: 'openDC', extensions: ['json'] }] });
    if (r.canceled || !r.filePath) return null;
    fs.writeFileSync(r.filePath, JSON.stringify(data, null, 1));
    C.log('accounts: exported', cid ? `character ${name} of ${id}` : `account ${id}`, 'to', r.filePath);
    return r.filePath;
  },
  async accImportOpen() {
    const r = await dialog.showOpenDialog(win, { properties: ['openFile'], filters: [{ name: 'openDC', extensions: ['json'] }] });
    if (r.canceled || !r.filePaths.length) return null;
    let data;
    try { data = JSON.parse(fs.readFileSync(r.filePaths[0], 'utf8')); } catch { throw new Error('bad_file'); }
    const info = await A.importCheck(data);
    pendingImport = data;
    return Object.assign({ file: path.basename(r.filePaths[0]) }, info);
  },
  async accImport(opts) {
    if (!pendingImport) throw new Error('bad_file');
    const r = await A.importData(pendingImport, opts || {});
    pendingImport = null;
    C.log('accounts: imported', JSON.stringify(r));
    return r;
  },
  // Proton (Linux): the one in use, the ones found, download GE-Proton, import a folder / archive
  laa: (action) => G.laa(['status', 'apply', 'remove', 'restore'].includes(action) ? action : 'status'),
  protonState: () => G.protonState(),
  protonReleases: () => G.geReleases(),
  async protonDownload(tag) {
    return guard('proton', async () => {
      const pr = await G.downloadGEProton((got, total) => send('progress', { job: 'proton', step: 0, n: 1, name: 'proton', frac: total ? got / total : 0, extra: { got, total } }), tag);
      G.useProton(pr);
    });
  },
  async protonImport(kind) {
    const r = await dialog.showOpenDialog(win, kind === 'dir'
      ? { properties: ['openDirectory'] }
      : { properties: ['openFile'], filters: [{ name: 'Proton', extensions: ['gz', 'xz', 'zst', 'zip', 'tar'] }] });
    if (r.canceled || !r.filePaths.length) return null;
    return guard('proton', async () => { const pr = await G.importProton(r.filePaths[0]); G.useProton(pr); return pr; });
  },
  protonUse: (pr) => G.useProton(pr),
  protonRemove: (pr) => G.removeProton(pr),
  async pickRoot() {
    const r = await dialog.showOpenDialog(win, { properties: ['openDirectory', 'createDirectory'] });
    return r.canceled ? null : r.filePaths[0];
  },
  adopt: (dir) => I.adoptFolder(dir),
  openPath: (which) => {
    const p = C.P();
    const map = { root: p.root, client: p.client, emu: p.emu, logs: p.logs, mods: p.mods, backups: p.backups };
    const target = map[which] || p.root;
    fs.mkdirSync(target, { recursive: true });
    return shell.openPath(target);
  },
  readLog(which) {
    const p = C.P();
    const f = { launcher: path.join(p.logs, 'launcher.log'), server: path.join(p.logs, 'server.out'), db: path.join(p.logs, 'postgres.log'),
      game: path.join(p.client, 'DriftCityLauncher.log') }[which];
    try { return fs.readFileSync(f, 'utf8').split(/\r?\n/).slice(-400).join('\n'); } catch { return ''; }
  },
  async testRemote(ip) { return C.portBusy(11105, ip) || C.portBusy(11005, ip); },
  backup: () => S.backupDb(),
  refreshTables: () => S.clientTables(true),
  minimize: () => win && win.minimize(),
  close: () => quitAll(),
  openUrl: (u) => (/^https:\/\//.test(u) ? shell.openExternal(u) : null),
};

for (const [name, fn] of Object.entries(api)) {
  ipcMain.handle(name, async (_e, ...args) => {
    try { return { ok: true, value: await fn(...args) }; }
    catch (e) { C.log('error in', name + ':', e.message); return { ok: false, error: e.message }; }
  });
}

// the window is designed at 1100 x 680; on small screens or with Windows display scaling (125%, 150%)
// that may not fit, so the whole window is zoomed down to fit the work area instead of being cut off
function fitZoom() {
  const wa = screen.getPrimaryDisplay().workAreaSize;
  return Math.min(1, (wa.width - 24) / 1100, (wa.height - 24) / 680);
}
function createWindow() {
  const zoom = fitZoom();
  C.log(`window: zoom ${zoom.toFixed(2)} (work area ${JSON.stringify(screen.getPrimaryDisplay().workAreaSize)}, scale ${screen.getPrimaryDisplay().scaleFactor})`);
  Menu.setApplicationMenu(null);   // no Ctrl+/- zoom, no menu accelerators
  win = new BrowserWindow({
    width: Math.floor(1100 * zoom), height: Math.floor(680 * zoom), useContentSize: true, resizable: false, frame: false, backgroundColor: '#07090C', show: false,
    title: 'openDC Launcher', icon: path.join(__dirname, 'ui', 'assets', 'icon.png'),
    webPreferences: { zoomFactor: zoom, preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.loadFile(path.join(__dirname, 'ui', 'index.html'));
  win.once('ready-to-show', () => win.show());
  win.webContents.setWindowOpenHandler(({ url }) => { if (/^https:\/\//.test(url)) shell.openExternal(url); return { action: 'deny' }; });
  win.on('close', (e) => { if (!quitting) { e.preventDefault(); quitAll(); } });
  C.bus.on('game', onGameEvent);
}

app.on('second-instance', showWindow);
app.whenReady().then(() => {
  C.initConfig(app.getPath('userData'));
  if (!C.config().lang) {
    // first start: the system's language when the launcher has it (pt / ru), otherwise English
    const sys = String((app.getPreferredSystemLanguages && app.getPreferredSystemLanguages()[0]) || app.getLocale() || '').toLowerCase();
    const lang = sys.startsWith('pt') ? 'pt' : sys.startsWith('ru') ? 'ru' : 'en';
    C.saveConfig({ lang });
    C.log(`language: ${lang} (system: ${sys || 'unknown'})`);
  }
  C.setSevenZip(res('bin', '7zz'));
  A.setHelper(res('helper', 'odc_helper.py'));
  createWindow();
});
app.on('window-all-closed', () => {});
