'use strict';
// The game: openDC's DriftCityLauncher (Windows .exe, Linux DriftCityLauncher2016 with Proton), its ini,
// Proton on Linux, and watching DriftCity.exe so the server can stop when the game closes.
const fs = require('fs');
const path = require('path');
const os = require('os');
const cp = require('child_process');
const C = require('./core');
const { IS_WIN, P, log } = C;

const home = os.homedir();
const expand = (s) => (s && s.startsWith('~') ? path.join(home, s.slice(1)) : s);
function launcherIni() { return path.join(P().client, 'DriftCityLauncher.ini'); }

// ---------- Proton (Linux) ----------
function steamRoots() {
  const roots = [
    path.join(home, '.local/share/Steam'), path.join(home, '.steam/steam'), path.join(home, '.steam/root'),
    path.join(home, '.var/app/com.valvesoftware.Steam/.local/share/Steam'),
  ];
  return [...new Set(roots.filter((r) => fs.existsSync(path.join(r, 'steamapps'))).map((r) => { try { return fs.realpathSync(r); } catch { return r; } }))];
}
function steamLibraries(root) {
  const libs = [path.join(root, 'steamapps')];
  try {
    const vdf = fs.readFileSync(path.join(root, 'steamapps', 'libraryfolders.vdf'), 'utf8');
    for (const m of vdf.matchAll(/"path"\s+"([^"]+)"/g)) libs.push(path.join(m[1], 'steamapps'));
  } catch { /* single library */ }
  return [...new Set(libs)];
}
// every Proton we can use: [{name, proton (script), steam (root)}], best first
function findProtons() {
  const out = [];
  for (const root of steamRoots()) {
    for (const lib of steamLibraries(root)) {
      const common = path.join(lib, 'common');
      let names = [];
      try { names = fs.readdirSync(common).filter((n) => n.startsWith('Proton')); } catch { continue; }
      for (const n of names) if (fs.existsSync(path.join(common, n, 'proton'))) out.push({ name: n, proton: path.join(common, n, 'proton'), steam: root });
    }
    try {
      for (const n of fs.readdirSync(path.join(root, 'compatibilitytools.d'))) {
        const pr = path.join(root, 'compatibilitytools.d', n, 'proton');
        if (fs.existsSync(pr)) out.push({ name: n, proton: pr, steam: root });
      }
    } catch { /* none */ }
  }
  for (const d of ['/usr/share/steam/compatibilitytools.d']) {
    try {
      for (const n of fs.readdirSync(d)) { const pr = path.join(d, n, 'proton'); if (fs.existsSync(pr)) out.push({ name: n, proton: pr, steam: steamRoots()[0] || null }); }
    } catch { /* none */ }
  }
  try {
    for (const n of fs.readdirSync(P().proton)) {
      const pr = path.join(P().proton, n, 'proton');
      if (fs.existsSync(pr)) out.push({ name: n, proton: pr, steam: path.join(P().proton, 'steam') });
    }
  } catch { /* none */ }
  // Heroic and Lutris keep their own Protons (native and Flatpak installs)
  const own = path.join(P().proton, 'steam');
  for (const [from, dirs] of [
    ['heroic', [path.join(home, '.config/heroic/tools/proton'), path.join(home, '.var/app/com.heroicgameslauncher.hgl/config/heroic/tools/proton')]],
    ['lutris', [path.join(home, '.local/share/lutris/runners/proton'), path.join(home, '.var/app/net.lutris.Lutris/data/lutris/runners/proton')]],
  ]) {
    for (const d of dirs) {
      try {
        for (const n of fs.readdirSync(d)) {
          const pr = path.join(d, n, 'proton');
          if (fs.existsSync(pr)) out.push({ name: n, proton: pr, steam: steamRoots()[0] || own, from });
        }
      } catch { /* none */ }
    }
  }
  for (const pr of C.config().protonExtra || []) {      // imported folders (used where they are)
    if (fs.existsSync(pr)) out.push({ name: path.basename(path.dirname(pr)), proton: pr, steam: steamRoots()[0] || path.join(P().proton, 'steam'), imported: true });
  }
  const rank = (x) => {
    const m = x.name.match(/(\d+)(?:[.-](\d+))?/);
    const v = m ? Number(m[1]) * 1000 + Number(m[2] || 0) : 0;
    // order: the system's Proton (/usr/share/steam/compatibilitytools.d, e.g. CachyOS's proton-cachyos-slr, which ran the
    // game well: user, 2026-11-20), then the newest of Steam / Heroic / Lutris / imported / the launcher's own
    return (x.proton.startsWith('/usr/') ? 1e5 : 0) + (/cachyos/i.test(x.name) ? 10 : 0) + (/experimental/i.test(x.name) ? 500 : 0) + v - (/beta|hotfix|next|easyanticheat|battleye/i.test(x.name) ? 1e6 : 0);
  };
  return out.filter((x) => !/(easyanticheat|battleye|runtime)/i.test(x.name)).sort((a, b) => rank(b) - rank(a));
}

