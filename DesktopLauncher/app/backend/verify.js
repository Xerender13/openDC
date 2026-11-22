'use strict';
// Settings > Folders > "Check files": what is missing from the client, the server (Emulator + Launcher) and the
// runtime (Python, PostgreSQL), and the repair that downloads only that.
//
//   client : runtime/client_manifest.json (every file of the client archive and its size, written when the client
//            is installed, updated or repaired). Without it (an adopted folder), only the main files are checked; the
//            repair then compares against the client archive (the cached download, or the README link again).
//            Files the player or a mod changes on purpose are checked for presence only (SIZE_FREE).
//   server : the GitHub tree of the installed commit (Emulator/, Launcher/): a missing file comes back from that
//            commit's zip; existing files are never overwritten (emulator.ini, mod tables...).
//   runtime: the portable Python and PostgreSQL, downloaded again when missing.
const fs = require('fs');
const path = require('path');
const C = require('./core');
const S = require('./server');
const G = require('./game');
const I = require('./install');
const { P, log } = C;

const MANIFEST = () => path.join(P().rt, 'client_manifest.json');
const CLIENT_EXE = ['DriftCity.exe', 'DriftCityUS.exe', 'DriftCityEU.exe'];
// the main client files when there is no manifest (the 2016 client's packs)
const ESSENTIAL = ['Data/Init.agt', 'Data/game.agt', 'Data/vehicles.agt', 'Data/decal.agt', 'Data/effects.agt',
  'Data/Localize.agt', 'Data/shader.agt', 'Data/Option.agt', 'Data/Init/def_option.ini'];
// present is enough: the game, the launchers or a mod change these
const SIZE_FREE = new Set(['data/init.agt', 'data_us/init_us.agt', 'data/init/goption.ini', 'driftcitylauncher.ini',
  'driftcity.exe', 'driftcityus.exe', 'driftcityeu.exe']);
const norm = (rel) => rel.split(path.sep).join('/');

function walk(dir) {
  const out = {};
  const go = (d) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const full = path.join(d, e.name);
      if (e.isDirectory()) go(full);
      else if (e.isFile()) out[norm(path.relative(dir, full))] = fs.statSync(full).size;
    }
  };
  go(dir);
  return out;
}

function writeManifest(fromDir) {
  try {
    fs.mkdirSync(P().rt, { recursive: true });
    fs.writeFileSync(MANIFEST(), JSON.stringify(walk(fromDir)));
  } catch (e) { log('verify: manifest:', e.message); }
}

function readManifest() {
  try { return JSON.parse(fs.readFileSync(MANIFEST(), 'utf8')); } catch { return null; }
}

function checkClient() {
  const p = P();
  const man = readManifest();
  const missing = [];
  if (!man) {
    const exe = CLIENT_EXE.find((x) => fs.existsSync(path.join(p.client, x)));
    if (!exe) missing.push('DriftCity.exe');
    for (const f of ESSENTIAL) if (!fs.existsSync(path.join(p.client, f))) missing.push(f);
    return { manifest: false, checked: ESSENTIAL.length + 1, missing };
  }
  for (const [rel, size] of Object.entries(man)) {
    const full = path.join(p.client, ...rel.split('/'));
    let st = null;
    try { st = fs.statSync(full); } catch { /* missing */ }
    if (!st) missing.push(rel);
    else if (st.size !== size && !SIZE_FREE.has(rel.toLowerCase())) missing.push(rel);
  }
  return { manifest: true, checked: Object.keys(man).length, missing };
}

async function repoTree(sha) {
  const t = await C.fetchJson(`https://api.github.com/repos/${C.REPO}/git/trees/${sha}?recursive=1`);
  return { files: (t.tree || []).filter((x) => x.type === 'blob').map((x) => x.path), truncated: !!t.truncated };
}

