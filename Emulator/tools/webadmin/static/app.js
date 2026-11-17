'use strict';
/* openDC web workshop: plain JavaScript, no framework and no CDN.
   The token from the printed URL is kept in sessionStorage and sent as X-Token. */

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

/* ------------------------------------------------------------------ token */
let token = null;
try {
  const params = new URLSearchParams(window.location.search);
  token = params.get('token') || sessionStorage.getItem('webadminToken');
  if (params.has('token')) {
    sessionStorage.setItem('webadminToken', params.get('token'));
    params.delete('token');
    const query = params.toString();
    window.history.replaceState(null, '', window.location.pathname + (query ? '?' + query : ''));
  }
} catch (error) {
  token = null;
}

/* ---------------------------------------------------------------- helpers */
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else node.setAttribute(key, value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function clear(node) {
  node.replaceChildren();
}

function debounce(fn, ms) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

function fmt(value) {
  const text = String(value === null || value === undefined ? '' : value).trim();
  if (text === '') return '–';
  if (/^[+-]?\d+$/.test(text) && !/^[+-]?0\d/.test(text)) {
    const number = Number(text);
    if (Number.isSafeInteger(number)) return number.toLocaleString();
  }
  if (/^[+-]?\d+\.\d+$/.test(text)) {
    return Number(text).toLocaleString(undefined, { maximumFractionDigits: 4 });
  }
  return text;
}

function enc(value) {
  return encodeURIComponent(String(value === null || value === undefined ? '' : value));
}

function say(text, kind = 'info') {
  const message = $('#msg');
  message.textContent = text || '';
  message.className = 'msg ' + kind;
  clearTimeout(say.timer);
  if (text) say.timer = setTimeout(() => { message.textContent = ''; }, 9000);
}

function markRestart() {
  $('#restart-note').classList.remove('hidden');
}

/* -------------------------------------------------------------------- API */
async function api(path, options = {}) {
  const method = options.method || 'GET';
  const headers = { 'X-Token': token };
  let body;
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(options.body);
  }
  const response = await fetch(path, { method, headers, body });
  const type = response.headers.get('content-type') || '';
  if (type.includes('application/json')) {
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 403) throw new Error(data.error || 'The token is missing or stale; open the URL printed by the tool.');
      throw new Error(data.error || ('HTTP ' + response.status));
    }
    return data;
  }
  if (!response.ok) throw new Error((await response.text()) || ('HTTP ' + response.status));
  return response;
}

/* ------------------------------------------------------------------ icons */
const iconCache = new Map();
function iconImage(id, key, className = 'icon') {
  const image = el('img', { class: className, alt: '', loading: 'lazy' });
  const cacheKey = String(id || '') + '|' + String(key || '');
  if (iconCache.has(cacheKey)) {
    image.src = iconCache.get(cacheKey);
    return image;
  }
  fetch('/api/icon?id=' + enc(id) + '&key=' + enc(key), { headers: { 'X-Token': token } })
    .then(response => (response.ok ? response.blob() : null))
    .then(blob => {
      if (!blob) { image.classList.add('noicon'); return; }
      const url = URL.createObjectURL(blob);
      iconCache.set(cacheKey, url);
      image.src = url;
    })
    .catch(() => image.classList.add('noicon'));
  return image;
}

function fillSelect(select, options, allLabel, current) {
  clear(select);
  if (allLabel !== null) select.append(el('option', { value: '', text: allLabel }));
  for (const option of options) select.append(el('option', { value: option.value, text: option.label }));
  if (current !== undefined && current !== null) select.value = current;
  return select;
}

