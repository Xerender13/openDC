'use strict';
/* openDC Launcher UI (no framework): pages are rebuilt from templates; window.odc is the backend. */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (s, o) => String(s).replace(/\{(\w+)\}/g, (_, k) => (o && o[k] != null ? o[k] : ''));

let L = 'pt';
let T = window.TX.pt;
let ST = null;                 // backend state
let page = 'home';
let upd = null;                // {available, emulator, client, launcher} | {error}
let commitsCache = null;
let commitsLoadErr = null;
let bar = null;                // {title, sub, frac, color}
let gameNote = null;
let launchT0 = 0, launchTick = null;   // when JOGAR was pressed (the game can take minutes to show up)           // {title, sub, color}
// every common mode from the smallest the client handles up to 4K; the list shown stops at the user's screen
const RES = ['800 × 600', '1024 × 600', '1024 × 768', '1152 × 864', '1280 × 720', '1280 × 768', '1280 × 800', '1280 × 960', '1280 × 1024',
  '1360 × 768', '1366 × 768', '1440 × 900', '1600 × 900', '1600 × 1200', '1680 × 1050', '1920 × 1080', '1920 × 1200', '2560 × 1080',
  '2560 × 1440', '2560 × 1600', '3440 × 1440', '3840 × 2160'];
function ratio(w, h) {
  const r = w / h;
  const known = [[4 / 3, '4:3'], [5 / 4, '5:4'], [16 / 10, '16:10'], [16 / 9, '16:9'], [21 / 9, '21:9'], [5 / 3, '5:3'], [128 / 75, '16:9']];
  let best = known[0];
  for (const k of known) if (Math.abs(k[0] - r) < Math.abs(best[0] - r)) best = k;
  return Math.abs(best[0] - r) < 0.04 ? best[1] : `${w}:${h}`;
}

function t(k, o) { return fmt(k.split('.').reduce((a, x) => (a ? a[x] : undefined), T) ?? k, o); }
function errText(e) { const m = ((e && e.message) || String(e)).replace(/^Error invoking remote method '\w+': (Error: )?/, ''); if (m.startsWith('busy:')) return T.busy; return (T.err && T.err[m]) || m.replace(/^Error: /, ''); }
function toast(msg, ok) {
  const el = $('#toast');
  el.textContent = msg; el.className = ok ? 'ok' : ''; el.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => { el.hidden = true; }, ok ? 2500 : 7000);
}
// the loading screen: shown when a call to the launcher's back end takes more than a moment (so the window never looks
// frozen), kept at least a short while so it doesn't flicker
const Loading = (() => {
  let el = null, timer = 0, since = 0, n = 0;
  const show = () => {
    // the garage has its own waits (the swap and sale animations): no loading screen over it
    if (document.getElementById('garage')) return;
    if (!el) {
      el = document.createElement('div');
      el.id = 'odcLoading';
      el.setAttribute('role', 'status');
      el.setAttribute('aria-live', 'polite');
      document.body.appendChild(el);
    }
    el.innerHTML = `<div class="ld-card"><span class="ld-ring" aria-hidden="true"></span><b>${esc((T && T.loading) || 'Carregando…')}</b><span class="ld-sub">${esc((T && T.loadingSub) || '')}</span></div>`;
    el.classList.add('on'); since = Date.now();
  };
  const hide = () => { if (!el) return; const wait = Math.max(0, 350 - (Date.now() - since)); setTimeout(() => { if (!n && el) el.classList.remove('on'); }, wait); };
  window.addEventListener('odc-busy', (e) => {
    n = e.detail || 0;
    if (n > 0 && !timer && !(el && el.classList.contains('on'))) timer = setTimeout(() => { timer = 0; if (n > 0) show(); }, 180);
    if (n <= 0) { clearTimeout(timer); timer = 0; hide(); }
  });
  return { show, hide };
})();

async function call(fn, ...a) { try { return await window.odc[fn](...a); } catch (e) { toast(errText(e)); throw e; } }

function setLang(l) {
  L = window.TX[l] ? l : 'pt'; T = window.TX[L];
  document.documentElement.lang = { pt: 'pt-BR', en: 'en', ru: 'ru' }[L];
  $$('[data-t]').forEach((el) => { el.textContent = t(el.dataset.t); });
  $('#btnMin').setAttribute('aria-label', T.min); $('#btnClose').setAttribute('aria-label', T.close);
  renderStatus(); render();
}

// ---------- status panel + version ----------
function renderStatus() {
  if (!ST) return;
  $('#verline').textContent = t('ver', { v: ST.version });
  $('#splashVer').textContent = t('ver', { v: ST.version });
  // while starting / stopping: yellow "Starting…" / "Stopping…" for what is still changing
  const line = (on, onTxt, offTxt, dot, txt) => {
    const wait = (ST.busy === 'start' && !on) ? T.stStarting : (ST.busy === 'stop' && on) ? T.stStopping : null;
    $(dot).className = 'dot' + (wait ? ' wait' : on ? ' on' : '');
    $(txt).textContent = wait ? (dot === '#dotDb' ? T.stDb : T.stSrv) + ' ' + wait : on ? onTxt : offTxt;
  };
  line(ST.db, T.dbOn, T.dbOff, '#dotDb', '#txtDb');
  line(ST.server, T.srvOn, T.srvOff, '#dotSrv', '#txtSrv');
  // keep the panel moving while a start / stop runs (the backend only reports its begin and end)
  if ((ST.busy === 'start' || ST.busy === 'stop') && !renderStatus.poll) {
    renderStatus.poll = setInterval(async () => { try { ST = await window.odc.state(); } catch { /* next tick */ } renderStatus(); if (page === 'home') renderHomeDynamic(); }, 1000);
  } else if (!(ST.busy === 'start' || ST.busy === 'stop') && renderStatus.poll) { clearInterval(renderStatus.poll); renderStatus.poll = null; }
  $('#txtCli').textContent = ST.installed ? t('cliOn', { c: ST.client, p: ST.port || (ST.client === '2011' ? 11005 : 11105) }) : T.cliOff;
  $$('#nav a').forEach((a) => a.classList.toggle('on', a.dataset.page === page));
}
async function refresh() { ST = await window.odc.state(); renderStatus(); }

// ---------- pages ----------
function render() {
  const m = $('#main');
  const f = { home: pageHome, notes: pageNotes, accounts: pageAccounts, settings: pageSettings, mods: pageMods }[page];
  m.innerHTML = '';
  f(m);
  renderStatus();
}
function go(p) { page = p; render(); }

