// Estimator UX V2 clickable prototype (docs/implementation/estimator/ESTIMATOR-UX-V2.md §3).
// No API calls and no real rates: ITEM amounts are illustrative, from the SYNTHETIC test card through the real engine
// (3 BHK, typical sizes). The calculation mirrors the engine's structure (typical-size band −15/+25 %, measured band
// −10/+15 %, Custom Features Allowance 5–15 % of room work, grouped preparation package, GST 18 % separate), not its
// prices. DOM built with textContent only.
'use strict';

const $ = (s) => document.querySelector(s);
const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k === 'text') n.textContent = v; else n.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids) if (k) n.append(k);
  return n;
};
const inr = (r) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(r);
const lakh = (r) => `₹${(r / 100000).toFixed(1)} L`;
// Room subtotals: lakh with two decimals from ₹1 lakh (₹1.16 L), rupees below (₹35,000).
const roomAmount = (r) => (r >= 100000 ? `₹${(r / 100000).toFixed(2)} L` : inr(r));

// --- room bundles (§3.2): item → illustrative amount (₹), engine product, per-home limit group ------------------------
const ITEMS = {
  kitchen: { label: 'Modular kitchen with wall units and loft', amount: 116340, product: 'KITCHEN' },
  pantry: { label: 'Tall pantry storage', amount: 21000, product: 'STORAGE_BOXES' },
  living_tv: { label: 'TV unit with wall panelling', amount: 72205, product: 'TV_UNIT' },
  living_wall: { label: 'Feature wall', amount: 57600, product: 'FEATURE_WALL' },
  living_beading: { label: 'Sofa-back beading', amount: 8000, product: 'VENEER_ACCENTS' },
  living_partition: { label: 'Partition', amount: 48000, product: 'PARTITION' },
  living_window: { label: 'Window seating', amount: 46000, product: 'WINDOW_SEATING' },
  dining_crockery: { label: 'Crockery unit', amount: 35000, product: 'CROCKERY_UNIT' },
  dining_basin: { label: 'Wash-basin unit', amount: 18400, product: 'VANITY_UNIT' },
  dining_wall: { label: 'Feature wall', amount: 57600, product: 'FEATURE_WALL' },
  dining_arch: { label: 'Veneer arch', amount: 18000, product: 'VENEER_ACCENTS' },
  wardrobe: { label: 'Wardrobe with loft', amount: 54300, product: 'WARDROBE' },
  bed_king: { label: 'King bed with storage', amount: 58000, product: 'BED' },
  bed_queen: { label: 'Queen bed with storage', amount: 52000, product: 'BED' },
  bath_vanity: { label: 'Bathroom vanity', amount: 13000, product: 'VANITY_UNIT' },
  dressing: { label: 'Dressing unit', amount: 18400, product: 'VANITY_UNIT' },
  study: { label: 'Study desk', amount: 22500, product: 'STUDY_UNIT' },
  bed_tv: { label: 'TV unit', amount: 10955, product: 'TV_UNIT' },
  bed_window: { label: 'Window seating', amount: 46000, product: 'WINDOW_SEATING' },
  bed_wall: { label: 'Feature wall', amount: 57600, product: 'FEATURE_WALL' },
  bedside: { label: 'Bedside table', amount: 9000, product: 'STORAGE_BOXES' },
  pooja: { label: 'Pooja unit with doors', amount: 43500, product: 'POOJA_UNIT' },
  asta: { label: 'Ceiling asta chakra', amount: 12000, product: null },
  utility: { label: 'Utility unit', amount: 13000, product: 'UTILITY' },
  ceiling: { label: 'False ceiling with lights', amount: 87750, product: 'FALSE_CEILING' },
  profile: { label: 'Profile lighting', amount: 36000, product: 'CEILING_PROFILE_LIGHTING' },
  painting: { label: 'Painting', amount: 87500, product: 'PAINTING', optional: true },
  electrical: { label: 'Electrical work', amount: 49000, product: 'ELECTRICAL', optional: true },
};
const BEDROOM = (bed) => ({ includes: ['wardrobe', bed, 'bath_vanity'], extras: [
  { id: 'dressing' }, { id: 'study' }, { id: 'bed_tv' }, { id: 'bed_window' }, { id: 'bed_wall' }, { id: 'bedside', count: 2 }] });
