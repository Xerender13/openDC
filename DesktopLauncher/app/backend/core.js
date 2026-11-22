'use strict';
// Shared helpers: settings, paths, log, downloads, archives, processes, ports.
const fs = require('fs');
const path = require('path');
const os = require('os');
const net = require('net');
const cp = require('child_process');
const { EventEmitter } = require('events');

const IS_WIN = process.platform === 'win32';
const bus = new EventEmitter();          // 'log' {line}, 'state' {...}, 'progress' {...}
bus.setMaxListeners(50);

const REPO = 'Xerender13/openDC';
const UA = { 'User-Agent': 'openDC-Launcher' };

// ---------- settings (userData/config.json) ----------
let cfgFile = null;
let cfg = null;
const DEFAULTS = {
  root: path.join(os.homedir(), 'Games', 'openDC'),
  lang: null,             // null = not chosen yet: the system's language (main.js), English when not pt / ru
  client: '2016',          // which client is installed / wanted
  autoStart: true,        // start the database + server when the launcher opens
  onGame: 'tray',          // tray | minimize | none : what the launcher does while the game is open
  serverMode: 'local',     // local | remote
  maxClients: 1,           // game clients open at the same time (1-4)
  remoteIp: '',
  installedSha: null,      // openDC commit the Emulator folder came from
  splash: true,
  autoBackup: true,
};
function initConfig(userData) {
  cfgFile = path.join(userData, 'config.json');
  try { cfg = Object.assign({}, DEFAULTS, JSON.parse(fs.readFileSync(cfgFile, 'utf8'))); }
  catch { cfg = Object.assign({}, DEFAULTS); }
  return cfg;
}
function config() { return cfg; }
function saveConfig(patch) {
  Object.assign(cfg, patch || {});
  fs.mkdirSync(path.dirname(cfgFile), { recursive: true });
  fs.writeFileSync(cfgFile, JSON.stringify(cfg, null, 2));
  return cfg;
}

// ---------- paths under the install folder ----------
function P() {
  const root = cfg.root;
  const rt = path.join(root, 'runtime');
  return {
    root, rt,
    emu: path.join(root, 'Emulator'),
    launcherSrc: path.join(root, 'Launcher'),
    client: path.join(root, cfg.client === '2011' ? 'Client US' : 'DriftCity Dev Ed'),
    py: path.join(rt, 'python'),
    pyExe: IS_WIN ? path.join(rt, 'python', 'python.exe') : path.join(rt, 'python', 'bin', 'python3'),
    pg: path.join(rt, 'pgsql'),
    pgBin: path.join(rt, 'pgsql', 'bin'),
    pgData: path.join(rt, 'pgdata'),
    logs: path.join(rt, 'logs'),
    down: path.join(rt, 'downloads'),
    tmp: path.join(rt, 'tmp'),
    proton: path.join(rt, 'proton'),
    backups: path.join(rt, 'backups'),
    mods: path.join(root, 'mods'),
  };
}
function exe(name) { return IS_WIN ? name + '.exe' : name; }

// ---------- log ----------
function log(...a) {
  const line = `${new Date().toISOString().slice(11, 19)} ${a.join(' ')}`;
  try {
    const p = P();
    fs.mkdirSync(p.logs, { recursive: true });
    fs.appendFileSync(path.join(p.logs, 'launcher.log'), line + '\n');
  } catch { /* the folder may not exist yet */ }
  bus.emit('log', line);
}
function progress(o) { bus.emit('progress', o); }

// ---------- processes ----------
function run(cmd, args, opts = {}) {
  // -> {code, out, err}; never throws
  return new Promise((resolve) => {
    let out = '', err = '';
    let p;
    try { p = cp.spawn(cmd, args, Object.assign({ windowsHide: true }, opts)); }
    catch (e) { resolve({ code: -1, out: '', err: String(e) }); return; }
    if (p.stdout) p.stdout.on('data', (d) => { out += d; if (opts.onLine) String(d).split(/\r?\n/).filter(Boolean).forEach(opts.onLine); });
    if (p.stderr) p.stderr.on('data', (d) => { err += d; if (opts.onLine) String(d).split(/\r?\n/).filter(Boolean).forEach(opts.onLine); });
    p.on('error', (e) => resolve({ code: -1, out, err: err + String(e) }));
    p.on('close', (code) => resolve({ code, out, err }));
    if (opts.input != null) { p.stdin.write(opts.input); p.stdin.end(); }
  });
}
function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

