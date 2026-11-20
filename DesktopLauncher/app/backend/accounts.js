'use strict';
// Accounts and characters: the helper (SQL through the portable Python) and the server's control port.
const path = require('path');
const C = require('./core');
const S = require('./server');

let helperPath = null;
function setHelper(p) { helperPath = p; }

async function helper(cmd, args = {}) {
  const p = C.P();
  if (!(await S.dbRunning())) await S.startDb();
  const e = S.emuConfig();
  const req = Object.assign({ cmd, db: { port: e.port, user: e.user, pass: e.pass, name: e.db, server_id: e.serverId },
    admin_list: path.join(p.emu, e.adminList) }, args);
  const r = await C.run(p.pyExe, ['-I', helperPath], { cwd: p.emu, input: JSON.stringify(req) });
  let out;
  try { out = JSON.parse(r.out); } catch { throw new Error('helper: ' + (r.err || r.out).slice(-300)); }
  if (!out.ok) throw new Error(out.error);
  return out;
}

async function control(line) {
  if (!S.serverRunning()) throw new Error('server_off');
  const r = await S.control(line);
  if (!r.ok) throw new Error(r.text);
  return r.text;
}

module.exports = {
  setHelper,
  list: () => helper('accounts').then((r) => r.accounts),
  get: (id) => helper('account', { id }).then((r) => r.account),
  create: (id, password, gm) => helper('create', { id, password, gm }),
  password: (id, password) => helper('password', { id, password }),
  gm: (id, on) => helper('gm', { id, on }),
  ban: (id, on) => helper('ban', { id, on }),
  coin: (id, coin) => helper('coin', { id, coin }),
  remove: (id) => helper('delete', { id }),
  char: (id, cid) => helper('char', { id, cid }).then((r) => r.char),
  rename: (id, cid, name) => helper('rename', { id, cid, name }),
  charDelete: (id, cid) => helper('char_delete', { id, cid }),
  mito: (id, cid, mito) => helper('char_stats', { id, cid, mito }),
  exportData: (id, cid) => helper('export', { id, cid: cid || null, client: C.config().client }).then((r) => r.data),
  importCheck: (data) => helper('import_check', { data }).then((r) => r.info),
  importData: (data, opts) => helper('import', Object.assign({ data }, opts)),
  // live server (control port)
  level: (name, level) => control(`level ${name} ${level}`),
  giveCar: (name, car) => control(`car ${name} ${car}`),
  giveItem: (name, item, count) => control(`item ${name} ${item} ${count || 1}`),
};