const ROOMS = [
  { id: 'kitchen', label: 'Kitchen', includes: ['kitchen'], extras: [{ id: 'pantry' }] },
  { id: 'living', label: 'Living room', includes: ['living_tv'], extras: [{ id: 'living_wall' }, { id: 'living_beading' }, { id: 'living_partition' }, { id: 'living_window' }] },
  { id: 'dining', label: 'Dining', includes: ['dining_crockery'], extras: [{ id: 'dining_basin' }, { id: 'dining_wall' }, { id: 'dining_arch' }] },
  { id: 'master', label: 'Master bedroom', ...BEDROOM('bed_king') },
  { id: 'bed2', label: 'Bedroom 2', ...BEDROOM('bed_queen') },
  { id: 'bed3', label: 'Bedroom 3', ...BEDROOM('bed_queen') },
  { id: 'pooja', label: 'Pooja room', includes: ['pooja'], extras: [{ id: 'asta' }] },
  { id: 'utility', label: 'Utility', includes: ['utility'], extras: [] },
  { id: 'whole', label: 'Whole home', includes: ['ceiling', 'profile'], extras: [{ id: 'painting', note: 'optional' }, { id: 'electrical', note: 'optional' }] },
];
// Engine limits, enforced here so no request can be refused (§3.2, U2-10).
const LIMITS = { VANITY_UNIT: 6, STORAGE_BOXES: 10, FEATURE_WALL: 6, WINDOW_SEATING: 6, TV_UNIT: 6, _TOTAL: 40 };
const PREP = 70000;
// Refinement (§2 screen 8): the measurements that move the price most; illustrative linear scaling of that item.
const REFINE = [
  { room: 'kitchen', item: 'kitchen', label: 'Kitchen counter length', typical: 12, unit: 'ft', hint: 'Along every wall with a counter.' },
  { room: 'master', item: 'wardrobe', label: 'Master bedroom wardrobe width', typical: 6, unit: 'ft', hint: 'Wall-to-wall width of the wardrobe.' },
  { room: 'living', item: 'living_tv', label: 'Living room TV wall width', typical: 7, unit: 'ft', hint: 'Width of the wall behind the TV.' },
  { room: 'whole', item: 'ceiling', label: 'False ceiling area', typical: 1300, unit: 'sq ft', hint: 'Usually close to the carpet area.' },
];

// --- state ------------------------------------------------------------------------------------------------------------
const KEY = 'veda-estimator-v2-prototype';
const fresh = () => ({
  screen: 1, type: 'APARTMENT', bhk: '3BHK', kind: 'NEW_HOME', city: '', pkg: 'ESSENTIAL', consult: false,
  rooms: Object.fromEntries(ROOMS.map((r) => [r.id, { on: true, extras: {} }])), measures: {}, estimate: null, events: [], started: Date.now(),
});
let state;
try { state = Object.assign(fresh(), JSON.parse(sessionStorage.getItem(KEY) || '{}')); } catch { state = fresh(); }
let frozen = false; // set while resetting, so a pending event cannot save the old state back
const save = () => { if (frozen) return; try { sessionStorage.setItem(KEY, JSON.stringify(state)); } catch { /* private mode */ } };
const log = (type, detail = {}) => { state.events.push({ t: Date.now() - state.started, screen: state.screen, type, ...detail }); save(); };

// --- selection model --------------------------------------------------------------------------------------------------
function selectedItems() {
  const out = [];
  for (const room of ROOMS) {
    const r = state.rooms[room.id];
    if (!r.on) continue;
    for (const id of room.includes) out.push({ room: room.id, id });
    for (const x of room.extras) {
      const v = r.extras[x.id];
      const n = x.count ? (v || 0) : (v ? 1 : 0);
      for (let i = 0; i < n; i += 1) out.push({ room: room.id, id: x.id });
    }
  }
  return out;
}
function usage(items = selectedItems()) {
  const u = { _TOTAL: items.filter((i) => ITEMS[i.id].product).length };
  for (const i of items) { const p = ITEMS[i.id].product; if (p) u[p] = (u[p] || 0) + 1; }
  return u;
}
function canAdd(id) {
  const u = usage();
  const p = ITEMS[id].product;
  if (!p) return true;
  return u._TOTAL + 1 <= LIMITS._TOTAL && (!(p in LIMITS) || (u[p] || 0) + 1 <= LIMITS[p]);
}