/* ----------------------------------------------------------- detail editor */
function makeEditor(host, detail, options = {}) {
  clear(host);
  const head = el('div', { class: 'detail-head' });
  if (options.icon) head.append(iconImage(options.icon.id, options.icon.key, 'bigicon'));
  head.append(el('div', { class: 'detail-title' },
    el('h2', { text: detail.title || detail.file }),
    el('div', { class: 'muted', text: detail.file + ' · row ' + detail.row + ' · ' + detail.path })));
  host.append(head);
  if (detail.note) host.append(el('div', { class: 'note', text: detail.note }));
  host.append(el('p', { class: 'desc', text: detail.description }));
  if (detail.hint) host.append(el('pre', { class: 'hint', text: detail.hint }));
  if (options.extra) host.append(options.extra);

  const table = el('table', { class: 'fields' });
  const inputs = [];
  for (const field of detail.fields) {
    const control = String(field.value).length > 90
      ? el('textarea', { rows: '2' })
      : el('input', { type: 'text' });
    control.value = field.value;
    control.dataset.col = String(field.col);
    control.dataset.original = field.value;
    if (field.locked) {
      control.readOnly = true;
      control.classList.add('locked');
      control.title = field.note || '';
    }
    const label = el('label', { class: 'field-label' },
      String(field.col).padStart(2, '0') + ' ' + field.label,
      field.locked ? el('span', { class: 'lock', text: ' fixed' }) : null);
    label.title = 'column ' + field.col;
    table.append(el('tr', {},
      el('td', { class: 'fl' }, label),
      el('td', {}, control),
      el('td', { class: 'fd muted', text: field.display || '' })));
    inputs.push(control);
  }
  host.append(table);

  const status = el('div', { class: 'muted status' });
  const save = el('button', { class: 'primary', text: 'Save changes' });
  const revert = el('button', { text: 'Revert' });
  save.addEventListener('click', async () => {
    const changes = inputs
      .filter(input => input.value !== input.dataset.original)
      .map(input => ({ row: detail.row, col: Number(input.dataset.col), value: input.value }));
    if (!changes.length) { status.textContent = 'No changes.'; return; }
    save.disabled = true;
    status.className = 'muted status';
    try {
      const result = await api('/api/table/apply', {
        method: 'POST',
        body: { path: detail.path, changes, save: true },
      });
      for (const input of inputs) input.dataset.original = input.value;
      status.textContent = 'Saved' + (result.backup ? ' · backup ' + result.backup : '') + '.';
      markRestart();
      say('Saved. Restart the emulator to load table changes.', 'ok');
      if (options.onSaved) options.onSaved();
    } catch (error) {
      status.className = 'muted status error';
      status.textContent = 'Not saved: ' + error.message;
    } finally {
      save.disabled = false;
    }
  });
  revert.addEventListener('click', () => {
    for (const input of inputs) input.value = input.dataset.original;
    status.textContent = 'Changes discarded (nothing was sent).';
  });
  const actions = el('div', { class: 'actions' }, save, revert, status);
  if (options.actions) actions.append(options.actions);
  host.append(actions);
  return { inputs };
}

async function rowDetail(path, row) {
  return api('/api/row?path=' + enc(path) + '&row=' + enc(row));
}

/* ------------------------------------------------------------------ state */
const App = {
  info: null,
  items: { rows: [], total: 0, offset: 0, limit: 100, q: '', table: '', kind: '', grade: '', selected: null },
  cars: { data: null, selected: null, grades: [], selectedGrade: null },
  rewards: { path: '', offset: 0, limit: 100, q: '', group: '', data: null, selected: null },
  settings: null,
  accounts: { rows: [], selected: null },
  gmHistory: [],
  gmPosition: 0,
};

/* ================================================================ ITEMS */
async function loadItems() {
  const state = App.items;
  const params = new URLSearchParams({
    q: state.q, table: state.table, kind: state.kind, grade: state.grade,
    offset: String(state.offset), limit: String(state.limit),
  });
  try {
    const data = await api('/api/items?' + params);
    state.total = data.total;
    state.rows = data.items;
    fillSelect($('#item-table'), data.tables.map(t => ({ value: t.path, label: t.file })), 'All tables', state.table);
    fillSelect($('#item-kind'), data.kinds.map(k => ({ value: k, label: k })), 'All kinds', state.kind);
    fillSelect($('#item-grade'), data.grades.map(g => ({ value: g, label: g })), 'All grades', state.grade);
    const body = $('#item-list tbody');
    clear(body);
    for (const item of state.rows) {
      const row = el('tr', { 'data-id': item.id },
        el('td', { class: 'thumb' }, iconImage(item.id, item.icon_key)),
        el('td', { class: 'mono', text: item.id }),
        el('td', { text: item.name }),
        el('td', { class: 'muted', text: item.kind || '–' }),
        el('td', { text: item.grade || '–' }),
        el('td', { text: item.level || '–' }),
        el('td', { class: 'num', text: fmt(item.price) }));
      row.addEventListener('click', () => selectItem(item, row));
      body.append(row);
    }
    $('#item-count').textContent = data.total
      ? (data.offset + 1).toLocaleString() + '–' + (data.offset + data.items.length).toLocaleString() +
        ' of ' + data.total.toLocaleString()
      : 'No items';
    $('#item-prev').disabled = data.offset <= 0;
    $('#item-next').disabled = data.offset + data.limit >= data.total;
  } catch (error) {
    say(error.message, 'error');
  }
}

async function selectItem(item, row) {
  App.items.selected = item;
  $('#item-detail').dataset.id = item.id;
  $$('#item-list tbody tr').forEach(tr => tr.classList.toggle('selected', tr === row));
  try {
    const detail = await rowDetail(item.table, item.row);
    if (App.items.selected !== item) return;
    makeEditor($('#item-detail'), detail, {
      icon: { id: item.id, key: item.icon_key },
      extra: givePanel(item),
      onSaved: loadItems,
    });
    if (item.table.endsWith('VisualItem.xlt')) await addShopEditor(item);
  } catch (error) {
    say(error.message, 'error');
  }
}

