'use strict';
/* The server notices (phone-style cards from the top), the game-style black tooltip of items, and the GM panel.
   Uses app.js's globals: T, t, esc, $, $$, call, toast, modal, closeModal, ICONS, loadIcons, errText, ST. */

// ---- notices: one card per server event, 10 s each, ✕ closes ----
const Notes = (() => {
  const LOOK = { rush: ['nkRush', 'RT', '#E07A00'], rushNow: ['nkRush', 'RT', '#E07A00'], realmatch: ['nkRm', 'RM', '#2F5FB0'],
    event: ['nkEvent', 'EV', '#3D8A3D'], eventsOn: ['nkEvent', 'EV', '#3D8A3D'], server: ['nkServer', '!', '#B03030'] };
  let box = null;
  const host = () => {
    if (box && document.body.contains(box)) return box;
    box = document.createElement('div');
    box.id = 'odcNotes'; box.setAttribute('aria-live', 'polite');
    document.getElementById('root').appendChild(box);
    return box;
  };
  function push(n) {
    const [k, glyph, bg] = LOOK[n.kind] || LOOK.server;
    const title = t('n_' + n.kind, n), body = t('n_' + n.kind + 'B', n);
    const el = document.createElement('div');
    el.className = 'note-card'; el.setAttribute('role', 'status');
    el.innerHTML = `<span class="ic" style="background:${bg}">${esc(glyph)}</span>
      <div class="tx"><div class="hd"><span>openDC · ${esc(T[k] || '')}</span><span>${esc(T.noteNow)}</span></div>
      <b>${esc(title)}</b>${body ? `<span>${esc(body)}</span>` : ''}</div>
      <button class="x" aria-label="${esc(T.noteClose)}">✕</button>`;
    const h = host();
    while (h.children.length >= 3) h.firstChild.remove();
    h.appendChild(el);
    const gone = () => { if (!el.parentNode) return; el.classList.add('out'); setTimeout(() => el.remove(), 380); };
    el.querySelector('.x').onclick = gone;
    setTimeout(gone, 10000);
  }
  return { push };
})();
if (window.odc && window.odc.on) window.odc.on('notice', (n) => Notes.push(n));

// ---- the black tooltip: any element with data-tip='{"name":..,"desc":..,"lines":[..]}' ----
const Tip = (() => {
  let el = null;
  const box = () => { if (!el) { el = document.createElement('div'); el.id = 'tipbox'; el.setAttribute('role', 'tooltip'); document.body.appendChild(el); } return el; };
  const hide = () => { if (el) el.style.visibility = 'hidden'; };
  document.addEventListener('mouseover', (e) => {
    const src = e.target.closest && e.target.closest('[data-tip]');
    if (!src) { hide(); return; }
    let d; try { d = JSON.parse(src.dataset.tip); } catch { return; }
    const b = box();
    const desc = String(d.desc || '').replace(/:::(.*?):::\n?/g, '[$1]\n').trim();
    b.innerHTML = `<div class="n">${esc(d.name || '')}</div>${desc ? `<div class="d">${esc(desc)}</div>` : ''}${(d.lines || []).filter(Boolean).map((x) => `<div>${esc(x)}</div>`).join('')}`;
    b.style.visibility = 'hidden'; b.style.left = '0px'; b.style.top = '0px';
    const r = src.getBoundingClientRect(), W = window.innerWidth, H = window.innerHeight;
    const bw = b.offsetWidth, bh = b.offsetHeight;
    let x = r.left + r.width / 2 - bw / 2, y = r.bottom + 6;
    if (y + bh > H - 6) y = r.top - bh - 6;
    x = Math.max(6, Math.min(W - bw - 6, x)); y = Math.max(6, y);
    b.style.left = x + 'px'; b.style.top = y + 'px'; b.style.visibility = 'visible';
  });
  document.addEventListener('dragstart', hide, true);
  document.addEventListener('mousedown', hide, true);
  return { attr: (d) => ` data-tip="${esc(JSON.stringify(d))}"`, hide };
})();

