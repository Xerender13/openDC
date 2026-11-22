'use strict';
// Every time the launcher opens it checks three things (GitHub is only READ):
//   emulator : new commits on openDC (main)                        -> download the repo zip, copy Emulator + Launcher
//   client   : the README's Google Drive link for this client changed -> download the new client, keep the player's settings
//   launcher : a newer "launcher-vX.Y.Z" release on the launcher repo  -> download it and restart into it
const fs = require('fs');
const path = require('path');
const cp = require('child_process');
const C = require('./core');
const S = require('./server');
const G = require('./game');
const I = require('./install');
const { IS_WIN, P, log } = C;

const DEFAULT_LAUNCHER_REPO = 'Xerender13/openDC';
// the player's own files inside the client folder, carried over to a new client
const KEEP = [['Data', 'Init', 'goption.ini'], ['DriftCityLauncher.ini']];

function newer(a, b) { // is version a > b ?
  const pa = a.split('.').map(Number), pb = b.split('.').map(Number);
  for (let i = 0; i < 3; i++) { if ((pa[i] || 0) !== (pb[i] || 0)) return (pa[i] || 0) > (pb[i] || 0); }
  return false;
}

// ---------- checks ----------
async function checkClient() {
  const cfg = C.config();
  const id = (await I.clientLinks())[cfg.client];
  if (!id) return { available: false };
  if (!cfg.clientId) { C.saveConfig({ clientId: id }); return { available: false }; } // first look: remember it
  return { available: id !== cfg.clientId, id };
}

async function checkLauncher(current) {
  const repo = C.config().launcherRepo || DEFAULT_LAUNCHER_REPO;
  const rels = await C.fetchJson(`https://api.github.com/repos/${repo}/releases?per_page=30`);
  const want = IS_WIN ? /-windows\.zip$/i : /x86_64\.appimage$/i;
  let best = null;
  for (const r of rels) {
    const m = !r.draft && !r.prerelease && /^launcher-v?(\d+\.\d+\.\d+)$/i.exec(r.tag_name || '');
    if (!m || !newer(m[1], current)) continue;
    const asset = (r.assets || []).find((a) => want.test(a.name));
    if (!asset) continue;
    if (!best || newer(m[1], best.version)) {
      best = { version: m[1], notes: (r.body || '').trim(), url: asset.browser_download_url, size: asset.size, page: r.html_url };
    }
  }
  return best ? Object.assign({ available: true }, best) : { available: false };
}

async function checkAll(current) {
  const installed = I.installed();
  const safe = (f) => f().catch((e) => ({ available: false, error: e.message }));
  const [emulator, client, launcher] = await Promise.all([
    installed ? safe(() => I.checkUpdate()) : { available: false },
    installed ? safe(checkClient) : { available: false },
    safe(() => checkLauncher(current)),
  ]);
  const r = { emulator, client, launcher, available: !!(emulator.available || client.available || launcher.available) };
  log('updates:', ['emulator', 'client', 'launcher'].map((k) => `${k}=${r[k].available ? 'new' : r[k].error ? 'error' : 'ok'}`).join(' '));
  return r;
}

// ---------- client ----------
async function updateClient(report) {
  if (await G.clientRunning()) throw new Error('close the game first');
  const cfg = C.config();
  const p = P();
  const id = (await I.clientLinks())[cfg.client];
  if (!id) throw new Error(`the openDC README has no ${cfg.client} client link`);
  fs.mkdirSync(p.down, { recursive: true });
  for (const n of fs.readdirSync(p.down)) if (n.startsWith('client-' + cfg.client + '.')) fs.rmSync(path.join(p.down, n), { force: true });
  report('client', 0);
  let archive = await C.gdriveDownload(id, p.down, (got, total) => report('client', total ? got / total : 0, { got, total }));
  const named = path.join(p.down, `client-${cfg.client}${path.extname(archive) || '.zip'}`);
  fs.renameSync(archive, named); archive = named;
  report('extract', 0.1);
  const tmp = path.join(p.tmp, 'client');
  C.rmrf(tmp);
  await C.extract(archive, tmp);
  const dir = C.findDirWith(tmp, ['DriftCity.exe'], 5);
  if (!dir) throw new Error('the client archive has no DriftCity.exe');
  // swap folders; keep the old one until the new one is in place
  const old = p.client + '.old';
  C.rmrf(old);
  if (fs.existsSync(p.client)) fs.renameSync(p.client, old);
  require('./verify').writeManifest(dir);
  try { C.moveDir(dir, p.client); } catch (e) { if (fs.existsSync(old)) fs.renameSync(old, p.client); throw e; }
  for (const parts of KEEP) {
    const from = path.join(old, ...parts);
    if (fs.existsSync(from)) { fs.mkdirSync(path.dirname(path.join(p.client, ...parts)), { recursive: true }); fs.copyFileSync(from, path.join(p.client, ...parts)); }
  }
  C.rmrf(old); C.rmrf(tmp);
  report('tables', 0.5);
  await S.clientTables(true);
  C.saveConfig({ clientId: id });
  await require('./mods').afterUpdate('client');   // a new Init.agt
  log('client: updated to', id);
}

// ---------- launcher ----------
// returns a function that main.js calls to quit into the new launcher (or null if it can't replace itself)
async function updateLauncher(info, report) {
  const p = P();
  fs.mkdirSync(p.tmp, { recursive: true });
  const prog = (got, total) => report('launcher', total ? got / total : 0, { got, total });
  if (!IS_WIN) {
    const target = process.env.APPIMAGE;
    if (!target) throw new Error('this launcher is not running from an AppImage: download the new one from ' + info.page);
    const tmpFile = target + '.new';
    await C.download(info.url, tmpFile, prog);
    fs.chmodSync(tmpFile, 0o755);
    fs.renameSync(tmpFile, target);      // the running copy stays mounted until we exit
    log('launcher: updated to', info.version);
    return { execPath: target };
  }
  const zip = path.join(p.tmp, 'launcher-new.zip');
  await C.download(info.url, zip, prog);
  const out = path.join(p.tmp, 'launcher-new');
  C.rmrf(out);
  await C.extract(zip, out);
  const src = C.findDirWith(out, ['openDC Launcher.exe'], 3);
  if (!src) throw new Error('the launcher download has no "openDC Launcher.exe"');
  const dest = path.dirname(process.execPath);
  const cmd = path.join(p.tmp, 'launcher-update.cmd');
  fs.writeFileSync(cmd, [
    '@echo off',
    ':wait',
    `tasklist /FI "PID eq ${process.pid}" | find "${process.pid}" >nul && (timeout /t 1 /nobreak >nul & goto wait)`,
    `robocopy "${src}" "${dest}" /E /R:5 /W:1 /NFL /NDL /NJH /NJS >nul`,
    `start "" "${path.join(dest, 'openDC Launcher.exe')}"`,
    `rmdir /s /q "${out}"`,
    `del "${zip}"`,
    '',
  ].join('\r\n'));
  log('launcher: update to', info.version, 'ready, restarting');
  return { run: () => cp.spawn('cmd.exe', ['/c', cmd], { detached: true, windowsHide: true, stdio: 'ignore' }).unref() };
}

module.exports = { checkAll, updateClient, updateLauncher, newer, DEFAULT_LAUNCHER_REPO };