// --- illustrative calculation (mirrors the engine's structure) ---------------------------------------------------------
function calculate() {
  const items = selectedItems();
  let low = 0, high = 0, base = 0, work = 0;
  const rooms = {};
  const assumptions = [];
  for (const i of items) {
    const item = ITEMS[i.id];
    const ref = REFINE.find((f) => f.room === i.room && f.item === i.id);
    const measured = ref && Number(state.measures[`${i.room}:${i.id}`]) > 0;
    const amount = measured ? Math.round(item.amount * Number(state.measures[`${i.room}:${i.id}`]) / ref.typical) : item.amount;
    const [lo, hi] = measured ? [0.10, 0.15] : [0.15, 0.25];
    base += amount; low += amount * (1 - lo); high += amount * (1 + hi);
    if (!item.optional) work += amount;
    rooms[i.room] = (rooms[i.room] || 0) + amount;
    if (ref && !measured) assumptions.push(`${ROOMS.find((r) => r.id === i.room).label}: ${ref.label.toLowerCase()} assumed ${ref.typical} ${ref.unit} (typical for a 3 BHK).`);
  }
  const prep = work > 0 ? PREP : 0;
  const allowance = [Math.round(work * 0.05), Math.round(work * 0.15)];
  base += prep + Math.round(work * 0.10);
  low = Math.floor((low + prep * 0.9 + allowance[0]) / 5000) * 5000;
  high = Math.ceil((high + prep * 1.15 + allowance[1]) / 5000) * 5000;
  assumptions.push('Other items use typical 3 BHK sizes; a site measurement confirms them.');
  const r1000 = (v) => Math.round(v / 1000) * 1000;
  return { low, high, base, prep, allowance: [Math.floor(allowance[0] / 1000) * 1000, Math.ceil(allowance[1] / 1000) * 1000],
    rooms: Object.entries(rooms).map(([id, v]) => ({ id, amount: r1000(v) })), assumptions,
    reference: `PROTO-${String(state.events.length).padStart(4, '0')}`, items: items.length };
}

// --- screens ------------------------------------------------------------------------------------------------------------
const FLOW = { 1: 2, 2: 3, 3: 4, 4: 5 };
function show(n, { focus = true } = {}) {
  state.screen = n; save(); log('screen');
  document.querySelectorAll('.screen').forEach((s) => { s.hidden = Number(s.dataset.screen) !== n; });
  const step = n <= 5 ? n : 0;
  $('#progress').hidden = !step;
  if (step) { $('#progress-text').textContent = `Step ${step} of 5`; $('#progress-fill').className = `w${step}`; }
  if (n === 4) renderRooms();
  if (n === 6) renderResult();
  if (n === 7) renderLead();
  if (n === 8) renderRefine();
  if (n === 5) renderPackage();
  if (n === 10) renderSpec();
  if (focus) document.querySelector(`[data-screen="${n}"] [tabindex="-1"]`)?.focus();
  window.scrollTo(0, 0);
}

function renderRooms() {
  const box = $('#rooms');
  box.replaceChildren();
  for (const room of ROOMS) {
    const r = state.rooms[room.id];
    const toggle = el('input', { type: 'checkbox', role: 'switch', 'aria-label': `Include ${room.label}`, checked: r.on });
    toggle.addEventListener('change', () => { r.on = toggle.checked; log('room', { room: room.id, on: r.on }); state.estimate = null; renderRooms(); });
    const card = el('article', { class: `room${r.on ? '' : ' off'}`, 'aria-label': room.label },
      el('div', { class: 'room-head' }, el('h3', { text: room.label }), el('label', { class: 'toggle' }, el('span', { text: r.on ? 'Included' : 'Not included' }), toggle)),
      el('p', { class: 'includes', text: room.includes.map((id) => ITEMS[id].label).join(' · ') }));
    if (room.extras.length) {
      // Extras stay folded until wanted, so the list of rooms reads as a home, not a catalogue.
      const chosen = room.extras.filter((x) => (x.count ? r.extras[x.id] > 0 : r.extras[x.id])).length;
      const details = el('details', { class: 'extras', open: state.openExtras?.[room.id] || false },
        el('summary', { text: chosen ? `Extras (${chosen} added)` : `Add extras (${room.extras.length})` }));
      details.addEventListener('toggle', () => { state.openExtras = { ...(state.openExtras || {}), [room.id]: details.open }; save(); });
      const extras = el('div', { class: 'extras-list' });
      details.append(extras);
      for (const x of room.extras) {
        const item = ITEMS[x.id];
        const label = `${item.label}${x.note ? ` (${x.note})` : ''}`;
        if (x.count) {
          const v = r.extras[x.id] || 0;
          const atLimit = !canAdd(x.id);
          const minus = el('button', { type: 'button', 'aria-label': `Fewer ${item.label.toLowerCase()}s`, 'aria-disabled': v === 0 ? 'true' : null, text: '−' });
          const plus = el('button', { type: 'button', 'aria-label': `More ${item.label.toLowerCase()}s`, 'aria-disabled': v >= x.count || atLimit ? 'true' : null, text: '+' });
          const out = el('output', { 'aria-live': 'polite', text: String(v) });
          minus.addEventListener('click', () => { if (v > 0) { r.extras[x.id] = v - 1; log('extra', { room: room.id, id: x.id, n: v - 1 }); state.estimate = null; renderRooms(); } });
          plus.addEventListener('click', () => { if (v < x.count && !atLimit) { r.extras[x.id] = v + 1; log('extra', { room: room.id, id: x.id, n: v + 1 }); state.estimate = null; renderRooms(); } });
          extras.append(el('div', { class: `extra${atLimit && v < x.count ? ' limit' : ''}` }, el('span', {}, `${item.label}s`, atLimit && v < x.count ? el('small', { text: 'Limit reached for your home' }) : null), el('span', { class: 'stepper' }, minus, out, plus)));
        } else {
          const on = !!r.extras[x.id];
          const blocked = !on && !canAdd(x.id);
          const id = `x-${room.id}-${x.id}`;
          const box2 = el('input', { type: 'checkbox', id, checked: on, disabled: blocked, 'aria-describedby': blocked ? `${id}-l` : null });
          box2.addEventListener('change', () => { r.extras[x.id] = box2.checked; log('extra', { room: room.id, id: x.id, on: box2.checked }); state.estimate = null; renderRooms(); });
          extras.append(el('label', { class: `extra${blocked ? ' limit' : ''}`, for: id }, el('span', {}, `+ ${label}`, blocked ? el('small', { id: `${id}-l`, text: 'Limit reached for your home' }) : null), box2));
        }
      }
      card.append(details);
    }
    box.append(card);
  }
  const anyOn = ROOMS.some((room) => state.rooms[room.id].on);
  $('#rooms-next').setAttribute('aria-disabled', anyOn ? 'false' : 'true');
  $('#rooms-hint').textContent = anyOn ? '' : 'Turn on at least one room to continue.';
}

