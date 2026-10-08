// Veda Spaces Preliminary Budgetary Estimate wizard (ADR-012). Plain JavaScript; the DOM is built with textContent only.
// The page is off unless <meta name="veda-estimator"> is "on" and the API base and Turnstile site key are set: the
// committed (production) page is off; the staging build switches it on. This file holds no rates: prices come only
// from the API, which returns totals, never line rates.
'use strict';

const meta = (name) => document.querySelector(`meta[name="${name}"]`)?.content?.trim() || '';
const apiBase = meta('veda-estimator') === 'on' && meta('veda-turnstile-sitekey') ? meta('veda-api-base') : '';
const credentials = meta('veda-api-credentials') === 'include' ? 'include' : 'same-origin';
const enabledPackages = (meta('veda-estimator-packages') || 'ESSENTIAL').split(',').map((p) => p.trim()).filter(Boolean);
const $ = (sel) => document.querySelector(sel);

const ROOMS = [
  ['KITCHEN', 'Kitchen', 1], ['UTILITY', 'Utility', 1], ['LIVING', 'Living room', 1], ['DINING', 'Dining', 1],
  ['MASTER_BEDROOM', 'Master bedroom', 1], ['BEDROOM_2', 'Bedroom 2', 2], ['BEDROOM_3', 'Bedroom 3', 3],
  ['BEDROOM_4', 'Bedroom 4', 4], ['STUDY', 'Study', 1], ['POOJA', 'Pooja room', 1], ['WHOLE_HOME', 'Whole home', 1],
];
const BEDROOMS = ['MASTER_BEDROOM', 'BEDROOM_2', 'BEDROOM_3', 'BEDROOM_4'];
const YES_NO = [['YES', 'Yes'], ['NO', 'No']];
const LEN = (name, label, hint) => ({ name, label, kind: 'length', hint });
const PRODUCTS = {
  KITCHEN: { label: 'Modular kitchen', rooms: ['KITCHEN'], inputs: [LEN('RUN', 'Counter length', 'Total length of the counter along every wall.'), { name: 'DRAWERS', label: 'Drawer stacks', kind: 'count', hint: 'How many drawer units you would like.' }], options: [['WALL_UNITS', 'Wall units', YES_NO], ['LOFT', 'Loft', YES_NO]] },
  WARDROBE: { label: 'Wardrobe', rooms: BEDROOMS, inputs: [LEN('WIDTH', 'Width', 'Wall-to-wall width of the wardrobe.'), LEN('HEIGHT', 'Height', 'Floor to top of the wardrobe (without loft).')], options: [['DOOR', 'Doors', [['HINGED', 'Hinged'], ['SLIDING', 'Sliding']]], ['LOFT', 'Loft above', YES_NO], ['GLASS', 'Profile glass', YES_NO]] },
  TV_UNIT: { label: 'TV unit', rooms: ['LIVING', ...BEDROOMS], inputs: [LEN('WIDTH', 'Wall width', 'Width of the TV wall.')], options: [['STYLE', 'Style', [['BOX', 'TV box only'], ['BOX_STORAGE', 'TV box with storage'], ['PANELLED', 'Full wall panelling']]]] },
  FEATURE_WALL: { label: 'Feature wall', rooms: ['LIVING', 'DINING', ...BEDROOMS], inputs: [LEN('WIDTH', 'Width', 'Width of the wall.'), LEN('HEIGHT', 'Height', 'Floor-to-ceiling height.')], options: [['FINISH', 'Finish', [['PANELLING', 'Panelling'], ['WALLPAPER', 'Wallpaper'], ['TEXTURE', 'Texture paint']]]] },
  CROCKERY_UNIT: { label: 'Crockery unit', rooms: ['DINING', 'LIVING'], inputs: [LEN('WIDTH', 'Width', 'Width of the unit.'), LEN('HEIGHT', 'Height', 'Height of the unit.')], options: [['GLASS', 'Profile glass', YES_NO]] },
  PARTITION: { label: 'Partition', rooms: ['LIVING', 'DINING'], inputs: [LEN('WIDTH', 'Width', 'Width of the partition.'), LEN('HEIGHT', 'Height', 'Height of the partition.')], options: [['FINISH', 'Finish', [['LAMINATE', 'Laminate'], ['FLUTED_GLASS', 'Fluted glass']]]] },
  FALSE_CEILING: { label: 'False ceiling', rooms: ['WHOLE_HOME', 'LIVING', 'DINING', 'KITCHEN', ...BEDROOMS], inputs: [{ name: 'AREA', label: 'Ceiling area', kind: 'area', hint: 'Usually close to the carpet area of the rooms covered.' }], options: [['DESIGN', 'Design', [['PLAIN', 'Plain'], ['COVE', 'Cove'], ['CLOUD', 'Cloud']]], ['LIGHTS', 'Panel lights', YES_NO]] },
  STUDY_UNIT: { label: 'Study unit', rooms: [...BEDROOMS, 'STUDY'], inputs: [LEN('WIDTH', 'Width', 'Width of the desk.')], options: [['STORAGE', 'Overhead storage', YES_NO]] },
  VANITY_UNIT: { label: 'Vanity unit', rooms: [...BEDROOMS, 'DINING', 'WHOLE_HOME'], inputs: [LEN('WIDTH', 'Width', 'Width of a dresser vanity (not needed for a toilet vanity).')], options: [['TYPE', 'Type', [['TOILET', 'Toilet vanity'], ['DRESSER', 'Dresser vanity']]], ['MIRROR', 'Mirror', YES_NO]] },
  BED: { label: 'Bed and headboard', rooms: BEDROOMS, inputs: [], options: [['SIZE', 'Size', [['QUEEN', 'Queen'], ['KING', 'King']]], ['STORAGE', 'Storage', [['HYDRAULIC', 'Hydraulic storage'], ['NONE', 'No storage']]], ['HEADBOARD', 'Headboard', [['PANEL', 'Panelled'], ['CUSHIONED', 'Cushioned'], ['NONE', 'None']]]] },
  UTILITY: { label: 'Utility unit', rooms: ['UTILITY'], inputs: [LEN('WIDTH', 'Width', 'Width of the utility wall unit.')], options: [] },
  POOJA_UNIT: { label: 'Pooja unit', rooms: ['POOJA', 'DINING', 'LIVING'], inputs: [LEN('WIDTH', 'Unit width', 'Width of the mandir unit.'), LEN('DOOR_WIDTH', 'Door opening width', 'Width of the pooja door opening.')], options: [['DOOR', 'Pooja doors', [['STANDARD', 'Standard doors'], ['CNC_VENEER', 'CNC-cut veneer doors'], ['NONE', 'No doors']]], ['BEADING', 'Veneer beading', YES_NO], ['ASTA_CHAKRA', 'Ceiling asta chakra', [['NO', 'No'], ['YES', 'Yes']]]] },
  WINDOW_SEATING: { label: 'Window seating', rooms: [...BEDROOMS, 'LIVING', 'STUDY'], inputs: [LEN('WIDTH', 'Window width', 'Width of the window or sit-out.')], options: [['ARCH', 'Window arch framing', YES_NO]] },
  VENEER_ACCENTS: { label: 'Veneer accents', rooms: ['LIVING', 'DINING', 'KITCHEN', 'POOJA', 'WHOLE_HOME', ...BEDROOMS], inputs: [LEN('LENGTH', 'Running length', 'Total length of the arch, ceiling strip or beading.')], options: [['STYLE', 'Accent', [['ARCH', 'Veneer arch'], ['CEILING_STRIP', 'Veneer strip in the ceiling'], ['BEADING', 'Sofa-back beading']]]] },
  STORAGE_BOXES: { label: 'Storage boxes', rooms: [...BEDROOMS, 'KITCHEN', 'LIVING', 'DINING', 'UTILITY'], inputs: [LEN('WIDTH', 'Width', 'Width of the box or tall unit.'), LEN('HEIGHT', 'Height', 'Height of a tall storage box (not needed for bedside units).')], options: [['TYPE', 'Type', [['TALL', 'Tall storage box'], ['BEDSIDE_BOX', 'Bedside box'], ['BEDSIDE_TABLE', 'Bedside table']]]] },
  CEILING_PROFILE_LIGHTING: { label: 'Ceiling profile lighting', rooms: ['WHOLE_HOME', 'LIVING', 'DINING', 'KITCHEN', ...BEDROOMS], inputs: [LEN('LENGTH', 'Profile length', 'Total running length of profile lights.'), { name: 'COB', label: 'COB lights', kind: 'count', hint: 'Number of COB lights, if any.' }], options: [] },
  PAINTING: { label: 'Painting (optional)', rooms: ['WHOLE_HOME'], inputs: [{ name: 'AREA', label: 'Wall area', kind: 'area', hint: 'Total wall area to paint.' }], options: [['SYSTEM', 'Paint system', [['FULL', 'Primer, putty and two coats'], ['REPAINT', 'Two coats only']]]] },
  ELECTRICAL: { label: 'Electrical and lighting (optional)', rooms: ['WHOLE_HOME'], inputs: [{ name: 'CARPET', label: 'Carpet area', kind: 'area', hint: 'Carpet area of the home.' }, { name: 'SPOTS', label: 'Spot lights', kind: 'count', hint: 'Number of spot lights.' }], options: [] },
};
const UNITS = { length: [['ft', 'ft'], ['in', 'in'], ['m', 'm'], ['cm', 'cm']], area: [['sqft', 'sq ft'], ['sqm', 'sq m']], count: [['nos', 'nos']] };
const PACKAGES = [['ESSENTIAL', 'Essential', 'Quality laminate finishes, branded plywood and standard soft-close hardware.'], ['PREMIUM', 'Premium', 'Upgraded finishes and hardware.'], ['LUXURY', 'Luxury', 'Design-led, bespoke materials and a dedicated designer.']];
// Luxury has no public price (ADR-012 D2): it leads straight to a design consultation.
const STATE_KEY = 'veda-estimate-v1';
const state = { step: 1, home: {}, items: [], package: 'ESSENTIAL', estimate: null, enquiryKey: null, luxury: false };

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v === null || v === undefined) continue;
    if (k === 'text') node.textContent = v; else node.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children) if (c) node.append(c);
  return node;
}
const save = () => { try { sessionStorage.setItem(STATE_KEY, JSON.stringify(state)); } catch { /* private mode */ } };
const randomToken = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, '0')).join('');
const clientToken = (() => { try { const t = sessionStorage.getItem('veda-client') || randomToken(); sessionStorage.setItem('veda-client', t); return t; } catch { return randomToken(); } })();
const inr = (minor) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(Math.round(minor / 100));
const bedroomsFor = (size) => ({ '1BHK': 1, '2BHK': 2, '3BHK': 3, '4BHK': 4 }[size] || 4);

