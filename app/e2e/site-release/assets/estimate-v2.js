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
  const COPY = window.VEDA_ESTIMATE_COPY;
  if (!apiBase || !COPY) return;
  const P = COPY.promise;
  const U = COPY.ui;
  const fmt = (t, vars) => t.replace(/\{(\w+)\}/g, (_, k) => String(vars[k]));
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
    kitchen: { label: P.items.kitchen, product: 'KITCHEN' },
    pantry: { label: P.items.pantry, product: 'STORAGE_BOXES' },
    living_tv: { label: P.items.living_tv, product: 'TV_UNIT', options: { STYLE: 'PANELLED' } },
    living_wall: { label: P.items.living_wall, product: 'FEATURE_WALL' },
    living_beading: { label: P.items.living_beading, product: 'VENEER_ACCENTS', options: { STYLE: 'BEADING' } },
    living_partition: { label: P.items.living_partition, product: 'PARTITION' },
    living_window: { label: P.items.living_window, product: 'WINDOW_SEATING' },
    dining_crockery: { label: P.items.dining_crockery, product: 'CROCKERY_UNIT' },
    dining_basin: { label: P.items.dining_basin, product: 'VANITY_UNIT', options: { TYPE: 'DRESSER' } },
    dining_wall: { label: P.items.dining_wall, product: 'FEATURE_WALL' },
    dining_arch: { label: P.items.dining_arch, product: 'VENEER_ACCENTS' },
    wardrobe: { label: P.items.wardrobe, product: 'WARDROBE' },
    bed_king: { label: P.items.bed_king, product: 'BED', options: { SIZE: 'KING' } },
    bed_queen: { label: P.items.bed_queen, product: 'BED' },
    bath_vanity: { label: P.items.bath_vanity, product: 'VANITY_UNIT', options: { TYPE: 'TOILET' } },
    dressing: { label: P.items.dressing, product: 'VANITY_UNIT', options: { TYPE: 'DRESSER' } },
    study: { label: P.items.study, product: 'STUDY_UNIT' },
    bed_tv: { label: P.items.bed_tv, product: 'TV_UNIT', options: { STYLE: 'BOX' } },
    bed_window: { label: P.items.bed_window, product: 'WINDOW_SEATING' },
    bed_wall: { label: P.items.bed_wall, product: 'FEATURE_WALL' },
    bedside: { label: P.items.bedside, product: 'STORAGE_BOXES', options: { TYPE: 'BEDSIDE_TABLE' } },
    pooja: { label: P.items.pooja, product: 'POOJA_UNIT' },
    asta: { label: P.items.asta, product: null }, // an option of the pooja unit, not a selection
    utility: { label: P.items.utility, product: 'UTILITY' },
    ceiling: { label: P.items.ceiling, product: 'FALSE_CEILING' },
    profile: { label: P.items.profile, product: 'CEILING_PROFILE_LIGHTING' },
    painting: { label: P.items.painting, product: 'PAINTING', optional: true },
    electrical: { label: P.items.electrical, product: 'ELECTRICAL', optional: true },
  };
  const BEDROOM = (bed) => ({ includes: ['wardrobe', bed, 'bath_vanity'],
    extras: [{ id: 'dressing' }, { id: 'study' }, { id: 'bed_tv' }, { id: 'bed_window' }, { id: 'bed_wall' }, { id: 'bedside', count: 2 }] });
  const ROOMS_BY_SIZE = {
    '3BHK': [
      { id: 'kitchen', label: U.rooms.kitchen, includes: ['kitchen'], extras: [{ id: 'pantry' }] },
      { id: 'living', label: U.rooms.living, includes: ['living_tv'], extras: [{ id: 'living_wall' }, { id: 'living_beading' }, { id: 'living_partition' }, { id: 'living_window' }] },
      { id: 'dining', label: U.rooms.dining, includes: ['dining_crockery'], extras: [{ id: 'dining_basin' }, { id: 'dining_wall' }, { id: 'dining_arch' }] },
      { id: 'master', label: U.rooms.master, ...BEDROOM('bed_king') },
      { id: 'bed2', label: U.rooms.bed2, ...BEDROOM('bed_queen') },
      { id: 'bed3', label: U.rooms.bed3, ...BEDROOM('bed_queen') },
      { id: 'pooja', label: U.rooms.pooja, includes: ['pooja'], extras: [{ id: 'asta' }] },
      { id: 'utility', label: U.rooms.utility, includes: ['utility'], extras: [] },
      { id: 'whole', label: U.rooms.whole, includes: ['ceiling', 'profile'], extras: [{ id: 'painting', note: P.optionalNote }, { id: 'electrical', note: P.optionalNote }] },
    ],
  };
  // Engine limits enforced here, so no request can be refused (ESTIMATOR-UX-V2 §3.2).
  const LIMITS = { VANITY_UNIT: 6, STORAGE_BOXES: 10, FEATURE_WALL: 6, WINDOW_SEATING: 6, TV_UNIT: 6, _TOTAL: 40 };
  // Refinement: the measurements that move the price most, in customer words (feet and square feet only).
  const REFINE = [
    { room: 'kitchen', item: 'kitchen', input: 'RUN', label: U.refine.RUN.label, unit: U.refine.RUN.unit, min: 0.5, max: 150, hint: U.hints.RUN },
    { room: 'master', item: 'wardrobe', input: 'WIDTH', label: U.refine.WIDTH_WARDROBE.label, unit: U.refine.WIDTH_WARDROBE.unit, min: 0.5, max: 150, hint: U.hints.WIDTH_WARDROBE },
    { room: 'living', item: 'living_tv', input: 'WIDTH', label: U.refine.WIDTH_TV.label, unit: U.refine.WIDTH_TV.unit, min: 0.5, max: 150, hint: U.hints.WIDTH_TV },
    { room: 'whole', item: 'ceiling', input: 'AREA', label: U.refine.AREA.label, unit: U.refine.AREA.unit, api: 'sqft', min: 10, max: 10000, hint: U.hints.AREA },
  ];

  // --- customer copy: estimate-v2-copy.js (every promise is in the customer-promise matrix) ---------------------------
  const PACKAGE_NAME = P.includes[1];
  const ALLOWANCE_NAME = P.includes[2];
  const PACKAGES = [['ESSENTIAL', 'Essential', P.packageSubtitle], ['PREMIUM', 'Premium', ''], ['LUXURY', 'Luxury', '']];
  const SIZE_LABEL = { '1BHK': '1 BHK', '2BHK': '2 BHK', '3BHK': '3 BHK', '4BHK': '4 BHK', CUSTOM: 'Custom' };
  const TYPE_LABEL = { APARTMENT: [U.labels.typeApartment, U.labels.typeApartmentSub], VILLA: [U.labels.typeVilla, ''] };

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
    if (step) { $('#v2-progress-text').textContent = fmt(U.labels.step, { step }); $('#v2-progress-fill').className = `v2-w${step}`; }
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
    box.replaceChildren(el('p', { text: U.pleaseCheck }), el('ul', {}, ...problems.map((p) => {
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
        el('span', {}, el('strong', { text: label }), el('small', { text: on ? sub : P.typeOff })));
    }));
  }
  function renderSizes() {
    $('#v2-sizes').replaceChildren(...['1BHK', '2BHK', '3BHK', '4BHK'].map((h) => {
      const on = homeSizes.includes(h);
      return el('label', { class: `v2-pill${on ? '' : ' v2-off'}` }, el('input', { type: 'radio', name: 'v2-size', value: h, checked: state.size === h, disabled: !on }), el('span', { text: SIZE_LABEL[h] }));
    }));
    const off = ['1BHK', '2BHK', '3BHK', '4BHK'].filter((h) => !homeSizes.includes(h)).map((h) => SIZE_LABEL[h]);
    $('#v2-size-note').textContent = off.length ? fmt(P.sizeOff, { sizes: off.join(', ') }) : '';
    $('#v2-city').value = state.city;
  }
  function renderRooms() {
    $('#v2-rooms-sub').textContent = fmt(P.roomsSub, { size: SIZE_LABEL[state.size] });
    const box = $('#v2-rooms');
    box.replaceChildren();
    for (const room of rooms()) {
      const r = roomState(room.id);
      const toggle = el('input', { type: 'checkbox', role: 'switch', 'aria-label': fmt(U.labels.includeRoom, { room: room.label }), checked: r.on });
      toggle.addEventListener('change', () => { r.on = toggle.checked; state.estimate = null; save(); renderRooms(); });
      const card = el('article', { class: `v2-room${r.on ? '' : ' v2-room-off'}`, 'aria-label': room.label },
        el('div', { class: 'v2-room-head' }, el('h3', { text: room.label }), el('label', { class: 'v2-toggle' }, el('span', { text: r.on ? U.labels.included : U.labels.notIncluded }), toggle)),
        el('p', { class: 'v2-includes', text: room.includes.map((id) => ITEMS[id].label).join(' · ') }));
      if (room.extras.length && r.on) {
        const picked = room.extras.filter((x) => (x.count ? r.extras[x.id] > 0 : r.extras[x.id])).length;
        const details = el('details', { class: 'v2-extras', open: state.openExtras?.[room.id] || false }, el('summary', { text: picked ? fmt(U.labels.extrasAdded, { count: picked }) : fmt(U.labels.addExtras, { count: room.extras.length }) }));
        details.addEventListener('toggle', () => { state.openExtras = { ...(state.openExtras || {}), [room.id]: details.open }; save(); });
        for (const x of room.extras) {
          const item = ITEMS[x.id];
          if (x.count) {
            const v = r.extras[x.id] || 0;
            const blocked = !canAdd(x.id);
            const minus = el('button', { type: 'button', 'aria-label': fmt(U.labels.fewer, { item: item.label.toLowerCase() }), 'aria-disabled': v === 0 ? 'true' : null, text: '−' });
            const plus = el('button', { type: 'button', 'aria-label': fmt(U.labels.more, { item: item.label.toLowerCase() }), 'aria-disabled': v >= x.count || blocked ? 'true' : null, text: '+' });
            minus.addEventListener('click', () => { if (v > 0) { r.extras[x.id] = v - 1; state.estimate = null; save(); renderRooms(); } });
            plus.addEventListener('click', () => { if (v < x.count && !blocked) { r.extras[x.id] = v + 1; state.estimate = null; save(); renderRooms(); } });
            details.append(el('div', { class: 'v2-extra' }, el('span', {}, `${item.label}s`, blocked && v < x.count ? el('small', { text: U.limitReached }) : null),
              el('span', { class: 'v2-stepper' }, minus, el('output', { 'aria-live': 'polite', text: String(v) }), plus)));
          } else {
            const on = !!r.extras[x.id];
            const blocked = !on && !canAdd(x.id);
            const id = `v2-x-${room.id}-${x.id}`;
            const box2 = el('input', { type: 'checkbox', id, checked: on, disabled: blocked, 'aria-describedby': blocked ? `${id}-l` : null });
            box2.addEventListener('change', () => { r.extras[x.id] = box2.checked; state.estimate = null; save(); renderRooms(); });
            details.append(el('label', { class: 'v2-extra', for: id }, el('span', {}, `+ ${item.label}${x.note ? ` (${x.note})` : ''}`, blocked ? el('small', { id: `${id}-l`, text: U.limitReached }) : null), box2));
          }
        }
        card.append(details);
      }
      box.append(card);
    }
    const any = rooms().some((room) => roomState(room.id).on);
    $('#v2-rooms-next').setAttribute('aria-disabled', any ? 'false' : 'true');
    $('#v2-rooms-hint').textContent = any ? '' : U.turnOnRoom;
  }
  function renderPackages() {
    $('#v2-packages').replaceChildren(...PACKAGES.map(([code, label, desc]) => {
      const luxury = code === 'LUXURY';
      const on = luxury || enabledPackages.includes(code);
      const input = el('input', { type: 'radio', name: 'v2-pkg', value: code, checked: state.pkg === code, disabled: !on });
      input.addEventListener('change', () => { state.pkg = code; save(); $('#v2-see').textContent = code === 'LUXURY' ? U.labels.requestConsultation : U.labels.seeBudget; });
      return el('label', { class: `v2-choice${on ? '' : ' v2-off'}` }, input,
        el('span', {}, el('strong', { text: label }), el('small', { text: luxury ? P.luxuryConsult : on ? desc : P.premiumSoon })));
    }));
    $('#v2-see').textContent = state.pkg === 'LUXURY' ? U.labels.requestConsultation : U.labels.seeBudget;
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
  const MESSAGES = U.messages;
  const explain = (body) => (body.code === 'VALIDATION_FAILED' && Array.isArray(body.errors) ? body.errors.map((e) => e.message)
    : [MESSAGES[body.code] || MESSAGES.OTHER]);
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
  // A specification without room promises (ESSENTIAL-1.0) is treated as none: V2 shows no material promise for it.
  // Material promises only from a specification with room promises whose reviewed matrix registers it (F1, M3).
  const spec = () => (state.estimate?.specification?.room_promises && state.estimate?.v2_copy?.approved ? state.estimate.specification : null);
  // Runtime API text only as the reviewed matrix registers it (M3); otherwise nothing, or the approved fallback.
  const approved = () => (state.estimate?.v2_copy?.approved ? state.estimate.v2_copy : { approved: false, disclaimer: null, exclusions: [], client_scope: [], assumptions: {} });
  const roomIdOf = (code) => Object.keys(ROOM_CODE).find((k) => ROOM_CODE[k] === code);
  const nearest = (minor) => Math.round(minor / 100000) * 100000; // ₹1,000, as the room amounts are rounded
  const signed = (minor) => `${minor < 0 ? '−' : '+'}${rupees(Math.abs(minor))}`;
  const WORDS = ['No', 'One', 'Two', 'Three', 'Four', 'Five', 'Six'];
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
    const A = P.assumptions;
    const picked = chosen();
    const on = (id) => roomState(id).on;
    const count = (id) => picked.filter((p) => p.id === id).length;
    const out = [];
    if (on('kitchen')) out.push(A.kitchen);
    const w = count('wardrobe');
    if (w) out.push(w === 1 ? A.wardrobe : fmt(A.wardrobes, { count: WORDS[w] || w }));
    if (on('living')) out.push(count('living_wall') || count('dining_wall') || count('bed_wall') ? A.tvWall : A.tv);
    const pu = [on('pooja') ? 'Pooja' : null, on('utility') ? 'utility' : null].filter(Boolean);
    if (pu.length) out.push(fmt(A.poojaUtility, { rooms: pu.join(' and ').replace(/^./, (c) => c.toUpperCase()) }));
    if (on('whole')) out.push(fmt(A.whole, { size: SIZE_LABEL[state.size] }));
    const measured = REFINE.filter((f) => Number(state.measures[`${f.room}:${f.item}`]) > 0).map((f) => f.label.toLowerCase());
    if (measured.length) out.push(fmt(A.measured, { items: measured.join(', ') }));
    return out;
  }
  const roomAssumptions = (code) => approved().assumptions?.[code] || [];
  function roomCard(r, details) {
    const s = spec();
    const id = roomIdOf(r.room);
    const def = rooms().find((x) => x.id === id);
    const std = def ? def.includes.map((x) => ITEMS[x].label) : [];
    const extras = [...new Set(chosen().filter((p) => p.room === id && !def?.includes.includes(p.id)).map((p) => (ITEMS[p.id].optional ? fmt(P.optionalExtra, { item: ITEMS[p.id].label }) : ITEMS[p.id].label)))];
    const m = details?.materials;
    const cats = s && m ? m.categories.map((code) => s.categories.find((c) => c.code === code)).filter(Boolean) : [];
    const material = cats.map((c) => el('div', { class: 'v2-spec-cat' }, el('p', {}, el('strong', { text: `${c.label}: ` }), c.requirement),
      c.brand_examples.length ? el('p', { class: 'v2-small', text: fmt(P.approvedExamples, { brands: c.brand_examples.join(', ') }) }) : null));
    return el('article', { class: 'v2-room-card', 'aria-label': def?.label || r.label },
      el('div', { class: 'v2-room-row' }, el('h4', { text: def?.label || r.label }), el('span', { class: 'v2-room-amount', text: roomAmount(r.amount_minor) })),
      el('p', { class: 'v2-room-std', text: [...std, ...extras.map((x) => `+ ${x}`)].join(' · ') }),
      s && m?.line ? el('p', { class: 'v2-spec-line' }, el('strong', { text: U.labels.essentialSpec }), m.line) : null,
      disclosure(U.labels.viewInclusions,
        el('h5', { text: U.labels.includedItems }), ul(std),
        el('h5', { text: U.labels.materialSpec }), ...(material.length ? [...material, el('p', { class: 'v2-small', text: s.final_selection })] : [el('p', { text: P.materialsFallback })]),
        el('h5', { text: U.labels.extras }), extras.length ? ul(extras) : el('p', { text: P.noneAdded }),
        el('h5', { text: U.labels.assumptions }), roomAssumptions(r.room).length ? ul(roomAssumptions(r.room)) : el('p', { text: P.measuredRoom })));
  }
  // The package components the engine priced for this scope, in the owner's wording (T5); never a fixed list.
  function packageParts(e) {
    const codes = e.project_preparation.component_codes || [];
    const parts = codes.map((code) => P.packageComponents[code] || P.packageOther);
    return [...new Set(parts)];
  }
  function renderResult() {
    const e = state.estimate;
    if (!e) return;
    const s = spec();
    const t = approved();
    const b = buildUp(e);
    const Lb = U.labels;
    const range = (low, high) => `${rupees(low)} – ${rupees(high)}`;
    $('#v2-range').textContent = range(e.range.low_minor, e.range.high_minor);
    $('#v2-gst').textContent = fmt(P.gstExtra, { pct: e.gst.pct, low: rupees(e.gst.low_minor), high: rupees(e.gst.high_minor) });
    const measured = Object.values(state.measures).some((v) => Number(v) > 0);
    $('#v2-basis').textContent = fmt(Lb.basis, { size: SIZE_LABEL[state.size], type: state.type === 'VILLA' ? Lb.villa : Lb.apartment,
      kind: state.kind === 'NEW_HOME' ? Lb.newHome : Lb.renovation, basis: measured ? P.basisMeasured : fmt(P.basisTypical, { size: SIZE_LABEL[state.size] }) });
    const toRefine = () => show(8);
    const toQuote = () => { state.consult = null; save(); show(7); };
    const toDesigner = () => { state.consult = 'designer'; save(); show(7); };
    const markers = P.markers.filter((m) => s || m !== P.markers[2]);
    $('#v2-top').replaceChildren(
      el('div', { class: 'v2-block v2-includes-block' }, el('h3', { text: Lb.yourEstimateIncludes }),
        ul(P.includes), el('p', { class: 'v2-small', text: P.gstSeparate })),
      el('ul', { class: 'v2-markers', 'aria-label': Lb.aboutEstimate }, ...markers.map((m) => el('li', { text: m }))),
      el('div', { class: 'v2-block' }, el('h3', { text: Lb.whyRange }), ul(P.whyRange),
        button('v2-primary v2-wide', Lb.personalise, toRefine)),
      el('p', {}, el('a', { class: 'v2-link', href: '#v2-next-steps', text: Lb.whatNextLink })));
    const details = Object.fromEntries((e.room_details || []).map((d) => [d.room, d]));
    const policy = e.warranty?.policy_url || '/warranty';
    const build = el('dl', { class: 'v2-build', id: 'v2-build' },
      ...amountRow(Lb.rowRooms, rupees(b.rooms), [b.rooms, b.rooms]),
      ...(b.optional ? amountRow(Lb.rowOptional, rupees(b.optional), [b.optional, b.optional]) : []),
      ...amountRow(`+ ${PACKAGE_NAME}`, rupees(b.pkg), [b.pkg, b.pkg]),
      ...amountRow(`+ ${ALLOWANCE_NAME}`, range(b.allowLow, b.allowHigh), [b.allowLow, b.allowHigh]),
      ...amountRow(Lb.rowVariation, fmt(Lb.variation, { low: signed(b.varLow), high: signed(b.varHigh) }), [b.varLow, b.varHigh]),
      el('dt', { class: 'v2-total', text: Lb.rowRange }), el('dd', { class: 'v2-total', text: range(e.range.low_minor, e.range.high_minor), 'data-low': e.range.low_minor, 'data-high': e.range.high_minor }),
      el('dt', { text: Lb.rowGst }), el('dd', { text: fmt(Lb.about, { low: rupees(e.gst.low_minor), high: rupees(e.gst.high_minor) }) }));
    // Only registered runtime text reaches the page (M3): exclusions and client scope from the approved block.
    const notIncluded = [...t.exclusions, ...(t.client_scope.length ? [fmt(P.supplied, { items: t.client_scope.join(', ') })] : [])];
    const technical = (e.room_details || []).filter((d) => roomAssumptions(d.room).length)
      .flatMap((d) => [el('h4', { text: (rooms().find((x) => x.id === roomIdOf(d.room)) || {}).label || d.room }), ul(roomAssumptions(d.room))]);
    $('#v2-result-body').replaceChildren(
      section(Lb.howBuilt, build, el('p', { class: 'v2-small', text: P.buildNote })),
      section(Lb.whatEssential, ...(s ? [el('p', { class: 'v2-small', text: s.summary }),
        disclosure(fmt(Lb.seeCategories, { count: s.categories.length }), el('dl', { class: 'v2-promise' }, ...s.categories.flatMap((c) => [el('dt', { text: c.label }), el('dd', { text: c.summary })]))),
        el('p', { class: 'v2-small', text: `${s.equivalent_policy} ${s.final_selection}` }),
        button('v2-link', Lb.viewSpec, () => { state.specReturn = 6; show(10); })]
        : [el('p', { text: P.materialsFallback })])),
      section(Lb.roomsTitle, ...e.rooms.map((r) => roomCard(r, details[r.room])), el('p', { class: 'v2-small', text: P.roomsNote })),
      section(PACKAGE_NAME, el('p', { class: 'v2-amount', text: rupees(b.pkg) }), el('p', { class: 'v2-badge', text: P.includedBadge }),
        el('p', { text: P.packageText }),
        disclosure(Lb.whatItCovers, ul(packageParts(e)), el('p', { class: 'v2-small', text: P.packageQuoteNote }))),
      section(ALLOWANCE_NAME, el('p', { class: 'v2-amount', text: range(b.allowLow, b.allowHigh) }), el('p', { class: 'v2-badge', text: P.includedBadge }),
        el('p', { text: P.allowanceText }), ul(P.allowanceNotes),
        disclosure(Lb.whatUsuallyCovers, ul(P.allowanceExamples))),
      section(Lb.warrantyTitle,
        el('h4', { text: Lb.manufacturerTitle }), el('p', { text: s?.warranty_summary || P.manufacturer }),
        el('h4', { text: Lb.serviceTitle }), el('p', { text: P.service }), el('p', { class: 'v2-small', text: P.serviceNote }),
        el('p', {}, el('a', { href: policy, text: Lb.policyLink }))),
      section(Lb.notIncludedTitle, notIncluded.length ? ul(notIncluded) : el('p', { text: P.exclusionsFallback })),
      section(Lb.compareTitle, el('p', { text: P.compareIntro }), ul(P.compare)),
      section(measured ? Lb.assumptionsUsed : fmt(Lb.typicalAssumptions, { size: SIZE_LABEL[state.size] }), ul(typicalAssumptions()),
        disclosure(Lb.technicalAssumptions, ...technical)),
      el('section', { class: 'v2-block v2-next-steps', id: 'v2-next-steps', 'aria-label': Lb.nextTitle }, el('h3', { text: Lb.nextTitle }),
        el('ol', { class: 'v2-steps' }, ...P.nextSteps.map((m) => el('li', { text: m }))),
        button('v2-primary v2-wide', Lb.personalise, toRefine),
        button('v2-ghost v2-wide', Lb.quotation, toQuote),
        button('v2-link', Lb.designer, toDesigner)),
    );
    $('#v2-disclaimer').textContent = t.disclaimer || P.disclaimer;
    $('#v2-meta').textContent = fmt(Lb.meta, { ref: e.reference, date: e.expires_on, spec: s ? `${s.name} ${s.version}` : P.specificationFallback });
  }
  function renderSpec() {
    const s = spec();
    $('#v2-spec-sub').textContent = s ? fmt(U.labels.specSub, { name: s.name, version: s.version, policy: s.equivalent_policy, final: s.final_selection }) : '';
    // Each category keeps the four parts apart (T3): what is promised, brand examples, the equivalent rule, final selection.
    const row = (term, value) => (value ? [el('dt', { text: term }), el('dd', { text: value })] : []);
    $('#v2-spec').replaceChildren(...(s ? s.categories.map((c) => el('section', { class: 'v2-spec-cat' }, el('h3', { text: c.label }),
      el('dl', { class: 'v2-spec-dl' },
        ...row(U.labels.requirement, c.requirement),
        ...row(U.labels.grade, c.grade),
        ...row(U.labels.thickness, c.thickness.join('; ')),
        ...row(U.labels.finish, c.finish),
        ...row(U.labels.brands, c.brand_examples.join(', ')),
        ...row(U.labels.equivalent, c.equivalent_rule),
        ...row(U.labels.finalSelection, c.final_selection),
        ...row(U.labels.warranty, c.warranty_summary)),
      c.details.length ? ul(c.details) : null))
      : [el('p', { text: P.materialsFallback })]));
  }
  function renderLead() {
    const c = state.consult;
    $('#v2-h7').textContent = c ? U.labels.consultTitle : U.labels.quoteTitle;
    $('#v2-lead-sub').textContent = c === 'luxury' ? P.leadLuxury : c === 'designer' ? P.leadDesigner : P.leadQuote;
    $('#v2-send').textContent = c ? U.labels.sendConsult : U.labels.sendQuote;
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
      const input = el('input', { id, type: 'number', inputmode: 'decimal', min: String(f.min), max: String(f.max), step: 'any', placeholder: U.labels.placeholder, value: state.measures[key] || '', 'aria-describedby': `${id}-h` });
      input.addEventListener('input', () => { state.measures[key] = input.value; save(); });
      box.append(el('label', { class: 'v2-measure', for: id }, el('span', {}, f.label, input), el('span', { class: 'v2-unit', text: f.unit }),
        el('small', { id: `${id}-h`, text: fmt(U.hintRange, f) })));
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
      if (v !== undefined && v !== '' && !(Number(v) >= f.min && Number(v) <= f.max)) problems.push({ text: fmt(U.rangeError, f), field: `v2-m-${f.room}-${f.item}` });
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
    if (!$('#v2-name').value.trim()) problems.push({ text: U.needName, field: 'v2-name' });
    if ($('#v2-phone').value.replace(/\D/g, '').length < 10) problems.push({ text: U.needPhone, field: 'v2-phone' });
    if (!$('#v2-consent').checked) problems.push({ text: U.needConsent, field: 'v2-consent' });
    if (problems.length) { summary(problems); return; }
    state.enquiryKey = state.enquiryKey || `est-${randomToken()}`; save();
    const e = state.estimate;
    const c = state.consult;
    const rooms3 = chosen().map((p) => ITEMS[p.id].label);
    const message = c === 'luxury' ? fmt(U.enquiry.luxury, { rooms: [...new Set(rooms3)].join(', ') }).slice(0, 500)
      : fmt(c === 'designer' ? U.enquiry.designer : U.enquiry.quote, { ref: e?.reference });
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
      $('#v2-next').textContent = c ? P.doneConsult : P.doneQuote;
      $('#v2-estimate-ref').textContent = c !== 'luxury' && e ? fmt(P.keepRef, { ref: e.reference }) : '';
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
  $('#est-lead').textContent = P.lead;
  $('#v2-refine-intro').textContent = P.refineIntro;
  if (!propertyTypes.includes(state.type)) state.type = propertyTypes[0];
  if (!homeSizes.includes(state.size)) state.size = homeSizes[0];
  const valid = state.estimate && state.estimate.expires_on >= new Date().toISOString().slice(0, 10);
  if (!valid) state.estimate = null;
  let start = state.screen;
  if ([6, 8, 10].includes(start) && !state.estimate) start = 5;
  if (start === 9) start = 1;
  show(start, { focus: false });
})();
