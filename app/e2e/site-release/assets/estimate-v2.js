// Veda Spaces Budgetary Estimate, customer experience V2 (docs/implementation/estimator/ESTIMATOR-UX-V2*.md).
// Runs only when <meta name="veda-estimator"> is "on" and <meta name="veda-estimator-ux"> is "v2" (staging build:
// STAGING_ESTIMATOR_UX=v2); V1 (estimate.js) runs otherwise. The same, unchanged API and engine: rooms and extras are
// sent as ordinary selections with no measurements (typical sizes) until the customer refines. No rates in this file;
// the DOM is built with textContent only.
'use strict';

(() => {
  const meta = (name) => document.querySelector(`meta[name="${name}"]`)?.content?.trim() || '';
  if (meta('veda-estimator') !== 'on' || meta('veda-estimator-ux') !== 'v2' || !meta('veda-turnstile-sitekey')) return;
  const apiBase = meta('veda-api-base');
  if (!apiBase) return;
  const credentials = meta('veda-api-credentials') === 'include' ? 'include' : 'same-origin';
  const list = (name, fallback) => (meta(name) || fallback).split(',').map((x) => x.trim()).filter(Boolean);
  const enabledPackages = list('veda-estimator-packages', 'ESSENTIAL');
  const homeSizes = list('veda-estimator-home-sizes', '3BHK');
  const propertyTypes = list('veda-estimator-property-types', 'APARTMENT');
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
  const rupees = (minor) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(Math.round(minor / 100));
  const roomAmount = rupees; // the same format as the build-up, so the rooms visibly add up

  // --- room bundles (ESTIMATOR-UX-V2 §3.2): customer words → unchanged engine selections ---------------------------
  const ROOM_CODE = { kitchen: 'KITCHEN', living: 'LIVING', dining: 'DINING', master: 'MASTER_BEDROOM', bed2: 'BEDROOM_2',
    bed3: 'BEDROOM_3', bed4: 'BEDROOM_4', pooja: 'POOJA', utility: 'UTILITY', whole: 'WHOLE_HOME' };
  const ITEMS = {
    kitchen: { label: 'Modular kitchen with wall units and loft', product: 'KITCHEN' },
    pantry: { label: 'Tall pantry storage', product: 'STORAGE_BOXES' },
    living_tv: { label: 'TV unit with wall panelling', product: 'TV_UNIT', options: { STYLE: 'PANELLED' } },
    living_wall: { label: 'Feature wall', product: 'FEATURE_WALL' },
    living_beading: { label: 'Sofa-back beading', product: 'VENEER_ACCENTS', options: { STYLE: 'BEADING' } },
    living_partition: { label: 'Partition', product: 'PARTITION' },
    living_window: { label: 'Window seating', product: 'WINDOW_SEATING' },
    dining_crockery: { label: 'Crockery unit', product: 'CROCKERY_UNIT' },
    dining_basin: { label: 'Wash-basin unit', product: 'VANITY_UNIT', options: { TYPE: 'DRESSER' } },
    dining_wall: { label: 'Feature wall', product: 'FEATURE_WALL' },
    dining_arch: { label: 'Veneer arch', product: 'VENEER_ACCENTS' },
    wardrobe: { label: 'Wardrobe with loft', product: 'WARDROBE' },
    bed_king: { label: 'King bed with storage', product: 'BED', options: { SIZE: 'KING' } },
    bed_queen: { label: 'Queen bed with storage', product: 'BED' },
    bath_vanity: { label: 'Bathroom vanity', product: 'VANITY_UNIT', options: { TYPE: 'TOILET' } },
    dressing: { label: 'Dressing unit', product: 'VANITY_UNIT', options: { TYPE: 'DRESSER' } },
    study: { label: 'Study desk', product: 'STUDY_UNIT' },
    bed_tv: { label: 'TV unit', product: 'TV_UNIT', options: { STYLE: 'BOX' } },
    bed_window: { label: 'Window seating', product: 'WINDOW_SEATING' },
    bed_wall: { label: 'Feature wall', product: 'FEATURE_WALL' },
    bedside: { label: 'Bedside table', product: 'STORAGE_BOXES', options: { TYPE: 'BEDSIDE_TABLE' } },
    pooja: { label: 'Pooja unit with doors', product: 'POOJA_UNIT' },
    asta: { label: 'Ceiling asta chakra', product: null }, // an option of the pooja unit, not a selection
    utility: { label: 'Utility unit', product: 'UTILITY' },
    ceiling: { label: 'False ceiling with lights', product: 'FALSE_CEILING' },
    profile: { label: 'Profile lighting', product: 'CEILING_PROFILE_LIGHTING' },
    painting: { label: 'Painting', product: 'PAINTING', optional: true },
    electrical: { label: 'Electrical work', product: 'ELECTRICAL', optional: true },
  };
  const BEDROOM = (bed) => ({ includes: ['wardrobe', bed, 'bath_vanity'],
    extras: [{ id: 'dressing' }, { id: 'study' }, { id: 'bed_tv' }, { id: 'bed_window' }, { id: 'bed_wall' }, { id: 'bedside', count: 2 }] });
  const ROOMS_BY_SIZE = {
    '3BHK': [
      { id: 'kitchen', label: 'Kitchen', includes: ['kitchen'], extras: [{ id: 'pantry' }] },
      { id: 'living', label: 'Living room', includes: ['living_tv'], extras: [{ id: 'living_wall' }, { id: 'living_beading' }, { id: 'living_partition' }, { id: 'living_window' }] },
      { id: 'dining', label: 'Dining', includes: ['dining_crockery'], extras: [{ id: 'dining_basin' }, { id: 'dining_wall' }, { id: 'dining_arch' }] },
      { id: 'master', label: 'Master bedroom', ...BEDROOM('bed_king') },
      { id: 'bed2', label: 'Bedroom 2', ...BEDROOM('bed_queen') },
      { id: 'bed3', label: 'Bedroom 3', ...BEDROOM('bed_queen') },
      { id: 'pooja', label: 'Pooja room', includes: ['pooja'], extras: [{ id: 'asta' }] },
      { id: 'utility', label: 'Utility', includes: ['utility'], extras: [] },
      { id: 'whole', label: 'Whole home', includes: ['ceiling', 'profile'], extras: [{ id: 'painting', note: 'optional' }, { id: 'electrical', note: 'optional' }] },
    ],
  };
  // Engine limits enforced here, so no request can be refused (ESTIMATOR-UX-V2 §3.2).
  const LIMITS = { VANITY_UNIT: 6, STORAGE_BOXES: 10, FEATURE_WALL: 6, WINDOW_SEATING: 6, TV_UNIT: 6, _TOTAL: 40 };
  // Refinement: the measurements that move the price most, in customer words (feet and square feet only).
  const REFINE = [
    { room: 'kitchen', item: 'kitchen', input: 'RUN', label: 'Kitchen counter length', unit: 'ft', min: 0.5, max: 150, hint: 'Total length along every wall with a counter.' },
    { room: 'master', item: 'wardrobe', input: 'WIDTH', label: 'Master bedroom wardrobe width', unit: 'ft', min: 0.5, max: 150, hint: 'Wall-to-wall width of the wardrobe.' },
    { room: 'living', item: 'living_tv', input: 'WIDTH', label: 'Living room TV wall width', unit: 'ft', min: 0.5, max: 150, hint: 'Width of the wall behind the TV.' },
    { room: 'whole', item: 'ceiling', input: 'AREA', label: 'False ceiling area', unit: 'sq ft', api: 'sqft', min: 10, max: 10000, hint: 'Usually close to your carpet area.' },
  ];

  // --- fixed customer copy (owner decisions T5–T7) -------------------------------------------------------------------
  const PACKAGE_NAME = 'Site Execution & Handover Package';
  const ALLOWANCE_NAME = 'Design Personalisation Allowance';
  const PACKAGE_TEXT = 'This covers the preparation, protection, material handling, completion and handover activities required to execute the selected project scope professionally.';
  const PACKAGE_PARTS = ['Site and floor protection', 'Plywood or material protection', 'Material freight and handling', 'Debris handling', 'Completion deep cleaning', 'Pest-control preparation where applicable'];
  const ALLOWANCE_TEXT = 'This planning allowance protects your budget for commonly selected design additions. It is not an automatic extra charge. Your detailed quotation replaces it with only the items you approve.';
  const ALLOWANCE_EXAMPLES = ['Extra drawers', 'Mirrors', 'Pelmets', 'Profile lighting', 'Sensors', 'Additional internal storage', 'Selected accessories'];
  // The engine sets the allowance as a share of your room work; measurements change it only through that rule.
  const ALLOWANCE_NOTES = ['The upper amount is not charged automatically.', 'The allowance is a share of your room work, so it moves when your room sizes change. Adding measurements does not remove it.', 'In your detailed quotation, the items you actually approve replace it.'];
  const WHY_RANGE = ['Typical sizes are used until you share measurements', 'Room configurations may change during design', 'Finishes and accessories affect the final value', 'The physical site measurement sets the final quantities', 'Site conditions may change what the work requires'];
  const COMPARE = ['Product sizes', 'Cabinet material', 'Door material and finish', 'Hardware brand and type', 'What each room includes', 'Installation', 'Freight and handling', 'Protection and cleaning', 'Taxes (GST)', 'Items you supply', 'What is excluded'];
  // Warranty (Phase 5): manufacturer-backed protection and Veda Spaces service support are separate promises. The one
  // duration shown is Veda Spaces' own, from the approved policy ("one year of free service from the project handover
  // date"); no material or hardware duration is shown until each product's documentation is reconciled.
  const MANUFACTURER_DEFAULT = 'Approved materials and hardware carry the applicable manufacturer warranty for the exact product selected and documented in your final quotation.';
  const SERVICE_SUPPORT = 'Veda Spaces provides one year of applicable workmanship and fitment service support from handover, subject to the Warranty, Service & Customer Care Policy.';
  const SERVICE_NOTE = 'A longer manufacturer warranty is the manufacturer’s own. It does not extend Veda Spaces workmanship or service support.';
  const TRUST_MARKERS = ['No contact details required for your first estimate', 'Room-wise estimate shown', 'Material specification available', 'Warranty and exclusions disclosed', 'GST shown separately'];
  const NEXT_STEPS = ['Personalise and narrow your estimate. No contact details are needed for this.', 'Request a designer consultation.', 'We complete a physical site measurement.', 'You confirm the design, materials and brands.', 'You receive your detailed final quotation.', 'You approve the scope before any work starts.'];
  const PACKAGES = [['ESSENTIAL', 'Essential', 'Branded plywood, laminate finishes and soft-close hardware'], ['PREMIUM', 'Premium', ''], ['LUXURY', 'Luxury', '']];
  const SIZE_LABEL = { '1BHK': '1 BHK', '2BHK': '2 BHK', '3BHK': '3 BHK', '4BHK': '4 BHK', CUSTOM: 'Custom' };
  const TYPE_LABEL = { APARTMENT: ['Apartment', 'Flat in a building or gated community'], VILLA: ['Villa or independent house', ''] };

  // --- state -----------------------------------------------------------------------------------------------------------
  const KEY = 'veda-estimate-v2';
  const fresh = () => ({ screen: 1, type: propertyTypes[0], size: homeSizes[0], kind: 'NEW_HOME', city: '', pkg: 'ESSENTIAL',
    rooms: {}, measures: {}, estimate: null, consult: null, enquiryKey: null, specReturn: 6 });
  let state;
  try { state = Object.assign(fresh(), JSON.parse(sessionStorage.getItem(KEY) || '{}')); } catch { state = fresh(); }
  const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify(state)); } catch { /* private mode */ } };
  const rooms = () => ROOMS_BY_SIZE[state.size] || ROOMS_BY_SIZE['3BHK'];
  const roomState = (id) => { state.rooms[id] = state.rooms[id] || { on: true, extras: {} }; return state.rooms[id]; };
  const randomToken = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, '0')).join('');
  const clientToken = (() => { try { const t = sessionStorage.getItem('veda-client') || randomToken(); sessionStorage.setItem('veda-client', t); return t; } catch { return randomToken(); } })();

  function chosen() {
    const out = [];
    for (const room of rooms()) {
      const r = roomState(room.id);
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
  function usage() {
    const u = { _TOTAL: 0 };
    for (const i of chosen()) { const p = ITEMS[i.id].product; if (p) { u._TOTAL += 1; u[p] = (u[p] || 0) + 1; } }
    return u;
  }
  const canAdd = (id) => { const p = ITEMS[id].product; if (!p) return true; const u = usage(); return u._TOTAL < LIMITS._TOTAL && (!(p in LIMITS) || (u[p] || 0) < LIMITS[p]); };
  function selections() {
    const sel = [];
    for (const i of chosen()) {
      const item = ITEMS[i.id];
      if (!item.product) continue;
      const options = { ...(item.options || {}) };
      if (i.id === 'pooja' && roomState('pooja').extras.asta) options.ASTA_CHAKRA = 'YES';
      const measurements = {};
      for (const f of REFINE) {
        const v = Number(state.measures[`${f.room}:${f.item}`]);
        if (f.room === i.room && f.item === i.id && v > 0) measurements[f.input] = { value: v, unit: f.api || 'ft' };
      }
      sel.push({ room: ROOM_CODE[i.room], product: item.product, options, measurements });
    }
    return sel;
  }

  // --- screens ---------------------------------------------------------------------------------------------------------
  const FLOW = { 1: 2, 2: 3, 3: 4, 4: 5 };
  function show(n, { focus = true } = {}) {
    state.screen = n; save();
    document.querySelectorAll('#est-v2 .v2-screen').forEach((s) => { s.hidden = Number(s.dataset.v2) !== n; });
    const step = n <= 5 ? n : 0;
    $('#v2-progress').hidden = !step;
    if (step) { $('#v2-progress-text').textContent = `Step ${step} of 5`; $('#v2-progress-fill').className = `v2-w${step}`; }
    clearSummary();
    ({ 1: renderTypes, 2: renderSizes, 4: renderRooms, 5: renderPackages, 6: renderResult, 7: renderLead, 8: renderRefine, 10: renderSpec })[n]?.();
    if (n === 5) widget('estimate', '#v2-ts-estimate');
    if (n === 7) widget('enquiry', '#v2-ts-enquiry');
    if (n === 8) widget('refine', '#v2-ts-refine');
    if (focus) document.querySelector(`[data-v2="${n}"] [tabindex="-1"]`)?.focus();
  }
  function clearSummary() {
    const s = $('#v2-summary'); s.hidden = true; s.replaceChildren();
    document.querySelectorAll('#est-v2 [aria-invalid="true"]').forEach((f) => f.removeAttribute('aria-invalid'));
    document.querySelectorAll('#est-v2 .v2-err').forEach((e) => { e.textContent = ''; });
  }
  function summary(problems) {
    clearSummary();
    const box = $('#v2-summary');
    box.replaceChildren(el('p', { text: 'Please check the following:' }), el('ul', {}, ...problems.map((p) => {
      const { text, field } = typeof p === 'string' ? { text: p, field: null } : p;
      const input = field && document.getElementById(field);
      if (!input) return el('li', { text });
      input.setAttribute('aria-invalid', 'true');
      const slot = document.getElementById(`${field}-err`); if (slot) slot.textContent = text;
      const a = el('a', { href: `#${field}`, text }); a.addEventListener('click', (e) => { e.preventDefault(); input.focus(); });
      return el('li', {}, a);
    })));
    box.hidden = false; box.focus();
  }

  function renderTypes() {
    $('#v2-types').replaceChildren(...['APARTMENT', 'VILLA'].map((t) => {
      const on = propertyTypes.includes(t);
      const [label, sub] = TYPE_LABEL[t];
      return el('label', { class: `v2-choice${on ? '' : ' v2-off'}` }, el('input', { type: 'radio', name: 'v2-type', value: t, checked: state.type === t, disabled: !on }),
        el('span', {}, el('strong', { text: label }), el('small', { text: on ? sub : 'Online estimates coming soon. Use “Talk to us instead” above.' })));
    }));
  }
  function renderSizes() {
    $('#v2-sizes').replaceChildren(...['1BHK', '2BHK', '3BHK', '4BHK'].map((h) => {
      const on = homeSizes.includes(h);
      return el('label', { class: `v2-pill${on ? '' : ' v2-off'}` }, el('input', { type: 'radio', name: 'v2-size', value: h, checked: state.size === h, disabled: !on }), el('span', { text: SIZE_LABEL[h] }));
    }));
    const off = ['1BHK', '2BHK', '3BHK', '4BHK'].filter((h) => !homeSizes.includes(h)).map((h) => SIZE_LABEL[h]);
    $('#v2-size-note').textContent = off.length ? `${off.join(', ')}: online estimates coming soon.` : '';
    $('#v2-city').value = state.city;
  }
  function renderRooms() {
    $('#v2-rooms-sub').textContent = `We’ve selected what most ${SIZE_LABEL[state.size]} homes include. Turn rooms on or off and add extras.`;
    const box = $('#v2-rooms');
    box.replaceChildren();
    for (const room of rooms()) {
      const r = roomState(room.id);
      const toggle = el('input', { type: 'checkbox', role: 'switch', 'aria-label': `Include ${room.label}`, checked: r.on });
      toggle.addEventListener('change', () => { r.on = toggle.checked; state.estimate = null; save(); renderRooms(); });
      const card = el('article', { class: `v2-room${r.on ? '' : ' v2-room-off'}`, 'aria-label': room.label },
        el('div', { class: 'v2-room-head' }, el('h3', { text: room.label }), el('label', { class: 'v2-toggle' }, el('span', { text: r.on ? 'Included' : 'Not included' }), toggle)),
        el('p', { class: 'v2-includes', text: room.includes.map((id) => ITEMS[id].label).join(' · ') }));
      if (room.extras.length && r.on) {
        const picked = room.extras.filter((x) => (x.count ? r.extras[x.id] > 0 : r.extras[x.id])).length;
        const details = el('details', { class: 'v2-extras', open: state.openExtras?.[room.id] || false }, el('summary', { text: picked ? `Extras (${picked} added)` : `Add extras (${room.extras.length})` }));
        details.addEventListener('toggle', () => { state.openExtras = { ...(state.openExtras || {}), [room.id]: details.open }; save(); });
        for (const x of room.extras) {
          const item = ITEMS[x.id];
          if (x.count) {
            const v = r.extras[x.id] || 0;
            const blocked = !canAdd(x.id);
            const minus = el('button', { type: 'button', 'aria-label': `Fewer ${item.label.toLowerCase()}s`, 'aria-disabled': v === 0 ? 'true' : null, text: '−' });
            const plus = el('button', { type: 'button', 'aria-label': `More ${item.label.toLowerCase()}s`, 'aria-disabled': v >= x.count || blocked ? 'true' : null, text: '+' });
            minus.addEventListener('click', () => { if (v > 0) { r.extras[x.id] = v - 1; state.estimate = null; save(); renderRooms(); } });
            plus.addEventListener('click', () => { if (v < x.count && !blocked) { r.extras[x.id] = v + 1; state.estimate = null; save(); renderRooms(); } });
            details.append(el('div', { class: 'v2-extra' }, el('span', {}, `${item.label}s`, blocked && v < x.count ? el('small', { text: 'Limit reached for your home' }) : null),
              el('span', { class: 'v2-stepper' }, minus, el('output', { 'aria-live': 'polite', text: String(v) }), plus)));
          } else {
            const on = !!r.extras[x.id];
            const blocked = !on && !canAdd(x.id);
            const id = `v2-x-${room.id}-${x.id}`;
            const box2 = el('input', { type: 'checkbox', id, checked: on, disabled: blocked, 'aria-describedby': blocked ? `${id}-l` : null });
            box2.addEventListener('change', () => { r.extras[x.id] = box2.checked; state.estimate = null; save(); renderRooms(); });
            details.append(el('label', { class: 'v2-extra', for: id }, el('span', {}, `+ ${item.label}${x.note ? ` (${x.note})` : ''}`, blocked ? el('small', { id: `${id}-l`, text: 'Limit reached for your home' }) : null), box2));
          }
        }
        card.append(details);
      }
      box.append(card);
    }
    const any = rooms().some((room) => roomState(room.id).on);
    $('#v2-rooms-next').setAttribute('aria-disabled', any ? 'false' : 'true');
    $('#v2-rooms-hint').textContent = any ? '' : 'Turn on at least one room to continue.';
  }
  function renderPackages() {
    $('#v2-packages').replaceChildren(...PACKAGES.map(([code, label, desc]) => {
      const luxury = code === 'LUXURY';
      const on = luxury || enabledPackages.includes(code);
      const input = el('input', { type: 'radio', name: 'v2-pkg', value: code, checked: state.pkg === code, disabled: !on });
      input.addEventListener('change', () => { state.pkg = code; save(); $('#v2-see').textContent = code === 'LUXURY' ? 'Request a design consultation →' : 'See my budget →'; });
      return el('label', { class: `v2-choice${on ? '' : ' v2-off'}` }, input,
        el('span', {}, el('strong', { text: label }), el('small', { text: luxury ? 'Priced after a design consultation' : on ? desc : 'Pricing coming soon' })));
    }));
    $('#v2-see').textContent = state.pkg === 'LUXURY' ? 'Request a design consultation →' : 'See my budget →';
  }

  // --- API ---------------------------------------------------------------------------------------------------------------
  const widgets = {};
  function loadTurnstile() {
    if (window.turnstile) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      s.async = true; s.onload = () => resolve(); s.onerror = () => reject(new Error('turnstile'));
      document.head.appendChild(s);
    });
  }
  async function widget(name, selector) {
    try {
      await loadTurnstile();
      if (widgets[name] === undefined) widgets[name] = window.turnstile.render(selector, { sitekey: meta('veda-turnstile-sitekey') });
      else window.turnstile.reset(widgets[name]);
    } catch { /* the request is refused with CAPTCHA_FAILED and explained */ }
  }
  const token = (name) => (window.turnstile && widgets[name] !== undefined ? window.turnstile.getResponse(widgets[name]) : '') || '';
  async function post(path, payload, headers = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const res = await fetch(`${apiBase}${path}`, { method: 'POST', signal: controller.signal, credentials,
        headers: { 'Content-Type': 'application/json', 'X-Veda-Client': clientToken, ...headers }, body: JSON.stringify(payload) });
      return { status: res.status, body: await res.json().catch(() => ({})) };
    } catch (err) {
      return { status: 0, body: { code: err.name === 'AbortError' ? 'TIMEOUT' : 'UNREACHABLE' } };
    } finally { clearTimeout(timer); }
  }
  const MESSAGES = {
    CAPTCHA_FAILED: 'We couldn’t verify this request. Please complete the check and try again.',
    RATE_LIMITED: 'We’re receiving a lot of requests right now. Please try again in a minute.',
    ESTIMATOR_UNAVAILABLE: 'Estimates are not available right now. Please contact us instead.',
    TIMEOUT: 'This is taking longer than expected. Please try again.',
    UNREACHABLE: 'We couldn’t reach our estimator. Please try again, or WhatsApp us.',
  };
  const explain = (body) => (body.code === 'VALIDATION_FAILED' && Array.isArray(body.errors) ? body.errors.map((e) => e.message)
    : [MESSAGES[body.code] || 'Something went wrong on our side. Please try again.']);
  async function requestEstimate(widgetName) {
    const r = await post('/api/v1/public/estimates', { property_type: state.type, home_size: state.size, project_kind: state.kind,
      city: state.city || null, package: state.pkg, selections: selections(), turnstile_token: token(widgetName) });
    widget(widgetName, widgetName === 'refine' ? '#v2-ts-refine' : '#v2-ts-estimate');
    if (r.status === 201) { state.estimate = r.body.data; state.enquiryKey = null; save(); return true; }
    summary(explain(r.body));
    return false;
  }

  // --- result (Variant B order, owner instruction) ---------------------------------------------------------------------
  const section = (title, ...kids) => el('section', { class: 'v2-block', 'aria-label': title }, el('h3', { text: title }), ...kids);
  const disclosure = (title, ...kids) => el('details', { class: 'v2-more' }, el('summary', { text: title }), ...kids);
  const ul = (items) => el('ul', {}, ...items.map((t) => el('li', { text: t })));
  const button = (cls, text, fn) => { const b = el('button', { class: cls, type: 'button', text }); b.addEventListener('click', fn); return b; };
  const spec = () => state.estimate?.specification || null;
  const roomIdOf = (code) => Object.keys(ROOM_CODE).find((k) => ROOM_CODE[k] === code);
  const nearest = (minor) => Math.round(minor / 100000) * 100000; // ₹1,000, as the room amounts are rounded
  const signed = (minor) => `${minor < 0 ? '−' : '+'}${rupees(Math.abs(minor))}`;
  const WORDS = ['No', 'One', 'Two', 'Three', 'Four', 'Five', 'Six'];
  const plural = (n, one, many) => `${WORDS[n] || n} ${n === 1 ? one : many}`;
  // Every amount on this page comes from the estimate response; the variation line is what remains between the
  // displayed components and the displayed range, so the build-up always adds up exactly (Phase 8).
  function buildUp(e) {
    const rooms = e.rooms.reduce((sum, r) => sum + r.amount_minor, 0);
    const optional = nearest(e.optional_items_minor || 0);
    const pkg = e.project_preparation.amount_minor;
    const a = e.custom_features_allowance;
    const low = rooms + optional + pkg + a.low_minor;
    const high = rooms + optional + pkg + a.high_minor;
    return { rooms, optional, pkg, allowLow: a.low_minor, allowHigh: a.high_minor, varLow: e.range.low_minor - low, varHigh: e.range.high_minor - high };
  }
  const amountRow = (term, text, data) => [el('dt', { text: term }), el('dd', { text, 'data-low': data?.[0] ?? null, 'data-high': data?.[1] ?? null })];
  function typicalAssumptions() {
    const picked = chosen();
    const on = (id) => roomState(id).on;
    const count = (id) => picked.filter((p) => p.id === id).length;
    const out = [];
    if (on('kitchen')) out.push('Standard modular kitchen with wall units and loft');
    if (count('wardrobe')) out.push(`${plural(count('wardrobe'), 'wardrobe', 'wardrobes')} with lofts`);
    if (on('living')) out.push(count('living_wall') || count('dining_wall') || count('bed_wall') ? 'TV unit and feature-wall scope' : 'TV unit scope');
    const pu = [on('pooja') ? 'Pooja' : null, on('utility') ? 'utility' : null].filter(Boolean);
    if (pu.length) out.push(`${pu.join(' and ')} scope as selected`.replace(/^./, (c) => c.toUpperCase()));
    if (on('whole')) out.push(`Whole-home ceiling and lighting based on typical ${SIZE_LABEL[state.size]} dimensions`);
    const measured = REFINE.filter((f) => Number(state.measures[`${f.room}:${f.item}`]) > 0).map((f) => f.label.toLowerCase());
    if (measured.length) out.push(`Your measurements are used for: ${measured.join(', ')}`);
    return out;
  }
  function roomCard(r, details) {
    const s = spec();
    const id = roomIdOf(r.room);
    const def = rooms().find((x) => x.id === id);
    const std = def ? def.includes.map((x) => ITEMS[x].label) : [];
    const extras = [...new Set(chosen().filter((p) => p.room === id && !def?.includes.includes(p.id)).map((p) => ITEMS[p.id].label + (ITEMS[p.id].optional ? ' (shown separately under optional items)' : '')))];
    const m = details?.materials;
    const cats = s && m ? m.categories.map((code) => s.categories.find((c) => c.code === code)).filter(Boolean) : [];
    const material = cats.map((c) => el('div', { class: 'v2-spec-cat' }, el('p', {}, el('strong', { text: `${c.label}: ` }), c.requirement),
      c.brand_examples.length ? el('p', { class: 'v2-small', text: `Approved examples: ${c.brand_examples.join(', ')}, or an approved equivalent` }) : null));
    return el('article', { class: 'v2-room-card', 'aria-label': def?.label || r.label },
      el('div', { class: 'v2-room-row' }, el('h4', { text: def?.label || r.label }), el('span', { class: 'v2-room-amount', text: roomAmount(r.amount_minor) })),
      el('p', { class: 'v2-room-std', text: [...std, ...extras.map((x) => `+ ${x}`)].join(' · ') }),
      m?.line ? el('p', { class: 'v2-spec-line' }, el('strong', { text: 'Essential specification: ' }), m.line) : null,
      disclosure('View inclusions & materials',
        el('h5', { text: 'Included items' }), ul(std),
        el('h5', { text: 'Material specification' }), ...(material.length ? [...material, el('p', { class: 'v2-small', text: s.final_selection })] : [el('p', { text: 'Materials are confirmed in your detailed quotation.' })]),
        el('h5', { text: 'Optional or selected extras' }), extras.length ? ul(extras) : el('p', { text: 'None added.' }),
        el('h5', { text: 'Assumptions' }), details?.assumptions?.length ? ul(details.assumptions) : el('p', { text: 'Your measurements are used for this room.' })));
  }
  function renderResult() {
    const e = state.estimate;
    if (!e) return;
    const s = spec();
    const b = buildUp(e);
    const gstText = `GST at ${e.gst.pct}% is extra: about ${rupees(e.gst.low_minor)} – ${rupees(e.gst.high_minor)}`;
    $('#v2-range').textContent = `${rupees(e.range.low_minor)} – ${rupees(e.range.high_minor)}`;
    $('#v2-gst').textContent = gstText;
    const measured = Object.values(state.measures).some((v) => Number(v) > 0);
    $('#v2-basis').textContent = `${SIZE_LABEL[state.size]} ${state.type === 'VILLA' ? 'villa' : 'apartment'} · ${state.kind === 'NEW_HOME' ? 'New home' : 'Renovation'} · Essential · ${measured ? 'Including your measurements' : `Based on typical ${SIZE_LABEL[state.size]} sizes`}`;
    const toRefine = () => show(8);
    const toQuote = () => { state.consult = null; save(); show(7); };
    const toDesigner = () => { state.consult = 'designer'; save(); show(7); };
    const markers = TRUST_MARKERS.filter((t) => s || t !== 'Material specification available');
    $('#v2-top').replaceChildren(
      el('div', { class: 'v2-block v2-includes-block' }, el('h3', { text: 'Your estimate includes' }),
        ul(['Your selected rooms and products', PACKAGE_NAME, ALLOWANCE_NAME]), el('p', { class: 'v2-small', text: 'GST is shown separately.' })),
      el('ul', { class: 'v2-markers', 'aria-label': 'About this estimate' }, ...markers.map((t) => el('li', { text: t }))),
      el('div', { class: 'v2-block' }, el('h3', { text: 'Why is this a range?' }), ul(WHY_RANGE),
        button('v2-primary v2-wide', 'Personalise and narrow my estimate', toRefine)),
      el('p', {}, el('a', { class: 'v2-link', href: '#v2-next-steps', text: 'What happens next ↓' })));
    const details = Object.fromEntries((e.room_details || []).map((d) => [d.room, d]));
    const policy = e.warranty?.policy_url || '/warranty';
    const build = el('dl', { class: 'v2-build', id: 'v2-build' },
      ...amountRow('Your selected rooms', rupees(b.rooms), [b.rooms, b.rooms]),
      ...(b.optional ? amountRow('+ Optional items you added', rupees(b.optional), [b.optional, b.optional]) : []),
      ...amountRow(`+ ${PACKAGE_NAME}`, rupees(b.pkg), [b.pkg, b.pkg]),
      ...amountRow(`+ ${ALLOWANCE_NAME}`, `${rupees(b.allowLow)} – ${rupees(b.allowHigh)}`, [b.allowLow, b.allowHigh]),
      ...amountRow('Size and site variation', `${signed(b.varLow)} to ${signed(b.varHigh)}`, [b.varLow, b.varHigh]),
      el('dt', { class: 'v2-total', text: 'Your estimated range' }), el('dd', { class: 'v2-total', text: `${rupees(e.range.low_minor)} – ${rupees(e.range.high_minor)}`, 'data-low': e.range.low_minor, 'data-high': e.range.high_minor }),
      el('dt', { text: 'GST, shown separately' }), el('dd', { text: `about ${rupees(e.gst.low_minor)} – ${rupees(e.gst.high_minor)}` }));
    $('#v2-result-body').replaceChildren(
      section('How your estimate is built', build,
        el('p', { class: 'v2-small', text: 'The size and site variation allows for actual sizes and site conditions. It is wider while typical sizes are used and narrows for the items you measure. Amounts are rounded, and the variation includes the rounding.' })),
      section('What Essential includes', ...(s ? [el('p', { class: 'v2-small', text: s.summary }),
        disclosure(`See all ${s.categories.length} material categories`, el('dl', { class: 'v2-promise' }, ...s.categories.flatMap((c) => [el('dt', { text: c.label }), el('dd', { text: c.summary })]))),
        el('p', { class: 'v2-small', text: `${s.equivalent_policy} ${s.final_selection}` }),
        button('v2-link', 'View detailed material specification →', () => { state.specReturn = 6; show(10); })]
        : [el('p', { text: 'Your materials are confirmed in your detailed quotation.' })])),
      section('Your rooms', ...e.rooms.map((r) => roomCard(r, details[r.room])), el('p', { class: 'v2-small', text: 'Room amounts are rounded and include installation. Rates are never shown on this page; your detailed quotation lists every item.' })),
      section(PACKAGE_NAME, el('p', { class: 'v2-amount', text: rupees(b.pkg) }), el('p', { class: 'v2-badge', text: 'Included in your estimated range' }),
        el('p', { text: PACKAGE_TEXT }),
        disclosure('What it covers', ul(PACKAGE_PARTS), el('p', { class: 'v2-small', text: 'Your detailed quotation shows the amount for each item.' }))),
      section(ALLOWANCE_NAME, el('p', { class: 'v2-amount', text: `${rupees(b.allowLow)} – ${rupees(b.allowHigh)}` }), el('p', { class: 'v2-badge', text: 'Included in your estimated range' }),
        el('p', { text: ALLOWANCE_TEXT }), ul(ALLOWANCE_NOTES),
        disclosure('What it usually covers', ul(ALLOWANCE_EXAMPLES))),
      section('Warranty and service',
        el('h4', { text: 'Manufacturer-backed protection' }), el('p', { text: s?.warranty_summary || MANUFACTURER_DEFAULT }),
        el('h4', { text: 'Veda Spaces service support' }), el('p', { text: SERVICE_SUPPORT }), el('p', { class: 'v2-small', text: SERVICE_NOTE }),
        el('p', {}, el('a', { href: policy, text: 'View full warranty and exclusions' }))),
      section('Not included', ul([...e.exclusions, ...(e.client_scope.length ? [`Supplied by you: ${e.client_scope.join(', ')}`] : [])])),
      section('How to compare this estimate', el('p', { text: 'Estimates only compare fairly when the scope is the same. Check each provider’s:' }), ul(COMPARE)),
      section(measured ? 'Assumptions used' : `Typical ${SIZE_LABEL[state.size]} assumptions used`, ul(typicalAssumptions()),
        disclosure('View technical assumptions', ...(e.room_details || []).filter((d) => d.assumptions.length).flatMap((d) => [el('h4', { text: (rooms().find((x) => x.id === roomIdOf(d.room)) || {}).label || d.room }), ul(d.assumptions)]),
          ...(e.room_details ? [] : [ul(e.assumptions)]))),
      el('section', { class: 'v2-block v2-next-steps', id: 'v2-next-steps', 'aria-label': 'What happens next?' }, el('h3', { text: 'What happens next?' }),
        el('ol', { class: 'v2-steps' }, ...NEXT_STEPS.map((t) => el('li', { text: t }))),
        button('v2-primary v2-wide', 'Personalise and narrow my estimate', toRefine),
        button('v2-ghost v2-wide', 'Get my detailed quotation', toQuote),
        button('v2-link', 'Talk to a designer', toDesigner)),
    );
    $('#v2-disclaimer').textContent = e.disclaimer;
    $('#v2-meta').textContent = `Estimate ${e.reference} · valid until ${e.expires_on} · ${s ? `${s.name} ${s.version}` : 'specification confirmed in your quotation'}`;
  }
  function renderSpec() {
    const s = spec();
    $('#v2-spec-sub').textContent = s ? `${s.name} ${s.version}. ${s.equivalent_policy} ${s.final_selection}` : '';
    // Each category keeps the four parts apart (T3): what is promised, brand examples, the equivalent rule, final selection.
    const row = (term, value) => (value ? [el('dt', { text: term }), el('dd', { text: value })] : []);
    $('#v2-spec').replaceChildren(...(s ? s.categories.map((c) => el('section', { class: 'v2-spec-cat' }, el('h3', { text: c.label }),
      el('dl', { class: 'v2-spec-dl' },
        ...row('Material requirement', c.requirement),
        ...row('Grade', c.grade),
        ...row('Thickness', c.thickness.join('; ')),
        ...row('Finish', c.finish),
        ...row('Approved brand examples', c.brand_examples.join(', ')),
        ...row('Approved equivalent', c.equivalent_rule),
        ...row('Final selection', c.final_selection),
        ...row('Warranty', c.warranty_summary)),
      c.details.length ? ul(c.details) : null))
      : [el('p', { text: 'Your materials are confirmed in your detailed quotation.' })]));
  }
  function renderLead() {
    const c = state.consult;
    $('#v2-h7').textContent = c ? 'Request a design consultation' : 'Get my detailed quotation';
    $('#v2-lead-sub').textContent = c === 'luxury' ? 'Luxury is priced after a design consultation. A designer will call you to understand your home.'
      : c === 'designer' ? 'A designer will call you to talk through your home, your estimate and your ideas.'
        : 'A designer will call you within one working day to arrange a physical site measurement. You then confirm the design, materials and brands, receive your detailed final quotation, and approve the scope before any work starts.';
    $('#v2-send').textContent = c ? 'Request my consultation →' : 'Send my request →';
    $('#v2-refine-link').hidden = Boolean(c) || !state.estimate;
  }
  function renderRefine() {
    const box = $('#v2-refine');
    box.replaceChildren();
    const picked = chosen();
    for (const f of REFINE) {
      if (!picked.some((p) => p.room === f.room && p.id === f.item)) continue;
      const key = `${f.room}:${f.item}`;
      const id = `v2-m-${f.room}-${f.item}`;
      const input = el('input', { id, type: 'number', inputmode: 'decimal', min: String(f.min), max: String(f.max), step: 'any', placeholder: 'typical size', value: state.measures[key] || '', 'aria-describedby': `${id}-h` });
      input.addEventListener('input', () => { state.measures[key] = input.value; save(); });
      box.append(el('label', { class: 'v2-measure', for: id }, el('span', {}, f.label, input), el('span', { class: 'v2-unit', text: f.unit }),
        el('small', { id: `${id}-h`, text: `${f.hint} Between ${f.min} and ${f.max} ${f.unit}.` })));
    }
    $('#v2-refined').textContent = state.estimate ? `${rupees(state.estimate.range.low_minor)} – ${rupees(state.estimate.range.high_minor)}` : '';
  }

  // --- wiring ------------------------------------------------------------------------------------------------------------
  document.querySelectorAll('#est-v2 [data-v2-next]').forEach((b) => b.addEventListener('click', () => {
    const n = state.screen;
    if (n === 1) state.type = document.querySelector('input[name="v2-type"]:checked')?.value || state.type;
    if (n === 2) { state.size = document.querySelector('input[name="v2-size"]:checked')?.value || state.size; state.city = $('#v2-city').value.trim(); }
    if (n === 3) state.kind = document.querySelector('input[name="v2-kind"]:checked').value;
    if (n === 4 && b.getAttribute('aria-disabled') === 'true') return;
    show(FLOW[n]);
  }));
  document.querySelectorAll('#est-v2 [data-v2-back]').forEach((b) => b.addEventListener('click', () => {
    show({ 2: 1, 3: 2, 4: 3, 5: 4, 7: state.consult === 'luxury' ? 5 : 6 }[state.screen] || 1);
  }));
  document.querySelectorAll('#est-v2 [data-v2-goto]').forEach((b) => b.addEventListener('click', () => show(Number(b.dataset.v2Goto))));
  $('#v2-spec-back').addEventListener('click', () => show(state.specReturn || 6));
  $('#v2-see').addEventListener('click', async (ev) => {
    if (state.pkg === 'LUXURY') { state.consult = 'luxury'; save(); show(7); return; }
    ev.target.disabled = true;
    const ok = await requestEstimate('estimate');
    ev.target.disabled = false;
    if (ok) { state.consult = null; show(6); }
  });
  $('#v2-update').addEventListener('click', async (ev) => {
    const problems = [];
    for (const f of REFINE) {
      const v = state.measures[`${f.room}:${f.item}`];
      if (v !== undefined && v !== '' && !(Number(v) >= f.min && Number(v) <= f.max)) problems.push({ text: `${f.label}: between ${f.min} and ${f.max} ${f.unit}, or leave it empty.`, field: `v2-m-${f.room}-${f.item}` });
    }
    if (problems.length) { summary(problems); return; }
    ev.target.disabled = true;
    const ok = await requestEstimate('refine');
    ev.target.disabled = false;
    if (ok) renderRefine();
  });
  $('#v2-lead').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const problems = [];
    if (!$('#v2-name').value.trim()) problems.push({ text: 'Enter your name.', field: 'v2-name' });
    if ($('#v2-phone').value.replace(/\D/g, '').length < 10) problems.push({ text: 'Enter a valid phone number.', field: 'v2-phone' });
    if (!$('#v2-consent').checked) problems.push({ text: 'Please agree to be contacted so we can prepare your quotation.', field: 'v2-consent' });
    if (problems.length) { summary(problems); return; }
    state.enquiryKey = state.enquiryKey || `est-${randomToken()}`; save();
    const e = state.estimate;
    const c = state.consult;
    const rooms3 = chosen().map((p) => ITEMS[p.id].label);
    const message = c === 'luxury' ? `Requested a Luxury design consultation for: ${[...new Set(rooms3)].join(', ')}.`.slice(0, 500)
      : c === 'designer' ? `Asked to talk to a designer about Budgetary Estimate ${e?.reference}.` : `Requested a detailed quotation after Budgetary Estimate ${e?.reference}.`;
    $('#v2-send').disabled = true;
    const r = await post('/api/v1/public/enquiries', {
      name: $('#v2-name').value.trim(), phone: $('#v2-phone').value.trim(), email: $('#v2-email').value.trim() || null,
      city: state.city || null, preferred_contact: document.querySelector('input[name="v2-contact"]:checked').value, message,
      consent: { acknowledged: true, policy_version: meta('veda-policy-version') },
      estimate_reference: c === 'luxury' ? null : e?.reference || null, company_website_url: $('#v2-website').value,
      turnstile_token: token('enquiry'), attribution: { form_page: '/estimate', landing_page: location.pathname },
      ...(c === 'luxury' ? { consultation: 'LUXURY_DESIGN' } : {}),
    }, { 'Idempotency-Key': state.enquiryKey });
    $('#v2-send').disabled = false;
    if (r.status === 201) {
      $('#v2-reference').textContent = r.body.data.reference;
      $('#v2-next').textContent = c ? 'Our designer will call you within one working day to arrange your design consultation.'
        : 'Our designer will call you within one working day to go through your estimate and arrange a site measurement.';
      $('#v2-estimate-ref').textContent = c !== 'luxury' && e ? `Keep your estimate reference ${e.reference} handy.` : '';
      show(9);
      try { sessionStorage.removeItem(KEY); } catch { /* ignore */ }
      return;
    }
    widget('enquiry', '#v2-ts-enquiry');
    summary(explain(r.body));
  });

  // --- start -------------------------------------------------------------------------------------------------------------
  $('#est-off').hidden = true;
  $('#est-v2').hidden = false;
  $('#est-lead').textContent = 'Answer a few questions about your home and see a preliminary budget range in about a minute. No measurements or contact details needed.';
  if (!propertyTypes.includes(state.type)) state.type = propertyTypes[0];
  if (!homeSizes.includes(state.size)) state.size = homeSizes[0];
  const valid = state.estimate && state.estimate.expires_on >= new Date().toISOString().slice(0, 10);
  if (!valid) state.estimate = null;
  let start = state.screen;
  if ([6, 8, 10].includes(start) && !state.estimate) start = 5;
  if (start === 9) start = 1;
  show(start, { focus: false });
})();