// --- trust layer: specification, labels, copy -------------------------------------------------------------------
const params = new URLSearchParams(location.search);
const SPEC_KEYS = { oct: 'candidate-oct-2026', jun: 'candidate-jun-2026' };
const specFor = () => window.VEDA_SPECS[SPEC_KEYS[state.specChoice] || 'baseline'];
const LABELS = {
  A: { prep: 'Project Preparation & Protection Package', allowance: 'Custom Features Allowance' },
  B: { prep: 'Site Execution & Handover Package', allowance: 'Design Personalisation Allowance' },
};
const ROOM_SPEC = { whole: ['ceiling'], default: ['structure', 'surface', 'hardware'] };
const roomSpecSummary = (roomId) => (ROOM_SPEC[roomId] || ROOM_SPEC.default)
  .map((id) => specFor().categories.find((c) => c.id === id && c.rooms.includes(roomId))?.summary).filter(Boolean).join(' · ');
const PREP_PARTS = ['Site and floor protection', 'Plywood and material protection', 'Freight and material handling', 'Debris handling', 'Completion deep cleaning', 'Pest-control preparation where applicable'];
const WHY_RANGE = ['Typical sizes are used until you share measurements', 'How much your design is personalised', 'The final configuration of each unit', 'The finishes and accessories you select', 'The physical site measurement', 'The quantities actually executed', 'Site conditions'];
const COMPARE = ['Product sizes', 'Cabinet material (carcass)', 'Door material and finish', 'Hardware brand and type', 'What each room includes', 'Installation', 'Freight and handling', 'Protection and cleaning', 'Taxes (GST)', 'Items you supply (sink, tiles, granite, taps)', 'What is excluded'];
const WARRANTY = [
  'Materials: the manufacturer’s warranty for the exact product supplied, on the manufacturer’s terms.',
  'Hardware: hinges and channels up to 5 years and kitchen drawers up to 3 years against manufacturing defects, as set out in our policy.',
  'Electrical items: 1 year, or the period the manufacturer documents for the item.',
  'Service: one year of free service from handover for fitment or workmanship issues within our scope.',
];
const NOT_INCLUDED = ['Civil work, appliances, loose furniture and décor', 'Sink, tiles, granite and taps are supplied by you'];
const variant = () => (state.variant === 'A' ? 'A' : 'B');

const section = (title, ...kids) => el('section', { class: 'block', 'aria-label': title }, el('h3', { text: title }), ...kids);
const disclosure = (title, ...kids) => el('details', { class: 'more' }, el('summary', { text: title }), ...kids);
const list = (items, cls) => el('ul', { class: cls || null }, ...items.map((t) => el('li', { text: t })));
const button = (cls, text, onClick) => { const b = el('button', { class: cls, type: 'button', text }); b.addEventListener('click', onClick); return b; };