async function addShopEditor(item) {
  const host = $('#item-detail');
  try {
    const shop = await api('/api/shop/row?id=' + enc(item.id));
    if (App.items.selected !== item) return;
    const details = el('details', { class: 'shop-entry' },
      el('summary', { text: 'Drift shop entry (VShopItem.xlt): price, durations and bonuses' }));
    const editorHost = el('div', { class: 'nested-detail' });
    details.append(editorHost);
    host.append(details);
    const detail = await rowDetail(shop.path, shop.row);
    makeEditor(editorHost, detail, { onSaved: loadItems });
  } catch (error) {
    if (!/No drift shop entry/.test(error.message)) say(error.message, 'error');
  }
}

function givePanel(item) {
  const isDrift = item.table.indexOf('VisualItem') >= 0;
  const name = el('input', { placeholder: 'Online character name', size: '18', autocomplete: 'off' });
  const amount = el('input', { value: isDrift ? '0' : '1', size: '5' });
  const amountLabel = el('span', { class: 'muted', text: isDrift ? 'Days (0 = permanent)' : 'Count' });
  const run = el('button', { text: isDrift ? 'Give drift item' : 'Give to player' });
  const out = el('div', { class: 'muted give-out' });
  run.addEventListener('click', async () => {
    const player = name.value.trim();
    if (!player) { out.textContent = 'Enter the online character name.'; return; }
    const value = amount.value.trim() || (isDrift ? '0' : '1');
    if (!/^\d+$/.test(value)) { out.textContent = 'Count / days must be a whole number.'; return; }
    const command = isDrift
      ? 'drift ' + player + ' ' + item.id + ' ' + value
      : 'item ' + player + ' ' + item.id + ' ' + value;
    out.textContent = 'Sending…';
    try {
      const reply = await api('/api/gm', { method: 'POST', body: { command } });
      out.textContent = reply.reply;
    } catch (error) {
      out.textContent = 'Failed: ' + error.message;
    }
  });
  return el('div', { class: 'give' },
    el('h3', { text: 'Give to an online player' }),
    el('div', { class: 'row' }, name, amount, amountLabel, run),
    out);
}

/* ================================================================= CARS */
async function loadCars() {
  try {
    App.cars.data = await api('/api/cars');
    renderCarRows();
  } catch (error) {
    say(error.message, 'error');
  }
}

function renderCarRows() {
  const body = $('#car-list tbody');
  clear(body);
  const query = $('#car-q').value.trim().toLowerCase();
  const models = App.cars.data.models.filter(model => !query ||
    (model.name + ' ' + model.car_name + ' ' + model.uid + ' ' + model.file).toLowerCase().includes(query));
  for (const model of models) {
    const row = el('tr', {},
      el('td', { text: model.name || model.car_name }),
      el('td', { class: 'muted', text: model.car_name }),
      el('td', { class: 'mono', text: model.uid }),
      el('td', { class: 'muted', title: 'VehicleList column 2', text: model.vehicle || '–' }),
      el('td', { class: 'num', text: String(model.grades) }));
    row.addEventListener('click', () => selectCar(model, row));
    body.append(row);
  }
  $('#car-count').textContent = models.length.toLocaleString() + ' of ' +
    App.cars.data.total.toLocaleString() + ' models';
}

async function selectCar(model, row) {
  if (row) App.cars.rowElement = row;
  row = row || App.cars.rowElement;
  App.cars.selected = model;
  App.cars.selectedGrade = null;
  $$('#car-list tbody tr').forEach(tr => tr.classList.toggle('selected', tr === row));
  try {
    const grades = await api('/api/car/grades?uid=' + enc(model.uid));
    App.cars.grades = grades.grades;
    const detail = await rowDetail(App.cars.data.table, model.row);
    makeEditor($('#car-detail'), detail, {
      extra: carGivePanel(model),
      onSaved: async () => { await loadCars(); await selectCar(model); },
    });
    renderCarGrades();
  } catch (error) {
    say(error.message, 'error');
  }
}

function carGivePanel(model) {
  if (!App.cars.grades.length) {
    return el('div', { class: 'give' },
      el('h3', { text: 'Give this car to an online player' }),
      el('p', { class: 'muted', text: 'No VehicleUpgrade rows for this model: the GM car command ' +
        'only gives player cars (VehicleList column 2 = 0) that have a V grade.' }));
  }
  const name = el('input', { placeholder: 'Online character name', size: '18', autocomplete: 'off' });
  const select = el('select');
  for (const grade of App.cars.grades) select.append(el('option', { value: String(grade.grade), text: 'V' + grade.grade }));
  const run = el('button', { text: 'Give car' });
  const out = el('div', { class: 'muted give-out' });
  run.addEventListener('click', async () => {
    const player = name.value.trim();
    if (!player) { out.textContent = 'Enter the online character name.'; return; }
    const carName = model.name || model.car_name;
    if (!carName) { out.textContent = 'This model has no name the GM car command can match.'; return; }
    const command = 'car ' + player + ' ' + carName + ' V' + select.value;
    out.textContent = 'Sending…';
    try {
      const reply = await api('/api/gm', { method: 'POST', body: { command } });
      out.textContent = reply.reply;
    } catch (error) {
      out.textContent = 'Failed: ' + error.message;
    }
  });
  return el('div', { class: 'give' },
    el('h3', { text: 'Give this car to an online player' }),
    el('div', { class: 'row' }, name, el('span', { class: 'muted', text: 'Grade' }), select, run),
    out);
}