// --- navigation ---------------------------------------------------------------------------------------------------------

function show(step) {
  state.step = step;
  document.querySelectorAll('.est-step').forEach((s) => { s.hidden = Number(s.dataset.step) !== step; });
  document.querySelectorAll('.est-steps li').forEach((li) => {
    const n = Number(li.dataset.stepLabel);
    li.classList.toggle('done', n < step);
    if (n === Math.min(step, 6)) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
  });
  clearSummary();
  const heading = document.querySelector(`[data-step="${step}"] h2`) || document.querySelector(`[data-step="${step}"]`);
  heading?.focus();
  save();
}
function clearSummary() { const s = $('#est-summary'); s.hidden = true; s.replaceChildren(); }
function summary(messages) {
  const s = $('#est-summary');
  s.replaceChildren(el('p', { text: 'Please check the following:' }), el('ul', {}, ...messages.map((m) => el('li', { text: m }))));
  s.hidden = false;
  s.focus();
}

// --- step 2: rooms and products -------------------------------------------------------------------------------------------

function renderRooms() {
  const box = $('#est-rooms');
  const beds = bedroomsFor(state.home.home_size);
  const selected = new Set(state.items.map((i) => `${i.room}:${i.product}`));
  box.replaceChildren();
  for (const [room, label, minBeds] of ROOMS) {
    if (BEDROOMS.includes(room) && minBeds > beds) continue;
    const products = Object.entries(PRODUCTS).filter(([, p]) => p.rooms.includes(room));
    const fs = el('fieldset', { class: 'est-room' }, el('legend', { text: label }));
    for (const [code, p] of products) {
      const id = `pick-${room}-${code}`;
      fs.append(el('label', { class: 'choice', for: id }, el('input', { type: 'checkbox', id, name: 'pick', value: `${room}:${code}`, checked: selected.has(`${room}:${code}`) }), ` ${p.label}`));
    }
    box.append(fs);
  }
}