function promiseList() {
  return el('dl', { class: 'promise' }, ...specFor().categories.flatMap((c) => [el('dt', { text: c.label }), el('dd', { text: c.promise })]));
}
function specButton() { return button('link', 'View detailed material specification →', () => { state.specReturn = state.screen; show(10); }); }

function renderResult() {
  const e = state.estimate;
  if (!e) return;
  const v = variant();
  const L = LABELS[v];
  log('variant_shown', { variant: v, spec: state.specChoice || 'baseline' });
  $('#range').textContent = `${inr(e.low)} – ${inr(e.high)}`;
  $('#gst').textContent = `Plus GST at 18%: about ${lakh(e.low * 0.18)} – ${lakh(e.high * 0.18)}`;
  const measured = Object.values(state.measures).some((x) => Number(x) > 0);
  $('#basis').textContent = `3 BHK apartment · ${state.kind === 'NEW_HOME' ? 'New home' : 'Renovation'} · Essential · ${measured ? 'Some of your measurements' : 'Based on typical 3 BHK sizes'}`;
  const inc = $('#included-line');
  inc.hidden = v !== 'B';
  inc.textContent = v === 'B' ? `Included in this range: your rooms, the ${L.prep} and the ${L.allowance}. GST is extra.` : '';
  const toQuote = () => { state.consult = false; log('cta', { cta: 'quotation', variant: v }); show(7); };
  const toRefine = () => { log('cta', { cta: 'refine', variant: v }); show(8); };
  const toDesigner = () => { state.consult = true; state.consultReason = 'designer'; log('cta', { cta: 'designer', variant: v }); show(7); };
  $('#cta').replaceChildren(...(v === 'B'
    ? [button('primary wide', 'Personalise and narrow my estimate', toRefine), button('ghost wide', 'Get a detailed quotation', toQuote), button('link', 'Talk to a designer', toDesigner)]
    : [button('primary wide', 'Get my detailed quotation →', toQuote), button('ghost wide', 'Tighten your range (optional)', toRefine)]));
  const roomsOn = e.rooms.map((r) => ({ ...r, room: ROOMS.find((x) => x.id === r.id), items: selectedItems().filter((i) => i.room === r.id) }));
  const body = v === 'B' ? resultB(e, L, roomsOn) : resultA(e, L, roomsOn);
  $('#result-body').replaceChildren(...body);
  $('#meta').textContent = `Estimate ${e.reference} · valid for 30 days`;
}

function roomItems(r) {
  const std = r.room.includes.map((id) => ITEMS[id].label);
  const extras = [...new Set(r.items.filter((i) => !r.room.includes.includes(i.id)).map((i) => ITEMS[i.id].label))];
  return { std, extras };
}

function resultA(e, L, rooms) {
  const table = el('table', { class: 'totals' }, el('caption', { class: 'sr', text: 'Room subtotals' }), el('tbody', {}, ...rooms.map((r) => {
    const { std, extras } = roomItems(r);
    return el('tr', {}, el('th', { scope: 'row' }, r.room.label, el('small', { text: [...std, ...extras].join(', ') }),
      el('small', { class: 'spec-line', text: `Essential: ${roomSpecSummary(r.id)}` })), el('td', { text: inr(r.amount) }));
  })));
  return [
    el('details', { open: true }, el('summary', { text: 'What’s included' }), table),
    el('details', {}, el('summary', { text: 'What Essential includes' }), promiseList(), specButton()),
    el('details', {}, el('summary', { text: L.prep }), el('p', { class: 'amount', text: inr(e.prep) }), list(PREP_PARTS), el('p', { class: 'small', text: 'One grouped value, included in the range above.' })),
    el('details', {}, el('summary', { text: L.allowance }), el('p', { class: 'amount', text: `${inr(e.allowance[0])} – ${inr(e.allowance[1])}` }),
      el('p', { text: 'Bespoke details usually added during design, such as extra drawers, mirrors, pelmets and lighting sensors. The detailed quotation replaces it with the actual items.' })),
    el('details', {}, el('summary', { text: 'Timeline, warranty and what’s not included' }), el('p', { text: 'Timeline: about 2½ months after design approval, plus up to 10 days’ grace.' }), list(WARRANTY), el('p', {}, el('a', { href: '/warranty', text: 'Full Warranty, Service & Customer Care Policy' })), list(NOT_INCLUDED)),
    el('details', {}, el('summary', { text: 'Assumptions' }), list(e.assumptions)),
  ];
}