function renderCarGrades() {
  const host = $('#car-grades');
  clear(host);
  host.append(el('h3', { text: 'V grades of ' + (App.cars.selected.name || '') }));
  if (!App.cars.grades.length) {
    host.append(el('p', { class: 'muted', text: 'No VehicleUpgrade rows for this model.' }));
    return;
  }
  const grid = el('div', { class: 'grade-grid' });
  for (const grade of App.cars.grades) {
    const button = el('button', {
      class: App.cars.selectedGrade === grade.row ? 'grade selected' : 'grade',
      title: 'VehicleUpgrade row ' + grade.row,
    }, el('strong', { text: 'V' + grade.grade }),
       el('span', { text: (grade.name || '') }),
       el('span', { class: 'muted', text: fmt(grade.price) + ' Mito · req ' + (grade.req_level || '–') }));
    button.addEventListener('click', () => openGrade(grade));
    grid.append(button);
  }
  host.append(grid);
}

async function openGrade(grade) {
  App.cars.selectedGrade = grade.row;
  renderCarGrades();
  try {
    const detail = await rowDetail(App.cars.data.upgrade_table, grade.row);
    const back = el('button', { text: '← Back to the model', onclick: () => selectCar(App.cars.selected) });
    makeEditor($('#car-detail'), detail, {
      actions: back,
      onSaved: async () => {
        markRestart();
        await selectCar(App.cars.selected);
        await openGrade(grade);
      },
    });
  } catch (error) {
    say(error.message, 'error');
  }
}

/* ======================================================== REWARDS & DROPS */
function buildRewardSources(info) {
  const group = info.groups.find(item => item.name === 'Rewards & drops');
  const select = $('#reward-source');
  clear(select);
  for (const table of (group ? group.tables : [])) {
    select.append(el('option', {
      value: table.path,
      text: table.file + (table.mode ? ' — ' + table.mode : ''),
    }));
  }
  App.rewards.path = select.value;
  $('#reward-group-wrap').classList.add('hidden');
}

async function loadRewards(reset) {
  if (!App.rewards.path) return;
  const state = App.rewards;
  if (reset) { state.offset = 0; state.selected = null; }
  const isRewardGroup = state.path.endsWith('RewardGroup.xlt');
  if (!isRewardGroup) { state.group = ''; $('#reward-group-wrap').classList.add('hidden'); }
  const params = new URLSearchParams({
    path: state.path, offset: String(state.offset), limit: String(state.limit),
    q: state.q, group: state.group,
  });
  try {
    const data = await api('/api/table?' + params);
    state.data = data;
    $('#reward-desc').textContent = data.description + (data.mode ? ' — ' + data.mode : '');
    $('#reward-prob').textContent = data.probability_sum === null || data.probability_sum === undefined
      ? ''
      : 'Sum of the probabilities of the ' + data.row_count.toLocaleString() + ' selected rows: ' +
        fmt(data.probability_sum) + ' % (as written in the table)';
    const body = $('#reward-list tbody');
    clear(body);
    for (const row of data.rows) {
      const tr = el('tr', {},
        el('td', { class: 'mono num', text: String(row.row) }),
        el('td', { text: row.title }),
        el('td', { class: 'muted', text: row.note || '' }));
      tr.addEventListener('click', () => selectRewardRow(row, tr));
      body.append(tr);
    }
    $('#reward-count').textContent = data.row_count
      ? (data.offset + 1).toLocaleString() + '–' + (data.offset + data.rows.length).toLocaleString() +
        ' of ' + data.row_count.toLocaleString()
      : 'No rows';
    $('#reward-prev').disabled = data.offset <= 0;
    $('#reward-next').disabled = data.offset + data.limit >= data.row_count;
    $('#reward-add').disabled = true;
  } catch (error) {
    say(error.message, 'error');
  }
}

async function loadRewardGroups() {
  try {
    const data = await api('/api/rewards/groups');
    const select = $('#reward-group');
    clear(select);
    select.append(el('option', { value: '', text: 'All groups (' + data.total.toLocaleString() + ')' }));
    for (const group of data.groups) {
      select.append(el('option', {
        value: group.group,
        text: group.group + ' — ' + group.rows + ' rows, ' + fmt(group.probability) + ' %' +
          (group.description ? ' — ' + group.description : ''),
      }));
    }
    select.value = App.rewards.group;
    $('#reward-group-wrap').classList.remove('hidden');
  } catch (error) {
    say(error.message, 'error');
  }
}