// --- step 3: measurements ---------------------------------------------------------------------------------------------------

function itemTitle(item) {
  const room = ROOMS.find(([r]) => r === item.room)?.[1] || item.room;
  return `${room} – ${PRODUCTS[item.product].label}`;
}
function renderMeasurements() {
  const box = $('#est-measurements');
  box.replaceChildren();
  const withInputs = state.items.filter((i) => PRODUCTS[i.product].inputs.length);
  if (!withInputs.length) box.append(el('p', { text: 'Nothing to measure for your selection.' }));
  state.items.forEach((item, idx) => {
    const p = PRODUCTS[item.product];
    if (!p.inputs.length) return;
    const fs = el('fieldset', { class: 'est-item' }, el('legend', { text: itemTitle(item) }));
    for (const input of p.inputs) {
      const m = item.measurements[input.name] || { typical: true, value: '', unit: UNITS[input.kind][0][0] };
      const base = `m-${idx}-${input.name}`;
      const typical = el('input', { type: 'checkbox', id: `${base}-t`, 'data-item': idx, 'data-input': input.name, 'data-role': 'typical', checked: m.typical });
      const value = el('input', { type: 'number', id: `${base}-v`, inputmode: 'decimal', min: '0', step: 'any', value: m.value, 'data-item': idx, 'data-input': input.name, 'data-role': 'value', 'aria-describedby': `${base}-h`, disabled: m.typical });
      const unit = el('select', { id: `${base}-u`, 'data-item': idx, 'data-input': input.name, 'data-role': 'unit', 'aria-label': `${input.label} unit`, disabled: m.typical }, ...UNITS[input.kind].map(([v, l]) => el('option', { value: v, selected: v === m.unit, text: l })));
      typical.addEventListener('change', () => { value.disabled = unit.disabled = typical.checked; if (!typical.checked) value.focus(); });
      fs.append(el('div', { class: 'est-measure' },
        el('label', { for: `${base}-v` }, `${input.label} `, value), unit,
        el('label', { class: 'choice', for: `${base}-t` }, typical, ' Use a typical size'),
        el('p', { class: 'hint', id: `${base}-h`, text: input.hint })));
    }
    box.append(fs);
  });
}
function readMeasurements() {
  const problems = [];
  state.items.forEach((item, idx) => {
    for (const input of PRODUCTS[item.product].inputs) {
      const typical = document.querySelector(`[data-item="${idx}"][data-input="${input.name}"][data-role="typical"]`).checked;
      const value = document.querySelector(`[data-item="${idx}"][data-input="${input.name}"][data-role="value"]`).value;
      const unit = document.querySelector(`[data-item="${idx}"][data-input="${input.name}"][data-role="unit"]`).value;
      const n = Number(value);
      if (!typical && !(n > 0)) problems.push(`${itemTitle(item)}: enter the ${input.label.toLowerCase()} or use a typical size.`);
      item.measurements[input.name] = { typical, value, unit };
    }
  });
  return problems;
}

