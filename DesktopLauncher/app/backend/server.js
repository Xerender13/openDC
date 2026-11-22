'use strict';
// Portable Python + PostgreSQL, the database, the client tables and the openDC server (python -m dcemu -q).
const fs = require('fs');
const path = require('path');
const net = require('net');
const cp = require('child_process');
const os = require('os');
const C = require('./core');
const { IS_WIN, P, log, run, sleep, portBusy } = C;

const PY_FALLBACK = { tag: '20261110', ver: '3.12.16' };
const PG_FALLBACK = '17.12.0';

function triple() {
  if (IS_WIN) return 'x86_64-pc-windows-msvc';
  const arch = os.arch() === 'arm64' ? 'aarch64' : 'x86_64';
  let musl = false;
  try { musl = fs.readdirSync('/lib').some((f) => f.startsWith('ld-musl-')); } catch { /* glibc */ }
  return `${arch}-unknown-linux-${musl ? 'musl' : 'gnu'}`;
}

// ---------- Python ----------
async function preparePython(onProg) {
  const p = P();
  if (!fs.existsSync(p.pyExe)) {
    const t = triple();
    let url = null;
    try {
      const rel = await C.fetchJson('https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest');
      const re = new RegExp(`^cpython-3\\.12\\.\\d+\\+\\d+-${t.replace(/[.]/g, '\\.')}-install_only\\.tar\\.gz$`);
      const a = rel.assets.find((x) => re.test(x.name));
      if (a) url = a.browser_download_url;
    } catch (e) { log('GitHub API (Python):', e.message); }
    url = url || `https://github.com/astral-sh/python-build-standalone/releases/download/${PY_FALLBACK.tag}/cpython-${PY_FALLBACK.ver}+${PY_FALLBACK.tag}-${t}-install_only.tar.gz`;
    const file = path.join(p.down, url.split('/').pop());
    if (!fs.existsSync(file)) await C.download(url, file, onProg);
    const tmp = path.join(p.tmp, 'python');
    C.rmrf(tmp);
    await C.extract(file, tmp);
    C.moveDir(path.join(tmp, 'python'), p.py);
    if (!fs.existsSync(p.pyExe)) throw new Error('the Python download has no python executable');
  }
  const ok = await run(p.pyExe, ['-c', 'import pg8000']);
  if (ok.code !== 0) {
    log('installing pg8000');
    const r = await run(p.pyExe, ['-m', 'pip', 'install', '--disable-pip-version-check', '--no-warn-script-location', 'pg8000']);
    if (r.code !== 0) throw new Error('installing pg8000 failed (PyPI): ' + r.err.slice(-300));
  }
}

// ---------- PostgreSQL ----------
async function preparePostgres(onProg) {
  const p = P();
  if (fs.existsSync(path.join(p.pgBin, C.exe('pg_ctl')))) return;
  const t = triple();
  const ext = IS_WIN ? 'zip' : 'tar.gz';
  let url = null;
  try {
    const rels = await C.fetchJson('https://api.github.com/repos/theseus-rs/postgresql-binaries/releases?per_page=100');
    const re = new RegExp(`^postgresql-(17\\.\\d+\\.\\d+)-${t.replace(/[.]/g, '\\.')}\\.${ext.replace('.', '\\.')}$`);
    const found = [];
    for (const r of rels) for (const a of r.assets) { const m = a.name.match(re); if (m) found.push([m[1], a.browser_download_url]); }
    found.sort((a, b) => a[0].localeCompare(b[0], undefined, { numeric: true }));
    if (found.length) url = found[found.length - 1][1];
  } catch (e) { log('GitHub API (PostgreSQL):', e.message); }
  url = url || `https://github.com/theseus-rs/postgresql-binaries/releases/download/${PG_FALLBACK}/postgresql-${PG_FALLBACK}-${t}.${ext}`;
  const file = path.join(p.down, url.split('/').pop());
  if (!fs.existsSync(file)) await C.download(url, file, onProg);
  const tmp = path.join(p.tmp, 'pgsql');
  C.rmrf(tmp);
  await C.extract(file, tmp);
  const bin = C.findDirWith(tmp, [C.exe('pg_ctl')], 4);
  if (!bin) throw new Error('the PostgreSQL download has no pg_ctl');
  C.moveDir(path.dirname(bin), p.pg);
  if (IS_WIN) {
    // the Windows build needs the Visual C++ runtime: the portable Python carries the same DLLs
    for (const dll of ['vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll']) {
      const src = path.join(p.py, dll), dst = path.join(p.pgBin, dll);
      if (fs.existsSync(src) && !fs.existsSync(dst)) fs.copyFileSync(src, dst);
    }
  }
}