async function geReleases() {
  const rels = await C.fetchJson('https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases?per_page=10');
  return rels.filter((r) => !r.draft).map((r) => {
    const a = (r.assets || []).find((x) => x.name.endsWith('.tar.gz'));
    return a && { tag: r.tag_name, url: a.browser_download_url, size: a.size, date: r.published_at };
  }).filter(Boolean);
}

async function downloadGEProton(onProg, tag) {
  let url = null;
  if (!tag) {
    tag = 'GE-Proton11-12';
    try { const r = (await geReleases())[0]; if (r) { url = r.url; tag = r.tag; } } catch (e) { log('GitHub API (GE-Proton):', e.message); }
  }
  url = url || `https://github.com/GloriousEggroll/proton-ge-custom/releases/download/${tag}/${tag}.tar.gz`;
  const p = P();
  fs.mkdirSync(p.down, { recursive: true });
  const file = path.join(p.down, url.split('/').pop());
  if (!fs.existsSync(file)) await C.download(url, file, onProg);
  await importArchive(file);
  C.rmrf(file);
  log('Proton: downloaded', tag);
  return path.join(p.proton, tag, 'proton');
}

// a Proton archive (.tar.gz / .tar.xz / .zip) goes into runtime/proton
async function importArchive(file) {
  const p = P();
  const tmp = path.join(p.tmp, 'proton-import');
  C.rmrf(tmp);
  await C.extract(file, tmp);
  const dir = C.findDirWith(tmp, ['proton'], 3);
  if (!dir || !fs.existsSync(path.join(dir, 'proton'))) { C.rmrf(tmp); throw new Error('no_proton'); }
  fs.mkdirSync(p.proton, { recursive: true });
  const dest = path.join(p.proton, path.basename(dir) === 'proton-import' ? path.basename(file).replace(/\.(tar\.\w+|zip)$/, '') : path.basename(dir));
  C.rmrf(dest);
  C.moveDir(dir, dest);
  C.rmrf(tmp);
  fs.mkdirSync(path.join(p.proton, 'steam'), { recursive: true });
  return path.join(dest, 'proton');
}

// import: a Proton folder (used where it is) or an archive (extracted into runtime/proton)
async function importProton(target) {
  if (fs.statSync(target).isDirectory()) {
    const pr = path.join(target, 'proton');
    if (!fs.existsSync(pr)) throw new Error('no_proton');
    const extra = (C.config().protonExtra || []).filter((x) => x !== pr);
    C.saveConfig({ protonExtra: [...extra, pr] });
    log('Proton: imported folder', target);
    return pr;
  }
  const pr = await importArchive(target);
  log('Proton: imported archive', target);
  return pr;
}

// the Proton DriftCityLauncher.ini uses now, and the list to pick from
function protonState() {
  const cur = C.iniRead(launcherIni());
  const using = expand(cur['linux.proton'] || '');
  const own = P().proton;
  return {
    runner: cur['linux.runner'] || 'proton',
    using,
    list: findProtons().map((x) => Object.assign({}, x, {
      from: x.proton.startsWith(own) ? 'launcher' : x.imported ? 'imported' : x.from || (x.proton.startsWith('/usr/') ? 'system' : 'steam'),
      using: x.proton === using,
    })),
  };
}