// ---- home ----
const SLIDES = [[94, 48, 100], [72, 46, 105], [54, 60, 100], [61, 74, 105], [100, 83, 100], [44, 73, 100], [24, 34, 100]];
let slideI = 0, slideT = null;
function pageHome(m) {
  const W = 900, H = 300;
  const slides = SLIDES.map(([pos, x, z], i) => {
    const w = W * z / 100, h = w * 1080 / 1400;
    return `<div class="slide" style="opacity:${i === slideI ? 1 : 0}"><img src="assets/bg${i + 1}.jpg" alt="" style="width:${w}px;height:${h}px;left:${(W - w) * x / 100}px;top:${(H - h) * pos / 100}px"></div>`;
  }).join('');
  const news = (commitsCache || []).slice(0, 2);
  m.innerHTML = `
  <section id="hero" aria-label="openDC">${slides}<div id="heroShade"></div>
    <div id="heroText"><div class="tag">${esc(t('heroTag', { c: ST.client }))}</div><h2>${esc(T.news)}</h2>
      ${news.length ? news.map((c) => `<div class="newsItem"><div><b>${esc(c.title)}</b><span class="d">${esc(shortDate(c.date))}</span></div>${c.body ? `<div class="x">${esc(c.body.split('\n')[0].slice(0, 140))}</div>` : ''}</div>`).join('')
        : `<div class="newsItem"><div class="x">${esc(T.newsNone)}</div></div>`}
    </div>
    <div id="dots" role="group">${SLIDES.map((_, i) => `<button aria-label="${i + 1}" data-i="${i}" style="width:${i === slideI ? 22 : 8}px;background:${i === slideI ? '#FF8A2B' : 'rgba(255,255,255,.45)'}"></button>`).join('')}</div>
  </section>
  <img id="girl" src="assets/girl.png" alt="">
  <img id="logo" src="assets/logo.png" alt="Open Drift City">
  <div id="updBox"></div>
  <div id="osLine"></div>
  <div id="playBox"><button id="playBtn"></button><div id="playMore" class="muted small" hidden></div></div>
  <div id="bar" role="status" aria-live="polite"><div id="barTop"><span id="barTitle"></span><span id="barPct"></span></div><div class="track"><div id="barFill"></div></div><div id="barSub"></div></div>`;
  $$('#dots button', m).forEach((b) => b.onclick = () => { slideI = +b.dataset.i; startSlides(); render(); });
  $('#playBtn').onclick = onPlay;
  renderHomeDynamic();
}
function startSlides() { clearInterval(slideT); slideT = setInterval(() => { slideI = (slideI + 1) % SLIDES.length; if (page === 'home') { $$('.slide').forEach((s, i) => { s.style.opacity = i === slideI ? 1 : 0; }); $$('#dots button').forEach((b, i) => { b.style.width = (i === slideI ? 22 : 8) + 'px'; b.style.background = i === slideI ? '#FF8A2B' : 'rgba(255,255,255,.45)'; }); } }, 10000); }
const shortDate = (iso) => { const d = new Date(iso); return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`; };

function renderHomeDynamic() {
  if (page !== 'home' || !$('#playBtn')) return;
  const btn = $('#playBtn');
  const busy = ST.busy;
  const icon = { play: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6 4l14 8-14 8z"/></svg>',
    dl: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg>' };
  let label, ic = '';
  if (busy === 'install') label = T.installing;
  else if (busy === 'repair') label = T.repairingBtn;
  else if (busy === 'start' || busy === 'update') label = T.starting;
  else if (ST.launching) label = T.opening;
  else if (closingNow()) label = T.waitBtn;
  else if (ST.game && !canMore()) label = T.inGame;
  else if (ST.installed) { label = T.play; ic = icon.play; } else { label = T.dl; ic = icon.dl; }
  btn.innerHTML = ic + esc(label);
  const off = !!busy || ST.launching || closingNow() || (ST.game && !canMore()) || noProton();
  btn.disabled = off;
  btn.classList.toggle('busy', off);
  // more clients allowed (Settings > Server): the button stays orange with how many more can still be opened
  const more = $('#playMore');
  const left = ST.clients ? ST.clients.max - ST.clients.clients : 0;
  more.hidden = !(ST.game && !off && left > 0);
  if (!more.hidden) more.textContent = t('moreClients', { n: left });
  // OS line
  const o = ST.os;
  const osIcon = o.linux
    ? '<svg width="13" height="13" viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="12.5" rx="6.5" ry="9" fill="#E8ECF2"/><path d="M12 3.5c-3.6 0-6.5 4-6.5 9 0 2 .5 3.8 1.3 5.3 1-3.3 2.8-5.3 5.2-5.3s4.2 2 5.2 5.3c.8-1.5 1.3-3.3 1.3-5.3 0-5-2.9-9-6.5-9z" fill="#2A313C"/><circle cx="10.2" cy="8.2" r="1" fill="#E8ECF2"/><circle cx="13.8" cy="8.2" r="1" fill="#E8ECF2"/><path d="M10.6 10.2h2.8L12 12z" fill="#FFB020"/><path d="M6 21.5c0-1.2 1.4-2 3-2s2 .8 2 2zM13 21.5c0-1.2.4-2 2-2s3 .8 3 2z" fill="#FFB020"/></svg>'
    : '<svg width="12" height="12" viewBox="0 0 24 24" fill="#4FA3E0" aria-hidden="true"><path d="M3 5l8-1.2V11H3zM12 3.6L21 2v9h-9zM3 12h8v7.2L3 18zM12 12h9v10l-9-1.6z"/></svg>';
  $('#osLine').innerHTML = osIcon + `<b>${esc(o.name)}</b>` + (o.old ? `<span class="warn">⚠ ${esc(T.oldOs)}</span>` : '');
  // update box
  const ub = $('#updBox');
  if (upd && upd.available && !busy) {
    ub.className = 'upHas';
    const parts = [];
    if (upd.launcher.available) parts.push(t('uLauncher', { v: upd.launcher.version }));
    if (upd.client.available) parts.push(T.uClient);
    if (upd.emulator.available) parts.push(t('uEmu', { n: upd.emulator.changes.length }));
    const sec = (title, rows) => `<div class="updSec">${esc(title)}</div>` + rows;
    let list = '';
    if (upd.launcher.available) {
      const lines = (upd.launcher.notes || '').split(/\r?\n/).map((x) => x.replace(/^[-*#\s]+/, '').trim()).filter(Boolean).slice(0, 8);
      list += sec(t('uLauncher', { v: upd.launcher.version }), (lines.length ? lines : [T.uLauncherD]).map((x) => `<div class="updItem"><span class="d b">•</span><span class="t">${esc(x)}</span></div>`).join(''));
    }
    if (upd.client.available) list += sec(T.uClient, `<div class="updItem"><span class="d b">•</span><span class="t">${esc(T.uClientD)}</span></div>`);
    if (upd.emulator.available) list += sec(t('uEmu', { n: upd.emulator.changes.length }), upd.emulator.changes.map((c) => `<div class="updItem"><span class="d">${esc(shortDate(c.date))}</span><span class="t">${esc(c.title)}</span></div>`).join(''));
    ub.innerHTML = `<div class="inl"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#FF9A45" stroke-width="2" aria-hidden="true"><path d="M21 12a9 9 0 1 1-3-6.7M21 4v5h-5"/></svg>
      <div class="grow" style="display:flex;flex-direction:column;gap:2px;min-width:0"><span style="font-size:13px;font-weight:600;color:#FFD2A8">${esc(T.updT)}</span><span style="font-size:11px;color:#B4BCC8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(parts.join(' · '))}</span></div>
      <button class="btn pri sm" id="updBtn">${esc(T.updBtn)}</button></div>
      <div id="updList">${list}</div>`;
    $('#updBtn').onclick = onUpdate;
  } else {
    ub.className = 'upOk';
    const failed = upd && ['emulator', 'client', 'launcher'].some((k) => upd[k] && upd[k].error) || (upd && upd.error);
    const green = ST.installed && !busy && upd && !failed;
    const title = busy === 'update' ? T.updating : !ST.installed ? T.noUpd : !upd ? T.checking : failed ? T.updFail : T.okUpd;
    const sub = busy === 'update' ? '' : !ST.installed ? T.noUpdSub : !upd ? '' : failed ? T.updFailSub : T.okUpdSub;
    ub.innerHTML = (green ? '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#3DDC84" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.7 2.7L16 9.8"/></svg>'
      : '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#8B95A5" stroke-width="2" aria-hidden="true"><path d="M21 12a9 9 0 1 1-3-6.7M21 4v5h-5"/></svg>')
      + `<span style="font-size:14px;font-weight:600">${esc(title)}</span><span class="muted small">${esc(sub)}</span>`;
  }
  // bar
  let b = bar;
  const ready = ST.installed && !busy && !ST.game && !ST.launching && !noProton();
  const barEl = $('#bar');
  barEl.onclick = null; barEl.style.cursor = '';
  if (!b && !busy && noProton()) {
    b = { title: T.noProtonT, sub: T.noProtonSub, frac: 0, color: '#FF9A45' };
    barEl.style.cursor = 'pointer'; barEl.onclick = goProton;
  }
  if (ST.launching && !busy) {
    const secs = Math.round((Date.now() - (launchT0 || Date.now())) / 1000);
    b = { title: T.steps.game + '…', sub: secs >= 45 ? t('openingSlow', { s: secs }) : t('openingSub', { s: secs }), frac: 0.9, color: '#FF8A2B' };
  }
  if (!b && ready && gameNote && gameNote.color !== '#FF8A8A') b = Object.assign({}, gameNote, { frac: 1, color: gameNote.color === '#FFB020' ? '#FFB020' : '#3DDC84' });
  if (!b) {
    if (gameNote) b = gameNote;
    else if (ST.installed) b = { title: T.done, sub: T.doneSub, frac: 1, color: '#3DDC84' };
    else b = { title: T.idle, sub: T.idleSub, frac: 0, color: '#8B95A5' };
  }
  $('#barTitle').textContent = b.title; $('#barSub').textContent = b.sub || '';
  const pct = Math.round((b.frac || 0) * 100);
  $('#barPct').textContent = pct + '%'; $('#barPct').style.color = b.color;
  $('#barFill').style.width = pct + '%'; $('#barFill').style.background = b.color;
}

// Linux: the game needs a Proton; without one JOGAR stays off and points to the Proton menu
const noProton = () => !!(ST && ST.os.linux && ST.installed && !ST.proton);
function goProton() { cfgTab = 'vid'; go('settings'); setTimeout(openProton, 150); }
function protonNotice() {
  if (!ST.os.linux || !ST.installed) return;
  const p = ST.proton;
  const from = { steam: 'Steam', launcher: 'Launcher', imported: T.pxImported, system: T.pxSystem, heroic: 'Heroic', lutris: 'Lutris', wine: 'Wine' };
  modal(`<div class="dlg" role="dialog" aria-label="Proton"><h2>${esc(p ? T.pnT : T.pnNoneT)}</h2>
    ${p ? `<div class="pick on" style="cursor:default"><span class="r"></span><span style="display:flex;flex-direction:column;gap:3px"><span class="n">${esc(p.name)}</span><span class="s">${esc(from[p.from] || p.from)}</span></span></div>` : ''}
    <div class="muted" style="font-size:13px;line-height:1.5">${esc(p ? T.pnSub : T.pnNoneSub)}</div>
    <div class="foot"><button class="btn" id="pnOk">${esc(p ? T.pnOk : T.pnLater)}</button><button class="btn pri" id="pnGo">${esc(p ? T.pnOpen : T.pnSet)}</button></div></div>`);
  $('#pnOk').onclick = closeModal;
  $('#pnGo').onclick = () => { closeModal(); goProton(); };
}

function onProgress(p) {
  if (p.job === 'proton') {
    const el = $('#pxProg');
    if (el) el.textContent = p.extra && p.extra.total ? `${Math.round(p.extra.got / 1048576)} / ${Math.round(p.extra.total / 1048576)} MB` : Math.round((p.frac || 0) * 100) + '%';
    return;
  }
  const n = p.n || 1;
  const total = Math.min(1, (p.step + (p.frac || 0)) / n);
  let title = p.job === 'start' && p.name === 'server' ? T.startServer : (T.steps[p.name] || p.name).replace('{c}', ST ? ST.client : '');
  if (p.job === 'update' && p.name !== 'download') title = T.updating + ' ' + title;
  let sub = `${T.step} ${p.step + 1} ${T.of} ${n}`;
  if (p.extra && p.extra.total) sub += ` · ${Math.round(p.extra.got / 1048576)} ${T.of} ${Math.round(p.extra.total / 1048576)} MB`;
  else if (p.frac) sub += ` · ${Math.round(p.frac * 100)}%`;
  bar = { title, sub, frac: total, color: '#FF8A2B' };
  renderHomeDynamic();
}

const closingNow = () => !!(ST.clients && ST.clients.closing);
const canMore = () => !!(ST.clients && ST.clients.clients < ST.clients.max);

async function onPlay() {
  if (ST.busy) return toast(T.busy);
  if (!ST.installed) return openInstall();
  gameNote = null;
  bar = { title: T.startServer, sub: '', frac: 0.1, color: '#FF8A2B' };
  renderHomeDynamic();
  try { await call('play'); bar = null; launchT0 = Date.now(); clearInterval(launchTick); launchTick = setInterval(() => { if (!ST.launching && launchT0 && Date.now() - launchT0 > 5000) { clearInterval(launchTick); launchT0 = 0; } renderHomeDynamic(); }, 1000); }
  catch (e) { bar = null; gameNote = { title: T.error, sub: errText(e), frac: 0, color: '#FF8A8A' }; }
  await refresh(); renderHomeDynamic();
}

async function onUpdate() {
  try {
    const r = await call('update');
    if (r && r.restarting) { bar = { title: T.restarting, sub: '', frac: 1, color: '#FF8A2B' }; renderHomeDynamic(); return; }
    upd = null; commitsCache = null; loadCommits().catch(() => {}); checkUpdate(); toast('✓', true);
  } catch { /* toast shown */ }
  bar = null; await refresh(); render();
}

function openInstall() {
  let client = '2016';
  const root = ST.cfg.root;
  const draw = () => {
    modal(`<div class="dlg" role="dialog" aria-label="${esc(T.pkTitle)}"><h2>${esc(T.pkTitle)}</h2>
      <div class="muted" style="font-size:13px;line-height:1.5">${esc(T.pkSub)}</div>
      ${[['2016', T.c16, T.c16d], ['2011', T.c11, T.c11d]].map(([id, n, s]) => `<button class="pick${client === id ? ' on' : ''}" data-c="${id}"><span class="r"></span><span style="display:flex;flex-direction:column;gap:3px"><span class="n">${esc(n)}</span><span class="s">${esc(s)}</span></span></button>`).join('')}
      <div class="field"><span>${esc(T.folder)}</span><div class="pathrow"><code id="instRoot">${esc(ST.cfg.root)}</code><button class="btn sm" id="pkRoot">${esc(T.change)}</button></div></div>
      <button class="linkbtn" id="pkHave" style="align-self:flex-start">${esc(T.haveIt)}</button>
      <div class="muted small" style="line-height:1.5">${esc(T.pkNote)}</div>
      <div class="foot"><button class="btn" id="pkNo">${esc(T.cancel)}</button><button class="btn pri" id="pkGo">${esc(T.go)}</button></div></div>`);
    $$('.pick').forEach((b) => b.onclick = () => { client = b.dataset.c; draw(); });
    $('#pkNo').onclick = closeModal;
    $('#pkRoot').onclick = async () => { const d = await call('pickRoot'); if (d) { await call('saveConfig', { root: d.replace(/[\\/]$/, '') }); await refresh(); draw(); } };
    $('#pkHave').onclick = async () => {
      const d = await call('pickRoot'); if (!d) return;
      try { await call('adopt', d); closeModal(); await refresh(); upd = null; checkUpdate(); render(); protonNotice(); } catch { /* toast */ }
    };
    $('#pkGo').onclick = async () => {
      closeModal();
      bar = { title: T.steps.client.replace('{c}', client), sub: '', frac: 0, color: '#FF8A2B' };
      try { await call('install', client); bar = null; gameNote = null; await refresh(); protonNotice(); autoStart(); } catch (e) { bar = { title: T.error, sub: errText(e), frac: 0, color: '#FF8A8A' }; }
      await refresh(); checkUpdate(); render();
    };
  };
  void root; draw();
}

// ---- patch notes ----
async function loadCommits() {
  try { commitsCache = await window.odc.commits(); } catch (e) { commitsLoadErr = errText(e); if (page === 'notes') render(); throw e; }
  commitsLoadErr = null;
  if (page === 'home' || page === 'notes') render();
}
function pageNotes(m) {
  m.innerHTML = `<div class="page"><div class="h1row"><h1>${esc(T.navNotes)}</h1><span class="muted" style="font-size:13px">${esc(T.notesSub)}</span></div>
    <div class="banner"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#FF9A45" stroke-width="2" aria-hidden="true"><path d="M4 14l4 1 8 5V4L8 9H4z"/></svg>
      <div style="display:flex;flex-direction:column;gap:2px"><span class="t">${esc(t('relTitle', { v: ST.version }))}</span><span class="x">${esc(T.relSub)}</span></div></div>
    <div class="scroll" id="notes">${commitsCache ? '' : esc(commitsLoadErr ? t('loadFail', { e: commitsLoadErr }) : T.loading)}</div></div>`;
  if (!commitsCache) { if (commitsLoadErr) return; loadCommits().catch((e) => { const n = $('#notes'); if (n) n.textContent = t('loadFail', { e: errText(e) }); }); return; }
  $('#notes').innerHTML = commitsCache.map((c) => `<article class="note"><span class="d">${esc(shortDate(c.date))}</span><div class="b"><span class="t">${esc(c.title)}</span>${c.body ? `<span class="x">${esc(c.body.slice(0, 600))}</span>` : ''}</div></article>`).join('');
}

// ---- accounts ----
function pageAccounts(m) {
  m.innerHTML = `<div class="page"><div class="h1row"><h1>${esc(T.accTitle)}</h1><span class="muted" style="font-size:13px">${esc(T.accSub)}</span><div class="grow"></div>
    <button class="btn" id="impAcc" ${ST.installed ? '' : 'disabled'}>${esc(T.imp)}</button><button class="btn pri" id="newAcc" ${ST.installed ? '' : 'disabled'}>${esc(T.newAcc)}</button></div><div class="scroll" id="accs"></div></div>`;
  if (!ST.installed) { $('#accs').innerHTML = `<div class="empty">${esc(T.needInstall)}</div>`; return; }
  $('#newAcc').onclick = openNewAccount;
  $('#impAcc').onclick = openImport;
  $('#accs').textContent = ST.db ? T.loading : T.dbStarting;
  window.odc.accList().then((list) => {
    refresh();
    const el = $('#accs'); if (!el) return;
    if (!list.length) { el.innerHTML = `<div class="empty">${esc(T.noAcc)}</div>`; return; }
    el.innerHTML = `<table><thead><tr><th>${esc(T.colId)}</th><th>${esc(T.colRunners)}</th><th>${esc(T.colCoin)}</th><th>${esc(T.colJoined)}</th><th></th></tr></thead><tbody>
      ${list.map((a) => `<tr><td><b>${esc(a.id)}</b>${a.gm ? `<span class="badge gm">${esc(T.gm)}</span>` : ''}${a.banned ? `<span class="badge ban">${esc(T.banned)}</span>` : ''}</td>
        <td>${a.chars}</td><td>${a.coin.toLocaleString()}</td><td class="muted">${esc(a.joined)}</td>
        <td style="text-align:right;white-space:nowrap"><button class="btn-open" data-edit="${esc(a.id)}">${esc(T.open)}</button> &nbsp; <button class="linkbtn" data-exp="${esc(a.id)}">${esc(T.expAcc)}</button> &nbsp; <button class="linkbtn red" data-del="${esc(a.id)}">${esc(T.del)}</button></td></tr>`).join('')}
      </tbody></table>`;
    $$('[data-edit]', el).forEach((b) => b.onclick = () => openEdit(b.dataset.edit));
    $$('[data-del]', el).forEach((b) => b.onclick = () => openDelete(b.dataset.del));
    $$('[data-exp]', el).forEach((b) => b.onclick = () => doExport(b.dataset.exp));
  }).catch((e) => { const el = $('#accs'); if (el) el.textContent = t('loadFail', { e: errText(e) }); });
}

function openNewAccount() {
  modal(`<div class="dlg" role="dialog" aria-label="${esc(T.newTitle)}"><h2>${esc(T.newTitle)}</h2>
    <label class="field">${esc(T.id)}<input type="text" id="naId" maxlength="32" autocomplete="off"></label>
    <label class="field">${esc(T.pw)}<input type="password" id="naPw" maxlength="63"></label>
    <label class="field">${esc(T.pw2)}<input type="password" id="naPw2" maxlength="63"></label>
    <label class="inl" style="font-size:13px"><input type="checkbox" id="naGm">${esc(T.makeGm)}</label>
    <div class="foot"><span class="bad" id="naErr"></span><button class="btn" id="naNo">${esc(T.cancel)}</button><button class="btn pri" id="naGo">${esc(T.create)}</button></div></div>`);
  $('#naId').focus();
  $('#naNo').onclick = closeModal;
  $('#naGo').onclick = async () => {
    const id = $('#naId').value.trim(), pw = $('#naPw').value;
    if (pw !== $('#naPw2').value) { $('#naErr').textContent = T.pwMismatch; return; }
    try { await window.odc.accCreate(id, pw, $('#naGm').checked); closeModal(); render(); }
    catch (e) { $('#naErr').textContent = errText(e); }
  };
}

function openDelete(id) {
  modal(`<div class="dlg" role="alertdialog" aria-label="${esc(t('delTitle', { id }))}"><h2>${esc(t('delTitle', { id }))}</h2>
    <div class="muted" style="font-size:13px;line-height:1.5">${esc(T.delSub)}</div>
    <div class="foot"><button class="btn" id="dNo">${esc(T.cancel)}</button><button class="btn danger" id="dGo">${esc(T.delYes)}</button></div></div>`);
  $('#dNo').onclick = closeModal;
  $('#dGo').onclick = async () => { try { await call('accDelete', id); closeModal(); render(); } catch { /* toast */ } };
}

// ---- Proton manager (Linux) ----
async function openProton() {
  let st, rels = null, relErr = '', working = '';
  const from = { steam: 'Steam', launcher: 'Launcher', imported: T.pxImported, system: T.pxSystem, heroic: 'Heroic', lutris: 'Lutris' };
  const load = async () => { try { st = await call('protonState'); } catch { st = { list: [] }; } };
  const draw = () => {
    const have = new Set(st.list.map((x) => x.name));
    modal(`<div class="dlg wide" role="dialog" aria-label="Proton" style="height:auto;max-height:600px">
      <div class="inl"><h2 class="grow">Proton</h2><button class="btn" id="pxClose">${esc(T.close)}</button></div>
      <div class="muted small" style="line-height:1.5">${esc(T.pxSub)}</div>
      <div class="cols" style="grid-template-columns:minmax(0,1.3fr) minmax(0,1fr)">
        <div class="colL"><div class="sec">${esc(T.pxHave)}</div>
          <div class="mini" style="max-height:330px"><table><tbody>${st.list.map((x, i) => `<tr><td><b>${esc(x.name)}</b><div class="muted small">${esc(from[x.from] || x.from)}</div></td>
            <td style="text-align:right;white-space:nowrap">${x.using ? `<span class="badge gm">${esc(T.pxUsing)}</span>` : `<button class="btn sm" data-use="${i}" ${working ? 'disabled' : ''}>${esc(T.pxUse)}</button>`}
            ${x.from === 'launcher' || x.from === 'imported' ? ` <button class="linkbtn red" data-rm="${i}" ${working ? 'disabled' : ''}>${esc(x.from === 'launcher' ? T.del : T.pxForget)}</button>` : ''}</td></tr>`).join('') || `<tr><td class="muted">${esc(T.pxNone)}</td></tr>`}</tbody></table></div>
          <div class="inl"><button class="btn sm" id="pxDir" ${working ? 'disabled' : ''}>${esc(T.pxImpDir)}</button><button class="btn sm" id="pxFile" ${working ? 'disabled' : ''}>${esc(T.pxImpFile)}</button></div>
        </div>
        <div class="colR"><div class="sec">${esc(T.pxGet)}</div>
          ${working ? `<div class="info"><span class="grow">${esc(working)}</span><b id="pxProg"></b></div>` : ''}
          <div class="mini" style="max-height:330px">${rels === null ? `<div class="muted small" style="padding:10px">${esc(relErr || T.loading)}</div>`
            : `<table><tbody>${rels.map((r, i) => `<tr><td><b>${esc(r.tag)}</b><div class="muted small">${esc(shortDate(r.date))} · ${Math.round(r.size / 1048576)} MB</div></td>
              <td style="text-align:right">${have.has(r.tag) ? `<span class="muted small">${esc(T.pxHas)}</span>` : `<button class="btn sm" data-dl="${i}" ${working ? 'disabled' : ''}>${esc(T.pxDl)}</button>`}</td></tr>`).join('')}</tbody></table>`}</div>
        </div>
      </div></div>`);
    $('#pxClose').onclick = async () => { if (working) return toast(T.busy); closeModal(); await refresh(); render(); };
    $$('[data-use]').forEach((b) => b.onclick = async () => { try { await call('protonUse', st.list[+b.dataset.use].proton); await load(); draw(); } catch { /* toast */ } });
    $$('[data-rm]').forEach((b) => b.onclick = async () => { try { await call('protonRemove', st.list[+b.dataset.rm].proton); await load(); draw(); } catch { /* toast */ } });
    const job = async (label, fn) => {
      working = label; draw();
      try { await fn(); toast('✓', true); } catch { /* toast */ }
      working = ''; await load(); draw();
    };
    $$('[data-dl]').forEach((b) => b.onclick = () => { const r = rels[+b.dataset.dl]; job(t('pxGetting', { v: r.tag }), () => call('protonDownload', r.tag)); });
    $('#pxDir').onclick = () => job(T.pxImporting, () => call('protonImport', 'dir'));
    $('#pxFile').onclick = () => job(T.pxImporting, () => call('protonImport', 'file'));
  };
  await load(); draw();
  window.odc.protonReleases().then((r) => { rels = r; }).catch((e) => { relErr = t('loadFail', { e: errText(e) }); }).then(() => { if ($('#pxClose')) draw(); });
}

async function doExport(id, cid, name) {
  try { const f = await call('accExport', id, cid || null, name || null); if (f) toast(t('expDone', { f }), true); } catch { /* toast */ }
}

async function openImport() {
  let info;
  try { info = await call('accImportOpen'); } catch { return; }
  if (!info) return;
  let accs = [];
  if (info.kind === 'char') { try { accs = await call('accList'); } catch { return; } if (!accs.length) { toast(T.noAcc); return; } }
  modal(`<div class="dlg" role="dialog" aria-label="${esc(T.impTitle)}"><h2>${esc(T.impTitle)}</h2>
    <div class="muted small">${esc(info.file)}</div>
    <div style="font-size:14px;line-height:1.5">${info.kind === 'account' ? esc(t('impAcc', { id: info.id, n: info.names.length })) : esc(T.impChar)}<br><b>${esc(info.names.join(', ') || T.none)}</b></div>
    ${info.kind === 'account' && info.exists ? `<label class="field">${esc(t('impExists', { id: info.id }))}<input type="text" id="impId" maxlength="32"></label>` : ''}
    ${info.kind === 'char' ? `<label class="field">${esc(T.impTo)}<select id="impTo">${accs.map((a) => `<option value="${esc(a.id)}">${esc(a.id)}</option>`).join('')}</select></label>` : ''}
    ${info.taken.map((n, i) => `<label class="field">${esc(t('impTaken', { n }))}<input type="text" data-old="${esc(n)}" id="impN${i}" maxlength="16"></label>`).join('')}
    <div class="muted small" style="line-height:1.5">${esc(T.expNote)}</div>
    <div class="foot"><span class="bad" id="impErr"></span><button class="btn" id="impNo">${esc(T.cancel)}</button><button class="btn pri" id="impGo">${esc(T.impGo)}</button></div></div>`);
  $('#impNo').onclick = closeModal;
  $('#impGo').onclick = async () => {
    const names = {};
    $$('[data-old]').forEach((el) => { if (el.value.trim()) names[el.dataset.old] = el.value.trim(); });
    const opts = { names };
    if ($('#impId')) opts.new_id = $('#impId').value.trim();
    if ($('#impTo')) opts.id = $('#impTo').value;
    try { await window.odc.accImport(opts); closeModal(); toast(T.impDone, true); render(); }
    catch (e) { $('#impErr').textContent = errText(e); }
  };
}

async function openEdit(id) {
  let acc, sel = null, ch = null;
  const load = async () => { acc = await call('accGet', id); if (acc.chars.length && !acc.chars.find((c) => c.cid === sel)) sel = acc.chars[0].cid; if (!acc.chars.length) sel = null; };
  const loadChar = async () => { ch = sel ? await call('charGet', id, sel) : null; };
  try { await load(); await loadChar(); } catch { return; }
  let note = '';
  // the character's own portrait (User Info picture of its avatar 1-8, OMD or ROO side)
  const faceKey = () => (ch ? `face:${ch.side || 'omd'}${((Math.max(1, ch.avatar || 1) - 1) % 8) + 1}` : '');
  const getFace = () => { if (ch) loadIcons([faceKey()]).then((n) => { if (n && document.querySelector('.dlg.ed')) draw(); }); };
  const draw = () => {
    const c = acc.chars.find((x) => x.cid === sel);
    const pt = ch ? ch.playtime || 0 : 0;
    const row = (k, v, inp) => `<tr><th>${esc(k)}</th><td>${inp || `<span class="ed-val">${esc(v)}</span>`}</td></tr>`;
    modal(`<div class="dlg ed" role="dialog" aria-label="${esc(t('editTitle', { id }))}">
      <div class="inl"><h2>${esc(id)}</h2>${acc.gm ? `<span class="badge gm">${esc(T.gm)}</span>` : `<span class="badge nrm">${esc(T.normal)}</span>`}${acc.banned ? `<span class="badge ban">${esc(T.banned)}</span>` : ''}
        <span class="muted small">${esc(acc.gm ? T.edSubGm : T.edSubNormal)}</span><span class="grow"></span>
        <button class="winx" id="eClose" aria-label="${esc(T.close)}">✕</button></div>
      <div class="ed-body">
        <section class="ed-left" aria-label="${esc(T.accSec)}">
          <div class="sec">${esc(T.accSec)}</div>
          <label class="field">${esc(T.newPw)}<input type="password" id="ePw" maxlength="63" placeholder="${esc(T.pwKeep || '')}"></label>
          <label class="inl small"><input type="checkbox" id="eGm" ${acc.gm ? 'checked' : ''}>${esc(T.gmOn)}</label>
          <div class="grow"></div>
          <button class="ed-big" id="eAuc" ${acc.chars.length ? '' : 'disabled'}>${esc(T.edAuction)}</button>
          <button class="ed-big" id="eMore" ${acc.chars.length ? '' : 'disabled'}>${esc(T.edMore)}</button>
          ${acc.gm ? `<button class="ed-gm" id="eGmp"><span>GM</span>${esc(T.edGmPanel)}</button>` : ''}
          <button class="ed-ban" id="eBan">${esc(acc.banned ? T.edUnban : T.edBan)}</button>
        </section>
        <section class="ed-right">
          <div class="inl"><span class="sec">${esc(T.runners)}</span>${acc.chars.map((x) => `<button class="chip${x.cid === sel ? ' on' : ''}" data-cid="${x.cid}">${esc(x.name)}</button>`).join('')}<span class="grow"></span>
            ${c ? `<button class="btn sm" id="cExp">${esc(T.expChar)}</button><button class="btn danger sm" id="cDel">${esc(T.delRunner)}</button>` : ''}</div>
          ${c && ch ? `<div class="ed-card">
            <div class="ed-card-h"><b>${esc(T.myInfo)}</b><span>${esc(c.name)}</span></div>
            <div class="ed-card-b"><div class="ed-ava" aria-hidden="true">${ICONS.get(faceKey()) ? `<img src="${ICONS.get(faceKey())}" alt="">` : '<svg viewBox="0 0 64 64"><circle cx="32" cy="24" r="12"/><path d="M10 60c2-14 11-20 22-20s20 6 22 20z"/></svg>'}</div>
              <table class="ed-tab"><tbody>
                ${row(T.iName, '', `<input type="text" id="cName" value="${esc(c.name)}" maxlength="16">`)}
                ${row(T.iLevel, '', `<input type="number" id="cLv" min="1" max="200" value="${c.level}">`)}
                ${row(T.iMito, '', `<input type="number" id="cMito" min="0" value="${c.mito}">`)}
                ${row(T.iDist, t('kmF', { n: Number(ch.km || 0).toLocaleString() }))}
                ${row(T.iPlay, t('playF', { h: Math.floor(pt / 3600), m: Math.floor((pt % 3600) / 60) }))}
                ${row(T.iCrew, ch.team || T.none)}
              </tbody></table></div></div>
          <div class="ed-btns"><button class="ed-inv" id="cInv">${esc(T.invOpen)}</button><button class="ed-gar" id="cGar" ${ch.cars.length ? '' : 'disabled'}>${esc(T.garOpen)}</button>
            <button class="ed-crew" disabled title="${esc(T.crewSoon)}">${esc(T.crew)}<small>${esc(T.soon)}</small></button></div>
          <p class="warn3d small">⚠ ${esc(T.v3dWarn)}</p>`
          : `<div class="empty">${esc(T.noRunners)}</div>`}
        </section>
      </div>
      <div class="inl"><span class="muted small grow" id="eNote" aria-live="polite">${note || esc(T.edNote)}</span></div>
    </div>`);
    const close = () => { closeModal(); render(); };
    $('#eClose').onclick = close;
    $('#eGm').onchange = async (e) => { try { await call('accGm', id, e.target.checked); await load(); draw(); } catch { /* toast */ } };
    $('#eBan').onclick = async () => { try { await call('accBan', id, !acc.banned); await load(); draw(); } catch { /* toast */ } };
    if ($('#eGmp')) $('#eGmp').onclick = () => openGmPanel(id, acc.chars, sel, () => openEdit(id));
    if ($('#eAuc')) $('#eAuc').onclick = () => openAuction(id, acc.chars, sel, () => openEdit(id));
    if ($('#eMore')) $('#eMore').onclick = () => openMore(id, acc.chars, sel, () => openEdit(id), acc.gm);
    $$('[data-cid]').forEach((b) => b.onclick = async () => { sel = Number(b.dataset.cid); note = ''; try { await loadChar(); } catch { /* toast */ } draw(); getFace(); });
    if (!c || !ch) return;
    $('#cInv').onclick = () => openInventory(id, sel, c.name, () => openEdit(id));
    $('#cGar').onclick = () => openGarage(id, sel);
    $('#cExp').onclick = () => doExport(id, sel, c.name);
    $('#cDel').onclick = async () => {
      if (!confirm(t('delRunnerQ', { n: c.name }))) return;
      try { await call('charDelete', id, sel); await load(); await loadChar(); draw(); } catch { /* toast */ }
    };
    // each field is saved as soon as it is changed (Enter or leaving the field): no Save / Cancel buttons
    const saveField = async (what, fn) => {
      let ok = false;
      try { await fn(); ok = true; } catch { /* toast */ }
      try { await load(); await loadChar(); } catch { /* toast */ }
      note = ok ? `<span class="ok">${esc(T.saved)}: ${esc(what)}</span>` : '';
      draw();
    };
    const onCommit = (el, fn) => {
      if (!el) return;
      el.onchange = fn;
      el.onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); el.blur(); } };
    };
    onCommit($('#ePw'), (e) => { const pw = e.target.value; if (pw) saveField(T.newPw, () => call('accPassword', id, pw)); });
    onCommit($('#cMito'), (e) => { const v = Number(e.target.value); if (v !== c.mito && v >= 0) saveField(T.iMito, () => call('charMito', id, sel, v)); });
    onCommit($('#cLv'), (e) => { const v = Number(e.target.value); if (v !== c.level && v >= 1) saveField(T.iLevel, () => call('charLevel', c.name, v)); });
    onCommit($('#cName'), (e) => { const v = e.target.value.trim(); if (v && v !== c.name) saveField(T.iName, () => call('charRename', id, sel, v)); });
  };
  draw(); getFace();
}

// ---- a character's inventory, as the game's Inventory window ----
// the game's pictures (DDS from the client, decoded here) -> data URLs, kept for the session
const ICONS = new Map();
async function loadIcons(names) {
  const need = names.filter((n) => n && !ICONS.has(n));
  if (!need.length) return false;
  need.forEach((n) => ICONS.set(n, null));
  let got = {};
  try { got = await window.odc.icons(need); } catch { return false; }
  for (const [n, e] of Object.entries(got)) {
    try {
      const bin = Uint8Array.from(atob(e.dds), (ch) => ch.charCodeAt(0));
      const img = DDS.decode(bin);
      const cv = document.createElement('canvas');
      const [u0, v0, u1, v1] = e.uv;
      const sx = Math.round(u0 * img.w), sy = Math.round(v0 * img.h);
      const sw = Math.max(1, Math.round((u1 - u0) * img.w)), sh = Math.max(1, Math.round((v1 - v0) * img.h));
      const full = document.createElement('canvas'); full.width = img.w; full.height = img.h;
      full.getContext('2d').putImageData(new ImageData(img.data, img.w, img.h), 0, 0);
      cv.width = sw; cv.height = sh;
      cv.getContext('2d').drawImage(full, sx, sy, sw, sh, 0, 0, sw, sh);
      ICONS.set(n, cv.toDataURL());
    } catch { /* stays without picture */ }
  }
  return true;
}
const pic = (n, cls) => (ICONS.get(n) ? `<img class="${cls}" src="${ICONS.get(n)}" alt="">` : '');
const PART_COLS = [['speed', 100], ['accel', 103], ['crash', 106], ['boost', 109]];
const NEO_COLS = [['neo_weapon', 112], ['neo_coil', 113], ['neo_fuse', 114], ['neo_armor', 115]];
async function openGarage(id, cid) {
  let inv;
  try { inv = await call('invGet', id, cid); } catch { return; }
  const act = async (args) => {
    try { return await window.odc.invDo(id, cid, args); } catch (e) {
      const m = ((e && e.message) || '').replace(/^Error invoking remote method '\w+': (Error: )?/, '');
      // a hyper / ultra part coming off the car (sell the car alone) asks for its Heat Treatment Kit
      if (m.startsWith('ask_kit_') && confirm(t('invKitQ', { g: m.slice(8) }))) return act(Object.assign({}, args, { kit: true }));
      throw new Error(m.startsWith('needs_kit_') ? t('invNeedKit', { g: m.slice(10) }) : (T.err && T.err[m]) || errText(e));
    }
  };
  window.Garage.open({ inv, T, onUse: (car) => act({ act: 'use_car', car: car.id }), onSell: (car, mode) => act({ act: 'sell_car', car: car.id, with: mode }) });
}

async function openInventory(id, cid, cname, back) {
  let st3 = null, st3Key = '';
  let inv, carIx = 0, selItem = null, selDrift = null, tab = 'parts', neoView = false, sortBy = 'type', page = 0, msg = '', mine = null, aPrice = '', aQty = '';
  const loadMine = async () => { try { mine = await window.odc.auc('mine', id, cid); } catch { mine = { mine: [], rules: { item_fee: 7, car_fee: 10, days: 7 } }; } };
  const PER = 40;
  const load = async () => {
    inv = await call('invGet', id, cid);
    if (carIx >= inv.cars.length) carIx = 0;
    if (selItem && !inv.items.find((x) => x.inv === selItem)) selItem = null;
    if (selDrift && !(inv.drift || []).find((x) => x.inv === selDrift)) selDrift = null;
  };
  try { await load(); } catch { return; }
  carIx = Math.max(0, inv.cars.findIndex((c) => c.current));
  const ikey = (id2) => 'item:' + String(id2 || '').toLowerCase();
  const iconNames = () => [...inv.items.flatMap((x) => [ikey(x.id), 'car:' + x.id.toLowerCase(), ...(x.alt || [])]), ...(inv.drift || []).map((d) => ikey(d.id)),
    ...inv.cars.flatMap((c) => ['logo:' + c.model])];
  const fetchIcons = () => loadIcons(iconNames()).then((ch) => { if (ch && document.querySelector('.dlg.inv2')) draw(); });
  const icon = (x) => ICONS.get(ikey(x.id)) || ICONS.get('car:' + String(x.id || '').toLowerCase()) || (x.alt || []).map((k) => ICONS.get(k)).find(Boolean) || '';
  const gr = (g) => (g ? `<span class="gr ${esc(g.replace(/^[FO]/, ''))}">${esc(g)}</span>` : '');
  const tipOf = (x) => ({ name: x.name, desc: x.desc, lines: [x.grade ? `${x.grade}${x.level ? ' · ' + t('tipLevel', { n: x.level }) : ''}${x.value ? ' · +' + x.value : ''}` : '', x.car ? T.tipOnCar : '', x.stack > 1 ? t('tipStack', { n: x.stack }) : '', x.sell ? t('tipSell', { m: Number(x.sell).toLocaleString() }) : '', x.id] });
  const left = (d) => (d.period ? t('invDays', { n: d.left == null ? d.period : d.left }) : T.invForGood);
  // a drift item on a car: "In use" and the car it is on (the cars' names from the inventory)
  const carName = (cid2) => { const c = (inv && inv.cars || []).find((x) => x.id === cid2); return c ? `${c.name} V${c.grade}` : '#' + cid2; };
  const tipD = (d) => ({ name: d.name, desc: d.desc, lines: [d.catName, left(d), d.on ? T.tipInUse : '', d.on && d.car ? t('tipOnCarN', { c: carName(d.car) }) : ''] });
  const fmt = (n) => Number(n || 0).toLocaleString();
  const act = async (args, okText) => {
    try {
      const r = await window.odc.invDo(id, cid, args);
      msg = okText ? `<span class="ok">${esc(okText(r))}</span>` : '';
    } catch (e) {
      const m = ((e && e.message) || '').replace(/^Error invoking remote method '\w+': (Error: )?/, '');
      if (m.startsWith('ask_kit_')) {
        if (confirm(t('invKitQ', { g: m.slice(8) }))) return act(Object.assign({}, args, { kit: true }), okText);
        return;
      }
      msg = `<span class="bad">${esc(m.startsWith('needs_kit_') ? t('invNeedKit', { g: m.slice(10) }) : (T.err && T.err[m]) || errText(e))}</span>`;
    }
    try { await load(); } catch { /* toast */ }
    draw();
    fetchIcons();
  };
  // drift slots on the car, by the game's categories (VisualItem.xlt)
  // as the game's inventory: Dress-Up (paint, tint, neon, decal, license plate), Tuning (aero, tire wheel, booster =
  // the muffler flames, aero / booster wing, air duct), Misc. (roof, driving skill, three closed slots)
  const DRIFT_ROWS = [['invRowVisual', [['dPaint', [1, 32]], ['dWindow', [3]], ['dNeon', [2]], ['dDecal', [11]], ['dPlate', [9]]]],
    ['invRowTuning', [['dAero', [4, 5, 6]], ['dTire', [8, 48]], ['dFlame', [10]], ['dWing', [7]], ['dDuct', [52]]]],
    ['invRowOther', [['dRoof', [47]], ['dSkill', [58]], ['', []], ['', []], ['', []]]]];
  const SLOT_CATS = new Set(DRIFT_ROWS.flatMap(([, sl]) => sl.flatMap(([, c]) => c)));
  const draw = () => {
    const car = inv.cars[carIx];
    const on = (s) => inv.items.filter((x) => car && x.car === car.id && x.slot === s);
    const it = tab === 'parts' || tab === 'auction' ? inv.items.find((x) => x.inv === selItem) : null;
    const dr = tab === 'drift' ? (inv.drift || []).find((x) => x.inv === selDrift) : null;
    const canGo = (s, k) => it && !it.car && ((k && it.kind === k) || (it.type <= 3 && PART_COLS.find(([kk]) => kk === it.kind) && Math.floor((s - 100) / 3) === PART_COLS.findIndex(([kk]) => kk === it.kind)));
    const slot = (s, k, label) => {
      const here = on(s);
      const part = here.find((x) => x.type <= 3 || x.kind.startsWith('neo_'));
      const extra = here.filter((x) => x !== part);
      return `<div class="bslot">
        <div class="bs${part ? ' full' : ''}${canGo(s, k) ? ' can' : ''}" data-slot="${s}" data-k="${k || ''}" ${part ? Tip.attr(tipOf(part)) : `title="${esc(label)}"`}${part ? ` draggable="true" data-drag="${part.inv}"` : ''}>
          ${part ? `${icon(part) ? `<img src="${icon(part)}" alt="">` : ''}<span class="nm">${gr(part.grade)}${esc(part.name)}</span>${extra.length ? `<span class="op">+${extra.length}</span>` : ''}${part.heat ? '<span class="heat">!</span>' : ''}` : `<span class="lb">${esc(label)}</span>`}
        </div>
        <button class="bx" ${part ? `data-off="${part.inv}"` : 'disabled'} aria-label="${esc(T.invOff)}">✕</button></div>`;
    };
    const lineCol = (s) => (on(s).length ? '#FFFFFF' : '#0A0D14');
    const P = car ? car.points : { base: [0, 0, 0, 0], parts: [0, 0, 0, 0] };
    const ptRow = (lab, k) => `<tr><td class="lab">${esc(lab)}</td><td class="n">${P.base[k]}</td><td class="n plus">+${P.parts[k]}</td><td class="n"><b>${P.base[k] + P.parts[k]}</b></td></tr>`;
    const sumB = P.base.reduce((a, b) => a + b, 0), sumP = P.parts.reduce((a, b) => a + b, 0);
    // right side: the list of the tab, sorted, 40 a page
    const sortF = sortBy === 'type' ? (a, b) => (a.type - b.type) || String(a.kind).localeCompare(String(b.kind)) || a.inv - b.inv : (a, b) => b.inv - a.inv;
    const list = tab === 'parts' || tab === 'auction' ? inv.items.filter((x) => !x.car).sort(sortF)
      : tab === 'drift' ? (inv.drift || []).filter((x) => !(x.on && car && x.car === car.id && SLOT_CATS.has(x.cat))).sort(sortBy === 'type' ? (a, b) => a.cat - b.cat || a.inv - b.inv : (a, b) => b.inv - a.inv) : [];
    const pages = Math.max(1, Math.ceil(list.length / PER));
    if (page >= pages) page = pages - 1;
    const shown = list.slice(page * PER, page * PER + PER);
    const cells = Array.from({ length: PER }, (_, i) => shown[i]);
    const tile = (x) => {
      if (!x) return '<div class="gcell empty"></div>';
      if (tab === 'drift') return `<div class="gcell${x.inv === selDrift ? ' sel' : ''}${x.on ? ' oncar' : ''}" data-dinv="${x.inv}" draggable="${x.on && [1, 32, 2, 3].includes(x.cat) ? 'false' : 'true'}" data-ddrag="${x.inv}"${Tip.attr(tipD(x))}>${x.on ? `<span class="inuse">${esc(T.tipInUse)}</span>` : ''}${icon(x) ? `<img src="${icon(x)}" alt="">` : `<span class="ph">${esc(x.name.slice(0, 2))}</span>`}${x.on ? '<span class="oc">●</span>' : ''}</div>`;
      return `<div class="gcell${x.inv === selItem ? ' sel' : ''}${x.auction || x.broken ? ' dim' : ''}" data-inv="${x.inv}" draggable="${x.auction ? 'false' : 'true'}" data-drag="${x.inv}"${Tip.attr(tipOf(x))}>
        ${icon(x) ? `<img src="${icon(x)}" alt="">` : `<span class="ph">${esc(x.name.slice(0, 2))}</span>`}${x.count > 1 ? `<span class="c">${x.count}</span>` : ''}</div>`;
    };
    const partLike = it && !it.car && (it.type <= 3 || it.kind.startsWith('neo_') || (it.type >= 6 && it.type <= 10));
    const tabs = [['parts', T.tabParts], ['drift', T.tabDrift], ['sticker', T.tabSticker], ['auction', T.tabAuction]];
    const driftOn = (cats) => (inv.drift || []).find((d) => d.on && car && d.car === car.id && cats.includes(d.cat));
    modal(`<div class="dlg inv2" role="dialog" aria-label="${esc(t('invTitle', { n: cname }))}">
      <div class="ihead"><span class="ring"></span><h2>${esc(T.invTitle2)}</h2><span class="who">${esc(cname)} · ${esc(T.level).toLowerCase()} ${inv.level}</span><span class="grow"></span>
        <div class="mitob"><span>${esc(T.myMito)}</span><b>${fmt(inv.mito)}</b><span>MITO</span></div>
        <button class="ix" id="iBack" aria-label="${esc(T.close)}">✕</button></div>
      <div class="ibody">
        <section class="iL" aria-label="${esc(T.invCar)}">
          <div class="cnav"><button class="arr" id="cPrev" ${inv.cars.length < 2 ? 'disabled' : ''} aria-label="${esc(T.garPrev)}">◀</button>
            <div class="cname">${car && ICONS.get('logo:' + car.model) ? `<img src="${ICONS.get('logo:' + car.model)}" alt="${esc(car.name)}">` : `<span>${car ? esc(car.name) : '—'}</span>`}</div>
            <span class="vg">V${car ? car.grade : ''}</span>
            <button class="arr" id="cNext" ${inv.cars.length < 2 ? 'disabled' : ''} aria-label="${esc(T.garNext)}">▶</button></div>
          <div class="crow"><b>${car ? `${carIx + 1} / ${inv.cars.length}` : ''}</b>
            ${tab === 'parts' ? `<button class="neob${neoView ? ' on' : ''}" id="iNeo" aria-pressed="${neoView}">${esc(neoView ? T.invNormalView : T.invNeoView)}</button>` : ''}
            ${car && car.auction ? `<span class="muted small">${esc(T.inAuction)}</span>` : ''}<span class="grow"></span>
            ${car && !car.current && !car.auction && inv.cars.length > 1 ? `<button class="mini danger" id="cRm">${esc(T.rmCarBtn)}</button>` : ''}
            ${car ? (car.current ? `<span class="drv">${esc(T.invDriving)}</span>` : `<button class="mini" id="cUse" ${car.auction ? 'disabled' : ''}>${esc(T.invUseCar)}</button>`) : ''}</div>
          ${tab === 'parts' ? (neoView ? `
          <div class="bp neo"><div class="bpi" style="width:410px;height:228px">
            <img src="assets/bp_neo.png" alt="" style="position:absolute;left:0;top:0;width:410px;height:134px">
            <svg width="410" height="228" viewBox="0 0 410 228" aria-hidden="true" style="position:absolute;left:0;top:0" fill="none" stroke-width="2">${NEO_COLS.map(([, s], i) => { const x = 60 + i * 97, y = [92, 82, 100, 88][i]; return `<path d="M${x} 150 V${y}" stroke="${lineCol(s)}"/><circle cx="${x}" cy="${y}" r="4" fill="${lineCol(s)}"/>`; }).join('')}</svg>
            <div class="brow" style="top:150px;left:22px;right:22px">${NEO_COLS.map(([k, s]) => slot(s, k, T['inv_' + k])).join('')}</div>
          </div></div>` : `
          <div class="bp"><div class="bpi" style="width:390px;height:346px">
            <img src="assets/bp_top.png" alt="" style="position:absolute;left:0;top:81px;width:390px;height:183px">
            <svg width="390" height="346" viewBox="0 0 390 346" aria-hidden="true" style="position:absolute;left:0;top:0" fill="none" stroke-width="2">${PART_COLS.map(([, b], i) => { const x = [50, 147, 244, 341][i], y1 = [118, 130, 130, 118][i], y2 = [228, 216, 216, 228][i]; return `<path d="M${x} 80 V${y1}" stroke="${lineCol(b)}"/><circle cx="${x}" cy="${y1}" r="4" fill="${lineCol(b)}"/><path d="M${x} 266 V${y2}" stroke="${lineCol(b + 1)}"/><circle cx="${x}" cy="${y2}" r="4" fill="${lineCol(b + 1)}"/>`; }).join('')}</svg>
            <div class="brow" style="top:0;left:20px;right:19px">${PART_COLS.map(([k, b]) => slot(b, '', T['inv_' + k])).join('')}</div>
            <div class="brow bot" style="bottom:0;left:20px;right:19px">${PART_COLS.map(([k, b]) => slot(b + 1, '', T['inv_' + k])).join('')}</div>
          </div></div>`) + `
          <table class="ipts"><tbody>
            <tr class="h"><td>${esc(T.invCarPts)}</td><td class="n">${esc(T.invCar)}</td><td class="n">${esc(T.invPartsCol)}</td><td class="n">${esc(T.invTotal)}</td></tr>
            ${ptRow(T.inv_speed, 0)}${ptRow(T.inv_accel, 1)}${ptRow(T.inv_crash, 2)}${ptRow(T.inv_boost, 3)}
            <tr><td class="lab">${esc(T.invTotal)}</td><td class="n">${sumB}</td><td class="n plus">+${sumP}</td><td class="n"><b>${sumB + sumP}</b></td></tr>
          </tbody></table>` : tab === 'drift' ? `
          <div class="dnote">${esc(T.invExpire)}</div>
          <div class="i3d" id="i3d"></div>
          ${DRIFT_ROWS.map(([row, slots]) => `<div class="drow"><span class="dl">${esc(T[row])}</span>${slots.map(([lab, cats]) => { if (!lab) return '<span class="ds closed" aria-hidden="true"></span>'; const d = driftOn(cats); const fixed = d && [1, 32, 2, 3].includes(d.cat); return `<button class="ds${d ? ' on' : ''}${fixed ? ' lock' : ''}" data-dcats="${cats.join(',')}" ${d ? `data-dinv="${d.inv}" draggable="${fixed ? 'false' : 'true'}" data-ddrag="${d.inv}"${Tip.attr(tipD(d))}` : 'aria-disabled="true" tabindex="-1"'}>${d && icon(d) ? `<img src="${icon(d)}" alt="${esc(d.name)}">` : `<span>${esc(d ? d.name : T[lab])}</span>`}${fixed ? '<i class="lk" aria-hidden="true">🔒</i>' : ''}</button>`; }).join('')}</div>`).join('')}
          <div class="muted small">${esc(T.invDropCar)} ${esc(T.invDriftNote)}</div>` : tab === 'sticker' ? `
          <div class="i3d big" id="i3d"></div>` : `
          <div class="aucL">
            <div class="ah">${esc(T.aucNew)}</div>
            ${it && !it.car ? `<div class="anew"><span class="dico">${icon(it) ? `<img src="${icon(it)}" alt="">` : ''}</span><div class="dtx"><b>${gr(it.grade)}${esc(it.name)}</b><span>${esc(T.aucQty)}: ${it.count}</span></div></div>
              <div class="aform">${it.count > 1 && it.type === 5 ? `<label>${esc(T.aucQty)}<input type="number" id="aQty" min="1" max="${it.count}" value="${esc(aQty || it.count)}"></label>` : ''}
                <label>${esc(T.aucAsk)}<input type="number" id="aPrice" min="1" value="${esc(aPrice)}" placeholder="100000"></label>
                <span class="small muted">${esc(t('aucFee', { f: Math.max(1, Math.floor((Number(aPrice) || 0) * (mine ? mine.rules.item_fee : 7) / 100)).toLocaleString(), p: mine ? mine.rules.item_fee : 7 }))} ${esc(t('aucDays', { d: mine ? mine.rules.days : 7 }))}</span>
                <button class="ybtn" id="aOn" ${it.auction ? 'disabled' : ''}>${esc(T.aucSell)}</button></div>`
              : `<div class="small muted">${esc(T.aucPick)}</div>`}
            ${car && !car.current && !car.auction ? `<div class="aform"><span class="small muted">${esc(car.name)} V${car.grade} · ${esc(T.aucCarNote)}</span>
              <div class="inl"><input type="number" id="aCarPrice" min="1" placeholder="1000000" aria-label="${esc(T.aucAsk)}"><button class="gbtn" id="aCarOn">${esc(T.aucSellCar)}</button></div></div>` : ''}
            <div class="ah">${esc(T.aucMine)}</div>
            <div class="amine">${mine && mine.mine.length ? mine.mine.map((x) => `<div class="arow"><span class="nm">${esc(x.name)}${x.count > 1 ? ' ×' + x.count : ''}</span><span class="pr">${Number(x.price).toLocaleString()}</span>
              <span class="st s${x.state}">${esc(T.aucSt[x.state] || '')}</span>${x.state === 2 ? `<button class="ybtn sm" data-col="${x.kind}:${x.serial}">${esc(T.aucCollect)}</button>` : `<button class="gbtn sm" data-can="${x.kind}:${x.serial}">${esc(T.aucCancel)}</button>`}</div>`).join('') : `<div class="small muted">${esc(T.aucMineEmpty)}</div>`}</div>
          </div>`}
        </section>
        <section class="iR" aria-label="${esc(T.invItems)}">
          <div class="itabs2" role="tablist">${tabs.map(([k, n]) => `<button role="tab" aria-selected="${tab === k}" class="${tab === k ? 'on' : ''}" data-tab="${k}">${esc(n)}</button>`).join('')}</div>
          <div class="ibox">
            ${tab !== 'sticker' ? `<div class="pgrow"><button class="pg" id="pgPrev" ${page ? '' : 'disabled'} aria-label="${esc(T.prevPage)}">◀</button><span class="pgn">${page + 1} <i>/ ${pages}</i></span><button class="pg" id="pgNext" ${page < pages - 1 ? '' : 'disabled'} aria-label="${esc(T.nextPage)}">▶</button>
              <span class="grow"></span><button class="srt${sortBy === 'type' ? ' on' : ''}" data-sort="type">${esc(T.invSortType)}</button><button class="srt${sortBy === 'date' ? ' on' : ''}" data-sort="date">${esc(T.invSortDate)}</button></div>
            <div class="g40">${cells.map(tile).join('')}</div>
            <div class="grow"></div>
            <div class="idet2">${it ? `
              <span class="dico">${icon(it) ? `<img src="${icon(it)}" alt="">` : ''}</span>
              <div class="dtx"><b>${gr(it.grade)}${esc(it.name)}${it.count > 1 ? ` ×${it.count}` : ''}</b>
                <span>${esc(it.kind)}${it.level ? ` · ${esc(T.level)} ${it.level}` : ''}${it.value ? ` · +${it.value}` : ''} · ${esc(T.invSellP)} ${fmt(it.sell)}${it.auction ? ` · ${esc(T.inAuction)}` : ''}${it.broken ? ` · ${esc(T.invBroken)}` : ''}</span>
                <small>${esc(T.invHint)}</small>${msg ? `<small class="imsg">${msg}</small>` : ''}</div>
              <div class="dbt">${it.car ? `<button class="ybtn" id="iOff">${esc(T.invOff)}</button>` : `
                ${partLike ? `<button class="ybtn" id="iOn" ${car && !it.auction ? '' : 'disabled'}>${esc(T.invOn)}</button>` : ''}
                <div class="inl">${it.count > 1 ? `<input type="number" id="iQty" min="1" max="${it.count}" value="${it.count}" aria-label="${esc(T.qty)}">` : ''}
                <button class="gbtn" id="iSell" ${it.auction ? 'disabled' : ''}>${esc(T.invSell)}</button><button class="rbtn" id="iDel" ${it.auction ? 'disabled' : ''}>${esc(T.remove)}</button></div>`}</div>`
              : dr ? `
              <span class="dico">${icon(dr) ? `<img src="${icon(dr)}" alt="">` : ''}</span>
              <div class="dtx"><b>${esc(dr.name)}</b><span>${esc(dr.catName)} · ${esc(left(dr))}${dr.on ? ' · ' + esc(T.tipOnCar) : ''}</span><small>${esc(dr.desc || '')}</small>${msg ? `<small class="imsg">${msg}</small>` : ''}</div>
              <div class="dbt">${dr.on && car && dr.car !== car.id && ![1, 32, 2, 3].includes(dr.cat) ? `<button class="ybtn" id="dOn">${esc(T.invUseOnCar)}</button>` : ''}${dr.on ? `<button class="ybtn" id="dOff" ${[1, 32, 2, 3].includes(dr.cat) ? 'disabled' : ''}>${esc(T.invOff)}</button>` : `<button class="ybtn" id="dOn" ${car && (dr.cat <= 13 || [32, 38, 47, 48, 52].includes(dr.cat)) ? '' : 'disabled'}>${esc(T.invUseOnCar)}</button>`}
                <div class="inl"><button class="rbtn" id="dDel">${esc(T.remove)}</button></div></div>`
              : `<span class="muted small" style="padding:8px">${esc(tab === 'drift' ? T.invPickDrift : tab === 'auction' ? T.aucPick : T.invPick2)}${msg ? `<br>${msg}` : ''}</span>`}</div>`
            : `<div class="soonbox big"><b>${esc(T.tabSticker)}</b><span>${esc(T.invStickerSoon)}</span></div>`}
          </div>
        </section>
      </div></div>`);
    // the drawing keeps its size and shrinks to fit a smaller window
    const bpi = $('.inv2 .bpi');
    if (bpi) { const p = bpi.parentElement; bpi.style.zoom = Math.min(1, (p.clientHeight - 8) / bpi.offsetHeight, (p.clientWidth - 8) / bpi.offsetWidth); }
    // the car in 3D on the Drift Item tab (as the game's inventory): one stage kept across redraws
    if ((tab === 'drift' || tab === 'sticker') && car && window.Garage && $('#i3d')) {
      if (!st3 || !st3.alive) { st3 = window.Garage.studio($('#i3d'), null, { yaw: -0.7, fit: 1.25 }); st3Key = ''; } else st3.mount($('#i3d'));
      const key = `${car.id}:${car.paint}:${car.tint}:${JSON.stringify(car.look || [])}`;
      if (key !== st3Key) {
        st3Key = key;
        const G = window.Garage;
        st3.set({ model: car.model, type: car.type, name: car.name, tire: car.tire, tire_scale: car.tire_scale, tire_width: car.tire_width, color: car.color, paintPal: car.paintPal, paint: car.paint == null ? null : car.paint,
          tint: car.tint == null ? null : car.tint, parts: G.lookParts(car.model, car.look || []), look: (f) => G.lookBuild(car.model, car.look || [], f) });
      }
    } else if (st3) { st3.dispose(); st3 = null; }
    $('#iBack').onclick = () => { if (st3) { st3.dispose(); st3 = null; } closeModal(); if (back) back(); };
    if ($('#cPrev')) $('#cPrev').onclick = () => { carIx = (carIx + inv.cars.length - 1) % inv.cars.length; msg = ''; draw(); };
    if ($('#cNext')) $('#cNext').onclick = () => { carIx = (carIx + 1) % inv.cars.length; msg = ''; draw(); };
    if ($('#cUse')) $('#cUse').onclick = () => act({ act: 'use_car', car: car.id }, () => T.invUsed);
    if ($('#iNeo')) $('#iNeo').onclick = () => { neoView = !neoView; draw(); };
    $$('[data-tab]').forEach((b) => b.onclick = async () => { tab = b.dataset.tab; page = 0; msg = ''; if (tab === 'auction') await loadMine(); draw(); });
    const aucAct = async (cmd, args, ok) => {
      try { const r = await window.odc.auc(cmd, id, cid, args); msg = `<span class="ok">${esc(ok(r))}</span>`; aPrice = ''; aQty = ''; selItem = null; }
      catch (e) { const m = ((e && e.message) || '').replace(/^Error invoking remote method '\w+': (Error: )?/, ''); msg = `<span class="bad">${esc((T.err && T.err[m]) || errText(e))}</span>`; }
      try { await load(); await loadMine(); } catch { /* toast */ } draw(); fetchIcons();
    };
    if ($('#aPrice')) $('#aPrice').oninput = (e) => { aPrice = e.target.value; const f = $('.aform .small'); if (f) f.textContent = t('aucFee', { f: Math.max(1, Math.floor((Number(aPrice) || 0) * (mine ? mine.rules.item_fee : 7) / 100)).toLocaleString(), p: mine ? mine.rules.item_fee : 7 }) + ' ' + t('aucDays', { d: mine ? mine.rules.days : 7 }); };
    if ($('#aQty')) $('#aQty').oninput = (e) => { aQty = e.target.value; };
    if ($('#aOn')) $('#aOn').onclick = () => aucAct('on', { kind: 'item', inv: it.inv, count: Number(aQty || it.count), price: Number(aPrice) }, (r) => t('aucListed', { f: Number(r.fee).toLocaleString() }));
    if ($('#aCarOn')) $('#aCarOn').onclick = () => { if (confirm(T.aucCarNote)) aucAct('on', { kind: 'car', car: car.id, price: Number($('#aCarPrice').value) }, (r) => t('aucListed', { f: Number(r.fee).toLocaleString() })); };
    $$('[data-can]').forEach((b) => b.onclick = () => { const [k, n] = b.dataset.can.split(':'); aucAct('cancel', { kind: k, serial: Number(n) }, () => T.aucBack); });
    $$('[data-col]').forEach((b) => b.onclick = () => { const [k, n] = b.dataset.col.split(':'); aucAct('collect', { kind: k, serial: Number(n) }, (r) => t('aucGot', { p: Number(r.collected).toLocaleString() })); });
    $$('[data-sort]').forEach((b) => b.onclick = () => { sortBy = b.dataset.sort; draw(); });
    if ($('#pgPrev')) $('#pgPrev').onclick = () => { page--; draw(); };
    if ($('#pgNext')) $('#pgNext').onclick = () => { page++; draw(); };
    $$('[data-inv]').forEach((b) => b.onclick = () => { selItem = Number(b.dataset.inv) === selItem ? null : Number(b.dataset.inv); msg = ''; draw(); });
    $$('[data-dinv]').forEach((b) => b.onclick = () => { selDrift = Number(b.dataset.dinv); msg = ''; draw(); });
    $$('[data-off]').forEach((b) => b.onclick = (e) => { e.stopPropagation(); act({ act: 'off', inv: Number(b.dataset.off) }, () => T.invTaken); });
    $$('[data-slot]').forEach((b) => b.onclick = () => {
      const s = Number(b.dataset.slot);
      if (it && !it.car && car) return act({ act: 'on', inv: it.inv, car: car.id, slot: s }, () => T.invPut);
      const part = on(s).find((x) => x.type <= 3 || x.kind.startsWith('neo_')) || on(s)[0];
      if (part) { selItem = part.inv; msg = ''; draw(); }
    });
    if ($('#cRm')) $('#cRm').onclick = async () => {
      if (!confirm(t('rmCarQ', { n: car.name, r: cname }))) return;
      try { await call('carDelete', id, cid, car.id); msg = `<span class="ok">${esc(T.removed)}</span>`; carIx = 0; await load(); draw(); fetchIcons(); } catch { /* toast */ }
    };
    // drag and drop: an item onto a slot of the car puts it there; a part from the car onto the items takes it off;
    // a pile onto another pile of the same item merges them
    let dragged = null;
    $$('[data-drag]').forEach((el) => {
      el.addEventListener('dragstart', (e) => { dragged = Number(el.dataset.drag); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(dragged)); });
      el.addEventListener('dragend', () => { dragged = null; $$('.over').forEach((o) => o.classList.remove('over')); });
    });
    const zone = (el, ok, drop) => {
      if (!el) return;
      el.addEventListener('dragover', (e) => { const x = inv.items.find((y) => y.inv === dragged); if (x && ok(x)) { e.preventDefault(); el.classList.add('over'); } });
      el.addEventListener('dragleave', () => el.classList.remove('over'));
      el.addEventListener('drop', (e) => { e.preventDefault(); el.classList.remove('over'); const x = inv.items.find((y) => y.inv === dragged); if (x && ok(x)) drop(x); });
    };
    $$('[data-slot]').forEach((el) => zone(el, (x) => !x.car && car, (x) => act({ act: 'on', inv: x.inv, car: car.id, slot: Number(el.dataset.slot) }, () => T.invPut)));
    zone($('.g40'), (x) => !!x.car, (x) => act({ act: 'off', inv: x.inv }, () => T.invTaken));
    $$('.gcell[data-inv]').forEach((el) => zone(el, (x) => !x.car && x.inv !== Number(el.dataset.inv) && x.id === (inv.items.find((y) => y.inv === Number(el.dataset.inv)) || {}).id && x.stack > 1,
      (x) => act({ act: 'merge', inv: x.inv, to: Number(el.dataset.inv) }, (r) => t('invMerged', { n: r.moved }))));
    // drift items: from the list onto the car (its 3D view or a slot) puts it on; from a slot onto the list takes it off
    if (tab === 'drift') {
      let dd = null;
      const dItem = () => (inv.drift || []).find((y) => y.inv === dd);
      $$('[data-ddrag]').forEach((el) => {
        el.addEventListener('dragstart', (e) => { dd = Number(el.dataset.ddrag); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', 'd' + dd); });
        el.addEventListener('dragend', () => { dd = null; $$('.over').forEach((o) => o.classList.remove('over')); });
      });
      const dzone = (el, ok, drop) => {
        if (!el) return;
        el.addEventListener('dragover', (e) => { const x = dItem(); if (x && ok(x)) { e.preventDefault(); el.classList.add('over'); } });
        el.addEventListener('dragleave', () => el.classList.remove('over'));
        el.addEventListener('drop', (e) => { e.preventDefault(); el.classList.remove('over'); const x = dItem(); if (x && ok(x)) drop(x); });
      };
      // any drift item that goes on cars, also one bought for or worn by another car (the helper checks it fits this
      // one); paint, neon and glass worn by another car stay there
      const wearable = (x) => car && !(x.on && x.car === car.id) && !(x.on && [1, 32, 2, 3].includes(x.cat)) && (x.cat <= 13 || [32, 38, 47, 48, 52].includes(x.cat));
      dzone($('#i3d'), wearable, (x) => act({ act: 'drift_on', inv: x.inv, car: car.id }, () => T.invPut));
      $$('.ds[data-dcats]').forEach((el) => dzone(el, (x) => wearable(x) && el.dataset.dcats.split(',').map(Number).includes(x.cat),
        (x) => act({ act: 'drift_on', inv: x.inv, car: car.id }, () => T.invPut)));
      dzone($('.g40'), (x) => x.on && car && x.car === car.id && ![1, 32, 2, 3].includes(x.cat), (x) => act({ act: 'drift_off', inv: x.inv }, () => T.invTaken));
    }
    if (dr) {
      if ($('#dOn')) $('#dOn').onclick = () => act({ act: 'drift_on', inv: dr.inv, car: car.id }, () => T.invPut);
      if ($('#dOff')) $('#dOff').onclick = () => act({ act: 'drift_off', inv: dr.inv }, () => T.invTaken);
      $('#dDel').onclick = () => { if (confirm(t('rmItemQ', { q: 1, n: dr.name, r: cname }))) act({ act: 'drift_del', inv: dr.inv }, () => T.removed); };
    }
    if (!it) return;
    if ($('#iOff')) $('#iOff').onclick = () => act({ act: 'off', inv: it.inv }, () => T.invTaken);
    if ($('#iOn')) $('#iOn').onclick = () => act({ act: 'on', inv: it.inv, car: car.id }, () => T.invPut);
    const qty = () => ($('#iQty') ? Math.max(1, Math.min(it.count, Number($('#iQty').value) || it.count)) : it.count);
    if ($('#iSell')) $('#iSell').onclick = () => {
      const n = qty();
      if (!confirm(t('invSellQ', { q: n, n: it.name, m: fmt(it.sell * n) }))) return;
      act({ act: 'sell', inv: it.inv, count: n }, (r) => t('invSold', { m: fmt(r.mito) }));
    };
    if ($('#iDel')) $('#iDel').onclick = () => {
      const n = qty();
      if (!confirm(t('rmItemQ', { q: n, n: it.name, r: cname }))) return;
      act({ act: 'delete', inv: it.inv, count: n }, () => T.removed);
    };
  };
  draw();
  fetchIcons();
}

// ---- settings ----
let cfgTab = 'srv', logWhich = 'launcher';
function pageSettings(m) {
  const tabs = [['srv', T.tSrv], ['vid', T.tVid], ['pas', T.tPas], ['idi', T.tIdi], ['adv', T.tAdv], ['log', T.tLog]];
  m.innerHTML = `<div class="page"><h1>${esc(T.cfgTitle)}</h1>
    <div class="tabs" role="tablist">${tabs.map(([k, n]) => `<button role="tab" class="${cfgTab === k ? 'on' : ''}" data-k="${k}">${esc(n)}</button>`).join('')}</div>
    <div id="tabBody" style="display:flex;flex-direction:column;gap:12px;flex-grow:1;min-height:0"></div></div>`;
  $$('[data-k]', m).forEach((b) => b.onclick = () => { cfgTab = b.dataset.k; render(); });
  ({ srv: tabServer, vid: tabVideo, pas: tabFolders, idi: tabLang, adv: tabAdvanced, log: tabLog }[cfgTab])($('#tabBody'));
}
// servers found on the network (Settings > Server): kept while the launcher is open
let lanFound = null, lanBusy = false;
function lanHtml(c) {
  if (lanBusy) return `<span class="muted small">${esc(T.lanScanning)}</span>`;
  if (!lanFound) return '';
  if (!lanFound.length) return `<span class="muted small">${esc(T.lanNone)}</span>`;
  return lanFound.map((s, i) => {
    const on = c.serverMode === 'remote' && c.remoteIp === s.ip;
    const other = s.client && c.client && String(s.client) !== String(c.client);
    if (!s.running) return `<div class="lanit off"><span class="ld offd"></span><span class="ln"><b>${esc(s.name)}</b><small>${esc(s.ip)} · ${esc(T.lanOff)}</small></span></div>`;
    return `<button class="lanit${on ? ' on' : ''}" data-lan="${i}" ${on ? 'aria-pressed="true"' : ''}>
      <span class="ld ${other ? 'warn' : 'ok'}"></span><span class="ln"><b>${esc(s.name)}</b><small>${esc(s.ip)}${s.port ? ':' + s.port : ''} · ${esc(s.client ? 'Drift City ' + s.client : '')}${s.launcher ? '' : ' · ' + esc(T.lanPlain)}${other ? ' · ' + esc(t('lanOther', { c: s.client, m: c.client })) : ''}</small></span>
      <span class="lu">${esc(on ? T.lanUsing : T.lanUse)}</span></button>`;
  }).join('');
}
function tabServer(el) {
  const c = ST.cfg;
  el.innerHTML = `<div class="grid2">
    <section>
      <div class="set"><div class="l"><b>${esc(T.where)}</b><span class="muted small">${esc(T.whereD)}</span></div><div class="seg"><button id="mLocal" class="${c.serverMode !== 'remote' ? 'on' : ''}">${esc(T.local)}</button><button id="mRemote" class="${c.serverMode === 'remote' ? 'on' : ''}">${esc(T.other)}</button></div></div>
      <div class="set"><div class="l"><b>${esc(T.maxCl)}</b><span class="muted small">${esc(T.maxClD)}</span></div><div class="seg" role="radiogroup" aria-label="${esc(T.maxCl)}">${[1, 2, 3, 4].map((n) => `<button role="radio" aria-checked="${(c.maxClients || 1) === n}" class="mc${(c.maxClients || 1) === n ? ' on' : ''}" data-n="${n}">${n}</button>`).join('')}</div></div>
      <div class="set"><div class="l"><b>${esc(T.addr)}</b><span class="muted small">${esc(T.addrD)}</span></div><input type="text" id="rIp" value="${esc(c.remoteIp)}" placeholder="192.168.0.15" style="width:150px" ${c.serverMode === 'remote' ? '' : 'disabled'}><button class="btn sm" id="rTest" ${c.serverMode === 'remote' ? '' : 'disabled'}>${esc(T.test)}</button></div>
      <div class="set"><div class="l"><span id="rRes" class="muted small"></span></div></div>
      <div class="set lanset"><div class="l"><b>${esc(T.lanFind)}</b><span class="muted small">${esc(T.lanFindD)}</span></div><button class="btn sm" id="lanGo">${esc(T.lanFind)}</button></div>
      <div class="lanlist" id="lanList" aria-live="polite">${c.serverMode === 'remote' ? lanHtml(c) : ''}</div>
      <div class="set"><div class="l"><b>${esc(T.onGame)}</b><span class="muted small">${esc(T.onGameD)}</span></div><select id="og">${[['tray', T.ogTray], ['minimize', T.ogMin], ['none', T.ogNone]].map(([v, n]) => `<option value="${v}" ${(c.onGame || 'tray') === v ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select></div>
    </section>
    <section>
      <div class="set"><div class="l"><b>${esc(T.srvNow)}</b><span class="muted small">${esc(ST.server ? T.srvOn : T.srvOff)}</span></div><button class="btn sm" id="sOn" ${ST.installed && !ST.server && !ST.busy ? '' : 'disabled'}>${esc(T.srvStart)}</button><button class="btn sm" id="sOff" ${(ST.server || ST.db) && !ST.busy ? '' : 'disabled'}>${esc(T.srvStop)}</button></div>
      <div class="set"><div class="l"><b>${esc(T.bk)}</b><span class="muted small">${esc(T.bkD)}</span></div><button class="btn sm" id="bkGo" ${ST.installed ? '' : 'disabled'}>${esc(T.bkNow)}</button></div>
      <div class="set"><div class="l"><b>${esc(T.bkAuto)}</b></div><input type="checkbox" id="bkAuto" ${c.autoBackup ? 'checked' : ''}></div>
      <div class="set"><div class="l"><b>${esc(T.srvUpd)}</b><span class="muted small" id="suRes">${esc(T.srvUpdD)}</span></div><button class="btn sm" id="suGo" ${ST.installed && !ST.busy ? '' : 'disabled'}>${esc(T.srvUpdBtn)}</button><button class="btn sm pri" id="suApply" hidden>${esc(T.updBtn)}</button></div>
      <div class="set"><div class="l"><b>${esc(T.tables)}</b><span class="muted small">${esc(T.tablesD)}</span></div><button class="btn sm" id="tbGo" ${ST.installed ? '' : 'disabled'}>${esc(T.repair)}</button></div>
    </section></div>`;
  const save = async (patch) => { await call('saveConfig', patch); await refresh(); };
  $$('.mc', el).forEach((b) => { b.onclick = async () => { await save({ maxClients: +b.dataset.n }); render(); }; });
  // back to this computer: the game plays on this server again (the next Play points the game at 127.0.0.1)
  $('#mLocal').onclick = async () => { await save({ serverMode: 'local' }); lanFound = null; toast(T.lanLocal, true); render(); };
  $('#mRemote').onclick = async () => { await save({ serverMode: 'remote' }); render(); if (!lanFound && !lanBusy) $('#lanGo').click(); };
  $('#lanGo').onclick = async () => {
    if (lanBusy) return;
    if (ST.cfg.serverMode !== 'remote') await save({ serverMode: 'remote' });
    lanBusy = true; render();
    try { lanFound = await call('lanScan'); } catch { lanFound = []; }
    lanBusy = false;
    if ($('#lanList')) render();
  };
  const bindLan = () => $$('[data-lan]', el).forEach((b) => b.onclick = async () => {
    const s = lanFound[+b.dataset.lan];
    await save({ serverMode: 'remote', remoteIp: s.ip, remotePort: s.port || null });
    toast(t('lanSet', { n: s.name, ip: s.ip }), true);
    render();
  });
  bindLan();
  $('#rIp').onchange = (e) => save({ remoteIp: e.target.value.trim(), remotePort: null });
  $('#rTest').onclick = async () => { $('#rRes').textContent = T.testing; const ok = await call('testRemote', $('#rIp').value.trim()); $('#rRes').textContent = ok ? T.testOk : T.testBad; $('#rRes').className = ok ? 'ok' : 'bad'; };
  $('#og').onchange = (e) => save({ onGame: e.target.value });
  $('#bkAuto').onchange = (e) => save({ autoBackup: e.target.checked });
  $('#sOn').onclick = async () => { $('#sOn').disabled = $('#sOff').disabled = true; try { await call('serverStart'); } catch { /* toast */ } await refresh(); render(); };
  $('#sOff').onclick = async () => { $('#sOn').disabled = $('#sOff').disabled = true; try { await call('serverStop'); } catch { /* toast */ } await refresh(); render(); };
  $('#bkGo').onclick = async () => { try { const f = await call('backup'); toast('✓ ' + f, true); } catch { /* toast */ } };
  // check the openDC server (emulator) on GitHub now, without restarting the launcher
  const showSrvUpd = () => {
    const el = $('#suRes'); if (!el) return;
    const e = upd && upd.emulator;
    if (!e) { el.textContent = T.srvUpdD; el.className = 'muted small'; $('#suApply').hidden = true; return; }
    if (e.error) { el.textContent = T.updFail; el.className = 'bad'; $('#suApply').hidden = true; return; }
    el.textContent = e.available ? t('srvUpdNew', { n: e.changes.length }) : T.okUpd;
    el.className = e.available ? 'ok' : 'muted small';
    $('#suApply').hidden = !e.available;
  };
  $('#suGo').onclick = async () => {
    $('#suGo').disabled = true; $('#suRes').textContent = T.checking; $('#suRes').className = 'muted small';
    try { upd = await window.odc.checkUpdate(); } catch { upd = { emulator: { error: true } }; }
    if ($('#suGo')) { $('#suGo').disabled = false; showSrvUpd(); }
  };
  $('#suApply').onclick = async () => { await onUpdate(); };
  $('#tbGo').onclick = async () => { try { await call('refreshTables'); toast('✓', true); } catch { /* toast */ } };
}
// the launcher's own 3D views (garage, drift shop, inventory, coupon book, gotcha): one quality for all, kept in step
// with the garage's and the drift shop's options
function gfx3dRow() {
  const G = window.Garage; const cur = G ? G.gfxGet() : 'mid';
  return `<div class="set g3d"><div class="l"><b>${esc(T.v3dTitle)}</b><span class="muted small">${esc(T.v3dDesc)}</span><span class="warn3d small">⚠ ${esc(T.v3dWarn)}</span></div>
    <div class="gseg" role="radiogroup" aria-label="${esc(T.v3dTitle)}">${['low', 'mid', 'high'].map((q) => `<button data-g3="${q}" role="radio" aria-checked="${q === cur}" class="${q === cur ? 'on' : ''}">${esc(T['garGfx_' + q] || q)}</button>`).join('')}</div></div>`;
}
function bindGfx3d(el) {
  el.querySelectorAll('[data-g3]').forEach((b) => { b.onclick = () => { if (window.Garage) window.Garage.gfxSet(b.dataset.g3); el.querySelectorAll('[data-g3]').forEach((x) => { x.classList.toggle('on', x === b); x.setAttribute('aria-checked', x === b ? 'true' : 'false'); }); }; });
}
async function tabVideo(el) {
  el.classList.add('vscroll');   // every video option, scrolling; Save stays at the bottom
  if (!ST.installed) { el.innerHTML = `${gfx3dRow()}<div class="empty">${esc(T.vNo)}</div>`; bindGfx3d(el); return; }
  let v;
  try { v = await call('video'); } catch { return; }
  if (!v.exists) { el.innerHTML = `${gfx3dRow()}<div class="empty">${esc(T.vNo)}</div>`; bindGfx3d(el); return; }
  const resKey = `${v.width} × ${v.height}`;
  const scr = ST.screen;
  const wh = (r) => r.split('×').map((x) => parseInt(x, 10));
  const fits = (r) => { const [w, h] = wh(r); return !scr || (w <= scr.w && h <= scr.h); };
  // a window also needs room for its title bar inside the work area (taskbar / panel excluded)
  const fitsWin = (r) => { const [w, h] = wh(r); return !scr || (w <= (scr.ww || scr.w) && h + 40 <= (scr.wh || scr.h)); };
  const native = scr ? `${scr.w} × ${scr.h}` : null;
  let resList = RES.filter(fits);
  if (native && !resList.includes(native)) resList.push(native);
  if (!resList.includes(resKey)) resList.push(resKey);
  resList.sort((a, b) => wh(a)[0] - wh(b)[0] || wh(a)[1] - wh(b)[1]);
  const resLabel = (r, full) => { const [w, h] = wh(r); return `${r}  (${ratio(w, h)})` + (r === native ? ` · ${T.resNative}` : '') + (!fits(r) ? ' ⚠' : !full && !fitsWin(r) ? ` · ${T.resNoWin}` : ''); };
  const sel = (id, opts, cur) => `<select id="${id}">${opts.map(([val, lab]) => `<option value="${val}" ${String(val) === String(cur) ? 'selected' : ''}>${esc(lab)}</option>`).join('')}</select>`;
  const lv = (from) => T.g.map((g, i) => [i + from, g]);
  const row = (lab, key, ctrl, d) => `<div class="set"><div class="l"><b>${esc(lab)}</b>${d ? `<span class="muted small">${esc(d)}</span>` : ''}<span class="code">${key}</span></div>${ctrl}</div>`;
  // the details a preset sets (DriftCity.exe 0x4f4b50), shown so a preset visibly changes everything it changes
  const q4 = [[1, T.g[0]], [2, T.g[1]], [3, T.g[2]], [4, T.g[3]]];
  const onOff = [[0, T.off], [1, T.on]];
  const ADV = [
    { k: 'VehicleShadow', o: [[1, T.g[0]], [2, T.g[1]], [3, T.g[2]]] }, { k: 'ShowObjectShadow', o: onOff },
    { k: 'ShadowRange', o: [[0, T.near], [1, T.far]] }, { k: 'ShadowMapType', o: [[0, T.g[0]], [1, T.g[1]], [2, T.g[2]]] },
    { k: 'DofType', o: onOff },
    { k: 'CarTextureQuality', o: q4 }, { k: 'ObjectTextureQuality', o: q4 }, { k: 'TerrainTextureQuality', o: q4 },
    { k: 'CarShader', o: [[1, T.g[0]], [2, T.g[1]], [3, T.g[2]]] }, { k: 'EnvMapType', o: [[0, T.off], [1, T.g[0]], [2, T.g[2]]] },
    { k: 'AniVisibleRange', o: [[0, T.near], [1, T.g[1]], [2, T.far]] },
    { k: 'ObjectAnimation', t: 'b' }, { k: 'BattleAnimation', t: 'b' }, { k: 'ShowEffectMine', t: 'b' }, { k: 'ShowEffectUsers', t: 'b' },
  ];
  const advRow = (d) => {
    const cur = v.adv[d.k];
    const opts = d.o.some(([x]) => x === cur) || cur === null ? d.o : [...d.o, [cur, String(cur)]];
    return row(T['a_' + d.k] || d.k, 'goption.ini · ' + d.k, sel('a_' + d.k, opts, cur === null ? d.o[0][0] : cur));
  };
  el.innerHTML = `${gfx3dRow()}<div class="info"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#C08A55" stroke-width="2" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></svg><span class="grow">${esc(T.vLink)}</span><button class="btn sm" id="vRest">${esc(T.vRestore)}</button></div>
    ${ST.os.linux ? `<div class="info"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#C08A55" stroke-width="2" aria-hidden="true"><path d="M4 17l6-6-6-6M12 19h8"/></svg><span class="grow">${esc(T.pxRow)} <b id="pxCur" style="color:#E8ECF2"></b></span><button class="btn sm" id="pxOpen">${esc(T.pxBtn)}</button></div>` : ''}
    <div class="grid2"><section>
      ${row(T.res, 'goption.ini · ScreenWidth, ScreenHeight', sel('vRes', resList.map((r) => [r, resLabel(r, v.fullscreen)]), resKey), scr ? t('resD', { w: scr.w, h: scr.h }) : '')}
      ${row(T.mode, 'goption.ini · Fullscreen + launcher display', sel('vMode', [[0, T.win], [1, T.full]], v.fullscreen ? 1 : 0), ST.os.linux ? T.modeD : '')}
      ${row(T.hud, 'goption.ini · MainUIType', sel('vHud', [[0, T.hud0], [1, T.hud1]], v.hud))}
    </section><section>
      ${row(T.preset, 'goption.ini · VideoGradeSet', sel('vPre', [[-1, T.custom], [0, T.pSpeed], [1, T.pNormal], [2, T.pQuality]], v.preset), T.presetD)}
      ${row(T.aa, 'goption.ini · MultiSampling', sel('vAa', [[0, T.off], [2, '2×'], [4, '4×']], v.msaa))}
      ${row(T.blur, 'goption.ini · MotionBlur, MotionBlurType', sel('vBlur', [[0, T.blurN], [1, T.blurM]], Math.min(1, v.blur)), T.blurD)}
      <div class="checks"><label><input type="checkbox" id="vFog" ${v.fog ? 'checked' : ''}>${esc(T.fog)}</label><label><input type="checkbox" id="vOut" ${v.outline ? 'checked' : ''}>${esc(T.outline)}</label></div>
    </section></div>
    <div class="sec" style="margin-top:6px">${esc(T.vAdv)}</div><div class="muted small">${esc(T.vAdvD)}</div>
    <div class="grid2"><section>
      ${row(T.range, 'goption.ini · VisibleRange', sel('vRange', [1, 2, 3, 4, 5].map((n) => [n, n === 1 ? `1 · ${T.near}` : n === 5 ? `5 · ${T.far}` : String(n)]), v.range))}
      ${ADV.filter((d) => d.t !== 'b').slice(0, 5).map(advRow).join('')}</section>
      <section>${ADV.filter((d) => d.t !== 'b').slice(5).map(advRow).join('')}
      <div class="checks">${ADV.filter((d) => d.t === 'b').map((d) => `<label title="goption.ini · ${d.k}"><input type="checkbox" id="a_${d.k}" ${v.adv[d.k] ? 'checked' : ''}>${esc(T['a_' + d.k] || d.k)}</label>`).join('')}</div></section></div>
    <div class="foot vfoot"><span class="ok" id="vOk"></span><button class="btn pri" id="vSave">${esc(T.save)}</button></div>`;
  if ($('#pxOpen')) {
    $('#pxOpen').onclick = openProton;
    window.odc.protonState().then((x) => { const el = $('#pxCur'); if (el) el.textContent = (x.list.find((p) => p.using) || {}).name || T.pxNone; }).catch(() => {});
  }
  // Graphic Quality presets, as in the game: picking one sets the details it governs; changing a detail makes it Custom
  const P = (aa, range, vs, sos, sr, smt, ct, ot, tt, cs, env, hdr, dof, ani, oa, eu) => ({ vAa: aa, vRange: range,
    a_VehicleShadow: vs, a_ShowObjectShadow: sos, a_ShadowRange: sr, a_ShadowMapType: smt, a_CarTextureQuality: ct,
    a_ObjectTextureQuality: ot, a_TerrainTextureQuality: tt, a_CarShader: cs, a_EnvMapType: env, a_DofType: dof,
    a_AniVisibleRange: ani, a_ObjectAnimation: oa, a_BattleAnimation: true, a_ShowEffectMine: true, a_ShowEffectUsers: eu });
  const PRESET_UI = {
    0: P(0, 2, 1, 0, 0, 0, 3, 1, 1, 2, 1, 0, 0, 0, false, false),
    1: P(2, 3, 1, 0, 0, 0, 4, 2, 2, 2, 2, 0, 0, 1, true, true),
    2: P(4, 4, 3, 1, 1, 1, 4, 3, 3, 2, 2, 0, 1, 2, true, true),
  };
  $('#vPre').onchange = () => {
    const p = PRESET_UI[$('#vPre').value];
    if (p) for (const [id, x] of Object.entries(p)) {
      const el = $('#' + id); if (!el) continue;
      if (el.type === 'checkbox') el.checked = !!x; else el.value = String(x);
    }
  };
  for (const id of ['vAa', 'vRange', 'vBlur', 'vFog', 'vOut', ...ADV.map((d) => 'a_' + d.k)]) {
    const el = $('#' + id);
    if (el) el.addEventListener('change', () => { $('#vPre').value = '-1'; });
  }
  // the "doesn't fit in a window" marks follow the screen mode picked
  $('#vMode').onchange = () => { const full = $('#vMode').value === '1'; $$('#vRes option').forEach((o) => { o.textContent = resLabel(o.value, full); }); };
  bindGfx3d(el);
  $('#vRest').onclick = async () => { try { await call('videoRestore'); render(); } catch { /* toast */ } };
  $('#vSave').onclick = async () => {
    const [w, h] = wh($('#vRes').value);
    const nv = { width: w, height: h, fullscreen: $('#vMode').value === '1', hud: +$('#vHud').value, msaa: +$('#vAa').value, preset: +$('#vPre').value,
      range: +$('#vRange').value,
      blur: +$('#vBlur').value, fog: $('#vFog').checked, outline: $('#vOut').checked,
      adv: Object.fromEntries(ADV.map((d) => [d.k, d.t === 'b' ? $('#a_' + d.k).checked : +$('#a_' + d.k).value])) };
    try { await call('videoSave', nv); $('#vOk').textContent = T.saved; setTimeout(() => { const o = $('#vOk'); if (o) o.textContent = ''; }, 2000); } catch { /* toast */ }
  };
}
function tabFolders(el) {
  el.innerHTML = `<section>
    <div class="set"><div class="l"><b>${esc(T.root)}</b><span class="muted small">${esc(T.rootD)}</span><div class="pathrow"><code>${esc(ST.cfg.root)}</code></div></div><button class="btn sm" id="fRoot">${esc(T.rootChange)}</button></div>
    <div class="set"><div class="l"><b>${esc(T.vfT)}</b><span class="muted small">${esc(T.vfD)}</span></div><button class="btn sm" id="vfGo" ${ST.installed && !ST.busy ? '' : 'disabled'}>${esc(T.vfBtn)}</button></div>
    <div id="vfRes"></div>
    ${[['client', T.openGame], ['emu', T.openSrv], ['logs', T.openLogs], ['backups', T.openBk]].map(([k, n]) => `<div class="set"><div class="l"><b>${esc(n)}</b></div><button class="btn sm" data-open="${k}">${esc(T.open)}</button></div>`).join('')}
  </section>`;
  $('#vfGo').onclick = async () => {
    const box = $('#vfRes');
    $('#vfGo').disabled = true;
    box.innerHTML = `<div class="info">${esc(T.vfChecking)}</div>`;
    let r;
    try { r = await window.odc.verifyFiles(); } catch (e) { box.innerHTML = `<div class="info bad">${esc(errText(e))}</div>`; $('#vfGo').disabled = false; return; }
    const line = (name, miss, extra) => `<div class="inl" style="font-size:13px"><span class="${miss ? 'bad' : 'ok'}">${miss ? '✗' : '✓'}</span><b>${esc(name)}</b><span class="muted small">${esc(extra)}</span></div>`;
    const rt = r.runtime.missing.map((x) => (x === 'python' ? 'Python' : 'PostgreSQL'));
    const sample = (l) => (l.length ? ' — ' + l.slice(0, 3).join(', ') + (l.length > 3 ? '…' : '') : '');
    box.innerHTML = `<div class="card" style="margin:8px 0">
      ${line(T.vfClient, r.client.missing.length, r.client.missing.length ? t('vfMissing', { n: r.client.missing.length }) + sample(r.client.missing) : t('vfOk', { n: r.client.checked }) + (r.client.manifest ? '' : ' · ' + T.vfNoMan))}
      ${line(T.vfServer, r.server.missing.length || r.server.error, r.server.error ? T.updFail : r.server.missing.length ? t('vfMissing', { n: r.server.missing.length }) + sample(r.server.missing) : t('vfOk', { n: r.server.checked }))}
      ${line(T.vfRuntime, rt.length, rt.length ? t('vfMissingRt', { l: rt.join(', ') }) : 'Python · PostgreSQL')}
      ${r.ok ? `<span class="ok">${esc(T.vfAllOk)}</span>` : !r.client.missing.length && !r.server.missing.length && !r.runtime.missing.length ? `<span class="muted small">${esc(T.vfPartial)}</span>` : `<div class="inl"><span class="muted small grow">${esc(T.vfRepairD)}</span><button class="btn pri sm" id="vfFix">${esc(T.vfRepair)}</button></div>`}
    </div>`;
    $('#vfGo').disabled = false;
    if ($('#vfFix')) $('#vfFix').onclick = async () => {
      go('home');
      bar = { title: T.vfRepairing, sub: '', frac: 0, color: '#FF8A2B' };
      renderHomeDynamic();
      try { const d = await call('repairFiles'); bar = null; toast(t('vfDone', { c: d.client, s: d.server }), true); }
      catch (e) { bar = { title: T.error, sub: errText(e), frac: 0, color: '#FF8A8A' }; }
      await refresh(); renderHomeDynamic();
    };
  };
  $$('[data-open]', el).forEach((b) => b.onclick = () => call('openPath', b.dataset.open));
  $('#fRoot').onclick = async () => {
    const d = await call('pickRoot'); if (!d) return;
    try { await window.odc.adopt(d); } catch { await call('saveConfig', { root: d }); }
    await refresh(); upd = null; checkUpdate(); render();
  };
}
function tabLang(el) {
  el.innerHTML = `<section>
    <div class="set"><div class="l"><b>${esc(T.lang)}</b><span class="muted small">${esc(T.langD)}</span></div><select id="lSel"><option value="pt">Português (Brasil)</option><option value="en">English</option><option value="ru">Русский</option></select></div>
    <div class="set"><div class="l"><b>${esc(T.gameLang)}</b><span class="muted small">${esc(T.gameLangD)}</span></div><select disabled><option>English (US)</option></select></div></section>`;
  $('#lSel').value = L;
  $('#lSel').onchange = async (e) => { await call('saveConfig', { lang: e.target.value }); await refresh(); setLang(e.target.value); };
}
function tabAdvanced(el) {
  const head = `<div class="set" style="align-items:flex-start"><div class="l"><b>${esc(T.laaT)}</b><span class="muted small" style="line-height:1.5">${esc(T.laaD)}</span><span class="code">Emulator/tools/laa.py · DriftCity.exe</span></div></div>`;
  if (ST.os.linux) { el.innerHTML = `<section>${head}<div class="info">${esc(T.laaLinux)}</div></section>`; return; }
  if (!ST.installed) { el.innerHTML = `<section>${head}<div class="empty">${esc(T.needInstall)}</div></section>`; return; }
  el.innerHTML = `<section>${head}
    <div class="set"><div class="l"><b>${esc(T.laaNow)}</b><span id="laaSt" class="muted small">${esc(T.loading)}</span></div>
      <button class="btn sm" data-laa="status">${esc(T.laaCheck)}</button><button class="btn sm pri" data-laa="apply">${esc(T.laaApply)}</button><button class="btn sm" data-laa="remove">${esc(T.laaRemove)}</button><button class="btn sm" data-laa="restore" disabled title="${esc(T.laaRestoreD)}">${esc(T.laaRestore)}</button></div>
    <div class="muted small" style="padding-top:10px;line-height:1.5">${esc(T.laaNote)}</div>
    <pre class="log" id="laaOut" style="max-height:160px;min-height:60px;margin-top:10px"></pre></section>`;
  const show = (r) => {
    const st = $('#laaSt'); if (!st) return;
    st.textContent = r.on ? T.laaOn : T.laaOff; st.className = r.on ? 'ok' : 'bad';
    $('#laaOut').textContent = (r.text && r.text !== r.status ? r.text + '\n' : '') + r.status;
    hasBackup = !!r.backup;
  };
  let hasBackup = false;
  const go = async (a) => {
    $$('[data-laa]').forEach((b) => { b.disabled = true; });
    try { show(await window.odc.laa(a)); }
    catch (e) { const st = $('#laaSt'); if (st) { st.textContent = errText(e); st.className = 'bad'; } }
    $$('[data-laa]').forEach((b) => { b.disabled = b.dataset.laa === 'restore' && !hasBackup; });
  };
  $$('[data-laa]').forEach((b) => b.onclick = () => go(b.dataset.laa));
  go('status');
}
function tabLog(el) {
  el.innerHTML = `<div class="inl"><div class="chips">${[['launcher', T.logL], ['server', T.logS], ['db', T.logD], ['game', T.logG]].map(([k, n]) => `<button class="chip${logWhich === k ? ' on' : ''}" data-l="${k}">${esc(n)}</button>`).join('')}</div><div class="grow"></div>
    <button class="btn sm" id="lRef">${esc(T.refresh)}</button><button class="btn sm" id="lOpen">${esc(T.openLogs)}</button></div><pre class="log" id="logTxt"></pre>`;
  const load = async () => { const txt = await call('readLog', logWhich); const p = $('#logTxt'); if (p) { p.textContent = txt; p.scrollTop = p.scrollHeight; } };
  $$('[data-l]', el).forEach((b) => b.onclick = () => { logWhich = b.dataset.l; render(); });
  $('#lRef').onclick = load; $('#lOpen').onclick = () => call('openPath', 'logs');
  load();
}

// ---- mods ----
function pageMods(m) {
  m.innerHTML = `<div class="page"><div class="h1row"><h1>${esc(T.navMods)}</h1><em class="exp" style="margin-left:0">${esc(T.exp)}</em><span class="muted" style="font-size:13px">${esc(T.modsSub)}</span></div>
    <div class="banner"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#FF9A45" stroke-width="2" aria-hidden="true"><path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.5"/></svg>
      <div style="display:flex;flex-direction:column;gap:3px"><span class="t">${esc(T.modsWarnT)}</span><span class="x">${esc(T.modsWarn)}</span></div></div>
    <div class="scroll" id="modList">${esc(T.loading)}</div>
    <div class="inl"><button class="btn" id="mOpen">${esc(T.modsOpen)}</button></div></div>`;
  $('#mOpen').onclick = () => call('openPath', 'mods');
  if (!ST.installed) { $('#modList').innerHTML = `<div class="empty">${esc(T.needInstall)}</div>`; return; }
  window.odc.modsList().then((list) => {
    const el = $('#modList'); if (!el) return;
    el.innerHTML = list.map((x) => `<div class="card" style="margin-bottom:10px">
      <div class="inl"><div class="grow" style="display:flex;flex-direction:column;gap:4px">
        <b style="font-size:15px">${esc(T['mod_' + x.id] || x.id)}</b>
        <span class="muted small" style="line-height:1.5">${esc(T['mod_' + x.id + 'D'] || '')}</span>
        <span class="small" id="mInfo_${x.id}">${x.supported ? '' : esc(T.modOnly2016)}</span></div>
        <span class="badge ${x.enabled ? 'gm' : ''}" style="margin:0 8px">${esc(x.enabled ? T.modOn : T.modOff)}</span>
        <button class="btn ${x.enabled ? '' : 'pri'} sm" data-mod="${x.id}" data-on="${x.enabled ? 1 : 0}" ${x.supported && !ST.game ? '' : 'disabled'}>${esc(x.enabled ? T.modDisable : T.modEnable)}</button>
      </div></div>`).join('');
    $$('[data-mod]', el).forEach((b) => b.onclick = async () => {
      const id = b.dataset.mod, on = b.dataset.on === '1';
      const info = $('#mInfo_' + id);
      $$('[data-mod]').forEach((x) => { x.disabled = true; });
      info.textContent = on ? T.modWorkingOff : T.modWorkingOn; info.className = 'small muted';
      try {
        const r = on ? await window.odc.modDisable(id) : await window.odc.modEnable(id);
        toast(on ? T.modDoneOff : t('modDoneOn', { n: r.client.from_rice, m: r.client.only_opendc }), true);
        render();
      } catch (e) { info.textContent = errText(e); info.className = 'small bad'; $$('[data-mod]').forEach((x) => { x.disabled = false; }); }
    });
  }).catch((e) => { const el = $('#modList'); if (el) el.textContent = t('loadFail', { e: errText(e) }); });
}

// ---------- modal ----------
function modal(html) { const m = $('#modal'); m.innerHTML = html; m.hidden = false; }
function closeModal() { const m = $('#modal'); m.hidden = true; m.innerHTML = ''; }
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('#modal').hidden && !document.querySelector('.quitdlg')) closeModal(); });

// ---------- updates ----------
async function checkUpdate() {
  if (!ST) return;
  try { upd = await window.odc.checkUpdate(); } catch { upd = { error: true }; }
  if (page === 'home') renderHomeDynamic();
}

// ---------- start the database + server with the launcher ----------
async function autoStart() {
  if (!ST.installed || ST.server || ST.busy || ST.cfg.serverMode === 'remote') return;
  bar = { title: T.startServer, sub: '', frac: 0.3, color: '#FF8A2B' };
  renderHomeDynamic();
  try { await window.odc.serverStart(); bar = null; }
  catch (e) { bar = { title: T.error, sub: errText(e), frac: 0, color: '#FF8A8A' }; toast(errText(e)); }
  await refresh(); renderHomeDynamic();
}

// ---------- boot ----------
async function boot() {
  $('#btnMin').onclick = () => window.odc.minimize();
  $('#btnClose').onclick = () => {
    if (!ST || !(ST.game || ST.launching)) return window.odc.close();
    modal(`<div class="dlg" role="alertdialog" aria-label="${esc(T.closeQ)}"><h2>${esc(T.closeQ)}</h2>
      <div class="muted" style="font-size:13px;line-height:1.5">${esc(T.closeQD)}</div>
      <div class="foot"><button class="btn" id="cqNo">${esc(T.cancel)}</button><button class="btn danger" id="cqGo">${esc(T.closeYes)}</button></div></div>`);
    $('#cqNo').onclick = closeModal;
    $('#cqGo').onclick = () => window.odc.close();
  };
  $$('#nav a').forEach((a) => a.onclick = (e) => { e.preventDefault(); go(a.dataset.page); });
  window.odc.on('progress', onProgress);
  // closing the launcher: a window with what is being shut, it goes by itself when the database is down
  window.odc.on('quitting', (k) => {
    const order = ['game', 'server', 'db', 'done'];
    const at = order.indexOf(k);
    const row = (key, label) => { const i = order.indexOf(key); const st = at > i ? 'ok' : at === i ? 'run' : 'wait';
      return `<li class="${st}"><span class="qi" aria-hidden="true">${st === 'ok' ? '✓' : st === 'run' ? '' : '•'}</span>${esc(label)}</li>`; };
    modal(`<div class="dlg quitdlg" role="alertdialog" aria-live="polite" aria-label="${esc(T.quitTitle)}"><h2>${esc(k === 'done' ? T.quitDone : T.quitTitle)}</h2>
      <ul class="qlist">${row('game', T.quitGame)}${row('server', T.quitServer)}${row('db', T.quitDb)}</ul>
      <div class="muted small">${esc(T.quitNote)}</div></div>`);
  });
  window.odc.on('state', async (s) => { if (s) ST = s; else await refresh(); renderStatus(); if (page === 'home') renderHomeDynamic(); });
  window.odc.on('game', async (g) => {
    if (g.closing && !g.running) { bar = null; gameNote = { title: T.gameClosing, sub: T.gameClosingSub, frac: 1, color: '#FFB020' }; }
    else if (g.running) { bar = null; gameNote = { title: T.gameOpen, sub: T.gameOpenSub, frac: 1, color: '#3DDC84' }; }
    else if (g.failed) { bar = null; gameNote = { title: T.gameFail, sub: (g.why || '').split('\n').pop(), frac: 0, color: '#FF8A8A' }; if (g.why) toast(T.gameFail + ':\n' + g.why); }
    else { bar = null; gameNote = { title: '✓ ' + T.gameClosed, sub: T.gameClosedSub, frac: 1, color: '#3DDC84' }; }
    await refresh(); if (page === 'home') renderHomeDynamic();
  });

  // splash: real start-up work behind the bar
  const fill = $('#splashFill'), txt = $('#splashTxt');
  const sp = (f, i) => { fill.style.width = Math.round(f * 100) + '%'; txt.textContent = T.splash[i]; };
  ST = await window.odc.state();
  setLang(ST.cfg.lang || 'en');
  sp(0.15, 0);
  const t0 = Date.now();
  sp(0.4, 1);
  await new Promise((r) => setTimeout(r, 300));
  sp(0.65, 2);
  await Promise.race([Promise.all([checkUpdate(), loadCommits().catch(() => {})]), new Promise((r) => setTimeout(r, 6000))]);
  sp(1, 3);
  await new Promise((r) => setTimeout(r, Math.max(250, 1500 - (Date.now() - t0))));
  const s = $('#splash'); s.classList.add('fade'); setTimeout(() => s.classList.add('gone'), 550);
  startSlides();
  render();
  autoStart();
}
boot();