function portBusy(port, host = '127.0.0.1') {
  return new Promise((resolve) => {
    const s = net.connect({ port, host });
    s.setTimeout(800);
    s.on('connect', () => { s.destroy(); resolve(true); });
    s.on('timeout', () => { s.destroy(); resolve(false); });
    s.on('error', () => resolve(false));
  });
}

async function processRunning(pattern) {
  // is a process whose image / command line matches running?
  if (IS_WIN) {
    const r = await run('tasklist', ['/FO', 'CSV', '/NH']);
    return r.out.toLowerCase().includes(`"${pattern.toLowerCase()}"`);
  }
  const r = await run('pgrep', ['-u', String(process.getuid()), '-f', pattern.replace('.', '\\.')]);
  return r.code === 0;
}

// ---------- downloads ----------
// fetch with a readable error ("can't reach github.com (ENOTFOUND)") instead of "fetch failed"
async function web(url, opts) {
  try { return await fetch(url, opts); }
  catch (e) {
    const c = e.cause || {};
    throw new Error(`can't reach ${new URL(url).host} (${c.code || c.message || e.message}) — check the internet connection`);
  }
}
async function fetchJson(url) {
  const r = await web(url, { headers: Object.assign({ Accept: 'application/vnd.github+json' }, UA) });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}
async function fetchText(url) {
  const r = await web(url, { headers: UA });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.text();
}

// stream a response to a file, with progress (bytes, total)
async function saveResponse(resp, dest, onProg) {
  const { Readable, Transform } = require('stream');
  const { pipeline } = require('stream/promises');
  const total = Number(resp.headers.get('content-length')) || 0;
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  const tmp = dest + '.partial';
  let got = 0, last = 0;
  const count = new Transform({
    transform(chunk, _enc, cb) {
      got += chunk.length;
      const now = Date.now();
      if (onProg && now - last > 150) { last = now; onProg(got, total); }
      cb(null, chunk);
    },
  });
  await pipeline(Readable.fromWeb(resp.body), count, fs.createWriteStream(tmp));
  if (onProg) onProg(got, total || got);
  fs.renameSync(tmp, dest);
  return dest;
}

async function download(url, dest, onProg) {
  log('download', url);
  const r = await web(url, { headers: UA, redirect: 'follow' });
  if (!r.ok) throw new Error(`download ${url}: HTTP ${r.status}`);
  return saveResponse(r, dest, onProg);
}

function fileNameFrom(resp) {
  const cd = resp.headers.get('content-disposition') || '';
  const m = cd.match(/filename\*=UTF-8''([^;]+)/i) || cd.match(/filename="?([^";]+)"?/i);
  return m ? decodeURIComponent(m[1]) : null;
}