async function selectRewardRow(row, tr) {
  App.rewards.selected = row;
  $$('#reward-list tbody tr').forEach(other => other.classList.toggle('selected', other === tr));
  $('#reward-add').disabled = false;
  try {
    const detail = await rowDetail(App.rewards.path, row.row);
    makeEditor($('#reward-detail'), detail, {
      onSaved: async () => {
        await loadRewards(false);
        if (App.rewards.path.endsWith('RewardGroup.xlt')) await loadRewardGroups();
      },
    });
  } catch (error) {
    say(error.message, 'error');
  }
}

async function duplicateReward() {
  const state = App.rewards;
  if (!state.selected) { say('Select a row to duplicate.', 'warn'); return; }
  try {
    const result = await api('/api/table/duplicate', {
      method: 'POST',
      body: { path: state.path, row: state.selected.row },
    });
    const limit = state.limit;
    const start = state.data ? state.data.start : 0;
    state.offset = Math.max(0, Math.floor((result.row - start) / limit) * limit);
    await loadRewards(false);
    if (state.path.endsWith('RewardGroup.xlt')) await loadRewardGroups();
    markRestart();
    say(result.message + (result.backup ? ' Backup: ' + result.backup : ''), 'ok');
    const tr = $$('#reward-list tbody tr').find(item => item.firstChild.textContent === String(result.row));
    if (tr) tr.click();
  } catch (error) {
    say(error.message, 'error');
  }
}

/* =============================================================== SETTINGS */
async function loadSettings() {
  try {
    App.settings = await api('/api/settings');
    renderSettings();
    await loadEvents();
  } catch (error) {
    say(error.message, 'error');
  }
}

function renderSettings() {
  if (!App.settings) return;
  const host = $('#settings-list');
  clear(host);
  const query = $('#settings-q').value.trim().toLowerCase();
  let shown = 0;
  for (const section of App.settings.sections) {
    const rows = section.rows.filter(row =>
      !query || (section.name + ' ' + row.key + ' ' + row.value).toLowerCase().includes(query));
    if (!rows.length) continue;
    shown += rows.length;
    const table = el('table', { class: 'settings' });
    table.append(el('thead', {}, el('tr', {},
      el('th', { text: 'Setting' }), el('th', { text: 'Value' }), el('th', { text: '' }))));
    const body = el('tbody');
    for (const row of rows) {
      const input = el('input', { type: 'text', value: row.value });
      const save = el('button', { text: 'Save' });
      const status = el('span', { class: 'muted' });
      save.addEventListener('click', async () => {
        save.disabled = true;
        try {
          const result = await api('/api/table/apply', {
            method: 'POST',
            body: { path: App.settings.path, changes: [{ row: row.row, col: 2, value: input.value }], save: true },
          });
          row.value = input.value;
          status.textContent = 'Saved' + (result.backup ? ' · ' + result.backup : '');
          markRestart();
        } catch (error) {
          status.textContent = 'Not saved: ' + error.message;
        } finally {
          save.disabled = false;
        }
      });
      body.append(el('tr', {},
        el('td', { class: 'key', title: row.hint || '' },
          el('div', { text: row.key }),
          row.hint ? el('div', { class: 'hintline muted', text: row.hint }) : null),
        el('td', {}, input),
        el('td', { class: 'nowrap' }, save, status)));
    }
    table.append(body);
    host.append(el('section', { class: 'settings-section' },
      el('h3', { text: '[' + section.name + ']' }), table));
  }
  $('#settings-count').textContent = shown.toLocaleString() + ' settings';
}

async function loadEvents() {
  try {
    const data = await api('/api/events');
    const host = $('#events-list');
    clear(host);
    const table = el('table', { class: 'settings events' });
    table.append(el('thead', {}, el('tr', {},
      el('th', { text: 'Event' }), el('th', { text: 'Auto window' }), el('th', { text: 'Mode' }))));
    const body = el('tbody');
    for (const event of data.events) {
      const segmented = el('div', { class: 'segmented' });
      for (const mode of data.modes) {
        const button = el('button', { class: event.mode === mode ? 'on' : '', text: mode });
        button.addEventListener('click', () => setEvent(event, mode));
        segmented.append(button);
      }
      body.append(el('tr', {},
        el('td', {}, el('div', { text: event.shown }), el('div', { class: 'muted mono', text: event.name })),
        el('td', { class: 'muted', text: event.window }),
        el('td', {}, segmented)));
    }
    table.append(body);
    host.append(table);
  } catch (error) {
    say(error.message, 'error');
  }
}

