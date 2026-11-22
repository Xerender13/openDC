'use strict';
// Mods: optional changes to the game tables, applied to the client and the server together, with a backup of the
// original files so turning a mod off puts everything back. The table work is helper/odc_mods.py (portable Python).
//
//   rice_shop: Enhanced Rice's car list (V, required level, prices per V, coupons, dealership order) on the openDC
//              cars that both have (2016 client). Its reference tables are in app/mods/rice_shop/.
//
// Backups: runtime/mods/<id>/backup/{client,server}/<file>. An openDC update brings the server tables back from
// GitHub and a client update brings a new Init.agt: afterUpdate() keeps the new files as the new originals and
// applies the mod again.
const fs = require('fs');
const path = require('path');
const C = require('./core');
const S = require('./server');
const G = require('./game');
const { P, log } = C;

// rev: raised when a mod changes what it writes; an enabled mod of an older rev is applied again at start (refresh)
//   rice_shop 2: a dealership car is bought at its V tab (server rows below it get Capacity 0)
//   rice_shop 3: every openDC car with a model is in the dealership and sold
//   rice_shop 4: the special cars only openDC has priced like Rice's (mods/rice_shop/especiais.tsv)
//   rice_shop 5: the cars openDC hides (Support 0: only the wheels show) stay hidden
//   rice_shop 6: openDC's V9 cars priced like Rice's; the whole dealership in order (V, price; specials last by kind)
//   rice_shop 7: openDC's coupon book kept, coupon cars at its V; gotcha restriction (Req Cond) off, small cars kept
const MODS = [{ id: 'rice_shop', clients: ['2016'], rev: 7 }];
const revOf = (id) => ((C.config().modsRev || {})[id]) || 1;
function setRev(id) { const m = MODS.find((x) => x.id === id); C.saveConfig({ modsRev: Object.assign({}, C.config().modsRev || {}, { [id]: m.rev }) }); }
let helperPath = null;
let refsRoot = null;
function setPaths(helper, mods) { helperPath = helper; refsRoot = mods; }

const enabled = (id) => !!((C.config().mods || {})[id]);
function setEnabled(id, on) { C.saveConfig({ mods: Object.assign({}, C.config().mods || {}, { [id]: on }) }); }

function serverInit() {
  const p = P();
  const cand = [path.join(p.emu, 'server_data_2016', 'Init'), path.join(p.emu, 'server_data', 'Init')];
  return C.config().client === '2016' ? cand[0] : cand[1];
}
const backupDir = (id) => path.join(P().rt, 'mods', id, 'backup');

async function helper(req) {
  const p = P();
  if (!fs.existsSync(p.pyExe)) throw new Error('install the game first');
  const r = await C.run(p.pyExe, ['-I', helperPath], { input: JSON.stringify(req) });
  let out;
  try { out = JSON.parse(r.out); } catch { throw new Error((r.err || r.out || 'mods helper failed').trim().split('\n').pop()); }
  if (!out.ok) throw new Error(out.error || 'mods helper failed');
  return out;
}

const request = (id, extra) => Object.assign({ cmd: id, client: P().client, server_init: serverInit(), refs: path.join(refsRoot, id) }, extra || {});

// which side a file is on, and its backup path
function sideOf(file) {
  const p = P();
  return file.startsWith(p.client + path.sep) ? 'client' : 'server';
}
function backupPath(id, file) {
  const p = P();
  const side = sideOf(file);
  const rel = path.relative(side === 'client' ? p.client : serverInit(), file);
  return path.join(backupDir(id), side, rel);
}

// copy the current files as the originals (only the sides asked; never over an existing backup unless fresh = true)
async function backup(id, sides, fresh) {
  const { files } = await helper(Object.assign(request(id), { cmd: 'targets' }));
  for (const f of files) {
    if (!sides.includes(sideOf(f))) continue;
    const b = backupPath(id, f);
    if (fs.existsSync(b) && !fresh) continue;
    fs.mkdirSync(path.dirname(b), { recursive: true });
    fs.copyFileSync(f, b);
  }
}

function restore(id) { const n = restoreFiles(id); C.rmrf(backupDir(id)); return n; }

function restoreFiles(id) {
  const root = backupDir(id);
  const p = P();
  let n = 0;
  for (const side of ['client', 'server']) {
    const base = path.join(root, side);
    if (!fs.existsSync(base)) continue;
    const walk = (dir) => {
      for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, e.name);
        if (e.isDirectory()) { walk(full); continue; }
        const dest = path.join(side === 'client' ? p.client : serverInit(), path.relative(base, full));
        fs.mkdirSync(path.dirname(dest), { recursive: true });
        fs.copyFileSync(full, dest + '.tmp');
        fs.renameSync(dest + '.tmp', dest);
        n++;
      }
    };
    walk(base);
  }
  return n;
}

// stop the server while the tables change (it reads them at start), and start it again after
async function withServerOff(fn) {
  if (await G.clientRunning()) throw new Error('close the game first');
  const wasOn = S.serverRunning();
  if (wasOn) await S.stopServer();
  try { return await fn(); } finally { if (wasOn) await S.startServer().catch((e) => log('mods: server start:', e.message)); }
}

function list() {
  const cl = C.config().client;
  return MODS.map((m) => ({ id: m.id, enabled: enabled(m.id), supported: m.clients.includes(cl) }));
}

async function preview(id) {
  return helper(request(id, { test: true }));
}

async function enable(id) {
  const m = MODS.find((x) => x.id === id);
  if (!m) throw new Error('unknown mod');
  if (!m.clients.includes(C.config().client)) throw new Error('mod_client');
  return withServerOff(async () => {
    await backup(id, ['client', 'server'], false);
    const r = await helper(request(id));
    setEnabled(id, true);
    setRev(id);
    log(`mods: ${id} on`, JSON.stringify(r.client), `(${r.written.length} files)`);
    return r;
  });
}

async function disable(id) {
  return withServerOff(async () => {
    const n = restore(id);
    setEnabled(id, false);
    log(`mods: ${id} off, ${n} files restored`);
    return { restored: n };
  });
}

// after an openDC update (side 'server') or a client update (side 'client'): the new files are the new originals
async function afterUpdate(side) {
  for (const m of MODS) {
    if (!enabled(m.id) || !m.clients.includes(C.config().client)) continue;
    try {
      await backup(m.id, [side], true);
      const r = await helper(request(m.id));
      log(`mods: ${m.id} applied again after the ${side} update`, JSON.stringify(r[side === 'client' ? 'client' : 'server']));
    } catch (e) { log(`mods: ${m.id} after the ${side} update:`, e.message); }
  }
}

// at start: an enabled mod written by an older launcher is applied again (on the original files from its backup)
async function refresh() {
  for (const m of MODS) {
    if (!enabled(m.id) || !m.clients.includes(C.config().client) || revOf(m.id) >= m.rev) continue;
    try {
      await withServerOff(async () => {
        restoreFiles(m.id);
        const r = await helper(request(m.id));
        setRev(m.id);
        log(`mods: ${m.id} updated to rev ${m.rev}`, JSON.stringify(r.server));
      });
    } catch (e) { log(`mods: ${m.id} refresh:`, e.message); }
  }
}

module.exports = { setPaths, list, preview, enable, disable, afterUpdate, refresh };