// Google Drive: small files come straight away, big ones after the "can't scan for viruses" page,
// whose form has the real address (drive.usercontent.google.com) and its fields (id, export, confirm, uuid).
async function gdriveDownload(id, destDir, onProg) {
  log('download Google Drive', id);
  let r = await web(`https://drive.google.com/uc?export=download&id=${id}`, { headers: UA, redirect: 'follow' });
  if (!r.ok) throw new Error(`Google Drive: HTTP ${r.status}`);
  if ((r.headers.get('content-type') || '').includes('text/html')) {
    const html = await r.text();
    const form = html.match(/<form[^>]*action="([^"]+)"[^>]*>([\s\S]*?)<\/form>/i);
    if (!form) throw new Error('Google Drive: the download page changed (no form); download the client by hand');
    const url = new URL(form[1].replace(/&amp;/g, '&'));
    for (const m of form[2].matchAll(/<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"/gi)) url.searchParams.set(m[1], m[2]);
    r = await web(url, { headers: UA, redirect: 'follow' });
    if (!r.ok || (r.headers.get('content-type') || '').includes('text/html')) {
      throw new Error('Google Drive refused the download (quota or link changed); try again later or download it by hand');
    }
  }
  const name = fileNameFrom(r) || `client-${id}.zip`;
  const dest = path.join(destDir, name.replace(/[\\/:*?"<>|]/g, '_'));
  return saveResponse(r, dest, onProg);
}

// ---------- archives ----------
let sevenZip = null;        // set by main.js (bundled 7zz on Linux)
function setSevenZip(p) { sevenZip = p; }

async function extract(archive, destDir) {
  fs.mkdirSync(destDir, { recursive: true });
  const low = archive.toLowerCase();
  const isTar = /\.(tar\.gz|tgz|tar\.xz|txz|tar\.zst|tar)$/.test(low);
  let r;
  if (IS_WIN) {
    // Windows 10+ tar.exe (bsdtar / libarchive): tar.*, zip, 7z and rar
    r = await run(path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'tar.exe'), ['-xf', archive, '-C', destDir]);
  } else if (isTar) {
    r = await run('tar', ['-xf', archive, '-C', destDir]);
  } else {
    if (!sevenZip || !fs.existsSync(sevenZip)) throw new Error('7-Zip (7zz) is missing from the launcher');
    r = await run(sevenZip, ['x', '-y', `-o${destDir}`, archive]);
  }
  if (r.code !== 0) throw new Error(`extracting ${path.basename(archive)} failed: ${(r.err || r.out).slice(-400)}`);
}

// find the first folder (depth <= maxDepth) that contains a file with one of these names
function findDirWith(dir, names, maxDepth = 4) {
  const want = names.map((n) => n.toLowerCase());
  const walk = (d, depth) => {
    let ents;
    try { ents = fs.readdirSync(d, { withFileTypes: true }); } catch { return null; }
    if (ents.some((e) => e.isFile() && want.includes(e.name.toLowerCase()))) return d;
    if (depth >= maxDepth) return null;
    for (const e of ents) if (e.isDirectory()) { const f = walk(path.join(d, e.name), depth + 1); if (f) return f; }
    return null;
  };
  return walk(dir, 0);
}

function rmrf(p) { try { fs.rmSync(p, { recursive: true, force: true, maxRetries: 3 }); } catch { /* ignore */ } }

// move a folder; across devices (or onto an existing one) copy then delete
function moveDir(src, dst) {
  rmrf(dst);
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  try { fs.renameSync(src, dst); }
  catch { fs.cpSync(src, dst, { recursive: true }); rmrf(src); }
}

// ---------- tiny ini editor (keeps comments, order and line endings) ----------
function iniRead(file) {
  const out = {};
  let sec = '';
  let txt;
  try { txt = fs.readFileSync(file, 'utf8'); } catch { return out; }
  for (let l of txt.split(/\r?\n/)) {
    l = l.trim();
    if (!l || l[0] === ';' || l[0] === '#') continue;
    const s = l.match(/^\[(.+)\]$/);
    if (s) { sec = s[1].trim(); continue; }
    const kv = l.match(/^([^=]+?)\s*=\s*(.*)$/);
    if (kv) out[`${sec}.${kv[1].trim()}`] = kv[2].replace(/\s+[;#].*$/, '').trim();
  }
  return out;
}
function iniSet(file, sets) {
  // sets: {'Section.Key': value}
  let txt = '';
  try { txt = fs.readFileSync(file, 'utf8'); } catch { /* new file */ }
  const eol = txt.includes('\r\n') ? '\r\n' : '\n';
  const lines = txt ? txt.split(/\r?\n/) : [];
  const pending = new Map(Object.entries(sets));
  let sec = '';
  for (let i = 0; i < lines.length; i++) {
    const t = lines[i].trim();
    const s = t.match(/^\[(.+)\]$/);
    if (s) { sec = s[1].trim(); continue; }
    const kv = t.match(/^([^=;#]+?)\s*=/);
    if (!kv) continue;
    const key = `${sec}.${kv[1].trim()}`;
    for (const [k, v] of pending) {
      if (k.toLowerCase() === key.toLowerCase()) {
        const spaced = /\s=\s/.test(lines[i]);
        lines[i] = `${kv[1].trim()}${spaced ? ' = ' : '='}${v}`;
        pending.delete(k);
      }
    }
  }
  for (const [k, v] of pending) {
    const dot = k.indexOf('.');
    const section = k.slice(0, dot), key = k.slice(dot + 1);
    let at = lines.findIndex((l) => l.trim().toLowerCase() === `[${section.toLowerCase()}]`);
    if (at < 0) { if (lines.length && lines[lines.length - 1] !== '') lines.push(''); lines.push(`[${section}]`); at = lines.length - 1; }
    let end = at + 1;
    while (end < lines.length && !/^\s*\[/.test(lines[end])) end++;
    while (end > at + 1 && lines[end - 1].trim() === '') end--;
    lines.splice(end, 0, `${key}=${v}`);
  }
  fs.writeFileSync(file, lines.join(eol));
}

module.exports = {
  IS_WIN, bus, REPO, UA, initConfig, config, saveConfig, P, exe, log, progress, run, sleep, portBusy,
  processRunning, fetchJson, fetchText, download, gdriveDownload, setSevenZip, extract, findDirWith, rmrf,
  moveDir, iniRead, iniSet,
};