async function setEvent(event, mode) {
  try {
    const result = await api('/api/events', { method: 'POST', body: { name: event.name, mode } });
    say('[' + event.name + '] ' + result.mode + ' saved to emulator.ini. ' + (result.reply || ''), result.live ? 'ok' : 'warn');
    await loadEvents();
  } catch (error) {
    say(error.message, 'error');
  }
}

/* ================================================================= SERVER */
async function refreshStatus() {
  const output = $('#server-status');
  output.textContent = 'Reading ./launch.sh status…';
  try {
    const data = await api('/api/server/status');
    output.textContent = (data.output || '(no output)') + (data.ok ? '' : '\n(launch.sh returned a non-zero exit code)');
  } catch (error) {
    output.textContent = error.message;
  }
}

async function refreshOnline() {
  const host = $('#server-online');
  try {
    const data = await api('/api/server/online');
    if (!data.ok) {
      host.replaceChildren(el('p', { class: 'error', text: data.reply || 'The emulator did not answer.' }));
      return;
    }
    if (!data.players.length) {
      host.replaceChildren(el('p', { class: 'muted', text: 'Nobody is online.' }));
      return;
    }
    const table = el('table', { class: 'list players' });
    table.append(el('thead', {}, el('tr', {},
      el('th', { text: 'Character' }), el('th', { text: 'Account' }), el('th', { text: 'Level' }),
      el('th', { text: 'Address' }), el('th', { text: '' }))));
    const body = el('tbody');
    for (const player of data.players) {
      const kick = el('button', { text: 'Kick' });
      kick.addEventListener('click', () => {
        if (confirm('Kick ' + player.name + '?')) runServerCommand('kick ' + player.name);
      });
      const block = el('button', { text: 'Block' });
      block.addEventListener('click', () => {
        const days = prompt('Block ' + player.name + ' for how many days?', '1');
        if (days === null) return;
        if (!/^\d+(\.\d+)?$/.test(days.trim())) { say('Days must be a number.', 'warn'); return; }
        runServerCommand('block ' + player.name + ' ' + days.trim());
      });
      const ban = el('button', { class: 'danger', text: 'Ban' });
      ban.addEventListener('click', () => {
        if (confirm('Ban account ' + player.account + '? This disconnects the account.')) {
          runServerCommand('ban ' + player.account);
        }
      });
      body.append(el('tr', {},
        el('td', { text: player.name }),
        el('td', { class: 'mono', text: player.account }),
        el('td', { class: 'num', text: player.level }),
        el('td', { class: 'muted', text: player.address }),
        el('td', { class: 'nowrap' }, kick, block, ban)));
    }
    table.append(body);
    host.replaceChildren(table);
  } catch (error) {
    host.replaceChildren(el('p', { class: 'error', text: error.message }));
  }
}

async function runServerCommand(command) {
  const log = $('#server-actions');
  log.append(el('div', { class: 'cmd', text: '> ' + command }));
  log.scrollTop = log.scrollHeight;
  try {
    const data = await api('/api/gm', { method: 'POST', body: { command } });
    log.append(el('div', { class: data.ok ? 'ok' : 'error', text: data.reply }));
    refreshOnline();
  } catch (error) {
    log.append(el('div', { class: 'error', text: error.message }));
  }
  log.scrollTop = log.scrollHeight;
}

async function runGm() {
  const input = $('#gm-input');
  const command = input.value.trim();
  if (!command) return;
  const first = command.split(/\s+/)[0].toLowerCase();
  if (first === 'account-create' || first === 'account-password') {
    say('Use the Accounts panel for passwords: they must not pass through the console history.', 'warn');
    return;
  }
  const output = $('#gm-output');
  output.append(el('div', { class: 'cmd', text: '> ' + command }));
  input.value = '';
  App.gmHistory.push(command);
  App.gmPosition = App.gmHistory.length;
  try {
    const data = await api('/api/gm', { method: 'POST', body: { command } });
    output.append(el('div', { class: data.ok ? 'ok' : 'error', text: data.reply }));
  } catch (error) {
    output.append(el('div', { class: 'error', text: error.message }));
  }
  while (output.childNodes.length > 400) output.removeChild(output.firstChild);
  output.scrollTop = output.scrollHeight;
}

function gmHistoryStep(direction) {
  if (!App.gmHistory.length) return;
  App.gmPosition = Math.max(0, Math.min(App.gmHistory.length, App.gmPosition + direction));
  $('#gm-input').value = App.gmHistory[App.gmPosition] || '';
}

async function searchAccounts() {
  const message = $('#account-msg');
  try {
    const data = await api('/api/server/accounts?q=' + enc($('#account-q').value.trim()));
    App.accounts.rows = data.rows;
    if (!data.ok) { message.textContent = data.reply || 'The account search failed.'; return; }
    message.textContent = '';
    renderAccountRows();
  } catch (error) {
    message.textContent = error.message;
  }
}