// what the home screen shows: the Proton the game will use (null = none on this PC)
function currentProton() {
  if (IS_WIN) return null;
  const st = protonState();
  if (st.runner === 'wine') return { name: 'Wine', from: 'wine' };
  let x = st.list.find((p) => p.using) || null;
  if (!x && st.list.length && fs.existsSync(launcherIni())) { useProton(st.list[0].proton); x = st.list[0]; }   // none set yet: the best one
  return x ? { name: x.name, from: x.from } : null;
}

function useProton(pr) {
  const pick = findProtons().find((x) => x.proton === pr);
  if (!pick) throw new Error('no_proton');
  const sets = { 'linux.runner': 'proton', 'linux.proton': pick.proton };
  if (pick.steam) { sets['linux.steam'] = pick.steam; try { fs.mkdirSync(pick.steam, { recursive: true }); } catch { /* read only */ } }
  if (!fs.existsSync(launcherIni())) throw new Error('install the game first');
  C.iniSet(launcherIni(), sets);
  log('Proton: using', pick.name);
}

// remove: a launcher-downloaded one is deleted; an imported folder is only forgotten (Steam's are never touched)
function removeProton(pr) {
  const own = P().proton;
  if (pr.startsWith(own + path.sep)) C.rmrf(path.dirname(pr));
  C.saveConfig({ protonExtra: (C.config().protonExtra || []).filter((x) => x !== pr) });
  log('Proton: removed', pr);
  // it was the one in use: switch to the best one left
  if (expand(C.iniRead(launcherIni())['linux.proton'] || '') === pr) { const next = findProtons()[0]; if (next) useProton(next.proton); }
}

// make sure DriftCityLauncher.ini points at a Proton that exists, and the prefix is Proton's
async function prepareProton(onProg) {
  if (IS_WIN) return null;
  const ini = launcherIni();
  const cur = C.iniRead(ini);
  if ((cur['linux.runner'] || 'proton') === 'wine') return { runner: 'wine' };
  let pick = null;
  const set = expand(cur['linux.proton'] || '');
  if (set && fs.existsSync(set)) pick = { name: path.basename(path.dirname(set)), proton: set, steam: expand(cur['linux.steam'] || '') };
  if (!pick) pick = findProtons()[0];
  // no automatic download: the system's Proton (CachyOS) first, else Steam's / an imported one; with none the
  // player picks one in Settings > Video > Proton… (download a GE-Proton or import)
  if (!pick) { log('no Proton found'); if (onProg === 'soft') return null; throw new Error('no_proton_setup'); }
  const sets = { 'linux.runner': 'proton', 'linux.proton': pick.proton };
  if (pick.steam) { sets['linux.steam'] = pick.steam; try { fs.mkdirSync(pick.steam, { recursive: true }); } catch { /* read only */ } }
  if (!cur['client.display']) sets['client.display'] = 'windowed';   // default only: the Video tab decides after that
  if (fs.existsSync(ini)) C.iniSet(ini, sets);
  // a prefix made by plain Wine breaks Proton (no tracked_files): move it aside
  const pfx = expand(cur['linux.prefix'] || '~/.local/share/drift2011-pfx');
  if (fs.existsSync(path.join(pfx, 'drive_c')) && !fs.existsSync(path.join(pfx, 'tracked_files'))) {
    const aside = `${pfx}.wine-${Date.now()}`;
    log(`the prefix ${pfx} was made by Wine: moved to ${aside}`);
    fs.renameSync(pfx, aside);
  }
  log('Proton:', pick.name);
  return pick;
}

// ---------- server address in DriftCityLauncher.ini ----------
function setServerAddress(address, port) {
  const ini = launcherIni();
  if (!fs.existsSync(ini)) return;
  const sets = { 'server.address': address };
  if (port) sets['server.port'] = String(port);
  C.iniSet(ini, sets);
}

