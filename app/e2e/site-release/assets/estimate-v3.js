// Veda Spaces Budgetary Estimate V3: the catalog-driven estimator (ADR-013).
// Runs only when <meta name="veda-estimator-version"> is "v3" and the API base and Turnstile key are set. Everything
// shown comes from the active catalog release (GET /api/v1/public/catalog): rooms, items, finishes, extras, images,
// copy. Estimate first, measurements later. No rates or prices are in this file or in the catalog view; the server
// prices every configuration with the existing engine and refuses unsupported combinations. 3D views load lazily,
// show a preview image first, fall back to the gallery, and never affect the estimate. The DOM is built with
// textContent only.
'use strict';

(() => {
  const meta = (name) => document.querySelector(`meta[name="${name}"]`)?.content?.trim() || '';
  if (meta('veda-estimator-version') !== 'v3' || !meta('veda-api-base') || !meta('veda-turnstile-sitekey')) return;
  const apiBase = meta('veda-api-base');
  const credentials = meta('veda-api-credentials') === 'include' ? 'include' : 'same-origin';
  const $ = (s) => document.querySelector(s);
  const el = (tag, attrs = {}, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === false || v == null) continue;
      if (k === 'text') n.textContent = v;
      else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? '' : v);
    }
    for (const k of kids) if (k) n.append(k);
    return n;
  };
  const rupees = (minor) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(Math.round(minor / 100));
  const byId = (map) => Object.entries(map || {});
  const sorted = (map) => byId(map).sort(([, a], [, b]) => (a.sort ?? 100) - (b.sort ?? 100));

  let C = null; // the catalog view
  // A random per-browser-session token: the rate-limit key the API prefers over the network address (ADR-012).
  const randomToken = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, '0')).join('');
  const clientToken = (() => { try { const t = sessionStorage.getItem('veda-client') || randomToken(); sessionStorage.setItem('veda-client', t); return t; } catch { return randomToken(); } })();
  const state = { home: null, pkg: null, kind: 'NEW_HOME', rooms: {}, estimate: null, screen: 1 };

  // --- API ---------------------------------------------------------------------------------------------------------------
  async function call(method, path, payload, extraHeaders = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const headers = { 'X-Veda-Client': clientToken, ...extraHeaders, ...(payload ? { 'Content-Type': 'application/json' } : {}) };
      const res = await fetch(`${apiBase}${path}`, { method, signal: controller.signal, credentials, headers, body: payload ? JSON.stringify(payload) : undefined });
      return { status: res.status, body: await res.json().catch(() => ({})) };
    } catch (err) {
      return { status: 0, body: { code: err.name === 'AbortError' ? 'TIMEOUT' : 'UNREACHABLE' } };
    } finally { clearTimeout(timer); }
  }
  // --- anti-bot readiness (customer-safety closure) ------------------------------------------------------------------
  // One state machine per widget: NOT_LOADED → LOADING → READY_NO_TOKEN → TOKEN_AVAILABLE → SUBMITTING → SUCCEEDED,
  // with FAILED and EXPIRED. A token is available only when Turnstile's own callback delivers it (never because the
  // renderer exists). Submitting needs TOKEN_AVAILABLE and reads the live token at that moment; an empty, stale,
  // expired or already-used token is never sent. While a request is in flight nothing else can be sent.
  const TOKEN_LIFETIME_MS = 280000; // Turnstile tokens are valid for 300 s; treat them as stale a little earlier
  const LOAD_TIMEOUT_MS = 15000;
  const STATUS = {
    NOT_LOADED: 'Preparing a quick security check…',
    LOADING: 'Preparing a quick security check…',
    READY_NO_TOKEN: 'Completing a quick security check…',
    TOKEN_AVAILABLE: 'Ready.',
    SUBMITTING: 'Preparing your estimate…',
    SUCCEEDED: '',
    FAILED: 'The security check could not be completed. Please retry.',
    EXPIRED: 'The security check expired. It is being renewed…',
  };
  const guards = {
    estimate: { box: '#v3-ts-estimate', button: '#v3-estimate', status: '#v3-ts-estimate-status', retry: '#v3-ts-estimate-retry' },
    refine: { box: '#v3-ts-refine', button: '#v3-reestimate', status: '#v3-ts-refine-status', retry: '#v3-ts-refine-retry' },
  };
  for (const g of Object.values(guards)) Object.assign(g, { state: 'NOT_LOADED', id: undefined, token: '', at: 0, used: new Set(), key: null, sent: null });
  const newKey = () => `v3-${randomToken()}`;
  function setState(g, next) {
    g.state = next;
    const ready = next === 'TOKEN_AVAILABLE';
    const button = $(g.button);
    if (button) { button.setAttribute('aria-disabled', String(!ready)); button.classList.toggle('v3-waiting', !ready); }
    const status = $(g.status);
    if (status) status.textContent = STATUS[next];
    const retry = $(g.retry);
    if (retry) retry.hidden = next !== 'FAILED';
  }
  let loading = null;
  function loadTurnstile() {
    if (window.turnstile) return Promise.resolve();
    if (loading) return loading;
    loading = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      s.async = true;
      const timer = setTimeout(() => { s.remove(); reject(new Error('timeout')); }, LOAD_TIMEOUT_MS);
      s.onload = () => { clearTimeout(timer); window.turnstile ? resolve() : reject(new Error('turnstile')); };
      s.onerror = () => { clearTimeout(timer); s.remove(); reject(new Error('turnstile')); };
      document.head.appendChild(s);
    }).catch((err) => { loading = null; throw err; });
    return loading;
  }
  function onToken(g, value) {
    if (!value || g.used.has(value)) { setState(g, g.state === 'SUBMITTING' ? 'SUBMITTING' : 'READY_NO_TOKEN'); return; }
    g.token = value; g.at = Date.now();
    if (g.state !== 'SUBMITTING') setState(g, 'TOKEN_AVAILABLE');
  }
  function onExpired(g) {
    g.token = '';
    if (g.state === 'SUBMITTING') return; // the request already carries its token; a fresh one is fetched after it
    setState(g, 'EXPIRED');
    renew(g);
  }
  function renew(g) {
    g.token = '';
    try { if (window.turnstile && g.id !== undefined) window.turnstile.reset(g.id); } catch { setState(g, 'FAILED'); }
  }
  async function prepare(name) {
    const g = guards[name];
    if (['LOADING', 'READY_NO_TOKEN', 'TOKEN_AVAILABLE', 'SUBMITTING', 'EXPIRED'].includes(g.state)) return;
    setState(g, 'LOADING');
    try {
      await loadTurnstile();
      if (g.id === undefined) {
        g.id = window.turnstile.render(g.box, {
          sitekey: meta('veda-turnstile-sitekey'),
          callback: (value) => onToken(g, value),
          'expired-callback': () => onExpired(g),
          'timeout-callback': () => onExpired(g),
          'error-callback': () => { g.token = ''; if (g.state !== 'SUBMITTING') setState(g, 'FAILED'); return true; },
        });
      } else renew(g);
      if (g.state === 'LOADING') setState(g, g.token ? 'TOKEN_AVAILABLE' : 'READY_NO_TOKEN');
    } catch {
      setState(g, 'FAILED'); // never submit without the check: the customer is offered a retry
    }
  }
  /** The live token, if one may be sent now; otherwise '' and the widget is renewed. */
  function liveToken(g) {
    if (g.state !== 'TOKEN_AVAILABLE' || !window.turnstile || g.id === undefined) return '';
    const live = window.turnstile.getResponse(g.id) || '';
    if (!live || live !== g.token || g.used.has(live) || Date.now() - g.at > TOKEN_LIFETIME_MS) {
      setState(g, 'EXPIRED');
      renew(g);
      return '';
    }
    return live;
  }
  for (const [name, g] of Object.entries(guards)) {
    const retry = $(g.retry);
    if (!retry) continue;
    retry.addEventListener('click', () => {
      if (g.id === undefined) { g.state = 'NOT_LOADED'; prepare(name); return; } // the script never loaded: try again
      setState(g, 'READY_NO_TOKEN'); // the widget exists: ask it for a fresh token
      renew(g);
    });
  }
  // Staging validation analytics: counts per catalog key only, never a person or free text; off unless the meta says so.
  const track = (event, subject) => {
    if (meta('veda-catalog-analytics') !== 'on' || navigator.doNotTrack === '1') return;
    call('POST', '/api/v1/public/catalog/events', { event, subject: subject || null });
  };

  // --- media -------------------------------------------------------------------------------------------------------------
  const media = (key) => (key && C.media[key]) || null;
  const abs = (url) => (url && url.startsWith('/') ? `${apiBase}${url}` : url); // media is served by the API host
  function picture(key, { sizes = '(max-width: 700px) 100vw, 50vw', cls = 'v3-img' } = {}) {
    const m = media(key);
    if (!m || !m.urls) return null;
    const src = abs(m.urls.mobile || m.urls.desktop || m.urls.thumb);
    const set = [['thumb', 320], ['mobile', 768], ['desktop', 1600]].filter(([k]) => m.urls[k]).map(([k, w]) => `${abs(m.urls[k])} ${w}w`).join(', ');
    const img = el('img', { src, srcset: set || null, sizes, alt: m.alt || '', loading: 'lazy', decoding: 'async', class: cls });
    img.addEventListener('error', () => img.replaceWith(el('span', { class: 'v3-img-missing', text: m.alt || m.title })));
    return el('figure', { class: 'v3-figure' }, img, el('figcaption', {}, el('span', { class: 'v3-badge', text: m.label }), m.caption ? ` ${m.caption}` : ''));
  }
  function openGallery(key) {
    const g = media(key);
    if (!g) return;
    track('gallery_viewed', key);
    $('#v3-gallery-title').textContent = g.title;
    $('#v3-gallery-body').replaceChildren(el('p', { class: 'v3-note', text: statement('copy.image-disclaimer', '') }),
      ...(g.items || []).map((k) => picture(k, { sizes: '(max-width: 700px) 100vw, 700px' })).filter(Boolean));
    $('#v3-gallery').showModal();
  }
  $('#v3-gallery-close').addEventListener('click', () => $('#v3-gallery').close());

  // 3D abstraction: preview first; the model loads only on request and only with a vendored renderer. Without one (the
  // renderer library is an owner decision, ADR-013), the customer sees the gallery instead. Never used for pricing.
  const Viewer3D = {
    available: () => !!(window.customElements && window.customElements.get('model-viewer')),
    mount(container, key) {
      const m = media(key);
      if (!m || !m.three_d) return;
      const preview = picture(m.three_d.preview_image);
      const button = el('button', { type: 'button', class: 'v3-ghost', text: 'View in 3D' });
      const box = el('div', { class: 'v3-3d' }, preview, button);
      button.addEventListener('click', () => {
        track('preview_3d_started', key);
        if (!this.available() || !m.urls.web) {
          track('preview_3d_fallback', key);
          box.replaceChildren(el('p', { class: 'v3-note', text: '3D view is not available on this device; here are photos instead.' }));
          openGallery(m.three_d.fallback_gallery);
          return;
        }
        const viewer = el('model-viewer', { src: abs(m.urls.web), alt: m.alt, 'camera-controls': true, loading: 'lazy', reveal: 'interaction' });
        viewer.addEventListener('load', () => track('preview_3d_succeeded', key));
        viewer.addEventListener('error', () => { track('preview_3d_fallback', key); openGallery(m.three_d.fallback_gallery); });
        box.replaceChildren(viewer, el('p', { class: 'v3-note', text: `${m.label}. The 3D view does not change your estimate.` }));
      });
      container.append(box);
    },
  };

  // --- state helpers -----------------------------------------------------------------------------------------------------
  const home = () => C.home_config[state.home];
  const roomState = (rkey) => {
    if (!state.rooms[rkey]) {
      const slot = home().rooms.find((r) => r.room_template === rkey);
      const room = C.room_template[rkey];
      state.rooms[rkey] = { on: slot ? slot.default_selected !== false : true, products: {}, extras: {} };
      for (const x of room.extras || []) if (C.extra[x]?.default_selected) state.rooms[rkey].extras[x] = {};
    }
    return state.rooms[rkey];
  };
  const variantOf = (pkey, slot, ps) => {
    const p = C.product[pkey];
    return p.variants.find((v) => v.key === (ps.variant || slot.variant)) || p.variants[0];
  };
  // A choice under a requires_consultation rule (no condition) is consultation-only: its message, or null.
  const consultation = (pkey, vkey, gkey, ckey) => {
    const paths = new Set([`product:${pkey}@${gkey}=${ckey}`, `product:${pkey}#${vkey}@${gkey}=${ckey}`]);
    const rule = Object.values(C.rule || {}).find((r) => r.type === 'requires_consultation' && !r.condition && paths.has(r.subject));
    return rule ? (C.copy[rule.message]?.statement || 'Discussed in a consultation.') : null;
  };
  const statement = (key, fallback) => C.copy[key]?.statement || fallback;
  const describe = (d) => [d.description && el('p', { text: d.description }),
    d.what_is_this && el('details', { class: 'v3-what' }, el('summary', { text: 'What is this?' }), el('p', { text: d.what_is_this }),
      d.typically_used_for ? el('p', { class: 'v3-note', text: `Typically used for: ${d.typically_used_for}` }) : null)];

  // --- screens -----------------------------------------------------------------------------------------------------------
  function show(n) {
    state.screen = n;
    document.querySelectorAll('#v3 .v3-screen').forEach((s) => { s.hidden = Number(s.dataset.v3) !== n; });
    $('#v3-summary').hidden = true;
    ({ 1: renderHome, 2: renderRooms, 3: renderResult })[n]();
    if (n === 2) prepare('estimate');
    document.querySelector(`[data-v3="${n}"] h2`)?.focus();
  }
  document.querySelectorAll('[data-v3-back]').forEach((b) => b.addEventListener('click', () => show(Number(b.dataset.v3Back))));

  function radio(name, value, checked, label, sub, onChange) {
    const input = el('input', { type: 'radio', name, value, checked });
    input.addEventListener('change', () => {
      onChange();
      // The change re-renders its section: keep keyboard focus on the same choice (never lost to the page body).
      const again = document.querySelector(`input[type="radio"][name="${CSS.escape(name)}"][value="${CSS.escape(value)}"]`);
      if (again && again !== input) again.focus();
    });
    return el('label', { class: 'v3-choice' }, input, el('span', {}, el('strong', { text: label }), sub ? el('small', { text: sub }) : null));
  }
  function renderHome() {
    $('#v3-homes').replaceChildren(...sorted(C.home_config).map(([k, h]) => radio('v3-home', k, state.home === k, h.name, h.description,
      () => { state.home = k; state.rooms = {}; state.pkg = null; renderHome(); })));
    const kinds = home().availability?.project_kinds?.length ? home().availability.project_kinds : ['NEW_HOME', 'RENOVATION'];
    if (!kinds.includes(state.kind)) state.kind = kinds[0];
    $('#v3-kinds').replaceChildren(...kinds.map((k) => radio('v3-kind', k, state.kind === k, k === 'NEW_HOME' ? 'New home' : 'Renovation', null, () => { state.kind = k; })));
    const pkgs = home().packages.map((k) => [k, C.package[k]]).filter(([, p]) => p);
    if (!state.pkg) state.pkg = (pkgs.find(([, p]) => p.recommended && !p.consultation_only) || pkgs.find(([, p]) => !p.consultation_only) || [])[0];
    $('#v3-packages').replaceChildren(...pkgs.map(([k, p]) => {
      const summary = C.copy[p.public_summary]?.statement;
      const choice = radio('v3-pkg', k, state.pkg === k, p.name, summary, () => { state.pkg = k; });
      if (p.consultation_only) { choice.querySelector('input').disabled = true; choice.classList.add('v3-off'); }
      return choice;
    }));
  }
  $('#v3-to-rooms').addEventListener('click', () => show(2));

  function productBlock(rkey, slot) {
    const p = C.product[slot.product];
    if (!p) return null;
    const rs = roomState(rkey);
    const ps = rs.products[slot.product] || (rs.products[slot.product] = {});
    const v = variantOf(slot.product, slot, ps);
    const block = el('div', { class: 'v3-product' }, el('h4', { text: p.name }), ...describe(p));
    const imgKey = (v.media || [])[0] || (p.media || []).find((k) => media(k)?.type === 'IMAGE');
    if (imgKey) block.append(picture(imgKey));
    if (p.variants.length > 1) {
      block.append(el('fieldset', { class: 'v3-group' }, el('legend', { text: 'Style' }),
        ...p.variants.map((x) => radio(`v3-${rkey}-${slot.product}-variant`, x.key, x.key === v.key, x.name, x.description,
          () => { ps.variant = x.key; ps.options = {}; renderRooms(); }))));
    }
    for (const g of v.option_groups || []) {
      const preset = v.key === slot.variant ? (slot.options || {})[g.key] : null;
      const current = (ps.options || {})[g.key] || preset || g.default;
      block.append(el('fieldset', { class: 'v3-group' }, el('legend', { text: g.name }),
        ...g.choices.map((c) => {
          const consult = consultation(slot.product, v.key, g.key, c.key);
          const label = radio(`v3-${rkey}-${slot.product}-${g.key}`, c.key, c.key === current && !consult, c.name, c.description,
            () => { ps.options = { ...(ps.options || {}), [g.key]: c.key }; renderRooms(); });
          if (consult) { // never priced online: shown, not selectable, and routed to a consultation
            label.querySelector('input').disabled = true;
            label.classList.add('v3-off');
            label.querySelector('span').append(el('small', { class: 'v3-note', text: consult }),
              el('a', { href: '/#contact', class: 'v3-consult', text: 'Ask about this in a consultation', onclick: () => track('quotation_requested', slot.product) }));
          }
          const cm = (c.materials || []).map((m) => C.material[m]).filter(Boolean);
          if (cm.length) label.querySelector('span').append(el('small', { class: 'v3-note', text: cm.map((m) => C.copy[m.statements?.[0]]?.statement || m.name).join(' ') }));
          return label;
        })));
    }
    const galleryKey = (p.media || []).find((k) => media(k)?.type === 'GALLERY');
    if (galleryKey) block.append(el('button', { type: 'button', class: 'v3-ghost', text: 'See examples', onclick: () => openGallery(galleryKey) }));
    const modelKey = (p.media || []).find((k) => ['GLB', 'GLTF', 'USDZ'].includes(media(k)?.type));
    if (modelKey) Viewer3D.mount(block, modelKey);
    return block;
  }
  function extraBlock(rkey, xkey) {
    const x = C.extra[xkey];
    if (!x) return null;
    const rs = roomState(rkey);
    const on = !!rs.extras[xkey];
    const input = el('input', { type: 'checkbox', checked: on });
    input.addEventListener('change', () => {
      if (input.checked) { rs.extras[xkey] = {}; track('extra_selected', xkey); } else delete rs.extras[xkey];
    });
    const box = el('div', { class: 'v3-extra' }, el('label', { class: 'v3-check' }, input, el('strong', { text: x.name })), ...describe(x));
    box.querySelector('details')?.addEventListener('toggle', () => track('extra_viewed', xkey), { once: true });
    if ((x.media || [])[0]) box.append(picture(x.media[0], { sizes: '200px', cls: 'v3-img v3-thumb' }));
    if (x.quantity === 'count') {
      const n = el('input', { type: 'number', min: 1, max: x.max_count, value: rs.extras[xkey]?.count || 1, 'aria-label': `How many: ${x.name}` });
      n.addEventListener('change', () => { if (rs.extras[xkey]) rs.extras[xkey].count = Math.max(1, Math.min(x.max_count, Number(n.value) || 1)); });
      box.append(n);
    }
    return box;
  }
  function renderRooms() {
    $('#v3-image-note').textContent = statement('copy.image-disclaimer', '');
    $('#v3-rooms').replaceChildren(...home().rooms.map((slot) => {
      const room = C.room_template[slot.room_template];
      if (!room) return null;
      const rs = roomState(slot.room_template);
      const toggle = el('input', { type: 'checkbox', checked: rs.on });
      toggle.addEventListener('change', () => { rs.on = toggle.checked; track(rs.on ? 'room_selected' : 'room_deselected', slot.room_template); renderRooms(); });
      const card = el('article', { class: `v3-room${rs.on ? '' : ' v3-room-off'}`, 'aria-label': room.name },
        picture(room.image), el('label', { class: 'v3-check v3-room-title' }, toggle, el('h3', { text: room.name })),
        el('p', { class: 'v3-note', text: `${room.included.length} items · ${Object.keys(rs.extras).length} extras chosen` }), ...describe(room));
      if (room.gallery) card.append(el('button', { type: 'button', class: 'v3-ghost', text: 'Room ideas', onclick: () => openGallery(room.gallery) }));
      if (rs.on) {
        card.append(...room.included.map((s) => productBlock(slot.room_template, s)).filter(Boolean));
        const extras = (room.extras || []).map((x) => extraBlock(slot.room_template, x)).filter(Boolean);
        if (extras.length) card.append(el('h4', { text: 'Add extras' }), ...extras);
      }
      return card;
    }).filter(Boolean));
  }

  function configuration() {
    return {
      home: state.home, package: state.pkg, project_kind: state.kind,
      rooms: home().rooms.filter((s) => roomState(s.room_template).on).map((s) => {
        const rs = roomState(s.room_template);
        const products = {};
        for (const [k, v] of Object.entries(rs.products)) {
          const entry = {};
          if (v.variant) entry.variant = v.variant;
          if (v.options && Object.keys(v.options).length) entry.options = v.options;
          if (v.measurements && Object.keys(v.measurements).length) entry.measurements = v.measurements;
          if (Object.keys(entry).length) products[k] = entry;
        }
        return { room: s.room_template, products, extras: rs.extras };
      }),
    };
  }
  function problems(heading, details = []) {
    const box = $('#v3-summary');
    box.replaceChildren(el('p', { 'data-field': 'summary', text: heading }),
      ...(details.length ? [el('ul', {}, ...[...new Set(details)].map((t) => el('li', { text: t })))] : []));
    box.hidden = false; box.focus();
  }
  // What the customer is told, by what actually happened (canonical customer-copy closure, Phase 8). Only an anti-bot
  // refusal says the security check failed; a server error, a timeout and a conflict each say what they are.
  const MESSAGES = {
    ANTI_BOT: 'The security check could not be completed. Please retry.',
    422: 'Please review the highlighted information.',
    409: 'This request conflicts with an earlier submission. Please refresh and try again.',
    429: 'Too many attempts. Please wait before trying again.',
    TIMEOUT: 'This is taking longer than expected. Your choices are kept; please try again.',
    UNREACHABLE: 'We could not reach our server. Your choices are kept; please try again.',
    SERVER: 'We could not prepare an estimate right now. Your choices are kept; please try again.',
  };
  function failure(r) {
    const code = r.body?.code;
    if (code === 'CAPTCHA_FAILED') return [MESSAGES.ANTI_BOT, []];
    if (r.status === 422) return [MESSAGES[422], (r.body?.errors || []).map((e) => e.message).filter(Boolean)];
    if (r.status === 409 || r.status === 429) return [MESSAGES[r.status], []];
    if (r.status === 0) return [MESSAGES[code] || MESSAGES.UNREACHABLE, []];
    return [MESSAGES.SERVER, []];
  }
  /** Send one estimate request, or nothing. Returns true on success. */
  async function estimate(name) {
    const g = guards[name];
    if (g.state === 'SUBMITTING') return false; // double click, key repeat: ignored while one is in flight
    const value = liveToken(g);
    if (!value) { prepare(name); return false; } // no valid token yet: nothing is sent
    const config = configuration();
    const configText = JSON.stringify(config);
    // One idempotency key per request; a retry of the same choices after a lost response reuses it.
    if (!g.sent || g.sent.config !== configText) g.sent = { config: configText, key: newKey() };
    g.used.add(value);
    setState(g, 'SUBMITTING');
    const r = await call('POST', '/api/v1/public/catalog/estimates', { configuration: config, turnstile_token: value },
      { 'Idempotency-Key': g.sent.key });
    g.token = '';
    if (r.status === 201) {
      g.sent = null;
      setState(g, 'SUCCEEDED');
      state.estimate = r.body.data;
      renew(g); setState(g, 'READY_NO_TOKEN'); // the next request gets its own token
      return true;
    }
    const lost = r.status === 0 || r.status >= 500;
    if (!lost) g.sent = null; // only a lost response is retried with the same key
    setState(g, 'FAILED');
    renew(g); // a fresh token arrives through the callback; the customer retries when ready
    problems(...failure(r));
    return false;
  }
  $('#v3-estimate').addEventListener('click', async () => { if (await estimate('estimate')) { track('estimate_reached'); show(3); } });

  function renderResult() {
    const e = state.estimate;
    const copyOf = (category) => Object.values(C.copy).filter((c) => c.category === category).map((c) => c.statement);
    // Every customer-critical field of the estimate response (E3); headings are page labels, names come from
    // registered catalog copy where it exists, otherwise from the estimate itself.
    const list = (items) => el('ul', {}, ...(items || []).map((x) => el('li', { text: x })));
    const block = (heading, ...kids) => el('section', { class: 'v3-block', 'aria-label': heading }, el('h3', { text: heading }), ...kids);
    const pp = e.project_preparation || {};
    const al = e.custom_features_allowance || {};
    const spec = e.specification;
    $('#v3-result').replaceChildren(
      el('p', { class: 'v3-range', 'data-field': 'range' }, el('strong', { text: `${rupees(e.range.low_minor)} – ${rupees(e.range.high_minor)}` })),
      el('p', { 'data-field': 'gst', text: `GST at ${e.gst.pct}% is added to this range: about ${rupees(e.gst.low_minor)} – ${rupees(e.gst.high_minor)}.` }),
      block('Your rooms', el('ul', { class: 'v3-rooms-total' }, ...(e.rooms || []).map((r) => el('li', {}, el('span', { text: r.label }), el('span', { text: rupees(r.amount_minor) }))))),
      block(statement('copy.label.site-package', pp.label), el('p', { 'data-field': 'project_preparation', text: `${rupees(pp.amount_minor || 0)}. ${pp.description || ''}` }), list(pp.inclusions)),
      block(statement('copy.label.allowance', al.label), el('p', { 'data-field': 'allowance', text: `${rupees(al.low_minor || 0)} – ${rupees(al.high_minor || 0)}. ${al.description || ''}` })),
      block('Timeline', el('p', { 'data-field': 'timeline', text: e.timeline ? `${e.timeline.label}: about ${e.timeline.min_days} – ${e.timeline.max_days} days` : '' })),
      block('Assumptions', list(e.assumptions)),
      block('Exclusions', list(e.exclusions)),
      block('What you supply', list(e.client_scope)),
      block('About this estimate',
        el('p', { 'data-field': 'validity', text: `Valid for ${e.validity_days} days, until ${e.expires_on}.` }),
        el('p', { 'data-field': 'specification', text: spec ? `Specification: ${spec.name || spec.spec_code} (${spec.spec_code})` : 'Specification: confirmed in your detailed quotation.' }),
        el('p', { 'data-field': 'release', text: `Reference ${e.configuration_reference} · catalog release ${e.catalog_release}` }),
        ...copyOf('next_step').map((t) => el('p', { text: t })),
        el('p', { class: 'v3-note', 'data-field': 'disclaimer', text: statement('copy.disclaimer', e.disclaimer) })),
    );
    // Refinement: the measurement prompts of the items chosen (estimate first, measurements later).
    const fields = [];
    for (const s of home().rooms) {
      const rs = roomState(s.room_template);
      if (!rs.on) continue;
      for (const slot of C.room_template[s.room_template].included) {
        const ps = rs.products[slot.product] || (rs.products[slot.product] = {});
        for (const m of variantOf(slot.product, slot, ps).measurements || []) {
          const id = `v3-m-${s.room_template}-${slot.product}-${m.input}`.replace(/[^\w-]/g, '_');
          const input = el('input', { id, type: 'number', inputmode: 'decimal', min: m.min, max: m.max, step: '0.5', value: ps.measurements?.[m.input] ?? '' });
          input.addEventListener('change', () => {
            ps.measurements = { ...(ps.measurements || {}) };
            if (input.value === '') delete ps.measurements[m.input]; else ps.measurements[m.input] = Number(input.value);
          });
          fields.push(el('label', { class: 'v3-field', for: id }, `${m.label} (${m.unit === 'sqft' ? 'sq ft' : 'ft'})`, input,
            el('small', { text: `${m.hint ? `${m.hint} ` : ''}Between ${m.min} and ${m.max}.` })));
        }
      }
    }
    $('#v3-refine').hidden = !fields.length;
    $('#v3-refine-fields').replaceChildren(...fields);
    $('#v3-refine').addEventListener('toggle', () => prepare('refine'), { once: true });
  }
  $('#v3-quote').addEventListener('click', () => track('quotation_requested'));
  $('#v3-reestimate').addEventListener('click', async () => { if (await estimate('refine')) { track('estimate_refined'); renderResult(); } });

  // --- start -------------------------------------------------------------------------------------------------------------
  (async () => {
    const r = await call('GET', '/api/v1/public/catalog');
    if (r.status !== 200 || !r.body.data) return; // the "Coming soon" panel stays
    C = r.body.data;
    const homes = sorted(C.home_config);
    if (!homes.length) return;
    state.home = homes[0][0];
    $('#v3-off').hidden = true;
    $('#v3').hidden = false;
    show(1);
  })();
})();