function renderAccountRows() {
  const body = $('#account-list tbody');
  clear(body);
  for (const row of App.accounts.rows) {
    const tr = el('tr', {},
      el('td', { class: 'mono', text: row.account }),
      el('td', { text: row.valid === 'y' ? 'yes' : 'banned' }),
      el('td', { class: 'muted', text: row.joined || '' }));
    tr.addEventListener('click', () => selectAccount(row.account, tr));
    body.append(tr);
  }
  $('#account-count').textContent = App.accounts.rows.length.toLocaleString() +
    ' accounts (at most 300 per search)';
}

async function selectAccount(member, tr) {
  try {
    const data = await api('/api/server/account?id=' + enc(member));
    if (!data.ok) { $('#account-msg').textContent = data.reply || 'No account detail.'; return; }
    App.accounts.selected = data.account;
    $$('#account-list tbody tr').forEach(other => other.classList.toggle('selected', other === tr));
    renderAccountDetail();
  } catch (error) {
    $('#account-msg').textContent = error.message;
  }
}

function renderAccountDetail() {
  const host = $('#account-detail');
  clear(host);
  const account = App.accounts.selected;
  if (!account) { host.append(el('p', { class: 'muted', text: 'Select an account.' })); return; }
  host.append(el('h3', { text: account.account }));
  host.append(el('div', { class: 'muted', text: (account.valid === 'y' ? 'Active' : 'Banned') +
    ' · G Coin ' + fmt(account.coins) }));
  if (!account.characters.length) host.append(el('p', { class: 'muted', text: 'No characters yet.' }));
  for (const character of account.characters) {
    host.append(el('div', { class: 'character' },
      el('strong', { text: character.name }),
      el('span', { class: 'muted', text: ' level ' + character.level + ' · ' + fmt(character.mito) +
        ' Mito · role ' + character.role + ' · ' + (character.online ? 'Online' : 'Offline') +
        ' · state ' + character.state })));
  }
}

async function accountAction(path, body, message) {
  try {
    const data = await api(path, { method: 'POST', body });
    $('#account-msg').textContent = data.reply || (data.ok ? 'Done.' : 'Failed.');
    if (data.ok && message) $('#account-msg').textContent += ' ' + message;
    return data;
  } catch (error) {
    $('#account-msg').textContent = error.message;
    return null;
  }
}

async function createAccount() {
  const id = $('#account-new-id').value.trim();
  const password = $('#account-new-pass').value;
  $('#account-new-pass').value = '';
  if (!id || !password) { $('#account-msg').textContent = 'Enter an account ID and a password.'; return; }
  const data = await accountAction('/api/server/account/create', { id, password });
  if (data && data.ok) await searchAccounts();
}

async function resetPassword() {
  const account = App.accounts.selected;
  if (!account) { $('#account-msg').textContent = 'Select an account first.'; return; }
  const password = $('#account-pass').value;
  $('#account-pass').value = '';
  if (!password) { $('#account-msg').textContent = 'Enter the new password.'; return; }
  await accountAction('/api/server/account/password', { id: account.account, password });
}

async function setRole(role) {
  const account = App.accounts.selected;
  if (!account) { $('#account-msg').textContent = 'Select an account first.'; return; }
  await accountAction('/api/server/account/role', { id: account.account, role });
}

async function accountBan(action) {
  const account = App.accounts.selected;
  if (!account) { $('#account-msg').textContent = 'Select an account first.'; return; }
  if (!confirm((action === 'ban' ? 'Ban' : 'Unban') + ' account ' + account.account + '?')) return;
  await runServerCommand(action + ' ' + account.account);
}

async function refreshLog() {
  try {
    const data = await api('/api/server/log?lines=200');
    $('#log-path').textContent = data.path ? 'logs: ' + data.path : 'No log file yet.';
    $('#server-log').textContent = data.lines.length ? data.lines.join('\n') : '(the log is empty)';
  } catch (error) {
    $('#server-log').textContent = error.message;
  }
}

async function restartEmulator() {
  if (!confirm('Restart the emulator now? Connected players will be disconnected.')) return;
  const output = $('#server-restart-out');
  output.textContent = 'Restarting…';
  try {
    const data = await api('/api/server/restart', { method: 'POST', body: { confirm: true } });
    output.textContent = (data.ok ? 'Restart finished.' : 'Restart failed.') +
      (data.output ? '\n' + data.output : '');
    refreshStatus();
    refreshOnline();
  } catch (error) {
    output.textContent = 'Restart failed: ' + error.message;
  }
}

/* ============================================================== BOOTSTRAP */
const loaders = {
  items: loadItems,
  cars: loadCars,
  rewards: async () => {
    if (App.rewards.path.endsWith('RewardGroup.xlt')) await loadRewardGroups();
    await loadRewards(true);
  },
  settings: loadSettings,
  server: async () => { refreshStatus(); refreshOnline(); refreshLog(); },
};