// ---- GM panel: give (cars, parts, usable, drift shop, Mito / G Coin) and the server commands ----
let CATALOG = null;
// the GM panel's car pictures drawn for the launcher (white car + the game's name logo); the others show the logo
const CAR_PNG = new Set(['pc_0070s', 'pc_0071s', 'pc_0072s', 'pc_0073s', 'pc_0088s', 'pc_0089s', 'pc_0144s', 'pc_0367s']);
const picOf = (kind, x, key) => (kind === 'cars' && CAR_PNG.has(x.model) ? `assets/cars/${x.model}.png` : ICONS.get(key));
async function openGmPanel(accId, chars, firstCid, back) {
  if (!CATALOG) { try { CATALOG = await call('catalog'); } catch { return; } }
  let tab = 'give', kind = 'cars', cid = firstCid || (chars[0] && chars[0].cid), sel = null, q = '', out = '', cmd = '', busy = false;
  let acc = null;
  const loadAcc = async () => { try { acc = await call('accGet', accId); } catch { /* toast */ } };
  await loadAcc();
  const runner = () => (acc ? acc.chars : chars).find((c) => c.cid === cid) || (acc ? acc.chars[0] : chars[0]);
  const LIMIT = 120;
  const keyOf = (x) => (kind === 'cars' ? 'logo:' + x.model : 'item:' + String(x.id).toLowerCase());
  const list = () => {
    const all = kind === 'money' ? [] : CATALOG[kind] || [];
    const s = q.trim().toLowerCase();
    const f = s ? all.filter((x) => (x.name || '').toLowerCase().includes(s) || String(x.id || x.model || '').toLowerCase().includes(s)) : all;
    return { shown: f.slice(0, LIMIT), total: f.length };
  };
  const srvOn = () => !!(ST && ST.server);
  const draw = () => {
    const r = runner();
    const L = list();
    const it = sel != null ? L.shown.find((x) => (x.id || x.model) === sel) || (CATALOG[kind] || []).find((x) => (x.id || x.model) === sel) : null;
    const kinds = [['cars', T.gmCars], ['parts', T.gmParts], ['use', T.gmUse], ['drift', T.gmDrift], ['money', T.gmMoney]];
    const tile = (x) => {
      const id = x.id || x.model, k = keyOf(x);
      const tip = kind === 'cars' ? { name: x.name, lines: [x.model, 'V' + (x.lvl || 1)] }
        : { name: x.name, lines: [x.id, x.grade ? `${x.grade} · ${t('tipLevel', { n: x.level })} · +${x.value}` : (x.kind || '')] };
      return `<button class="gm-tile${kind === 'cars' ? ' car' : ''}${sel === id ? ' on' : ''}" data-pick="${esc(id)}"${Tip.attr(tip)}>
        ${picOf(kind, x, k) ? `<img src="${picOf(kind, x, k)}" alt="">` : `<span class="ph">${esc((x.name || '?').slice(0, 2))}</span>`}
        <span class="nm">${esc(x.name)}</span>${kind === 'cars' ? `<span class="sub">${esc(x.model)}</span>` : ''}</button>`;
    };
    modal(`<div class="dlg gmp" role="dialog" aria-label="${esc(T.gmTitle)}">
      <div class="inl"><span class="badge gm" style="margin:0">GM</span><h2 class="grow">${esc(T.gmTitle)}</h2>
        <div class="gm-tabs" role="tablist"><button role="tab" aria-selected="${tab === 'give'}" class="${tab === 'give' ? 'on' : ''}" data-tab="give">${esc(T.gmGive)}</button><button role="tab" aria-selected="${tab === 'cmd'}" class="${tab === 'cmd' ? 'on' : ''}" data-tab="cmd">${esc(T.gmCmds)}</button></div>
        <button class="btn" id="gmClose">${esc(T.close)}</button></div>
      ${srvOn() ? '' : `<div class="gm-warn">${esc(T.gmNeedSrv)}</div>`}
      ${tab === 'give' ? `
      <div class="inl wrap"><span class="muted small">${esc(T.gmFor)}</span>${(acc ? acc.chars : chars).map((c) => `<button class="chip${c.cid === (r && r.cid) ? ' on' : ''}" data-cid="${c.cid}">${esc(c.name)} · ${c.level}</button>`).join('')}</div>
      <div class="gm-body">
        <div class="gm-left">
          <div class="inl wrap">${kinds.map(([k, n]) => `<button class="chip${kind === k ? ' on' : ''}" data-kind="${k}">${esc(n)}</button>`).join('')}
            ${kind !== 'money' ? `<input type="search" id="gmQ" placeholder="${esc(T.gmSearch)}" value="${esc(q)}" aria-label="${esc(T.gmSearch)}" style="margin-left:auto;width:220px">` : ''}</div>
          ${kind === 'money' ? `<div class="gm-money">
            <label class="field">${esc(T.gmMito)} (${esc(r ? r.name : '')})<div class="inl"><input type="number" id="gmMito" value="${r ? r.mito : 0}" min="0"><button class="btn sm" id="gmMitoSet">${esc(T.gmSet)}</button></div></label>
            <label class="field">${esc(T.gmCoin)} (${esc(accId)})<div class="inl"><input type="number" id="gmCoin" value="${acc ? acc.coin : 0}" min="0"><button class="btn sm" id="gmCoinSet">${esc(T.gmSet)}</button></div></label>
          </div>` : `<div class="gm-grid${kind === 'cars' ? ' cars' : ''}">${L.shown.map(tile).join('') || `<div class="muted small">${esc(T.none)}</div>`}</div>
          <div class="muted small">${esc(t('gmShown', { n: L.shown.length, t: L.total }))}${L.total > L.shown.length ? ' · ' + esc(T.gmMore) : ''}</div>`}
        </div>
        <aside class="gm-side">
          <div class="sec">${esc(T.gmGive)}</div>
          ${kind === 'money' ? '' : it ? `<div class="gm-sel">${picOf(kind, it, keyOf(it)) ? `<img src="${picOf(kind, it, keyOf(it))}" alt="">` : ''}<b>${esc(it.name)}</b><span class="muted small">${esc(it.id || it.model)}</span></div>
            ${kind === 'parts' || kind === 'use' ? `<label class="field">${esc(T.gmQty)}<input type="number" id="gmN" value="1" min="1" max="999"></label>` : ''}
            ${kind === 'drift' ? `<label class="field">${esc(T.gmDays)}<input type="number" id="gmN" value="0" min="0" max="3650"></label>` : ''}
            <button class="btn pri" id="gmGo" ${busy || !srvOn() || !r ? 'disabled' : ''}>${esc(T.gmGiveBtn)} → ${esc(r ? r.name : '')}</button>` : `<span class="muted small">${esc(T.gmPick)}</span>`}
          ${kind === 'cars' || kind === 'drift' ? `<div class="muted small" style="line-height:1.5">${esc(T.gmOnline)}</div>` : ''}
          <div class="grow"></div>
          <div class="gm-out" aria-live="polite">${out}</div>
        </aside>
      </div>` : `
      <div class="muted small">${esc(T.gmCmdNote)}</div>
      <div class="gm-cmds">${T.gmCmdList.map(([g, rows]) => `<section><div class="sec">${esc(g)}</div>${rows.map(([c, d]) => `<button class="gm-cmd" data-cmd="${esc(c)}"><code>${esc(c)}</code><span>${esc(d)}</span></button>`).join('')}</section>`).join('')}</div>
      <div class="inl"><label class="grow field" style="flex-direction:row;align-items:center;gap:8px">${esc(T.gmCmdLbl)}<input type="text" id="gmCmd" value="${esc(cmd)}" spellcheck="false" style="flex-grow:1;font-family:monospace"></label><button class="btn pri" id="gmRun" ${busy || !srvOn() ? 'disabled' : ''}>${esc(T.gmRun)}</button></div>
      <div class="sec">${esc(T.gmOut)}</div><pre class="gm-pre">${out}</pre>`}
    </div>`);
    $('#gmClose').onclick = () => { closeModal(); if (back) back(); };
    $$('[data-tab]').forEach((b) => b.onclick = () => { tab = b.dataset.tab; out = ''; draw(); });
    $$('[data-cid]').forEach((b) => b.onclick = () => { cid = Number(b.dataset.cid); draw(); });
    $$('[data-kind]').forEach((b) => b.onclick = () => { kind = b.dataset.kind; sel = null; q = ''; out = ''; draw(); fetch(); });
    $$('[data-pick]').forEach((b) => b.onclick = () => { sel = b.dataset.pick; draw(); });
    const qi = $('#gmQ');
    if (qi) { qi.oninput = () => { q = qi.value; clearTimeout(qi._t); qi._t = setTimeout(() => { const pos = qi.selectionStart; draw(); fetch(); const n = $('#gmQ'); if (n) { n.focus(); n.setSelectionRange(pos, pos); } }, 220); }; }
    const say = (ok, text) => { out = `<span class="${ok ? 'ok' : 'bad'}">${esc(text)}</span>`; };
    const run = async (line, after) => {
      busy = true; draw();
      try { const r2 = await call('gmRun', line); say(true, r2 || T.gmSent); if (after) await after(); } catch (e) { say(false, errText(e)); }
      busy = false; draw();
    };
    if ($('#gmGo')) $('#gmGo').onclick = () => {
      const n = Math.max(0, Number(($('#gmN') || {}).value) || (kind === 'drift' ? 0 : 1));
      const who = r.name;
      if (kind === 'cars') return run(`car ${who} ${it.model}`);
      if (kind === 'drift') return run(`drift ${who} ${it.id} ${n}`);
      return run(`item ${who} ${it.id} ${Math.max(1, n)}`);
    };
    if ($('#gmMitoSet')) $('#gmMitoSet').onclick = async () => {
      try { await call('charMito', accId, r.cid, Number($('#gmMito').value) || 0); say(true, T.saved); await loadAcc(); } catch (e) { say(false, errText(e)); }
      draw();
    };
    if ($('#gmCoinSet')) $('#gmCoinSet').onclick = async () => {
      try { await call('accCoin', accId, Number($('#gmCoin').value) || 0); say(true, T.saved); await loadAcc(); } catch (e) { say(false, errText(e)); }
      draw();
    };
    $$('[data-cmd]').forEach((b) => b.onclick = () => { cmd = b.dataset.cmd.replace(/\b(NOME|NAME|ИМЯ)\b/, runner() ? runner().name : '$&').replace(/\b(CONTA|ACCOUNT|АККАУНТ)\b/, accId); draw(); const c = $('#gmCmd'); if (c) { c.focus(); c.select(); } });
    if ($('#gmCmd')) $('#gmCmd').onkeydown = (e) => { if (e.key === 'Enter') $('#gmRun').click(); };
    if ($('#gmRun')) $('#gmRun').onclick = () => { cmd = $('#gmCmd').value.trim(); if (cmd) run(cmd); };
  };
  const fetch = () => {
    if (tab !== 'give' || kind === 'money') return;
    loadIcons(list().shown.map(keyOf)).then((ch) => { if (ch && document.querySelector('.dlg.gmp')) draw(); });
  };
  draw(); fetch();
}