// --- step 4: preferences -------------------------------------------------------------------------------------------------------

function renderPreferences() {
  const fs = $('#est-packages');
  fs.replaceChildren(el('legend', { text: 'Package' }));
  for (const [code, label, description] of PACKAGES) {
    const luxury = code === 'LUXURY';
    const on = luxury || enabledPackages.includes(code);
    const input = el('input', { type: 'radio', name: 'package', value: code, checked: state.package === code, disabled: !on });
    input.addEventListener('change', packageChanged);
    fs.append(el('label', { class: `choice package${on ? '' : ' unavailable'}` }, input,
      ` ${label} — ${luxury ? `${description} Priced after a design consultation.` : on ? description : 'pricing coming soon'}`));
  }
  packageChanged();
  const box = $('#est-options');
  box.replaceChildren();
  state.items.forEach((item, idx) => {
    const p = PRODUCTS[item.product];
    if (!p.options.length) return;
    const fs2 = el('fieldset', { class: 'est-item' }, el('legend', { text: itemTitle(item) }));
    for (const [name, label, choices] of p.options) {
      const id = `o-${idx}-${name}`;
      const current = item.options[name] || choices[0][0];
      fs2.append(el('label', { for: id }, `${label} `, el('select', { id, 'data-item': idx, 'data-option': name }, ...choices.map(([v, l]) => el('option', { value: v, selected: v === current, text: l })))));
    }
    box.append(fs2);
  });
}
function packageChanged() {
  const luxury = document.querySelector('input[name="package"]:checked')?.value === 'LUXURY';
  $('#est-calculate').textContent = luxury ? 'Request a design consultation →' : 'See my estimate →';
  $('#est-turnstile-estimate').hidden = luxury;
}
function readPreferences() {
  state.package = document.querySelector('input[name="package"]:checked')?.value || 'ESSENTIAL';
  document.querySelectorAll('[data-option]').forEach((s) => { state.items[Number(s.dataset.item)].options[s.dataset.option] = s.value; });
}

