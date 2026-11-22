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

// the game's pictures of items and cars (helper/odc_icons.py copies them out of the client once): name -> DDS + uv
async function icons(names) {
  const p = C.P();
  const fs = require('fs');
  const out = path.join(p.rt, 'icons');
  const r = await C.run(p.pyExe, ['-I', path.join(path.dirname(helperPath), 'odc_icons.py')],
    { cwd: p.emu, input: JSON.stringify({ client: p.client, out, names }) });
  let j;
  try { j = JSON.parse(r.out); } catch { throw new Error('icons: ' + (r.err || r.out).slice(-300)); }
  if (!j.ok) throw new Error(j.error);
  const res = {};
  for (const [n, e] of Object.entries(j.icons)) {
    try { res[n] = { dds: fs.readFileSync(e.file).toString('base64'), uv: e.uv }; } catch { /* gone */ }
  }
  return res;
}

// the game's 3D files for the Garage window (helper/odc_models.py copies them out of the client once): the cars'
// NIFs and textures, the garage NIF, the garage music and select sound -> their bytes
async function models(cars, garage = true, bgm = 'garage') {
  const p = C.P();
  const fs = require('fs');
  const out = path.join(p.rt, 'models');
  const r = await C.run(p.pyExe, ['-I', path.join(path.dirname(helperPath), 'odc_models.py')],
    { cwd: p.emu, input: JSON.stringify({ client: p.client, out, cars, garage: !!garage, bgm }) });
  let j;
  try { j = JSON.parse(r.out); } catch { throw new Error('models: ' + (r.err || r.out).slice(-300)); }
  if (!j.ok) throw new Error(j.error);
  const read = (f) => { try { return f ? fs.readFileSync(f) : null; } catch { return null; } };
  const res = { cars: {}, textures: {}, palette: j.palette || {}, garage: read(j.garage), music: read(j.music), select: read(j.select), sell: read(j.sell) };
  for (const [m, c] of Object.entries(j.cars)) {
    res.cars[m] = { body: read(c.body), dm: read(c.dm), shadow: read(c.shadow), light: read(c.light), spoiler: read(c.spoiler), tire: read(c.tire), map: read(c.map), mask: read(c.mask), neon: read(c.neon), decal: read(c.decal), decals: c.decals || {}, parts: {} };
    for (const [k, f] of Object.entries(c.parts || {})) res.cars[m].parts[k] = read(f);
  }
  for (const [n, f] of Object.entries(j.textures)) res.textures[n] = read(f);
  return res;
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
  carDelete: (id, cid, car) => helper('car_delete', { id, cid, car }),
  itemDelete: (id, cid, slot, count) => helper('item_delete', { id, cid, slot, count }),
  inv: (id, cid) => helper('inv', { id, cid }).then((r) => r.inv),
  icons,
  models,
  invDo: (id, cid, args) => helper('inv_do', Object.assign({}, args, { id, cid })),
  auc: (cmd, id, cid, args) => helper('auc_' + cmd, Object.assign({}, args, { id, cid })),
  more: (cmd, id, cid, args) => helper('more_' + cmd, Object.assign({}, args, { id, cid })),
  mito: (id, cid, mito) => helper('char_stats', { id, cid, mito }),
  exportData: (id, cid) => helper('export', { id, cid: cid || null, client: C.config().client }).then((r) => r.data),
  importCheck: (data) => helper('import_check', { data }).then((r) => r.info),
  importData: (data, opts) => helper('import', Object.assign({ data }, opts)),
  // live server (control port)
  level: (name, level) => control(`level ${name} ${level}`),
  giveCar: (name, car) => control(`car ${name} ${car}`),
  giveItem: (name, item, count) => control(`item ${name} ${item} ${count || 1}`),
  catalog: () => helper('catalog').then((r) => r.catalog),
  // the GM panel's commands: only these go to the control port (the same as the in-game gm... chat commands)
  gmRun: (line) => {
    const w = String(line || '').trim().split(/\s+/).filter(Boolean);
    const ok = ['who', 'kick', 'block', 'unblock', 'chatblock', 'ban', 'unban', 'level', 'exp', 'money', 'coin', 'item', 'car', 'drift', 'neo',
      'rushtimenow', 'rushtime', 'getrushtime', 'rushend', 'realmatch', 'gate', 'cbattle', 'event', 'crewexp'];
    if (!w.length || !ok.includes(w[0].toLowerCase())) throw new Error('gm_cmd');
    if (w.some((x) => /[\r\n]/.test(x))) throw new Error('gm_cmd');
    return control(w.join(' '));
  },
  control,
};
