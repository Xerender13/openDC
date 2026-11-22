'use strict';
const { contextBridge, ipcRenderer } = require('electron');

const NAMES = ['state', 'install', 'play', 'serverStart', 'serverStop', 'checkUpdate', 'update', 'commits',
  'accList', 'accGet', 'accCreate', 'accPassword', 'accGm', 'accBan', 'accCoin', 'accDelete', 'charGet', 'charRename',
  'charDelete', 'carDelete', 'itemDelete', 'invGet', 'invDo', 'icons', 'models', 'accExport', 'accImportOpen', 'accImport', 'charMito', 'charLevel', 'giveCar', 'giveItem', 'catalog', 'gmRun', 'notices', 'auc', 'more', 'video', 'videoSave', 'videoRestore', 'saveConfig',
  'laa', 'verifyFiles', 'repairFiles', 'modsList', 'modPreview', 'modEnable', 'modDisable', 'protonState', 'protonReleases', 'protonDownload', 'protonImport', 'protonUse', 'protonRemove', 'pickRoot', 'adopt', 'openPath', 'readLog', 'testRemote', 'lanScan', 'backup', 'refreshTables', 'minimize', 'close', 'openUrl'];

// the calls that make the window wait (the helper reads the database / the game's files): while one runs the page gets
// 'odc-busy' events with the count, and shows its loading screen (background polls, icons and 3D files are left out)
const QUIET = new Set(['state', 'notices', 'icons', 'models', 'commits', 'readLog', 'minimize', 'close', 'openUrl', 'openPath', 'checkUpdate', 'protonState', 'saveConfig']);
let busy = 0;
const tell = () => { try { window.dispatchEvent(new CustomEvent('odc-busy', { detail: busy })); } catch { /* no page yet */ } };
const api = {};
for (const n of NAMES) {
  api[n] = async (...args) => {
    const loud = !QUIET.has(n) && !(n === 'more' && args[0] === 'gotcha');
    if (loud) { busy++; tell(); }
    try {
      const r = await ipcRenderer.invoke(n, ...args);
      if (!r.ok) throw new Error(r.error);
      return r.value;
    } finally { if (loud) { busy--; tell(); } }
  };
}
api.on = (ch, fn) => { if (['log', 'state', 'progress', 'game', 'quitting', 'notice'].includes(ch)) ipcRenderer.on(ch, (_e, d) => fn(d)); };
contextBridge.exposeInMainWorld('odc', api);