// Windows display scaling (125%, 150%...) stretches the old client: at a high resolution the game
// window becomes bigger than the screen and is cut off. Mark the exes as DPI aware for this user
// (the same as Properties > Compatibility > "Override high DPI scaling: Application"; no admin needed).
async function dpiAware(exes) {
  const key = 'HKCU\\Software\\Microsoft\\Windows NT\\CurrentVersion\\AppCompatFlags\\Layers';
  for (const e of exes) {
    if (!fs.existsSync(e)) continue;
    const q = await C.run('reg', ['query', key, '/v', e]);
    const m = q.code === 0 && q.out.match(/REG_SZ\s+(.*)$/m);
    const cur = m ? m[1].trim() : '';
    if (/HIGHDPIAWARE/i.test(cur)) continue;
    const val = cur ? `${cur.startsWith('~') ? '' : '~ '}${cur} HIGHDPIAWARE` : '~ HIGHDPIAWARE';
    const r = await C.run('reg', ['add', key, '/v', e, '/t', 'REG_SZ', '/d', val, '/f']);
    log(`game: DPI aware ${path.basename(e)}:`, r.code === 0 ? 'ok' : (r.err || r.out).trim());
  }
}

// ---------- launch + watch ----------
// One watcher counts the open clients (DriftCity.exe) every 1.5 s: up to Settings > Server "clients at once" can be
// opened. When the last one goes the launcher says "Closing..." at once and, after a short wait (a channel change
// reopens the client), that the game closed.
let watching = null;
let gameSeen = false;
let clients = 0, closingSince = 0, pending = [], onGone = null;
const clientRunning = () => C.processRunning('DriftCity.exe');
async function countClients() {
  if (IS_WIN) {
    const r = await C.run('tasklist', ['/FI', 'IMAGENAME eq DriftCity.exe', '/FO', 'CSV', '/NH']);
    return (r.out.toLowerCase().match(/^"driftcity\.exe"/gm) || []).length;
  }
  // under Proton the client's process is named DriftCity.exe; its wrappers only carry it in the command line
  const x = await C.run('pgrep', ['-c', '-u', String(process.getuid()), '-x', 'DriftCity.exe']);
  const n = parseInt(x.out, 10) || 0;
  if (n) return n;
  return (await clientRunning()) ? 1 : 0;
}
function emit(extra) {
  C.bus.emit('game', Object.assign({ running: clients > 0, clients, closing: !!closingSince, launching: pending.length > 0 }, extra || {}));
}
function watch() {
  if (watching) return;
  watching = setInterval(async () => {
    const n = await countClients();
    const now = Date.now();
    // a launch counts as done when a new client appears; a launcher that exits without one has failed
    if (n > clients) {
      for (let k = clients; k < n && pending.length; k++) {
        const pd = pending.shift();
        log(`game: up after ${Math.round((now - pd.started) / 1000)} s (${n} open)`);
      }
    }
    for (const pd of pending.slice()) {
      const alive = pd.child.exitCode === null && pd.child.signalCode === null;
      if (!alive && now - pd.started > 8000) {
        pending.splice(pending.indexOf(pd), 1);
        if (n === 0) {
          let why = '';
          try { why = fs.readFileSync(path.join(P().client, 'DriftCityLauncher.log'), 'utf8').split(/\r?\n/).filter(Boolean).slice(-6).join('\n'); } catch { /* none */ }
          emit({ failed: true, why });
        }
      }
    }
    const was = clients;
    clients = n;
    if (n > 0) {
      gameSeen = true;
      if (closingSince || n !== was) { closingSince = 0; emit(); }
      else if (!was) emit();
      return;
    }
    if (gameSeen && was > 0 && !closingSince) { closingSince = now; log('game: closing'); emit(); return; }
    if (closingSince && now - closingSince > 4000) {      // gone for 4 s
      closingSince = 0; gameSeen = false;
      log('game: closed');
      emit();
      const cb = onGone; onGone = null;
      if (cb) cb();
    }
    if (!gameSeen && !pending.length && !closingSince) { clearInterval(watching); watching = null; }
  }, 1500);
}