function resultB(e, L, rooms) {
  const roomWork = rooms.reduce((sum, r) => sum + r.amount, 0);
  const roomCards = rooms.map((r) => {
    const { std, extras } = roomItems(r);
    const cats = specFor().categories.filter((c) => c.rooms.includes(r.id));
    return el('article', { class: 'room-card', 'aria-label': r.room.label },
      el('div', { class: 'room-row' }, el('h4', { text: r.room.label }), el('span', { class: 'room-amount', text: roomAmount(r.amount) })),
      el('p', { class: 'room-std', text: std.join(', ') }),
      extras.length ? el('p', { class: 'room-extras', text: `Your extras: ${extras.join(', ')}` }) : null,
      el('p', { class: 'spec-line' }, el('strong', { text: 'Essential specification: ' }), roomSpecSummary(r.id)),
      disclosure('View room details', list([...std, ...extras].map((t) => `${t} — sized to typical 3 BHK dimensions until measured`))),
      disclosure('View material details', ...cats.map((c) => el('div', { class: 'spec-cat' }, el('p', {}, el('strong', { text: `${c.label}: ` }), c.promise), list(c.details)))));
  });
  return [
    section('What Essential includes', promiseList(), specButton()),
    section('Your rooms', ...roomCards, el('p', { class: 'small', text: 'Room amounts are rounded and include installation. Rates are never shown on this page; your detailed quotation lists every item.' })),
    section(L.prep, el('p', { class: 'amount', text: inr(e.prep) }), el('p', { class: 'badge', text: 'Included in your estimated range' }),
      el('p', { text: 'The execution and handover work that protects your home during the project and completes it professionally.' }),
      disclosure('Why this is needed', el('p', { text: 'Interiors work brings materials, cutting and dust into a finished home. Protecting floors and materials, moving and clearing materials and debris, and a final deep clean are part of doing the work properly, so they are planned and shown rather than added later.' })),
      disclosure('View detailed breakdown', list(PREP_PARTS), el('p', { class: 'small', text: 'Your detailed quotation shows the amount for each item.' }))),
    section(L.allowance, el('p', { class: 'amount', text: `${inr(e.allowance[0])} – ${inr(e.allowance[1])}` }), el('p', { class: 'badge', text: 'Included in your estimated range' }),
      el('p', { text: 'This protects your planning budget for design additions most homeowners choose once the design takes shape. It is a planning allowance, not an automatic extra charge: your detailed quotation replaces it with only the items you approve.' }),
      disclosure('What it usually covers', list(['Extra drawers', 'Mirrors', 'Pelmets', 'Additional profile lighting', 'Lighting sensors', 'Extra internal storage', 'Selected accessories'])),
      disclosure('How it gets narrower', el('p', { text: 'Deciding these details with your designer turns the allowance into specific items. Sharing measurements narrows the rest of your range.' }))),
    section('How your range is built',
      el('dl', { class: 'build' },
        el('dt', { text: 'Your rooms (typical sizes)' }), el('dd', { text: inr(roomWork) }),
        el('dt', { text: `+ ${L.prep}` }), el('dd', { text: inr(e.prep) }),
        el('dt', { text: `+ ${L.allowance}` }), el('dd', { text: `${inr(e.allowance[0])} – ${inr(e.allowance[1])}` }),
        el('dt', { text: 'Planning range, allowing for actual sizes and site conditions' }), el('dd', { class: 'total', text: `${inr(e.low)} – ${inr(e.high)}` })),
      disclosure('Why is this a range?', el('p', { text: 'Your final price depends on:' }), list(WHY_RANGE)),
      button('ghost wide', 'Narrow my range', () => { log('cta', { cta: 'narrow', variant: 'B' }); show(8); })),
    // Reference sections stay one tap away, so the page stays short on a phone.
    el('section', { class: 'block reference', 'aria-label': 'More about this estimate' },
      el('details', { class: 'ref' }, el('summary', { text: 'Warranty' }), list(WARRANTY), el('p', {}, el('a', { href: '/warranty', text: 'Read the full Warranty, Service & Customer Care Policy, including exclusions' }))),
      el('details', { class: 'ref' }, el('summary', { text: 'Not included' }), list(NOT_INCLUDED)),
      el('details', { class: 'ref' }, el('summary', { text: 'How to compare this estimate' }), el('p', { text: 'Estimates only compare fairly when the scope is the same. Check each provider’s:' }), list(COMPARE)),
      el('details', { class: 'ref' }, el('summary', { text: 'Assumptions' }), list(e.assumptions))),
  ];
}

