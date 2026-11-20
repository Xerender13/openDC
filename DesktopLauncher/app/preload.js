'use strict';
const { contextBridge, ipcRenderer } = require('electron');

const NAMES = ['state', 'install', 'play', 'serverStart', 'serverStop', 'checkUpdate', 'update', 'commits',
  'accList', 'accGet', 'accCreate', 'accPassword', 'accGm', 'accBan', 'accCoin', 'accDelete', 'charGet', 'charRename',
  'charDelete', 'accExport', 'accImportOpen', 'accImport', 'charMito', 'charLevel', 'giveCar', 'giveItem', 'video', 'videoSave', 'videoRestore', 'saveConfig',
  'laa', 'protonState', 'protonReleases', 'protonDownload', 'protonImport', 'protonUse', 'protonRemove', 'pickRoot', 'adopt', 'openPath', 'readLog', 'testRemote', 'backup', 'refreshTables', 'minimize', 'close', 'openUrl'];

const api = {};
for (const n of NAMES) {
  api[n] = async (...args) => {
    const r = await ipcRenderer.invoke(n, ...args);
    if (!r.ok) throw new Error(r.error);
    return r.value;
  };
}
api.on = (ch, fn) => { if (['log', 'state', 'progress', 'game'].includes(ch)) ipcRenderer.on(ch, (_e, d) => fn(d)); };
contextBridge.exposeInMainWorld('odc', api);