// --- Turnstile (one widget per request: tokens are single use) ------------------------------------------------------------------

const widgets = {};
function loadTurnstile() {
  if (window.turnstile) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('turnstile'));
    document.head.appendChild(script);
  });
}
async function renderWidget(name, selector) {
  try {
    await loadTurnstile();
    if (widgets[name] === undefined) widgets[name] = window.turnstile.render(selector, { sitekey: meta('veda-turnstile-sitekey') });
    else window.turnstile.reset(widgets[name]);
  } catch { /* the request will be refused with CAPTCHA_FAILED and explained */ }
}
const token = (name) => (window.turnstile && widgets[name] !== undefined ? window.turnstile.getResponse(widgets[name]) : '') || '';

// --- API ------------------------------------------------------------------------------------------------------------------------

async function post(path, payload, headers = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch(`${apiBase}${path}`, {
      method: 'POST', signal: controller.signal, credentials,
      headers: { 'Content-Type': 'application/json', 'X-Veda-Client': clientToken, ...headers },
      body: JSON.stringify(payload),
    });
    return { status: res.status, body: await res.json().catch(() => ({})) };
  } catch (err) {
    return { status: 0, body: { code: err.name === 'AbortError' ? 'TIMEOUT' : 'OFFLINE' } };
  } finally { clearTimeout(timer); }
}
const MESSAGES = {
  CAPTCHA_FAILED: 'We couldn’t verify this request. Please complete the check and try again.',
  RATE_LIMITED: 'We’re receiving a lot of requests right now. Please try again in a minute.',
  ESTIMATOR_UNAVAILABLE: 'Estimates are not available right now. Please contact us instead.',
  TIMEOUT: 'This is taking longer than expected. Please try again.',
  OFFLINE: 'You appear to be offline.',
};
function requestBody() {
  return {
    property_type: state.home.property_type, home_size: state.home.home_size, project_kind: state.home.project_kind,
    city: state.home.city || null, package: state.package,
    selections: state.items.map((i) => ({
      room: i.room, product: i.product, options: i.options,
      measurements: Object.fromEntries(Object.entries(i.measurements).filter(([, m]) => !m.typical).map(([k, m]) => [k, { value: Number(m.value), unit: m.unit }])),
    })),
    turnstile_token: token('estimate'),
  };
}
function explain(body) {
  if (body.code === 'VALIDATION_FAILED' && Array.isArray(body.errors)) {
    return body.errors.map((e) => {
      const match = /^selections\[(\d+)\]/.exec(e.field || '');
      const item = match ? state.items[Number(match[1])] : null;
      return item ? `${itemTitle(item)}: ${e.message}` : e.message;
    });
  }
  return [MESSAGES[body.code] || 'Something went wrong on our side. Please try again.'];
}

