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
  async function call(method, path, payload) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const res = await fetch(`${apiBase}${path}`, { method, signal: controller.signal, credentials,
        headers: payload ? { 'Content-Type': 'application/json', 'X-Veda-Client': clientToken } : { 'X-Veda-Client': clientToken }, body: payload ? JSON.stringify(payload) : undefined });
      return { status: res.status, body: await res.json().catch(() => ({})) };
    } catch (err) {
      return { status: 0, body: { code: err.name === 'AbortError' ? 'TIMEOUT' : 'UNREACHABLE' } };
    } finally { clearTimeout(timer); }
  }
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
    } catch { /* refused with CAPTCHA_FAILED and explained */ }
  }
  const token = (name) => (window.turnstile && widgets[name] !== undefined ? window.turnstile.getResponse(widgets[name]) : '') || '';
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
    $('#v3-gallery-body').replaceChildren(el('p', { class: 'v3-note', text: 'Images show the kind of work, not the exact design you will receive.' }),
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
  const describe = (d) => [d.description && el('p', { text: d.description }),
    d.what_is_this && el('details', { class: 'v3-what' }, el('summary', { text: 'What is this?' }), el('p', { text: d.what_is_this }),
      d.typically_used_for ? el('p', { class: 'v3-note', text: `Typically used for: ${d.typically_used_for}` }) : null)];

  // --- screens -----------------------------------------------------------------------------------------------------------
  function show(n) {
    state.screen = n;
    document.querySelectorAll('#v3 .v3-screen').forEach((s) => { s.hidden = Number(s.dataset.v3) !== n; });
    $('#v3-summary').hidden = true;
    ({ 1: renderHome, 2: renderRooms, 3: renderResult })[n]();
    if (n === 2) widget('estimate', '#v3-ts-estimate');
    document.querySelector(`[data-v3="${n}"] h2`)?.focus();
  }
  document.querySelectorAll('[data-v3-back]').forEach((b) => b.addEventListener('click', () => show(Number(b.dataset.v3Back))));

  function radio(name, value, checked, label, sub, onChange) {
    const input = el('input', { type: 'radio', name, value, checked });
    input.addEventListener('change', onChange);
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
          const label = radio(`v3-${rkey}-${slot.product}-${g.key}`, c.key, c.key === current, c.name, c.description,
            () => { ps.options = { ...(ps.options || {}), [g.key]: c.key }; renderRooms(); });
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
    $('#v3-rooms').replaceChildren(...home().rooms.map((slot) => {
      const room = C.room_template[slot.room_template];
      if (!room) return null;
      const rs = roomState(slot.room_template);
      const toggle = el('input', { type: 'checkbox', checked: rs.on });
      toggle.addEventListener('change', () => { rs.on = toggle.checked; track(rs.on ? 'room_selected' : 'room_deselected', slot.room_template); renderRooms(); });
      const card = el('article', { class: `v3-room${rs.on ? '' : ' v3-room-off'}`, 'aria-label': room.name },
        picture(room.image), el('label', { class: 'v3-check v3-room-title' }, toggle, el('h3', { text: room.name })),
        el('p', { class: 'v3-note', text: `${room.included.length} included · ${Object.keys(rs.extras).length} extras selected` }), ...describe(room));
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
  function problems(body) {
    const list = Array.isArray(body.errors) && body.errors.length ? body.errors.map((e) => e.message) : ['We could not prepare an estimate right now. Please try again.'];
    const box = $('#v3-summary');
    box.replaceChildren(el('p', { text: 'Please check the following:' }), el('ul', {}, ...[...new Set(list)].map((t) => el('li', { text: t }))));
    box.hidden = false; box.focus();
  }
  async function estimate(widgetName) {
    const r = await call('POST', '/api/v1/public/catalog/estimates', { configuration: configuration(), turnstile_token: token(widgetName) });
    widget(widgetName, widgetName === 'refine' ? '#v3-ts-refine' : '#v3-ts-estimate');
    if (r.status === 201) { state.estimate = r.body.data; return true; }
    problems(r.body);
    return false;
  }
  $('#v3-estimate').addEventListener('click', async () => { if (await estimate('estimate')) { track('estimate_reached'); show(3); } });

  function renderResult() {
    const e = state.estimate;
    const copyOf = (category) => Object.values(C.copy).filter((c) => c.category === category).map((c) => c.statement);
    $('#v3-result').replaceChildren(
      el('p', { class: 'v3-range' }, el('strong', { text: `${rupees(e.range.low_minor)} – ${rupees(e.range.high_minor)}` })),
      el('ul', { class: 'v3-rooms-total' }, ...(e.rooms || []).map((r) => el('li', {}, el('span', { text: r.label }), el('span', { text: rupees(r.amount_minor) })))),
      el('p', { class: 'v3-note', text: `Reference ${e.configuration_reference} · catalog ${e.catalog_release}` }),
      ...copyOf('next_step').map((t) => el('p', { text: t })),
      ...copyOf('disclaimer').map((t) => el('p', { class: 'v3-note', text: t })),
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
    $('#v3-refine').addEventListener('toggle', () => widget('refine', '#v3-ts-refine'), { once: true });
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
