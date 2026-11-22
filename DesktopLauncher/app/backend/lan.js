'use strict';
// Finding openDC servers on the local network (LAN), so another computer can join with one click.
//
// Every launcher answers a UDP question on DISCOVERY_PORT while its own server runs: "ODC?" -> a small JSON with the
// computer's name, the game version (2011 / 2016), the server's login port and the launcher version.
// scan() asks the whole network (broadcast on every IPv4 interface) and, for servers started without a launcher
// (an emulator run by hand), also knocks on the login ports of the local /24 networks.
const dgram = require('dgram');
const net = require('net');
const os = require('os');

const DISCOVERY_PORT = 11097;
const ASK = 'ODC?';
const LOGIN_PORTS = [11105, 11005];

// this computer's IPv4 networks (not loopback): address, netmask, broadcast
function networks() {
  const out = [];
  for (const list of Object.values(os.networkInterfaces())) {
    for (const a of list || []) {
      if (a.family !== 'IPv4' && a.family !== 4) continue;
      if (a.internal) continue;
      const ip = a.address.split('.').map(Number), mask = a.netmask.split('.').map(Number);
      const bc = ip.map((b, i) => (b & mask[i]) | (~mask[i] & 255)).join('.');
      out.push({ address: a.address, netmask: a.netmask, broadcast: bc });
    }
  }
  return out;
}

// the answering side: info() gives what to tell (null = the server is off, stay silent)
let sock = null;
function startResponder(info) {
  if (sock) return;
  try {
    sock = dgram.createSocket({ type: 'udp4', reuseAddr: true });
    sock.on('error', () => { try { sock.close(); } catch { /* closed */ } sock = null; });
    sock.on('message', (msg, from) => {
      if (msg.toString('utf8').trim() !== ASK) return;
      let i = null;
      try { i = info(); } catch { i = null; }
      if (!i) return;
      const body = Buffer.from(JSON.stringify(Object.assign({ odc: 1, name: os.hostname() }, i)));
      sock.send(body, from.port, from.address);
    });
    sock.bind(DISCOVERY_PORT, '0.0.0.0');
  } catch { sock = null; }
}
function stopResponder() { if (sock) { try { sock.close(); } catch { /* closed */ } sock = null; } }

const knock = (host, port, ms) => new Promise((resolve) => {
  const s = net.connect({ port, host });
  const done = (ok) => { s.destroy(); resolve(ok); };
  s.setTimeout(ms);
  s.on('connect', () => done(true));
  s.on('timeout', () => done(false));
  s.on('error', () => done(false));
});

// -> [{ip, name, client, port, version, launcher: bool}] found within about two seconds
async function scan() {
  const nets = networks();
  const mine = new Set(nets.map((n) => n.address));
  const found = new Map();
  // 1. ask every launcher
  await new Promise((resolve) => {
    let s;
    try { s = dgram.createSocket('udp4'); } catch { resolve(); return; }
    s.on('error', () => { try { s.close(); } catch { /* closed */ } resolve(); });
    s.on('message', (msg, from) => {
      try {
        const j = JSON.parse(msg.toString('utf8'));
        if (j.odc && !mine.has(from.address)) found.set(from.address, { ip: from.address, name: j.name || from.address, client: j.client || '', port: j.port || 0, version: j.version || '', launcher: true, running: j.running !== false });
      } catch { /* not ours */ }
    });
    s.bind(0, () => {
      try { s.setBroadcast(true); } catch { /* no broadcast */ }
      const ask = Buffer.from(ASK);
      for (const target of ['255.255.255.255', ...nets.map((n) => n.broadcast)]) s.send(ask, DISCOVERY_PORT, target, () => {});
      setTimeout(() => { try { s.close(); } catch { /* closed */ } resolve(); }, 1500);
    });
  });
  // 2. servers without a launcher: the login ports of the /24 networks this computer is on (small networks only)
  const hosts = [];
  for (const n of nets) {
    if (!n.netmask.startsWith('255.255.255.')) continue;
    const base = n.address.split('.').slice(0, 3).join('.');
    for (let i = 1; i < 255; i++) { const h = `${base}.${i}`; if (!mine.has(h) && !found.has(h)) hosts.push(h); }
  }
  const queue = hosts.slice();
  const worker = async () => {
    while (queue.length) {
      const h = queue.shift();
      for (const p of LOGIN_PORTS) {
        if (await knock(h, p, 350)) { found.set(h, { ip: h, name: h, client: p === 11005 ? '2011' : '2016', port: p, version: '', launcher: false, running: true }); break; }
      }
    }
  };
  await Promise.all(Array.from({ length: 48 }, worker));
  return [...found.values()].sort((a, b) => (b.running - a.running) || (b.launcher - a.launcher) || a.ip.localeCompare(b.ip, undefined, { numeric: true }));
}

module.exports = { scan, startResponder, stopResponder, networks, DISCOVERY_PORT };