// --- step 5: result ---------------------------------------------------------------------------------------------------------------

function list(selector, items) { $(selector).replaceChildren(...items.map((t) => el('li', { text: t }))); }
function renderResult(e) {
  $('#est-result-title').textContent = e.title;
  $('#est-disclaimer').textContent = e.disclaimer;
  list('#est-subject-to', e.subject_to);
  $('#est-range').textContent = `${inr(e.range.low_minor)} – ${inr(e.range.high_minor)}`;
  $('#est-gst').textContent = `Plus GST at ${e.gst.pct}%: about ${inr(e.gst.low_minor)} – ${inr(e.gst.high_minor)}.`;
  $('#est-rooms-table').replaceChildren(...e.rooms.map((r) => el('tr', {}, el('th', { scope: 'row', text: r.label }), el('td', { text: inr(r.amount_minor) }))));
  $('#est-prep-label').textContent = e.project_preparation.label;
  $('#est-prep-amount').textContent = inr(e.project_preparation.amount_minor);
  $('#est-prep-description').textContent = e.project_preparation.description;
  list('#est-prep-inclusions', e.project_preparation.inclusions);
  $('#est-prep-note').textContent = e.project_preparation.note;
  const optional = $('#est-optional');
  optional.hidden = !e.optional_items_minor;
  optional.textContent = e.optional_items_minor ? `Optional items you selected (included above): ${inr(e.optional_items_minor)}.` : '';
  const allowance = e.custom_features_allowance;
  $('#est-allowance-label').textContent = allowance.label;
  $('#est-allowance-range').textContent = `${inr(allowance.low_minor)} – ${inr(allowance.high_minor)}`;
  $('#est-allowance-description').textContent = allowance.description;
  $('#est-timeline').textContent = `${e.timeline.label} (about ${e.timeline.min_days}–${e.timeline.max_days} days after design approval).`;
  list('#est-assumptions', e.assumptions.length ? e.assumptions : ['All measurements were entered by you.']);
  list('#est-exclusions', e.exclusions);
  list('#est-client-scope', e.client_scope);
  list('#est-warranty', e.warranty.items);
  $('#est-warranty-note').textContent = e.warranty.note;
  const policy = $('#est-policy');
  if (e.warranty.policy_url) { policy.href = e.warranty.policy_url; policy.hidden = false; }
  $('#est-meta').textContent = `Estimate ${e.reference} · rate card ${e.rate_card_version} · valid until ${e.expires_on}.`;
}

function toEnquiry() {
  $('#eq-location').value = state.home.city || '';
  $('#eq-intro').textContent = state.luxury
    ? 'Luxury is priced after a design consultation. Our designer will call you to understand your home and arrange a site visit.'
    : 'Our designer will review your estimate with you, arrange a site measurement and prepare your detailed quotation.';
  $('#eq-back').textContent = state.luxury ? '← Back to preferences' : '← Back to my estimate';
  show(6);
  renderWidget('enquiry', '#est-turnstile-enquiry');
}

// --- wiring -----------------------------------------------------------------------------------------------------------------------

