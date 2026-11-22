'use strict';
// Install (client from the README's Google Drive link, openDC from GitHub, Python, PostgreSQL, Proton),
// state detection, openDC updates and the commit list (patch notes). GitHub is only READ.
const fs = require('fs');
const path = require('path');
const C = require('./core');
const S = require('./server');
const G = require('./game');
const { IS_WIN, P, log } = C;

const CLIENT_EXE = ['DriftCity.exe', 'DriftCityUS.exe', 'DriftCityEU.exe'];

function installed() {
  const p = P();
  return fs.existsSync(path.join(p.emu, 'dcemu')) && fs.existsSync(path.join(p.client, 'DriftCity.exe'));
}

// an existing openDC folder (e.g. "openDC Client US 2016") the player already has
function adoptFolder(dir) {
  const ok = fs.existsSync(path.join(dir, 'Emulator', 'dcemu'));
  if (!ok) throw new Error('this folder has no Emulator\\dcemu: pick the folder that holds Emulator and the client');
  const client = fs.existsSync(path.join(dir, 'DriftCity Dev Ed', 'DriftCity.exe')) ? '2016'
    : fs.existsSync(path.join(dir, 'Client US', 'DriftCity.exe')) ? '2011' : C.config().client;
  C.saveConfig({ root: dir, client });
  return { root: dir, client };
}

// ---------- GitHub (read only) ----------
async function commits(n = 40) {
  const list = await C.fetchJson(`https://api.github.com/repos/${C.REPO}/commits?sha=main&per_page=${n}`);
  return list.map((c) => ({
    sha: c.sha,
    date: c.commit.author.date,
    title: c.commit.message.split('\n')[0],
    body: c.commit.message.split('\n').slice(1).join('\n').trim(),
  }));
}

async function clientLinks() {
  // the README's "2011 US client download" / "2016 US client download" Google Drive links
  const md = await C.fetchText(`https://raw.githubusercontent.com/${C.REPO}/main/README.md`);
  const links = {};
  for (const m of md.matchAll(/\[(\d{4})[^\]]*client download\]\((https:\/\/drive\.google\.com\/[^)]+)\)/gi)) {
    const id = (m[2].match(/\/d\/([\w-]+)/) || m[2].match(/id=([\w-]+)/) || [])[1];
    if (id) links[m[1]] = id;
  }
  return links;
}

async function downloadRepo(sha, onProg) {
  const p = P();
  const file = path.join(p.down, `openDC-${sha.slice(0, 7)}.zip`);
  if (!fs.existsSync(file)) await C.download(`https://codeload.github.com/${C.REPO}/zip/${sha}`, file, onProg);
  const tmp = path.join(p.tmp, 'repo');
  C.rmrf(tmp);
  await C.extract(file, tmp);
  const top = fs.readdirSync(tmp).map((n) => path.join(tmp, n)).find((d) => fs.existsSync(path.join(d, 'Emulator', 'dcemu')));
  if (!top) throw new Error('the openDC download has no Emulator folder');
  return top;
}

// copy the repo's Emulator and Launcher over the install, keeping what the player made
function applyRepo(top) {
  const p = P();
  const ini = path.join(p.emu, 'emulator.ini');
  if (fs.existsSync(ini)) fs.copyFileSync(ini, ini + '.before-update');
  fs.cpSync(path.join(top, 'Emulator'), p.emu, { recursive: true, force: true });
  if (fs.existsSync(path.join(top, 'Launcher'))) fs.cpSync(path.join(top, 'Launcher'), p.launcherSrc, { recursive: true, force: true });
  for (const f of ['README.md', 'openDC GM Commands.pdf', 'openDC_logo_white.png']) {
    if (fs.existsSync(path.join(top, f))) fs.copyFileSync(path.join(top, f), path.join(p.root, f));
  }
}

// ---------- install ----------
// steps for the progress bar; the UI shows step i of n with its percent
function steps() {
  const s = ['client', 'extract', 'server', 'python', 'postgres'];
  if (!IS_WIN) s.push('proton');
  s.push('database', 'tables');
  return s;
}

