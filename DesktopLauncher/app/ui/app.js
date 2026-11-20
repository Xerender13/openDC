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
  <div id="playBox"><button id="playBtn"></button></div>
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
  else if (busy === 'start' || busy === 'update') label = T.starting;
  else if (ST.launching) label = T.opening;
  else if (ST.game) label = T.inGame;
  else if (ST.installed) { label = T.play; ic = icon.play; } else { label = T.dl; ic = icon.dl; }
  btn.innerHTML = ic + esc(label);
  btn.disabled = !!busy || ST.game || ST.launching || noProton();
  btn.classList.toggle('busy', !!busy || ST.game || ST.launching || noProton());
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
  if (!b && ready && gameNote && gameNote.color !== '#FF8A8A') b = Object.assign({}, gameNote, { frac: 1, color: '#3DDC84' });
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
        <td style="text-align:right;white-space:nowrap"><button class="linkbtn" data-edit="${esc(a.id)}">${esc(T.edit)}</button> &nbsp; <button class="linkbtn" data-exp="${esc(a.id)}">${esc(T.expAcc)}</button> &nbsp; <button class="linkbtn red" data-del="${esc(a.id)}">${esc(T.del)}</button></td></tr>`).join('')}
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
  let acc, sel = null, ch = null, tab = 'cars';
  const load = async () => { acc = await call('accGet', id); if (acc.chars.length && !acc.chars.find((c) => c.cid === sel)) sel = acc.chars[0].cid; if (!acc.chars.length) sel = null; };
  const loadChar = async () => { ch = sel ? await call('charGet', id, sel) : null; };
  try { await load(); await loadChar(); } catch { return; }
  const saved = (el) => { el.textContent = T.saved; setTimeout(() => { el.textContent = ''; }, 2000); };
  const draw = () => {
    const gmFull = acc.gm;
    const c = acc.chars.find((x) => x.cid === sel);
    modal(`<div class="dlg wide" role="dialog" aria-label="${esc(t('editTitle', { id }))}">
      <div class="inl"><h2 class="grow">${esc(t('editTitle', { id }))}${acc.gm ? `<span class="badge gm">${esc(T.gm)}</span>` : ''}</h2><button class="btn" id="eClose">${esc(T.close)}</button></div>
      <div class="cols">
        <div class="colL">
          <div class="sec">${esc(T.accSec)}</div>
          <div class="field">${esc(T.newPw)}<div class="inl"><input type="password" id="ePw" maxlength="63"><button class="btn sm" id="ePwGo">${esc(T.setPw)}</button></div><span class="ok" id="ePwOk"></span></div>
          <label class="inl" style="font-size:13px"><input type="checkbox" id="eGm" ${acc.gm ? 'checked' : ''}>${esc(T.gmOn)}</label>
          <label class="inl" style="font-size:13px"><input type="checkbox" id="eBan" ${acc.banned ? 'checked' : ''}>${esc(T.banOn)}</label>
          ${gmFull ? `<div class="field">${esc(T.coin)}<div class="inl"><input type="number" id="eCoin" min="0" value="${acc.coin}"><button class="btn sm" id="eCoinGo">${esc(T.save)}</button></div><span class="ok" id="eCoinOk"></span></div>` : ''}
          <div class="sec">${esc(T.runners)}</div>
          ${acc.chars.length ? `<div class="chips">${acc.chars.map((x) => `<button class="chip${x.cid === sel ? ' on' : ''}" data-cid="${x.cid}">${esc(x.name)} · ${x.level}</button>`).join('')}</div>` : `<div class="muted small">${esc(T.noRunners)}</div>`}
        </div>
        <div class="colR">${c && ch ? `
          <div class="inl"><label class="field grow">${esc(T.name)}<div class="inl"><input type="text" id="cName" value="${esc(c.name)}" maxlength="16"><button class="btn sm" id="cRen">${esc(T.rename)}</button></div></label></div>
          ${gmFull ? `<div class="inl"><label class="field">${esc(T.level)}<div class="inl"><input type="number" id="cLv" min="1" max="200" value="${c.level}" style="width:90px"><button class="btn sm" id="cLvGo">${esc(T.save)}</button></div></label>
            <label class="field">${esc(T.mito)}<div class="inl"><input type="number" id="cMito" min="0" value="${c.mito}" style="width:140px"><button class="btn sm" id="cMitoGo">${esc(T.save)}</button></div></label><span class="ok" id="cOk"></span></div>` : ''}
          <div class="tabs"><button class="${tab === 'cars' ? 'on' : ''}" data-tab="cars">${esc(T.cars)} (${ch.cars.length})</button><button class="${tab === 'inv' ? 'on' : ''}" data-tab="inv">${esc(T.inv)} (${ch.items.length})</button></div>
          <div class="mini">${tab === 'cars'
            ? `<table><tbody>${ch.cars.map((x) => `<tr><td>${esc(x.name)}</td><td class="muted">#${x.type}</td><td class="muted">${esc(T.grade)} ${x.grade}</td></tr>`).join('') || `<tr><td class="muted">${T.none}</td></tr>`}</tbody></table>`
            : `<table><tbody>${ch.items.map((x) => `<tr><td class="muted">${esc(T.slot)} ${x.slot}</td><td>${esc(x.item)}</td><td>×${x.count}</td></tr>`).join('') || `<tr><td class="muted">${T.none}</td></tr>`}</tbody></table>`}</div>
          ${gmFull ? `<div class="inl"><input type="text" id="gCar" placeholder="${esc(T.carName)}"><button class="btn sm" id="gCarGo">${esc(T.giveCar)}</button></div>
            <div class="inl"><input type="text" id="gItem" placeholder="${esc(T.itemId)}"><input type="number" id="gQty" value="1" min="1" style="width:70px" aria-label="${esc(T.qty)}"><button class="btn sm" id="gItemGo">${esc(T.giveItem)}</button></div>` : ''}
          <div class="inl"><span class="muted small grow">${esc(T.offline)}</span><button class="btn sm" id="cExp">${esc(T.expChar)}</button><button class="btn danger sm" id="cDel">${esc(T.delRunner)}</button></div>` : `<div class="empty">${esc(T.noRunners)}</div>`}
        </div>
      </div></div>`);
    $('#eClose').onclick = () => { closeModal(); render(); };
    $('#ePwGo').onclick = async () => { try { await call('accPassword', id, $('#ePw').value); $('#ePw').value = ''; saved($('#ePwOk')); } catch { /* toast */ } };
    $('#eGm').onchange = async (e) => { try { await call('accGm', id, e.target.checked); await load(); draw(); } catch { /* toast */ } };
    $('#eBan').onchange = async (e) => { try { await call('accBan', id, e.target.checked); } catch { /* toast */ } };
    if ($('#eCoinGo')) $('#eCoinGo').onclick = async () => { try { await call('accCoin', id, Number($('#eCoin').value)); saved($('#eCoinOk')); } catch { /* toast */ } };
    $$('[data-cid]').forEach((b) => b.onclick = async () => { sel = Number(b.dataset.cid); await loadChar(); draw(); });
    $$('[data-tab]').forEach((b) => b.onclick = () => { tab = b.dataset.tab; draw(); });
    if (!c || !ch) return;
    $('#cRen').onclick = async () => { try { await call('charRename', id, sel, $('#cName').value.trim()); await load(); await loadChar(); draw(); } catch { /* toast */ } };
    if ($('#cLvGo')) $('#cLvGo').onclick = async () => { try { await call('charLevel', c.name, Number($('#cLv').value)); await load(); draw(); } catch { /* toast */ } };
    if ($('#cMitoGo')) $('#cMitoGo').onclick = async () => { try { await call('charMito', id, sel, Number($('#cMito').value)); saved($('#cOk')); await load(); } catch { /* toast */ } };
    if ($('#gCarGo')) $('#gCarGo').onclick = async () => { try { const r = await call('giveCar', c.name, $('#gCar').value.trim()); toast(r || '✓', true); await loadChar(); draw(); } catch { /* toast */ } };
    if ($('#gItemGo')) $('#gItemGo').onclick = async () => { try { const r = await call('giveItem', c.name, $('#gItem').value.trim(), Number($('#gQty').value) || 1); toast(r || '✓', true); await loadChar(); draw(); } catch { /* toast */ } };
    $('#cExp').onclick = () => doExport(id, sel, c.name);
    $('#cDel').onclick = async () => {
      if (!confirm(t('delRunnerQ', { n: c.name }))) return;
      try { await call('charDelete', id, sel); await load(); await loadChar(); draw(); } catch { /* toast */ }
    };
  };
  draw();
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
function tabServer(el) {
  const c = ST.cfg;
  el.innerHTML = `<div class="grid2">
    <section>
      <div class="set"><div class="l"><b>${esc(T.where)}</b><span class="muted small">${esc(T.whereD)}</span></div><div class="seg"><button id="mLocal" class="${c.serverMode !== 'remote' ? 'on' : ''}">${esc(T.local)}</button><button id="mRemote" class="${c.serverMode === 'remote' ? 'on' : ''}">${esc(T.other)}</button></div></div>
      <div class="set"><div class="l"><b>${esc(T.addr)}</b><span class="muted small">${esc(T.addrD)}</span></div><input type="text" id="rIp" value="${esc(c.remoteIp)}" placeholder="192.168.0.15" style="width:150px" ${c.serverMode === 'remote' ? '' : 'disabled'}><button class="btn sm" id="rTest" ${c.serverMode === 'remote' ? '' : 'disabled'}>${esc(T.test)}</button></div>
      <div class="set"><div class="l"><span id="rRes" class="muted small"></span></div></div>
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
  $('#mLocal').onclick = async () => { await save({ serverMode: 'local' }); render(); };
  $('#mRemote').onclick = async () => { await save({ serverMode: 'remote' }); render(); };
  $('#rIp').onchange = (e) => save({ remoteIp: e.target.value.trim() });
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
async function tabVideo(el) {
  el.classList.add('vscroll');   // every video option, scrolling; Save stays at the bottom
  if (!ST.installed) { el.innerHTML = `<div class="empty">${esc(T.vNo)}</div>`; return; }
  let v;
  try { v = await call('video'); } catch { return; }
  if (!v.exists) { el.innerHTML = `<div class="empty">${esc(T.vNo)}</div>`; return; }
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
  el.innerHTML = `<div class="info"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#C08A55" stroke-width="2" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></svg><span class="grow">${esc(T.vLink)}</span><button class="btn sm" id="vRest">${esc(T.vRestore)}</button></div>
    ${ST.os.linux ? `<div class="info"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#C08A55" stroke-width="2" aria-hidden="true"><path d="M4 17l6-6-6-6M12 19h8"/></svg><span class="grow">${esc(T.pxRow)} <b id="pxCur" style="color:#E8ECF2"></b></span><button class="btn sm" id="pxOpen">${esc(T.pxBtn)}</button></div>` : ''}
    <div class="grid2"><section>
      ${row(T.res, 'goption.ini · ScreenWidth, ScreenHeight', sel('vRes', resList.map((r) => [r, resLabel(r, v.fullscreen)]), resKey), scr ? t('resD', { w: scr.w, h: scr.h }) : '')}
      ${row(T.mode, 'goption.ini · Fullscreen + launcher display', sel('vMode', [[0, T.win], [1, T.full]], v.fullscreen ? 1 : 0), ST.os.linux ? T.modeD : '')}
      ${row(T.hud, 'goption.ini · MainUIType', sel('vHud', [[0, T.hud0], [1, T.hud1]], v.hud))}
      ${row(T.aa, 'goption.ini · MultiSampling', sel('vAa', [[0, T.off], [2, '2×'], [4, '4×']], v.msaa))}
      ${row(T.preset, 'goption.ini · VideoGradeSet', sel('vPre', [[-1, T.custom], ...lv(1)], v.preset), T.presetD)}
    </section><section>
      ${row(T.shadows, 'goption.ini · ShadowQuality', sel('vSh', [[0, T.off], ...lv(1)], v.shadow))}
      ${row(T.carD, 'goption.ini · CarDetail', sel('vCar', lv(1), v.car))}
      ${row(T.env, 'goption.ini · EnvironmentDetail', sel('vEnv', lv(1), v.env))}
      ${row(T.fx, 'goption.ini · EffectDetail', sel('vFx', lv(1), v.fx))}
      ${row(T.blur, 'goption.ini · MotionBlur, MotionBlurType', sel('vBlur', [[0, T.blurN], [1, T.blurM]], Math.min(1, v.blur)), T.blurD)}
      ${row(T.range, 'goption.ini · VisibleRange', sel('vRange', [1, 2, 3, 4, 5].map((n) => [n, n === 1 ? `1 · ${T.near}` : n === 5 ? `5 · ${T.far}` : String(n)]), v.range))}
      <div class="checks"><label><input type="checkbox" id="vFog" ${v.fog ? 'checked' : ''}>${esc(T.fog)}</label><label><input type="checkbox" id="vOut" ${v.outline ? 'checked' : ''}>${esc(T.outline)}</label></div>
    </section></div>
    <div class="foot vfoot"><span class="ok" id="vOk"></span><button class="btn pri" id="vSave">${esc(T.save)}</button></div>`;
  if ($('#pxOpen')) {
    $('#pxOpen').onclick = openProton;
    window.odc.protonState().then((x) => { const el = $('#pxCur'); if (el) el.textContent = (x.list.find((p) => p.using) || {}).name || T.pxNone; }).catch(() => {});
  }
  // the "doesn't fit in a window" marks follow the screen mode picked
  $('#vMode').onchange = () => { const full = $('#vMode').value === '1'; $$('#vRes option').forEach((o) => { o.textContent = resLabel(o.value, full); }); };
  $('#vRest').onclick = async () => { try { await call('videoRestore'); render(); } catch { /* toast */ } };
  $('#vSave').onclick = async () => {
    const [w, h] = wh($('#vRes').value);
    const nv = { width: w, height: h, fullscreen: $('#vMode').value === '1', hud: +$('#vHud').value, msaa: +$('#vAa').value, preset: +$('#vPre').value,
      shadow: +$('#vSh').value, car: +$('#vCar').value, env: +$('#vEnv').value, fx: +$('#vFx').value, range: +$('#vRange').value,
      blur: +$('#vBlur').value, fog: $('#vFog').checked, outline: $('#vOut').checked };
    try { await call('videoSave', nv); $('#vOk').textContent = T.saved; setTimeout(() => { const o = $('#vOk'); if (o) o.textContent = ''; }, 2000); } catch { /* toast */ }
  };
}
function tabFolders(el) {
  el.innerHTML = `<section>
    <div class="set"><div class="l"><b>${esc(T.root)}</b><span class="muted small">${esc(T.rootD)}</span><div class="pathrow"><code>${esc(ST.cfg.root)}</code></div></div><button class="btn sm" id="fRoot">${esc(T.rootChange)}</button></div>
    ${[['client', T.openGame], ['emu', T.openSrv], ['logs', T.openLogs], ['backups', T.openBk]].map(([k, n]) => `<div class="set"><div class="l"><b>${esc(n)}</b></div><button class="btn sm" data-open="${k}">${esc(T.open)}</button></div>`).join('')}
  </section>`;
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
    <div class="empty"><b>${esc(T.modsNone)}</b><span>${esc(T.modsNoneD)}</span></div>
    <div class="inl"><button class="btn" id="mOpen">${esc(T.modsOpen)}</button></div></div>`;
  $('#mOpen').onclick = () => call('openPath', 'mods');
}

// ---------- modal ----------
function modal(html) { const m = $('#modal'); m.innerHTML = html; m.hidden = false; }
function closeModal() { const m = $('#modal'); m.hidden = true; m.innerHTML = ''; }
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('#modal').hidden) closeModal(); });

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
  window.odc.on('state', async (s) => { if (s) ST = s; else await refresh(); renderStatus(); if (page === 'home') renderHomeDynamic(); });
  window.odc.on('game', async (g) => {
    if (g.running) { bar = null; gameNote = { title: T.gameOpen, sub: T.gameOpenSub, frac: 1, color: '#3DDC84' }; }
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