function init() {
  if (!apiBase) return; // off: the "coming soon" panel stays
  $('#est-off').hidden = true;
  $('#est-app').hidden = false;
  try { Object.assign(state, JSON.parse(sessionStorage.getItem(STATE_KEY) || '{}')); } catch { /* fresh start */ }

  document.querySelectorAll('[data-back]').forEach((b) => b.addEventListener('click', () => {
    const back = { 2: 1, 3: 2, 4: 3, 5: 4, 6: state.luxury ? 4 : 5 }[state.step] || 1;
    if (back === 2) renderRooms(); if (back === 3) renderMeasurements(); if (back === 4) { renderPreferences(); renderWidget('estimate', '#est-turnstile-estimate'); }
    show(back);
  }));

  $('#step-1').addEventListener('submit', (ev) => {
    ev.preventDefault();
    const f = new FormData(ev.target);
    state.home = { property_type: f.get('property_type'), home_size: f.get('home_size'), project_kind: f.get('project_kind'), city: String(f.get('city') || '').trim() };
    renderRooms();
    show(2);
  });
  $('#step-2').addEventListener('submit', (ev) => {
    ev.preventDefault();
    const picks = [...document.querySelectorAll('input[name="pick"]:checked')].map((c) => c.value);
    if (!picks.length) { summary(['Choose at least one room or product.']); return; }
    const previous = new Map(state.items.map((i) => [`${i.room}:${i.product}`, i]));
    state.items = picks.map((key) => { const [room, product] = key.split(':'); return previous.get(key) || { room, product, measurements: {}, options: {} }; });
    renderMeasurements();
    show(3);
  });
  $('#step-3').addEventListener('submit', (ev) => {
    ev.preventDefault();
    const problems = readMeasurements();
    if (problems.length) { summary(problems); return; }
    renderPreferences();
    show(4);
    renderWidget('estimate', '#est-turnstile-estimate');
  });
  $('#step-4').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    readPreferences();
    state.luxury = state.package === 'LUXURY';
    if (state.luxury) { toEnquiry(); return; }
    const button = $('#est-calculate');
    button.disabled = true;
    ev.target.setAttribute('aria-busy', 'true');
    const r = await post('/api/v1/public/estimates', requestBody());
    button.disabled = false;
    ev.target.removeAttribute('aria-busy');
    if (r.status === 201) {
      state.estimate = r.body.data;
      state.enquiryKey = null;
      renderResult(state.estimate);
      show(5);
      return;
    }
    renderWidget('estimate', '#est-turnstile-estimate');
    summary(explain(r.body));
  });
  $('#est-to-quote').addEventListener('click', toEnquiry);
  $('#step-6').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const f = new FormData(ev.target);
    const problems = [];
    if (!String(f.get('name') || '').trim()) problems.push('Enter your name.');
    if (String(f.get('phone') || '').replace(/\D/g, '').length < 10) problems.push('Enter a valid phone number.');
    if (!f.get('consent')) problems.push('Please agree to be contacted so we can prepare your quotation.');
    if (problems.length) { summary(problems); return; }
    state.enquiryKey = state.enquiryKey || `est-${randomToken()}`;
    save();
    const button = $('#eq-submit');
    button.disabled = true;
    const r = await post('/api/v1/public/enquiries', {
      name: String(f.get('name')).trim(), phone: String(f.get('phone')).trim(), email: String(f.get('email') || '').trim() || null,
      city: String(f.get('location') || '').trim() || null, preferred_contact: f.get('preferred_contact'),
      message: state.luxury ? `Requested a Luxury design consultation for: ${state.items.map(itemTitle).join(', ')}.`.slice(0, 500) : `Requested a detailed quotation after Budgetary Estimate ${state.estimate.reference}.`,
      consent: { acknowledged: true, policy_version: meta('veda-policy-version') },
      estimate_reference: state.luxury ? null : state.estimate.reference, company_website_url: String(f.get('company_website_url') || ''),
      ...(state.luxury ? { consultation: 'LUXURY_DESIGN' } : {}),
      turnstile_token: token('enquiry'),
      attribution: { form_page: '/estimate', landing_page: location.pathname },
    }, { 'Idempotency-Key': state.enquiryKey });
    button.disabled = false;
    if (r.status === 201) {
      $('#eq-reference').textContent = r.body.data.reference;
      $('#eq-estimate-line').hidden = state.luxury;
      if (!state.luxury) $('#eq-estimate-reference').textContent = state.estimate.reference;
      show(7);
      try { sessionStorage.removeItem(STATE_KEY); } catch { /* ignore */ }
      return;
    }
    renderWidget('enquiry', '#est-turnstile-enquiry');
    summary(explain(r.body));
  });

  if (state.estimate && !state.luxury && state.step >= 5 && state.step <= 6) { renderResult(state.estimate); show(5); } else show(1);
}

init();