// ---- the Auction House (helper/odc_auc.py on the server's tables) ----
async function openAuction(accId, chars, firstCid, back) {
  let kind = 'item', type = 0, lo = '', hi = '', q = '', usable = false, page = 0, sel = null, cid = firstCid || (chars[0] && chars[0].cid), data = null, msg = '';
  const PER = 14;
  const errOf = (e) => { const m = ((e && e.message) || '').replace(/^Error invoking remote method '\w+': (Error: )?/, ''); return (T.err && T.err[m]) || errText(e); };
  const load = async () => { try { data = await window.odc.auc('list', accId, cid, { kind }); } catch (e) { data = { list: [], rules: {}, mito: 0, level: 0 }; msg = `<span class="bad">${esc(errOf(e))}</span>`; } };
  await load();
  const fits = (x) => {
    if (kind === 'item' && type) {
      const t2 = x.type;
      const ok = [null, t2 === 0, t2 === 1, t2 === 2, t2 === 3, t2 >= 6 && t2 <= 10, t2 === 11, t2 === 12, t2 === 5][type];
      if (!ok) return false;
    }
    if (kind === 'car' && type && x.grade !== type) return false;
    if (lo && x.level < Number(lo)) return false;
    if (hi && x.level > Number(hi)) return false;
    if (usable && kind === 'item' && x.level > data.level) return false;
    const s = q.trim().toLowerCase();
    return !s || x.name.toLowerCase().includes(s) || x.seller.toLowerCase().includes(s) || String(x.id).toLowerCase().includes(s);
  };
  const draw = () => {
    const list = data.list.filter(fits);
    const pages = Math.max(1, Math.ceil(list.length / PER));
    if (page >= pages) page = pages - 1;
    const shown = list.slice(page * PER, page * PER + PER);
    const it = data.list.find((x) => x.serial === sel);
    const head = kind === 'item' ? T.aucH : kind === 'car' ? T.aucHCar : T.aucHDrift;
    const who = chars.find((c) => c.cid === cid);
    const state = !it ? '' : it.cid === cid ? T.aucOwn : it.price > data.mito ? T.aucNoMoney : T.aucCanBuy;
    const types = kind === 'item' ? T.aucTypesItem : kind === 'car' ? T.aucTypesCar : null;
    const row = (x) => `<tr class="${x.serial === sel ? 'on' : ''}" data-ser="${x.serial}"${Tip.attr({ name: x.name, desc: x.desc, lines: [x.grade ? `${x.grade} · +${x.value || ''}` : '', x.catName || '', x.id] })}>
      <td>${kind === 'drift' ? esc(x.catName) : kind === 'car' ? 'V' + x.grade : x.level}</td>
      <td><span class="nmw">${ICONS.get(x.icon) ? `<img src="${ICONS.get(x.icon)}" alt="">` : ''}${esc(x.name)}${x.grade && kind === 'item' ? ` (${esc(x.grade)})` : ''}</span></td>
      <td>${Number(x.price).toLocaleString()}</td><td>${kind === 'item' ? x.count : x.left}</td><td>${esc(x.seller)}</td>
      <td>${esc(t('aucHist', { r: x.hist[0], b: x.hist[1], s: x.hist[2] }))}</td></tr>`;
    modal(`<div class="dlg auc" role="dialog" aria-label="${esc(T.aucTitle)}">
      <div class="ihead"><span class="ring"></span><h2>${esc(T.aucTitle)}</h2><span class="who">${esc(who ? who.name : '')} · ${esc(T.level).toLowerCase()} ${data.level}</span><span class="grow"></span>
        <label class="muted small">${esc(T.aucBuyer)} <select id="aWho">${chars.map((c) => `<option value="${c.cid}" ${c.cid === cid ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select></label>
        <button class="ix" id="aClose" aria-label="${esc(T.close)}">✕</button></div>
      <div class="abody">
        <div class="abar"><div class="radios" role="radiogroup">${['item', 'car', 'drift'].map((k, i) => `<button role="radio" aria-checked="${kind === k}" class="${kind === k ? 'on' : ''}" data-kind="${k}"><span></span>${esc(T.aucKinds[i])}</button>`).join('')}</div>
          <span class="grow"></span>${types ? `<select id="aType">${types.map((n, i) => `<option value="${i}" ${type === i ? 'selected' : ''}>${esc(n)}</option>`).join('')}</select>` : ''}
          <button class="ybtn" id="aRef">⟳ ${esc(T.aucRefresh)}</button></div>
        <div class="afil"><label>${esc(T.aucLvl)} <input type="number" id="aLo" value="${esc(lo)}" placeholder="1"></label><span>–</span><input type="number" id="aHi" value="${esc(hi)}" placeholder="200" aria-label="${esc(T.aucLvl)}">
          <label>${esc(T.aucWho)} <input type="text" id="aQ" value="${esc(q)}"></label><button class="gbtn" id="aGo">${esc(T.aucSearch)}</button>
          ${kind === 'item' ? `<label class="chk"><input type="checkbox" id="aUse" ${usable ? 'checked' : ''}>${esc(T.aucUsable)}</label>` : ''}</div>
        <div class="atab">${kind === 'drift' && !data.rules.drift ? `<div class="soonbox">${esc(T.aucDriftOff)}</div>` : `
          <table><thead><tr>${head.map((h) => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${shown.map(row).join('')}${Array.from({ length: PER - shown.length }, () => '<tr class="e"><td colspan="6"></td></tr>').join('')}</tbody></table>
          ${list.length ? '' : `<div class="aempty">${esc(T.aucEmpty)}</div>`}`}
          <div class="apg"><button class="pg" id="aPrev" ${page ? '' : 'disabled'} aria-label="${esc(T.prevPage)}">❮</button><span>${page + 1} / ${pages}</span><button class="pg" id="aNext" ${page < pages - 1 ? '' : 'disabled'} aria-label="${esc(T.nextPage)}">❯</button></div></div>
        <div class="afoot"><div class="mitob"><span>${esc(T.myMito)}</span><b>${Number(data.mito).toLocaleString()}</b><span>M</span></div>
          <span class="muted">${esc(T.aucPrice)}</span><b class="ap">${it ? Number(it.price).toLocaleString() : '—'}</b>
          <span class="${it && it.cid !== cid && it.price <= data.mito ? 'ok' : 'bad'} small">${esc(state)}</span><span class="grow small">${msg}</span>
          <button class="ybtn big" id="aBuy" ${it && it.cid !== cid && it.price <= data.mito ? '' : 'disabled'}>${esc(T.aucBuy)}</button></div>
      </div></div>`);
    $('#aClose').onclick = () => { closeModal(); if (back) back(); };
    $('#aWho').onchange = async (e) => { cid = Number(e.target.value); sel = null; msg = ''; await load(); draw(); };
    $$('[data-kind]').forEach((b) => b.onclick = async () => { kind = b.dataset.kind; type = 0; sel = null; page = 0; msg = ''; await load(); draw(); fetch(); });
    if ($('#aType')) $('#aType').onchange = (e) => { type = Number(e.target.value); page = 0; draw(); };
    $('#aRef').onclick = async () => { msg = ''; await load(); draw(); fetch(); };
    const filt = () => { lo = $('#aLo').value; hi = $('#aHi').value; q = $('#aQ').value; page = 0; draw(); };
    $('#aGo').onclick = filt; $('#aQ').onkeydown = (e) => { if (e.key === 'Enter') filt(); };
    if ($('#aUse')) $('#aUse').onchange = (e) => { usable = e.target.checked; draw(); };
    $('#aPrev').onclick = () => { page--; draw(); }; $('#aNext').onclick = () => { page++; draw(); };
    $$('[data-ser]').forEach((r) => r.onclick = () => { sel = Number(r.dataset.ser); draw(); });
    $('#aBuy').onclick = async () => {
      if (!it || !confirm(t('aucBuyQ', { n: it.name, p: Number(it.price).toLocaleString() }))) return;
      try { await window.odc.auc('buy', accId, cid, { kind, serial: it.serial }); msg = `<span class="ok">${esc(t('aucBought', { n: it.name }))}</span>`; sel = null; } catch (e) { msg = `<span class="bad">${esc(errOf(e))}</span>`; }
      await load(); draw(); fetch();
    };
  };
  const fetch = () => loadIcons(data.list.map((x) => x.icon)).then((ch) => { if (ch && document.querySelector('.dlg.auc')) draw(); });
  draw(); fetch();
}

// ---- the More menu (placeholder until each window is in) ----
async function openMore(accId, chars, cid, back, gm) {
  const items = [['community', T.moreCommunity], ['ranking', T.moreRanking], ['coupon', T.moreCoupon], ['license', T.moreLicense], ['skill', T.moreSkill], ['shop', T.moreShop], ['gotcha', T.moreGotcha]];
  modal(`<div class="dlg more" role="dialog" aria-label="${esc(T.moreTitle)}">
    <div class="ihead"><span class="ring"></span><h2>${esc(T.moreTitle)}</h2><span class="grow"></span><button class="ix" id="mClose" aria-label="${esc(T.close)}">✕</button></div>
    <div class="mlist">${items.map(([k, n]) => `<button class="mbtn" data-m="${k}">${esc(n)}</button>`).join('')}</div></div>`);
  $('#mClose').onclick = () => { closeModal(); if (back) back(); };
  $$('[data-m]').forEach((b) => b.onclick = () => openMoreWindow(b.dataset.m, accId, chars, cid, () => openMore(accId, chars, cid, back, gm), gm));
}

// ---- the More windows: one frame (title, character chips, Mito / CC, ← Menu, ✕) around each page ----
const MORE_PAGES = {};
async function openMoreWindow(page, accId, chars, cid, back, gm) {
  const title = { community: T.moreCommunity, ranking: T.moreRanking, coupon: T.moreCoupon, license: T.moreLicense, skill: T.moreSkill, shop: T.moreShop, gotcha: T.moreGotcha }[page];
  const ctx = { accId, chars, cid: cid || (chars[0] && chars[0].cid), back, gm: !!gm, msg: '' };
  const frame = (body, sub) => {
    if (ctx.cleanup) { try { ctx.cleanup(); } catch { /* gone */ } ctx.cleanup = null; }
    const c = ctx.chars.find((x) => x.cid === ctx.cid) || {};
    modal(`<div class="dlg mwin" role="dialog" aria-label="${esc(title)}">
      <div class="mhead"><h2>${esc(title)}</h2><span class="sub">${esc(sub || '')}</span><span class="grow"></span>
        <span class="muted small">${esc(T.moreRunner)}</span>${ctx.chars.map((x) => `<button class="mchip${x.cid === ctx.cid ? ' on' : ''}" data-runner="${x.cid}">${esc(x.name)}</button>`).join('')}
        <span class="small muted">Mito <b style="color:#7FB7FF">${Number(ctx.mito != null ? ctx.mito : c.mito || 0).toLocaleString()}</b> · CC <b style="color:#FFC21A">${Number(ctx.cc || 0).toLocaleString()}</b></span>
        <button class="btn sm" id="mMenu">← ${esc(T.moreBack)}</button><button class="ix" id="mX" aria-label="${esc(T.close)}">✕</button></div>
      <div class="mbody">${body}</div></div>`);
    const leave = () => { if (ctx.cleanup) { try { ctx.cleanup(); } catch { /* gone */ } ctx.cleanup = null; } };
    $('#mMenu').onclick = () => { leave(); back(); };
    $('#mX').onclick = () => { leave(); closeModal(); };
    $$('[data-runner]').forEach((b) => b.onclick = () => { ctx.cid = Number(b.dataset.runner); ctx.msg = ''; ctx.won = null; ctx.mid = null; ctx.reload = true; run(); });
  };
  ctx.frame = frame;
  const run = () => (MORE_PAGES[page] ? MORE_PAGES[page](ctx) : frame(`<div class="soonbox big"><b>${esc(title)}</b><span>${esc(T.moreBuilding)}</span></div>`));
  ctx.redraw = run;
  run();
}