const loaded = new Set(['items']);

function showTab(name) {
  $$('#tabs button').forEach(button => button.classList.toggle('active', button.dataset.tab === name));
  $$('.panel').forEach(panel => panel.classList.toggle('active', panel.id === 'tab-' + name));
  if (!loaded.has(name)) {
    loaded.add(name);
    loaders[name]();
  }
}

function wire() {
  $$('#tabs button').forEach(button => button.addEventListener('click', () => showTab(button.dataset.tab)));

  const itemSearch = debounce(() => {
    App.items.q = $('#item-q').value.trim();
    App.items.offset = 0;
    loadItems();
  }, 250);
  $('#item-q').addEventListener('input', itemSearch);
  $('#item-table').addEventListener('change', () => {
    App.items.table = $('#item-table').value;
    App.items.offset = 0;
    loadItems();
  });
  $('#item-kind').addEventListener('change', () => {
    App.items.kind = $('#item-kind').value;
    App.items.offset = 0;
    loadItems();
  });
  $('#item-grade').addEventListener('change', () => {
    App.items.grade = $('#item-grade').value;
    App.items.offset = 0;
    loadItems();
  });
  $('#item-prev').addEventListener('click', () => {
    App.items.offset = Math.max(0, App.items.offset - App.items.limit);
    loadItems();
  });
  $('#item-next').addEventListener('click', () => {
    App.items.offset += App.items.limit;
    loadItems();
  });

  $('#car-q').addEventListener('input', debounce(renderCarRows, 150));

  $('#reward-source').addEventListener('change', async () => {
    App.rewards.path = $('#reward-source').value;
    App.rewards.group = '';
    App.rewards.q = '';
    $('#reward-q').value = '';
    if (App.rewards.path.endsWith('RewardGroup.xlt')) await loadRewardGroups();
    await loadRewards(true);
  });
  $('#reward-group').addEventListener('change', () => {
    App.rewards.group = $('#reward-group').value;
    loadRewards(true);
  });
  const rewardSearch = debounce(() => {
    App.rewards.q = $('#reward-q').value.trim();
    App.rewards.offset = 0;
    loadRewards(false);
  }, 250);
  $('#reward-q').addEventListener('input', rewardSearch);
  $('#reward-prev').addEventListener('click', () => {
    App.rewards.offset = Math.max(0, App.rewards.offset - App.rewards.limit);
    loadRewards(false);
  });
  $('#reward-next').addEventListener('click', () => {
    App.rewards.offset += App.rewards.limit;
    loadRewards(false);
  });
  $('#reward-add').addEventListener('click', duplicateReward);

  $('#settings-q').addEventListener('input', debounce(renderSettings, 150));

  $('#server-status-refresh').addEventListener('click', refreshStatus);
  $('#server-online-refresh').addEventListener('click', refreshOnline);
  $('#server-log-refresh').addEventListener('click', refreshLog);
  $('#server-restart').addEventListener('click', restartEmulator);
  $('#gm-run').addEventListener('click', runGm);
  $('#gm-input').addEventListener('keydown', event => {
    if (event.key === 'Enter') { event.preventDefault(); runGm(); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); gmHistoryStep(-1); }
    else if (event.key === 'ArrowDown') { event.preventDefault(); gmHistoryStep(1); }
  });
  $('#account-search').addEventListener('click', searchAccounts);
  $('#account-q').addEventListener('keydown', event => {
    if (event.key === 'Enter') { event.preventDefault(); searchAccounts(); }
  });
  $('#account-create').addEventListener('click', createAccount);
  $('#account-password').addEventListener('click', resetPassword);
  $('#account-role-a').addEventListener('click', () => setRole('A'));
  $('#account-role-n').addEventListener('click', () => setRole('N'));
  $('#account-ban').addEventListener('click', () => accountBan('ban'));
  $('#account-unban').addEventListener('click', () => accountBan('unban'));

  setInterval(() => {
    if ($('#tab-server').classList.contains('active')) refreshOnline();
  }, 15000);
}

async function boot() {
  if (!token) {
    document.body.replaceChildren(el('main', { class: 'token-help' },
      el('h1', { text: 'openDC web workshop' }),
      el('p', { text: 'This page needs the token from the URL printed when the tool starts:' }),
      el('pre', { text: 'python -m tools.webadmin' }),
      el('p', { text: 'Open the address it prints (it ends with ?token=…). The token changes at every start.' })));
    return;
  }
  wire();
  try {
    App.info = await api('/api/tables');
    $('#version').textContent = 'version ' + App.info.version + ' · ' + App.info.data_root;
    if (App.info.warning) say(App.info.warning, 'error');
    buildRewardSources(App.info);
    await loadItems();
  } catch (error) {
    say(error.message, 'error');
  }
}

boot();