// ---------- emulator.ini, read the way the emulator reads it ----------
let emu = null;          // {version, authPort, controlPort, db, port, user, pass}
async function readEmuConfig() {
  const p = P();
  const keys = ['client.version', 'services.auth', 'database.name', 'database.port', 'database.user', 'database.password',
    'emulator.control_port', 'native.admin_list', 'database.server_id'];
  const r = await run(p.pyExe, ['-m', 'dcemu', '--get', ...keys], { cwd: p.emu });
  if (r.code !== 0) throw new Error('emulator.ini: ' + (r.err || r.out).slice(-300));
  const v = r.out.split(/\r?\n/);
  emu = {
    version: v[0] || '2016',
    authPort: parseInt((v[1] || '11105').split(/\s+/)[0], 10),
    db: v[2] || 'skdb2016test',
    port: parseInt(v[3] || '15432', 10),
    user: v[4] || 'dcemu',
    pass: v[5] || '',
    controlPort: parseInt(v[6] || '11199', 10) || 11199,
    adminList: v[7] || 'server_data/adminlist.txt',
    serverId: parseInt(v[8] || '100', 10) || 100,
  };
  return emu;
}
function emuConfig() { return emu; }

// ---------- database ----------
function pg(tool, args, opts = {}) {
  const p = P();
  return run(path.join(p.pgBin, C.exe(tool)), args, Object.assign({ env: Object.assign({}, process.env, { PGPASSWORD: (emu && emu.pass) || '' }) }, opts));
}
function psql(db, args) {
  return pg('psql', ['-h', '127.0.0.1', '-p', String(emu.port), '-U', emu.user, '-d', db, '-v', 'ON_ERROR_STOP=1', '-q', ...args]);
}
async function dbRunning() {
  const p = P();
  if (!emu && fs.existsSync(p.pyExe)) await readEmuConfig().catch(() => null);
  if (!fs.existsSync(path.join(p.pgData, 'PG_VERSION'))) return false;
  const r = await pg('pg_ctl', ['-D', p.pgData, 'status']);
  return r.code === 0;
}

async function stopContainers() {
  // openDC through Docker / podman uses the same ports: stop its containers (their data stays)
  for (const e of IS_WIN ? ['docker'] : ['podman', 'docker']) {
    const r = await run(e, ['ps', '--format', '{{.Names}}']);
    if (r.code !== 0) continue;
    const names = r.out.split(/\r?\n/).filter((n) => n === 'dcemu_pg' || n === 'dcemu2011_emu');
    if (names.length) { log(`stopping the ${e} containers ${names.join(', ')} (same ports)`); await run(e, ['stop', ...names]); }
  }
}

async function startDb() {
  const p = P();
  if (!emu) await readEmuConfig();
  fs.mkdirSync(p.logs, { recursive: true });
  if (!fs.existsSync(path.join(p.pgData, 'PG_VERSION'))) {
    log('creating the database folder');
    C.rmrf(p.pgData);
    // no password file (initdb on Windows sometimes can't read it): trust first, then the password (below)
    const r = await pg('initdb', ['-D', p.pgData, '-U', emu.user, '-E', 'UTF8', '--no-locale', '--auth=trust']);
    if (r.code !== 0) throw new Error('initdb failed: ' + (r.err || r.out).slice(-400));
  }
  let running = await dbRunning();
  if (running && !(await portBusy(emu.port))) {
    // a postmaster.pid left by a database that was killed (power off, crash) whose process id now belongs to
    // another program: pg_ctl status says "running" but nothing listens. The file goes and the database starts.
    log('database: stale postmaster.pid (nothing on the port), removed');
    try { fs.unlinkSync(path.join(p.pgData, 'postmaster.pid')); } catch { /* gone */ }
    running = false;
  }
  if (!running) {
    if (await portBusy(emu.port)) { await stopContainers(); await sleep(1500); }
    if (await portBusy(emu.port)) throw new Error(`port ${emu.port} is already in use by another program (Docker? another PostgreSQL?)`);
    log('database: starting');
    const opts = `-p ${emu.port} -c listen_addresses=127.0.0.1` + (IS_WIN ? '' : " -c unix_socket_directories=''");
    const r = await pg('pg_ctl', ['-D', p.pgData, '-l', path.join(p.logs, 'postgres.log'), '-w', '-t', '60', '-o', opts, 'start'],
      { stdio: ['ignore', 'ignore', 'ignore'] });
    if (r.code !== 0) throw new Error('the database did not start (runtime/logs/postgres.log)');
  }
  await setPassword();
  const has = await psql('postgres', ['-tAc', `SELECT 1 FROM pg_database WHERE datname='${emu.db}'`]);
  if (has.code !== 0) throw new Error(`can't talk to the database on port ${emu.port}`);
  if (has.out.trim() !== '1') await createDb(cleanDump());
  log(`database: ready (${emu.db})`);
}