async function checkServer() {
  const p = P();
  const sha = C.config().installedSha || 'main';
  let tree;
  try { tree = await repoTree(sha); } catch (e) { return { error: e.message, missing: [] }; }
  const missing = [];
  for (const f of tree.files) {
    let local = null;
    if (f.startsWith('Emulator/')) local = path.join(p.emu, ...f.slice(9).split('/'));
    else if (f.startsWith('Launcher/')) local = path.join(p.launcherSrc, ...f.slice(9).split('/'));
    if (local && !fs.existsSync(local)) missing.push(f);
  }
  return { sha, checked: tree.files.filter((f) => /^(Emulator|Launcher)\//.test(f)).length, missing, truncated: tree.truncated };
}

function checkRuntime() {
  const p = P();
  const missing = [];
  if (!fs.existsSync(p.pyExe)) missing.push('python');
  if (!fs.existsSync(path.join(p.pgBin, C.exe('pg_ctl')))) missing.push('postgres');
  return { missing, database: fs.existsSync(path.join(p.pgData, 'PG_VERSION')) };
}

async function verify() {
  if (!I.installed()) throw new Error('install the game first');
  const [client, server] = [checkClient(), await checkServer()];
  const runtime = checkRuntime();
  const r = { client, server, runtime, ok: !client.missing.length && !server.missing.length && !runtime.missing.length && !server.error };
  log('verify:', `client ${client.missing.length} of ${client.checked}${client.manifest ? '' : ' (no manifest)'},`,
    `server ${server.missing.length}${server.error ? ' (' + server.error + ')' : ''}, runtime [${runtime.missing}]`);
  return r;
}

// ---------- repair: only what is missing ----------
async function repair(report) {
  const p = P();
  const v = await verify();
  const list = [];
  if (v.server.missing.length) list.push('server');
  if (v.runtime.missing.includes('python')) list.push('python');
  if (v.runtime.missing.includes('postgres')) list.push('postgres');
  if (v.client.missing.length) list.push('client', 'extract');
  const step = (name, frac, extra) => report({ step: Math.max(0, list.indexOf(name)), n: list.length || 1, name, frac: frac || 0, extra });
  const prog = (name) => (got, total) => step(name, total ? got / total : 0, { got, total });
  const done = { server: 0, client: 0, python: false, postgres: false };

  if (v.server.missing.length) {
    step('server', 0);
    const top = await I.downloadRepo(v.server.sha, prog('server'));
    for (const f of v.server.missing) {
      const src = path.join(top, ...f.split('/'));
      const dest = f.startsWith('Emulator/') ? path.join(p.emu, ...f.slice(9).split('/')) : path.join(p.launcherSrc, ...f.slice(9).split('/'));
      if (fs.existsSync(src) && !fs.existsSync(dest)) {
        fs.mkdirSync(path.dirname(dest), { recursive: true });
        fs.copyFileSync(src, dest);
        done.server++;
      }
    }
    C.rmrf(path.join(p.tmp, 'repo'));
  }
  if (v.runtime.missing.includes('python')) { step('python', 0); await S.preparePython(prog('python')); done.python = true; }
  if (v.runtime.missing.includes('postgres')) { step('postgres', 0); await S.preparePostgres(prog('postgres')); done.postgres = true; }

  if (v.client.missing.length) {
    if (await G.clientRunning()) throw new Error('close the game first');
    step('client', 0);
    const cl = C.config().client;
    fs.mkdirSync(p.down, { recursive: true });
    let archive = fs.readdirSync(p.down).find((n) => n.startsWith('client-' + cl + '.'));
    if (archive) archive = path.join(p.down, archive);
    else {
      const id = (await I.clientLinks())[cl];
      if (!id) throw new Error(`the openDC README has no ${cl} client link`);
      archive = await C.gdriveDownload(id, p.down, prog('client'));
      const named = path.join(p.down, `client-${cl}${path.extname(archive) || '.zip'}`);
      fs.renameSync(archive, named);
      archive = named;
    }
    step('extract', 0.1);
    const tmp = path.join(p.tmp, 'client-check');
    C.rmrf(tmp);
    await C.extract(archive, tmp);
    const dir = C.findDirWith(tmp, CLIENT_EXE, 5);
    if (!dir) throw new Error('the client archive has no DriftCity.exe');
    const fresh = walk(dir);
    // without a manifest the whole archive is compared now (missing files, and wrong sizes outside SIZE_FREE)
    const want = v.client.manifest ? v.client.missing : Object.keys(fresh).filter((rel) => {
      const full = path.join(p.client, ...rel.split('/'));
      if (!fs.existsSync(full)) return true;
      return !SIZE_FREE.has(rel.toLowerCase()) && fs.statSync(full).size !== fresh[rel];
    });
    for (const rel of want) {
      const src = path.join(dir, ...rel.split('/'));
      if (!fs.existsSync(src)) continue;
      const dest = path.join(p.client, ...rel.split('/'));
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      fs.copyFileSync(src, dest + '.tmp');
      fs.renameSync(dest + '.tmp', dest);
      done.client++;
    }
    writeManifest(dir);
    C.rmrf(tmp);
    step('extract', 1);
    if (done.client) {
      await S.clientTables(false);
      await require('./mods').afterUpdate('client');   // Init.agt may be the original again
    }
  }
  log('verify: repaired', JSON.stringify(done));
  return done;
}

module.exports = { verify, repair, writeManifest };