async function install(client, report) {
  C.saveConfig({ client });
  const p = P();
  for (const d of [p.root, p.rt, p.down, p.tmp, p.logs]) fs.mkdirSync(d, { recursive: true });
  const list = steps();
  const step = (name, frac, extra) => report({ step: list.indexOf(name), n: list.length, name, frac: frac || 0, extra });
  const prog = (name) => (got, total) => step(name, total ? got / total : 0, { got, total });

  // 1-2) the client, unless it is already there
  if (!fs.existsSync(path.join(p.client, 'DriftCity.exe'))) {
    step('client', 0);
    const links = await clientLinks();
    if (!links[client]) throw new Error(`the openDC README has no ${client} client link`);
    let archive = fs.readdirSync(p.down).find((n) => n.startsWith('client-' + client + '.'));
    archive = archive ? path.join(p.down, archive) : await C.gdriveDownload(links[client], p.down, prog('client'));
    if (!path.basename(archive).startsWith('client-')) {
      const named = path.join(p.down, `client-${client}${path.extname(archive) || '.zip'}`);
      fs.renameSync(archive, named);
      archive = named;
    }
    step('extract', 0.1);
    const tmp = path.join(p.tmp, 'client');
    C.rmrf(tmp);
    await C.extract(archive, tmp);
    const dir = C.findDirWith(tmp, CLIENT_EXE, 5);
    if (!dir) throw new Error('the client archive has no DriftCity.exe');
    require('./verify').writeManifest(dir);   // for Settings > Folders > Check files
    C.moveDir(dir, p.client);
    C.rmrf(tmp);
    C.saveConfig({ clientId: links[client] });
    step('extract', 1);
  }

  // 3) openDC (Emulator + Launcher) from GitHub
  step('server', 0);
  if (!fs.existsSync(path.join(p.emu, 'dcemu'))) {
    let sha = 'main';
    try { sha = (await commits(1))[0].sha; } catch (e) { log('GitHub API:', e.message); }
    const top = await downloadRepo(sha, prog('server'));
    applyRepo(top);
    C.rmrf(path.join(p.tmp, 'repo'));
    if (sha !== 'main') C.saveConfig({ installedSha: sha });
  }

  // 4-5) Python + PostgreSQL
  step('python', 0);
  await S.preparePython(prog('python'));
  await S.readEmuConfig();
  step('postgres', 0);
  await S.preparePostgres(prog('postgres'));

  // 6) Linux: Proton (Steam's, or GE-Proton)
  if (!IS_WIN) { step('proton', 0); await G.prepareProton('soft'); }   // picks one; none is not an install error

  // 7-8) database + client tables
  step('database', 0.3);
  await S.clientTables(false);
  await S.startDb();
  step('tables', 1);
  C.rmrf(p.tmp);
  log('install: done');
}

// ---------- updates ----------
async function checkUpdate() {
  const cfg = C.config();
  const list = await commits(40);
  if (!list.length) return { available: false, changes: [] };
  const latest = list[0].sha;
  if (!cfg.installedSha) {
    // unknown (an adopted folder): don't claim an update, just remember where we are
    C.saveConfig({ installedSha: latest });
    return { available: false, latest, changes: [] };
  }
  if (cfg.installedSha === latest) return { available: false, latest, changes: [] };
  const i = list.findIndex((c) => c.sha === cfg.installedSha);
  const changes = (i < 0 ? list : list.slice(0, i));
  return { available: changes.length > 0, latest, changes };
}

async function update(report) {
  const wasOn = S.serverRunning();
  report({ step: 0, n: 3, name: 'check', frac: 0.5 });
  const list = await commits(1);
  const sha = list[0].sha;
  report({ step: 1, n: 3, name: 'download', frac: 0 });
  const top = await downloadRepo(sha, (got, total) => report({ step: 1, n: 3, name: 'download', frac: total ? got / total : 0 }));
  report({ step: 2, n: 3, name: 'restart', frac: 0.2 });
  if (wasOn) await S.stopServer();
  applyRepo(top);
  C.rmrf(path.join(P().tmp, 'repo'));
  C.saveConfig({ installedSha: sha });
  await S.readEmuConfig();
  await require('./mods').afterUpdate('server');   // the server tables came back from GitHub
  if (wasOn) await S.startServer();
  report({ step: 2, n: 3, name: 'restart', frac: 1 });
}

module.exports = { installed, adoptFolder, commits, clientLinks, install, steps, checkUpdate, update, downloadRepo };