async function setPassword() {
  const p = P();
  const hba = path.join(p.pgData, 'pg_hba.conf');
  const lines = fs.readFileSync(hba, 'utf8').split(/\r?\n/);
  if (!lines.some((l) => /^\s*host.*\strust\s*$/.test(l))) return;
  log('database: setting the password');
  const s = emu.pass.replace(/'/g, "''");
  const r = await psql('postgres', ['-c', "SET password_encryption = 'scram-sha-256'", '-c', `ALTER ROLE "${emu.user}" PASSWORD '${s}'`]);
  if (r.code !== 0) throw new Error("couldn't set the database password");
  fs.writeFileSync(hba, lines.map((l) => (/^\s*#/.test(l) ? l : l.replace(/\strust\s*$/, ' scram-sha-256'))).join('\n'));
  await pg('pg_ctl', ['-D', p.pgData, 'reload']);
  await sleep(800);
}

function cleanDump() {
  const f = path.join(P().emu, 'db', 'postgres', `${emu.db}_clean.dump`);
  return fs.existsSync(f) ? f : path.join(P().emu, 'db', 'postgres', 'skdbtw_clean.dump');
}

async function createDb(file) {
  log('creating the database', emu.db, 'from', path.basename(file));
  let r = await psql('postgres', ['-c', `DROP DATABASE IF EXISTS "${emu.db}" WITH (FORCE)`, '-c', `CREATE DATABASE "${emu.db}"`]);
  if (r.code !== 0) throw new Error("couldn't create the database: " + r.err.slice(-300));
  r = await pg('pg_restore', ['-h', '127.0.0.1', '-p', String(emu.port), '-U', emu.user, '-d', emu.db, '--no-owner', '--exit-on-error', file]);
  if (r.code !== 0) throw new Error('pg_restore failed: ' + r.err.slice(-300));
  for (const s of ['00_compat.sql', '02_procedures.sql']) {
    r = await psql(emu.db, ['-f', path.join(P().emu, 'db', 'postgres', s)]);
    if (r.code !== 0) throw new Error(`${s} failed: ` + r.err.slice(-300));
  }
}

async function stopDb() {
  const p = P();
  if (!fs.existsSync(path.join(p.pgBin, C.exe('pg_ctl')))) return;
  if (await dbRunning()) {
    log('database: stopping');
    await pg('pg_ctl', ['-D', p.pgData, '-m', 'fast', '-w', '-t', '30', 'stop']);
  }
}

async function backupDb(file) {
  const p = P();
  fs.mkdirSync(p.backups, { recursive: true });
  const f = file || path.join(p.backups, `${emu.db}_${new Date().toISOString().slice(0, 16).replace(/[T:]/g, '-')}.dump`);
  const r = await pg('pg_dump', ['-h', '127.0.0.1', '-p', String(emu.port), '-U', emu.user, '-Fc', '--no-owner', '-f', f, emu.db]);
  if (r.code !== 0) throw new Error('backup failed: ' + r.err.slice(-300));
  // keep the 7 newest automatic backups
  const all = fs.readdirSync(p.backups).filter((n) => n.endsWith('.dump')).map((n) => path.join(p.backups, n))
    .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
  all.slice(7).forEach((x) => C.rmrf(x));
  return f;
}

// ---------- client tables ----------
async function clientTables(force) {
  const p = P();
  const chk = await run(p.pyExe, ['-m', 'tools.client_setup', '--check'], { cwd: p.emu });
  if (chk.code === 0 && !force) return;
  log('copying the client tables');
  const args = ['-m', 'tools.client_setup', '--version', C.config().client, '--client', p.client];
  if (force) args.push('--refresh');
  const r = await run(p.pyExe, args, { cwd: p.emu, onLine: (l) => log('  ' + l) });
  if (r.code !== 0) throw new Error('copying the client tables failed: ' + (r.err || r.out).slice(-300));
  await readEmuConfig();
}

// ---------- server ----------
let server = null;       // child process
function clearOldLogs(keep = 5) {
  const dir = path.join(P().emu, 'logs');
  const files = [];
  const walk = (d, depth) => {
    let ents; try { ents = fs.readdirSync(d, { withFileTypes: true }); } catch { return; }
    for (const e of ents) {
      const f = path.join(d, e.name);
      if (e.isDirectory() && depth < 1) walk(f, depth + 1);
      else if (e.isFile() && e.name.endsWith('.msgs.txt')) files.push(f);
    }
  };
  walk(dir, 0);
  files.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
  let mb = 0;
  for (const f of files.slice(keep)) { mb += fs.statSync(f).size / 1048576; C.rmrf(f); }
  if (files.length > keep) log(`old server logs: deleted ${files.length - keep} (${Math.round(mb)} MB)`);
}

function serverRunning() { return !!(server && server.exitCode === null); }

async function startServer() {
  const p = P();
  if (serverRunning()) return;
  if (!emu) await readEmuConfig();
  if (await portBusy(emu.authPort)) { await stopContainers(); await sleep(1500); }
  if (await portBusy(emu.authPort)) throw new Error(`port ${emu.authPort} is already in use (another openDC server?)`);
  clearOldLogs();
  log('server: starting');
  const out = fs.openSync(path.join(p.logs, 'server.out'), 'a');
  server = cp.spawn(p.pyExe, ['-m', 'dcemu', '-q'], { cwd: p.emu, windowsHide: true, stdio: ['ignore', out, out] });
  server.on('exit', (code) => { log('server: exited', code); C.bus.emit('state'); });
  for (let i = 0; i < 90; i++) {
    if (await portBusy(emu.authPort)) { log(`server: running (version ${emu.version}, port ${emu.authPort})`); C.bus.emit('state'); return; }
    if (!serverRunning()) {
      let tail = '';
      try { tail = fs.readFileSync(path.join(p.logs, 'server.out'), 'utf8').split(/\r?\n/).slice(-8).join('\n'); } catch { /* none */ }
      throw new Error('the server closed while starting:\n' + tail);
    }
    await sleep(1000);
  }
  throw new Error("the server didn't answer in 90 s");
}

async function stopServer() {
  if (!serverRunning()) { server = null; return; }
  log('server: stopping');
  const s = server;
  s.kill();
  for (let i = 0; i < 20 && s.exitCode === null; i++) await sleep(250);
  if (s.exitCode === null) { try { s.kill('SIGKILL'); } catch { /* gone */ } }
  server = null;
  C.bus.emit('state');
}

// one line to the control port -> {ok, text}
function control(line) {
  return new Promise((resolve) => {
    if (!emu) { resolve({ ok: false, text: 'server not configured' }); return; }
    const s = net.connect({ port: emu.controlPort, host: '127.0.0.1' });
    let buf = '';
    s.setTimeout(15000);
    s.on('connect', () => s.write(line + '\n'));
    s.on('data', (d) => { buf += d; });
    s.on('timeout', () => { s.destroy(); resolve({ ok: false, text: 'control port timeout' }); });
    s.on('error', (e) => resolve({ ok: false, text: 'the server is off (' + e.code + ')' }));
    s.on('close', () => {
      const t = buf.trim();
      if (t.startsWith('OK ')) resolve({ ok: true, text: t.slice(3) });
      else if (t.startsWith('OK')) resolve({ ok: true, text: '' });
      else resolve({ ok: false, text: t.replace(/^FAILED ?/, '') || 'no answer' });
    });
  });
}

async function prepareRuntime(onProg) {
  await preparePython(onProg);
  await readEmuConfig();
  await preparePostgres(onProg);
}

async function startAll() {
  await prepareRuntime();
  await clientTables(false);
  await startDb();
  if (C.config().autoBackup) {
    const day = new Date().toISOString().slice(0, 10);
    const marker = path.join(P().backups, `.last-${day}`);
    if (!fs.existsSync(marker)) {
      try { await backupDb(); fs.mkdirSync(P().backups, { recursive: true }); fs.writeFileSync(marker, ''); }
      catch (e) { log('backup:', e.message); }
    }
  }
  await startServer();
}
async function stopAll() { await stopServer(); await stopDb(); }

module.exports = {
  triple, preparePython, preparePostgres, prepareRuntime, readEmuConfig, emuConfig, startDb, stopDb, dbRunning, createDb,
  cleanDump, backupDb, clientTables, startServer, stopServer, serverRunning, control, startAll, stopAll, stopContainers,
};