function renderSpec() {
  const s = specFor();
  $('#spec-sub').textContent = s.status === 'DRAFT' ? 'Shown here: what is agreed in both current specifications (draft for owner approval).' : `${s.title} (draft for owner approval).`;
  $('#spec-detail').replaceChildren(...s.categories.map((c) => el('section', { class: 'spec-cat' }, el('h3', { text: c.label }), el('p', { text: c.promise }), list(c.details))));
  $('#spec-equivalent').textContent = `${s.orEquivalent}.`;
}

function renderPackage() {
  $('#pkg-promise').replaceChildren(...specFor().categories.map((c) => el('li', {}, el('strong', { text: `${c.label}: ` }), c.summary)));
}

function renderLead() {
  const c = state.consult;
  $('#h7').textContent = c ? 'Request a design consultation' : 'Get my detailed quotation';
  $('#lead-sub').textContent = c
    ? (state.consultReason === 'designer' ? 'A designer will call you to talk through your home, your estimate and your ideas.' : state.pkg === 'LUXURY' ? 'Luxury is priced after a design consultation. A designer will call you to understand your home.' : 'Online estimates for your home are coming soon. A designer will call you to understand your home.')
    : 'A designer will call you within one working day and arrange a free site measurement.';
  $('#send').textContent = c ? 'Request my consultation →' : 'Send my request →';
  $('#refine-link').hidden = c;
}

function renderRefine() {
  $('#h8').textContent = variant() === 'B' ? 'Personalise and narrow my estimate' : 'Tighten your range';
  const box = $('#refine-fields');
  box.replaceChildren();
  const items = selectedItems();
  for (const f of REFINE) {
    if (!items.some((i) => i.room === f.room && i.id === f.item)) continue;
    const key = `${f.room}:${f.item}`;
    const id = `m-${f.room}-${f.item}`;
    const input = el('input', { id, type: 'number', inputmode: 'decimal', min: '0', step: 'any', placeholder: `typical ${f.typical}`, value: state.measures[key] || '', 'aria-describedby': `${id}-h` });
    input.addEventListener('input', () => { state.measures[key] = input.value; save(); });
    box.append(el('label', { class: 'measure', for: id }, el('span', {}, f.label, input), el('span', { class: 'unit', text: f.unit }), el('small', { id: `${id}-h`, text: f.hint })));
  }
  $('#refined-range').textContent = state.estimate ? `${inr(state.estimate.low)} – ${inr(state.estimate.high)}` : '';
}