// clients already open when the launcher starts (it was closed and reopened while playing): watch them too
async function adopt(onClosed) {
  const n = await countClients();
  if (!n) return 0;
  clients = n; gameSeen = true; onGone = onClosed || onGone;
  log(`game: ${n} client(s) already open`);
  watch();
  emit();
  return n;
}

async function launch(onClosed) {
  const p = P();
  const name = IS_WIN ? 'DriftCityLauncher.exe' : (C.config().client === '2011' ? 'DriftCityLauncher' : 'DriftCityLauncher2016');
  const exe = path.join(p.client, name);
  if (!fs.existsSync(exe)) throw new Error(`can't find ${exe}`);
  const max = Math.max(1, Math.min(4, Number(C.config().maxClients) || 1));
  if (clients + pending.length >= max) throw new Error('max_clients');
  if (!IS_WIN) { try { fs.chmodSync(exe, 0o755); } catch { /* read only */ } await prepareProton(); }
  log('game: opening', name, `(${clients} open, up to ${max})`);
  const out = fs.openSync(path.join(p.logs, 'launcher-output.log'), 'a');
  if (IS_WIN) await dpiAware([path.join(p.client, 'DriftCity.exe'), exe]);
  const child = cp.spawn(exe, [], { cwd: p.client, detached: true, stdio: ['ignore', out, out], windowsHide: false });
  child.unref();
  pending.push({ child, started: Date.now() });
  onGone = onClosed || onGone;
  watch();
  emit();
}
// close the game (and Xerender's launcher / the Wine side of it) when the openDC launcher closes
async function killGame() {
  clearInterval(watching); watching = null; gameSeen = false; clients = 0; closingSince = 0; pending = [];
  if (IS_WIN) {
    for (const im of ['DriftCity.exe', 'DriftCityLauncher.exe']) await C.run('taskkill', ['/F', '/T', '/IM', im]);
  } else {
    await C.run('pkill', ['-u', String(process.getuid()), '-f', 'DriftCity\\.exe|DriftCityLauncher']);
  }
  log('game: closed by the launcher');
}
// Large Address Aware on DriftCity.exe (Xerender's Emulator/tools/laa.py: status / apply / remove).
// The flag lets the 32-bit client use 4 GB instead of 2 GB on 64-bit Windows (the "abnormal program termination" crash).
async function laa(action) {
  const p = P();
  const exe = path.join(p.client, 'DriftCity.exe');
  if (!fs.existsSync(exe)) throw new Error(`can't find ${exe}`);
  if (!fs.existsSync(path.join(p.emu, 'tools', 'laa.py'))) throw new Error('no_laa_tool');
  if (action !== 'status' && await clientRunning()) throw new Error('close the game first');
  const keep = path.join(p.emu, 'client_backup', 'DriftCity.exe.before_laa');
  let text;
  if (action === 'restore') {
    // put back the exe laa.py saved before its first apply
    if (!fs.existsSync(keep)) throw new Error('no_laa_backup');
    fs.copyFileSync(keep, exe + '.tmp');
    fs.renameSync(exe + '.tmp', exe);
    text = 'restored from ' + keep;
  } else {
    const r = await C.run(p.pyExe, ['-m', 'tools.laa', action, exe], { cwd: p.emu });
    text = (r.out + r.err).trim();
    if (r.code !== 0) throw new Error(text || `laa ${action}: exit ${r.code}`);
  }
  log(`laa ${action}:`, text.replace(/\s+/g, ' '));
  const st = await C.run(p.pyExe, ['-m', 'tools.laa', 'status', exe], { cwd: p.emu });
  return { on: /LAA on/.test(st.out), text, status: st.out.trim(), backup: fs.existsSync(keep) };
}
function gameRunning() { return clients > 0; }
function gameLaunching() { return pending.length > 0; }   // started, the game window not up yet
function gameClients() { return { clients, closing: !!closingSince, max: Math.max(1, Math.min(4, Number(C.config().maxClients) || 1)) }; }

module.exports = { currentProton, laa, geReleases, downloadGEProton, importProton, protonState, useProton, removeProton, findProtons, prepareProton, setServerAddress, launch, adopt, gameRunning, gameLaunching, gameClients, killGame, clientRunning, launcherIni };