// --- wiring -------------------------------------------------------------------------------------------------------------
function readForm(n) {
  if (n === 1) state.type = document.querySelector('input[name="type"]:checked').value;
  if (n === 2) { state.bhk = document.querySelector('input[name="bhk"]:checked').value; state.city = $('#city').value.trim(); }
  if (n === 3) state.kind = document.querySelector('input[name="kind"]:checked').value;
}
document.querySelectorAll('[data-next]').forEach((b) => b.addEventListener('click', () => {
  const n = state.screen;
  if (n === 4 && b.getAttribute('aria-disabled') === 'true') { $('#rooms-hint').focus?.(); return; }
  readForm(n);
  show(FLOW[n]);
}));
document.querySelectorAll('[data-back]').forEach((b) => b.addEventListener('click', () => {
  const back = { 2: 1, 3: 2, 4: 3, 5: 4, 7: state.consult ? (state.consultReason === 'designer' ? 6 : state.pkg === 'LUXURY' ? 5 : 1) : 6 }[state.screen] || 1;
  show(back);
}));
document.querySelectorAll('[data-spec]').forEach((b) => b.addEventListener('click', () => { state.specReturn = state.screen; log('spec_opened'); show(10); }));
$('#spec-back').addEventListener('click', () => show(state.specReturn || 6));
document.querySelectorAll('[data-goto]').forEach((b) => b.addEventListener('click', () => show(Number(b.dataset.goto))));
document.querySelectorAll('[data-consult]').forEach((b) => b.addEventListener('click', () => { state.consult = true; state.consultReason = b.dataset.consult; log('consult', { reason: b.dataset.consult }); show(7); }));
document.querySelectorAll('input[name="pkg"]').forEach((r) => r.addEventListener('change', () => {
  state.pkg = r.value;
  $('#see-budget').textContent = r.value === 'LUXURY' ? 'Request a design consultation →' : 'See my budget →';
}));
$('#see-budget').addEventListener('click', () => {
  if (!$('#verify').checked) { $('#pkg-hint').textContent = 'Please complete the check above to continue.'; $('#verify').focus(); return; }
  $('#pkg-hint').textContent = '';
  if (state.pkg === 'LUXURY') { state.consult = true; state.consultReason = 'luxury'; log('consult', { reason: 'luxury' }); show(7); return; }
  state.consult = false;
  state.estimate = calculate();
  if (!state.firstEstimateAt) { state.firstEstimateAt = Date.now() - state.started; log('first_estimate', { ms: state.firstEstimateAt }); }
  show(6);
});
$('#update').addEventListener('click', () => { state.estimate = calculate(); log('refined', { measures: Object.keys(state.measures).filter((k) => Number(state.measures[k]) > 0).length }); renderRefine(); });
$('#lead').addEventListener('submit', (ev) => {
  ev.preventDefault();
  const problems = [];
  const mark = (id, msg) => { $(`#${id}`).setAttribute('aria-invalid', 'true'); $(`#${id}-err`).textContent = msg; problems.push({ id, msg }); };
  document.querySelectorAll('#lead [aria-invalid]').forEach((f) => f.removeAttribute('aria-invalid'));
  document.querySelectorAll('#lead .err').forEach((e) => { e.textContent = ''; });
  if (!$('#name').value.trim()) mark('name', 'Enter your name.');
  if ($('#phone').value.replace(/\D/g, '').length < 10) mark('phone', 'Enter a 10-digit phone number.');
  if (!$('#consent').checked) mark('consent', 'Please agree to be contacted.');
  if (!problems.length && !$('#verify2').checked) problems.push({ id: 'verify2', msg: 'Please complete the human check.' });
  const box = $('#lead-summary');
  if (problems.length) {
    box.replaceChildren(el('p', { text: 'Please check the following:' }), el('ul', {}, ...problems.map((p) => {
      const a = el('a', { href: `#${p.id}`, text: p.msg });
      a.addEventListener('click', (e) => { e.preventDefault(); $(`#${p.id}`).focus(); });
      return el('li', {}, a);
    })));
    box.hidden = false; box.focus(); log('lead_errors', { n: problems.length });
    return;
  }
  box.hidden = true;
  log('lead_sent', { consult: state.consult });
  $('#next-text').textContent = state.consult
    ? 'Our designer will call you within one working day to arrange your design consultation.'
    : 'Our designer will call you within one working day to go through your estimate and arrange a site measurement.';
  $('#estimate-ref').textContent = !state.consult && state.estimate ? `Keep your estimate reference ${state.estimate.reference} handy.` : '';
  show(9);
});
$('#restart').addEventListener('click', () => { const events = state.events; state = fresh(); state.events = events; log('restart'); save(); frozen = true; location.reload(); });

// Facilitator tools (?facilitator=1): time to first estimate, export of the anonymous event log, reset.
if (new URLSearchParams(location.search).get('facilitator') === '1') {
  $('#facilitator').hidden = false;
  const tick = () => {
    $('#ttfe').textContent = state.firstEstimateAt ? `${Math.round(state.firstEstimateAt / 1000)} s` : '—';
    $('#fvariant').textContent = variant();
    $('#fspec').textContent = specFor().id;
  };
  setInterval(tick, 1000); tick();
  $('#export').addEventListener('click', () => {
    const blob = new Blob([JSON.stringify({ prototype: 'estimator-v2', events: state.events, firstEstimateMs: state.firstEstimateAt || null }, null, 2)], { type: 'application/json' });
    const a = el('a', { href: URL.createObjectURL(blob), download: `estimator-v2-session-${Date.now()}.json` });
    document.body.append(a); a.click(); a.remove();
  });
  $('#reset').addEventListener('click', () => { frozen = true; try { sessionStorage.removeItem(KEY); } catch { /* ignore */ } location.reload(); });
}

// Experiment arms and specification candidate (facilitator or test link): ?variant=A|B, ?spec=oct|jun.
if (['A', 'B'].includes(params.get('variant'))) state.variant = params.get('variant');
if (!state.variant) state.variant = Math.random() < 0.5 ? 'A' : 'B';
if (['oct', 'jun'].includes(params.get('spec'))) state.specChoice = params.get('spec');
save();

// Restore the answers and the screen (a stale estimate is recalculated, never shown as old).
for (const [name, value] of [['type', state.type], ['bhk', state.bhk], ['kind', state.kind], ['pkg', state.pkg]]) {
  const r = document.querySelector(`input[name="${name}"][value="${value}"]`);
  if (r && !r.disabled) r.checked = true;
}
$('#city').value = state.city;
if (state.screen === 6 && !state.estimate) state.screen = 5;
show(state.screen, { focus: false });
