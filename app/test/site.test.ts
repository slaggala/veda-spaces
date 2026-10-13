import { ContextProvider } from '@lit/context';
import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import '../src/design-system/components.js';
import { emptyRoom, fromMeasurement, toPayload } from '../src/modules/site/capture-model.js';
import type { SpaceMeasurement } from '../src/modules/site/api.js';
import { ApiClient } from '../src/core/api/client.js';
import type { Me } from '../src/core/api/types.js';
import { session, SessionController } from '../src/core/auth/session.js';
import { sessionContext } from '../src/core/authz/context.js';
import { MemoryStore, OfflineQueue, queue, sendBytes, SITE_DB } from '../src/modules/site/offline-queue.js';
import { siteDatabaseExists, siteSignOutGuard } from '../src/modules/site/sign-out.js';
import { fitWithin } from '../src/modules/site/photos.js';
import { formatArea, formatLength, parseLength } from '../src/modules/site/units.js';
import '../src/modules/site/index.js';

/** MTQ B1-T10: the site capture client (units, payloads, offline queue, photo sizing, pages). */

// The real design tokens (--vs-target is 44 px, the focus ring colour), so the pages measured and scanned are the ones
// a surveyor gets.
let tokens: HTMLLinkElement;
before(async () => {
  tokens = Object.assign(document.createElement('link'), { rel: 'stylesheet', href: '/src/design-system/tokens.css' });
  const loaded = new Promise((resolve) => { tokens.onload = resolve; });
  document.head.append(tokens);
  await loaded;
});
after(() => tokens.remove());

/** Every rendered control smaller than 44 × 44 px (B1-PE-04); a checkbox or file input counts by the label holding it. */
function smallTargets(root: ShadowRoot): string[] {
  for (const d of root.querySelectorAll('details')) d.open = true;
  const controls = new Set<Element>();
  for (const el of root.querySelectorAll('button, a[href], input, select, textarea, summary')) {
    const wrapped = el.matches('input[type="checkbox"], input[type="radio"], input[type="file"]') ? el.closest('label') : null;
    controls.add(wrapped ?? el);
  }
  return [...controls].flatMap((el) => {
    const r = el.getBoundingClientRect();
    const name = `${el.tagName.toLowerCase()}${el.className ? `.${String(el.className).replace(/ /g, '.')}` : ''} "${(el.textContent ?? '').trim().slice(0, 30)}"`;
    return r.height >= 44 && r.width >= 44 ? [] : [`${name} ${Math.round(r.width)}×${Math.round(r.height)}`];
  });
}

describe('site units (blueprint §6.1, AR-16)', () => {
  it('parses feet-inches and millimetres to integer millimetres', () => {
    expect(parseLength(`11' 10"`, 'FT_IN')).to.equal(3607);
    expect(parseLength('11ft 10in', 'FT_IN')).to.equal(3607);
    expect(parseLength('11 10', 'FT_IN')).to.equal(3607);
    expect(parseLength('11', 'FT_IN')).to.equal(3353);
    expect(parseLength('142"', 'FT_IN')).to.equal(3607);
    expect(parseLength('3600', 'MM')).to.equal(3600);
    expect(parseLength('3600mm', 'FT_IN')).to.equal(3600);
    expect(parseLength('3.6m', 'FT_IN')).to.equal(3600);
    for (const bad of ['', 'abc', '11 x 10', '-5']) expect(parseLength(bad, 'MM'), bad).to.equal(null);
  });
  it('formats for the surveyor', () => {
    expect(formatLength(3607, 'FT_IN')).to.equal(`11' 10"`);
    expect(formatLength(3600, 'MM')).to.equal('3600 mm');
    expect(formatLength(null, 'MM')).to.equal('');
    expect(formatArea(10463)).to.equal('104.63 sq ft');
  });
});

describe('capture payloads', () => {
  it('converts every length and refuses what cannot be read', () => {
    const d = emptyRoom('s1');
    d.length = `11' 10"`; d.width = '9ft'; d.ceiling = '9 6'; d.complete = true;
    d.walls = d.walls.map((w, i) => ({ ...w, length: i % 2 ? '11 10' : '9', tags: i === 1 ? ['WARDROBE'] : [] }));
    d.walls[1].obstructions = [{ kind: 'SWITCHBOARD', offset: '1', width: '6"', heightFromFloor: '4' }];
    d.attrs = { ac_point_count: '1', has_drain: 'true' };
    const ok = toPayload(d, 'FT_IN', 'BEDROOM');
    expect(ok.errors).to.deep.equal([]);
    const p = ok.payload!;
    expect(p.length_mm).to.equal(3607);
    expect(p.ceiling_height_mm).to.equal(2896);
    expect((p.attributes as Record<string, unknown>).has_drain).to.equal(true);
    expect(((p.walls as Array<Record<string, unknown>>)[1].obstructions as Array<Record<string, unknown>>)[0].offset_mm).to.equal(305);
    d.width = 'nine feet';
    const bad = toPayload(d, 'FT_IN', 'BEDROOM');
    expect(bad.payload).to.equal(null);
    expect(bad.errors[0]).to.contain('width');
  });
  it('round-trips a server measurement and keeps base_version for conflicts', () => {
    const sm = {
      id: 'm1', version: 3, space_id: 's1', client_ref: 'sm-1', shape_code: 'L_SHAPE', length_mm: 5000, width_mm: 5000, ceiling_height_mm: 2900,
      beam_bottom_height_mm: null, floor_to_lintel_mm: null, stated_floor_area_sqft_centi: null, polygon: null, flooring_code: 'WOOD',
      existing_condition_code: null, confidence_code: 'HIGH', is_complete: false,
      attributes: { l_shape: { turn_code: 'LEFT', leg_a: { l_mm: 5000, w_mm: 3000 }, leg_b: { l_mm: 2000, w_mm: 2500 } } },
      derived_floor_area_sqft_centi: null, derived_perimeter_mm: null, derived_wall_area_net_sqft_centi: null, captured_by: 'u', claim_expires_on: null,
      walls: [{ wall_index: 1, length_mm: 3000, wall_type_code: 'MASONRY', usable_for_code: ['NONE'], obstructions: [], openings: [] }],
      electrical_points: [],
    } as unknown as SpaceMeasurement;
    const d = fromMeasurement(sm, 'MM');
    const p = toPayload(d, 'MM', 'LIVING').payload!;
    expect(p.base_version).to.equal(3);
    expect((p.attributes as Record<string, unknown>).l_shape).to.deep.equal(sm.attributes.l_shape);
  });
});

describe('offline queue (B1-T09/T10)', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; });

  function respond(results: unknown[]) {
    window.fetch = async () => new Response(JSON.stringify({ data: { results } }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }

  it('keeps conflicts and refusals, drops what landed, and replaces an unsent write to the same room', async () => {
    const q = new OfflineQueue(new MemoryStore(), () => 'u1');
    const first = await q.enqueue('set1', 'space', { length_mm: 1 }, { spaceId: 'room1', label: 'Kitchen' });
    const second = await q.enqueue('set1', 'space', { length_mm: 2 }, { spaceId: 'room1', label: 'Kitchen' });
    const note = await q.enqueue('set1', 'note', { body: 'x', note_type_code: 'OBSERVATION' });
    let pending = await q.pending('set1');
    expect(pending.map((o) => o.op_id)).to.deep.equal([second.op_id, note.op_id], 'the newer room write replaced the older one');
    expect(pending.some((o) => o.op_id === first.op_id)).to.equal(false);
    respond([{ op_id: second.op_id, status: 'CONFLICT', current_version: 7, conflicting_fields: ['length_mm'] }, { op_id: note.op_id, status: 'APPLIED' }]);
    await q.flush('set1');
    pending = await q.pending('set1');
    expect(pending.length).to.equal(1);
    expect(pending[0].state).to.equal('CONFLICT');
    await q.resolve(pending[0], 'MINE');
    const rebased = (await q.pending('set1'))[0];
    expect(rebased.state).to.equal('PENDING');
    expect(rebased.data.base_version).to.equal(7, 'resent on the server version, never last-write-wins');
  });

  it('keeps everything when the network fails', async () => {
    const q = new OfflineQueue(new MemoryStore(), () => 'u1');
    await q.enqueue('set2', 'note', { body: 'x', note_type_code: 'OBSERVATION' });
    window.fetch = async () => { throw new TypeError('offline'); };
    await q.flush('set2');
    expect((await q.pending('set2')).map((o) => o.state)).to.deep.equal(['PENDING']);
    expect(q.online).to.equal(false);
  });
});

describe('offline queue bound to the signed-in user (B1-PE-01)', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; });

  function recordSync(): Array<Array<{ op_id: string }>> {
    const sent: Array<Array<{ op_id: string }>> = [];
    window.fetch = async (_input: RequestInfo | URL, init?: RequestInit) => {
      const ops = (JSON.parse(String(init?.body)) as { operations: Array<{ op_id: string }> }).operations;
      sent.push(ops);
      return new Response(JSON.stringify({ data: { results: ops.map((o) => ({ op_id: o.op_id, status: 'APPLIED' })) } }),
        { status: 200, headers: { 'Content-Type': 'application/json' } });
    };
    return sent;
  }

  it('lists, counts and sends only the signed-in user\'s operations', async () => {
    const store = new MemoryStore();
    let user: string | null = 'alice';
    const q = new OfflineQueue(store, () => user);
    const hers = await q.enqueue('set1', 'note', { body: 'a' });
    await q.queuePhoto('set1', { client_ref: 'ph-a' }, new Blob([new Uint8Array([1])]));
    user = 'bob';
    expect(await q.pending('set1')).to.deep.equal([], 'Bob never sees Alice\'s operations');
    const his = await q.enqueue('set1', 'note', { body: 'b' });
    expect(his.user_id).to.equal('bob');
    await q.discard(hers.op_id);
    expect((await store.all()).some((o) => o.op_id === hers.op_id)).to.equal(true, 'Bob cannot discard Alice\'s operation');
    const sent = recordSync();
    await q.flush('set1');
    expect(sent.flat().map((o) => o.op_id)).to.deep.equal([his.op_id], 'only Bob\'s operation goes out under Bob\'s session');
    user = 'alice';
    expect((await q.pending('set1')).map((o) => o.user_id)).to.deep.equal(['alice', 'alice'], 'Alice\'s queue is intact');
    user = null;
    expect(await q.mine()).to.deep.equal([]);
    let refused = false;
    try { await q.enqueue('set1', 'note', { body: 'x' }); } catch { refused = true; }
    expect(refused).to.equal(true, 'nothing is queued without a signed-in user');
  });

  it('never sends operations queued before ownership was recorded, and discards them only on request', async () => {
    const store = new MemoryStore();
    await store.put({ op_id: 'op-legacy', set_id: 'set1', seq: 1, type: 'note', space_id: null, data: { body: 'old' }, state: 'PENDING', label: 'note' });
    await store.putBlob('op-legacy', new Blob([new Uint8Array([7])]));
    const q = new OfflineQueue(store, () => 'carol');
    const sent = recordSync();
    await q.flush('set1');
    expect(sent).to.deep.equal([], 'an unowned operation is not sent under whoever is signed in');
    expect(await q.pending('set1')).to.deep.equal([]);
    expect((await q.unowned()).map((o) => o.op_id)).to.deep.equal(['op-legacy'], 'kept and counted, never silently lost');
    await q.discardUnowned();
    expect(await q.unowned()).to.deep.equal([]);
    expect(await store.getBlob('op-legacy')).to.equal(undefined);
  });

  it('uploads photo bytes only for their owner', async () => {
    const store = new MemoryStore();
    let user = 'dave';
    const q = new OfflineQueue(store, () => user);
    const op = await q.queuePhoto('set4', { client_ref: 'ph-d' }, new Blob([new Uint8Array([3])]));
    expect(await store.getBlob(op.op_id)).to.have.property('user_id', 'dave');
    await store.put({ ...op, state: 'UPLOADING', result: { op_id: op.op_id, status: 'APPLIED', entity_id: 'att9' } });
    user = 'erin';
    const calls: string[] = [];
    window.fetch = async (input: RequestInfo | URL) => { calls.push(String(input)); return new Response('{}', { status: 200 }); };
    await q.resumeUploads('set4');
    expect(calls).to.deep.equal([], 'Erin\'s session never uploads Dave\'s photo');
  });
});

describe('sign-out with site captures on the device (B1-PE-02)', () => {
  const originalFetch = window.fetch;
  const as = (id: string | null) => {
    session.state = id ? { status: 'authenticated', me: { id } as Me } : { status: 'anonymous', me: null };
  };
  const dropDb = () => new Promise<void>((resolve) => {
    const req = indexedDB.deleteDatabase(SITE_DB);
    req.onsuccess = req.onerror = req.onblocked = () => resolve();
  });
  const listed = async () => (await indexedDB.databases()).some((d) => d.name === SITE_DB);
  const dialog = () => document.querySelector('vs-site-sign-out-dialog');
  const button = (name: RegExp) => [...dialog()!.shadowRoot!.querySelectorAll('button')].find((b) => name.test(b.textContent ?? ''))!;
  async function seed() {
    as('bob');
    await queue.enqueue('setB', 'note', { body: 'his' });
    as('alice');
    await queue.enqueue('setA', 'note', { body: 'hers' });
    await queue.queuePhoto('setA', { client_ref: 'ph-a' }, new Blob([new Uint8Array([1])]));
  }
  async function everyone(): Promise<string[]> {
    const out: string[] = [];
    for (const u of ['alice', 'bob']) { as(u); out.push(...(await queue.mine()).map(() => u)); }
    return out;
  }

  beforeEach(async () => { await dropDb(); });
  afterEach(async () => { window.fetch = originalFetch; as(null); dialog()?.remove(); await dropDb(); });

  it('does nothing, asks nothing and creates nothing when the site module was never used', async () => {
    expect(await listed()).to.equal(false);
    expect(await siteSignOutGuard('alice')).to.equal(true);
    expect(dialog()).to.equal(null);
    expect(await listed()).to.equal(false, 'the check never creates the database');
    const databases = indexedDB.databases;
    Object.defineProperty(indexedDB, 'databases', { value: undefined, configurable: true });
    try {
      expect(await siteDatabaseExists()).to.equal(false, 'fallback probe for browsers without databases()');
    } finally {
      delete (indexedDB as unknown as Record<string, unknown>).databases;
    }
    expect(indexedDB.databases).to.equal(databases);
    expect(await listed()).to.equal(false, 'the fallback probe aborts its upgrade, creating nothing');
  });

  it('signs out without asking when nothing is unsent, deleting only that user\'s site data', async () => {
    as('bob');
    await queue.enqueue('setB', 'note', { body: 'his' });
    as('alice');
    await queue.mine(); // the database exists, Alice has nothing queued
    expect(await siteSignOutGuard('alice')).to.equal(true);
    expect(dialog()).to.equal(null);
    expect(await everyone()).to.deep.equal(['bob'], 'Bob\'s pending operation survives Alice\'s sign-out');
  });

  it('asks accessibly, and "Stay signed in" keeps everything', async () => {
    await seed();
    const answer = siteSignOutGuard('alice');
    await waitUntil(() => dialog()?.shadowRoot?.querySelector('vs-dialog')?.open, 'confirmation shown');
    expect(dialog()!.shadowRoot!.textContent).to.contain('2 changes');
    await expect(dialog()).to.be.accessible();
    button(/Stay signed in/).click();
    expect(await answer).to.equal(false);
    expect(await everyone()).to.deep.equal(['alice', 'alice', 'bob']);
  });

  it('"Discard and sign out" deletes that user\'s operations and photos only', async () => {
    await seed();
    const answer = siteSignOutGuard('alice');
    await waitUntil(() => dialog()?.shadowRoot?.querySelector('vs-dialog')?.open, 'confirmation shown');
    button(/Discard and sign out/).click();
    expect(await answer).to.equal(true);
    expect(await everyone()).to.deep.equal(['bob']);
  });

  it('"Sync now" sends, then signs out once nothing is left, or says what remains', async () => {
    await seed();
    let online = false;
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      if (!online) throw new TypeError('offline');
      const u = String(input);
      if (u.includes('/sync')) {
        const ops = (JSON.parse(String(init?.body)) as { operations: Array<{ op_id: string; type: string }> }).operations;
        return new Response(JSON.stringify({ data: { results: ops.map((o) => ({ op_id: o.op_id, status: 'APPLIED',
          ...(o.type === 'attachment' ? { entity_id: 'att1', upload: { required: false } } : {}) })) } }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }
      return new Response(JSON.stringify({ data: {} }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    };
    const answer = siteSignOutGuard('alice');
    await waitUntil(() => dialog()?.shadowRoot?.querySelector('vs-dialog')?.open, 'confirmation shown');
    button(/Sync now/).click();
    await waitUntil(() => dialog()!.shadowRoot!.textContent!.includes('could still not be sent'), 'offline: still two left');
    online = true;
    button(/Sync now/).click();
    expect(await answer).to.equal(true);
    expect(await everyone()).to.deep.equal(['bob'], 'only Alice\'s operations were sent');
  });

  it('keeps the session when a guard says stay, and signs out when a guard fails', async () => {
    const calls: string[] = [];
    const client = new ApiClient('', (async (input: RequestInfo | URL) => {
      calls.push(String(input));
      return new Response(JSON.stringify({ data: {} }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }) as typeof fetch);
    const s = new SessionController(client);
    s.state = { status: 'authenticated', me: { id: 'u1' } as Me };
    s.addLogoutGuard(async () => false);
    expect(await s.logout()).to.equal(false);
    expect(calls).to.deep.equal([], 'no logout request');
    expect(s.isAuthenticated).to.equal(true);
    const t = new SessionController(client);
    t.state = { status: 'authenticated', me: { id: 'u1' } as Me };
    t.addLogoutGuard(async () => { throw new Error('IndexedDB unavailable'); });
    expect(await t.logout()).to.equal(true);
    expect(t.isAuthenticated).to.equal(false);
  });
});

describe('photo upload to the private bucket (B1-T11)', () => {
  it('sends the pre-signed fields first and the file last, without credentials or CORS', async () => {
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const fake = (async (url: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(url), init: init! });
      return new Response(null, { status: 200 });
    }) as typeof fetch;
    const url = 'https://veda-stg-attachments-111122223333.s3.ap-south-1.amazonaws.com/';
    await sendBytes('a1', new Blob([new Uint8Array([1, 2, 3])], { type: 'image/jpeg' }),
      { required: true, method: 'POST', url, fields: { key: 'upload/abc', policy: 'p', 'Content-Type': 'image/jpeg' } }, undefined, fake);
    expect(calls.length).to.equal(1);
    expect(calls[0].url).to.equal(url);
    expect(calls[0].init.mode).to.equal('no-cors');
    expect(calls[0].init.credentials).to.equal('omit');
    const keys = [...(calls[0].init.body as FormData).keys()];
    expect(keys).to.deep.equal(['key', 'policy', 'Content-Type', 'file']);
  });

  it('keeps a photo queued until the server confirms it arrived, and retries with fresh instructions', async () => {
    const originalFetch = window.fetch;
    const store = new MemoryStore();
    const q = new OfflineQueue(store, () => 'u1');
    const op = await q.queuePhoto('set3', { client_ref: 'ph-1' }, new Blob([new Uint8Array([9])], { type: 'image/jpeg' }));
    const seen: string[] = [];
    let arrived = false;
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const u = String(input);
      seen.push(`${init?.method ?? 'GET'} ${u.replace(/^https?:\/\/[^/]+/, '')}`);
      if (u.includes('/sync')) {
        return new Response(JSON.stringify({ data: { results: [{ op_id: op.op_id, status: 'APPLIED', entity_id: 'att1', upload: { required: true, method: 'PUT', url: '/api/v1/attachments/att1/content' } }] } }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }
      if (u.endsWith('/complete')) {
        return arrived ? new Response(JSON.stringify({ data: { upload_status: 'RECEIVED' } }), { status: 200, headers: { 'Content-Type': 'application/json' } })
          : new Response(JSON.stringify({ status: 409, code: 'UPLOAD_NOT_RECEIVED', title: 'Conflict' }), { status: 409, headers: { 'Content-Type': 'application/problem+json' } });
      }
      if (u.endsWith('/attachments/att1') && (init?.method ?? 'GET') === 'GET') {
        return new Response(JSON.stringify({ data: { upload: { required: true, method: 'PUT', url: '/api/v1/attachments/att1/content' } } }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }
      return new Response(JSON.stringify({ data: {} }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    };
    try {
      await q.flush('set3');
      expect((await q.pending('set3')).map((o) => o.state)).to.deep.equal(['UPLOADING'], 'not confirmed: kept');
      arrived = true;
      seen.length = 0;
      await q.resumeUploads('set3');
      expect(seen[0]).to.equal('GET /api/v1/attachments/att1', 'fresh instructions first');
      expect(seen).to.include('POST /api/v1/attachments/att1/complete');
      expect(await q.pending('set3')).to.deep.equal([]);
    } finally {
      window.fetch = originalFetch;
    }
  });
});

describe('photo sizing (closure §6.2)', () => {
  it('scales the long edge to 2048 px and never upscales', () => {
    expect(fitWithin(4000, 3000)).to.deep.equal({ width: 2048, height: 1536 });
    expect(fitWithin(3000, 4000)).to.deep.equal({ width: 1536, height: 2048 });
    expect(fitWithin(1200, 900)).to.deep.equal({ width: 1200, height: 900 });
  });
});

describe('site pages', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; });

  it('says the feature is off when the API answers 404', async () => {
    window.fetch = async () => new Response(JSON.stringify({ status: 404, code: 'NOT_FOUND', title: 'Not found' }), {
      status: 404, headers: { 'Content-Type': 'application/problem+json' },
    });
    const el = await fixture(html`<vs-site-home-page></vs-site-home-page>`);
    await waitUntil(() => el.shadowRoot!.textContent!.includes('not enabled'), 'disabled message');
  });

  it('renders the capture page for a Full survey with required markers, accessibly, at phone width', async () => {
    const set = { id: 'set1', version: 1, property_id: 'p1', revision_no: 1, status: 'DRAFT', survey_level_code: 'FULL', method_code: 'LASER',
      unit_system_code: 'MM', captured_by: 'u1', summary: {}, property_capture: {}, spaces: [], notes: [] };
    const property = { id: 'p1', version: 1, property_number: 'VS-P-1', display_label: '1 BHK apartment', spaces: [
      { id: 'k1', version: 1, label: 'Kitchen', space_type_code: 'KITCHEN', is_in_scope: true, zone_code: 'INDOOR', level_index: 0, sort_order: 10 },
    ] };
    const templates = { template_version: '2026.10.1', property_templates: {}, space_templates: {
      KITCHEN_DEFAULT: { space_types: ['KITCHEN'], full_required: ['FL', 'ATTR:has_gas_line'], checklist: [] } } };
    const checks = { survey_level: 'FULL', ready_to_submit: false, ready_to_verify: false, verify_problems: [], usable_segments: {},
      submit_problems: [{ pointer: '/spaces/k1', code: 'NOT_MEASURED', message: 'This in-scope space has no measurement.' }] };
    window.fetch = async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes('/checks') ? checks : url.includes('/mtq/templates') ? templates : url.includes('/properties/') ? property : set;
      return new Response(JSON.stringify({ data: body }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    };
    const el = await fixture(html`<div style="width: 360px"><vs-capture-page .location=${{ params: { id: 'set1' } }}></vs-capture-page></div>`);
    const page = el.querySelector('vs-capture-page')!;
    await waitUntil(() => page.shadowRoot!.querySelector('#room-title'), 'room editor');
    const root = page.shadowRoot!;
    expect(root.querySelector('#room-title')!.textContent).to.equal('Kitchen');
    const required = [...root.querySelectorAll('.label.req')].map((x) => x.textContent);
    expect(required).to.include('Floor to lintel');
    expect(required).to.include('Has gas line');
    expect(root.textContent).to.contain('1 items before submission');
    expect(root.textContent).to.not.contain('₹');
    await expect(page).to.be.accessible();
  });
});

describe('site pages accessibility at phone width (B1-PE-03)', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; });

  const PERMS = ['measurement.visit.read', 'measurement.visit.create', 'measurement.read', 'measurement.verify', 'measurement.capture',
    'property.read', 'property.create', 'property.update'];
  const spaces = [
    { id: 'l1', version: 1, property_id: 'p1', parent_space_id: null, label: 'Living', space_type_code: 'LIVING', is_in_scope: true, zone_code: 'INDOOR', level_index: 0, sort_order: 10 },
    { id: 'b1', version: 1, property_id: 'p1', parent_space_id: null, label: 'Bedroom 1', space_type_code: 'BEDROOM', is_in_scope: true, zone_code: 'INDOOR', level_index: 0, sort_order: 20 },
    { id: 't1', version: 1, property_id: 'p1', parent_space_id: 'b1', label: 'Toilet 1', space_type_code: 'TOILET', is_in_scope: false, zone_code: 'INDOOR', level_index: 0, sort_order: 30 },
  ];
  const property = { id: 'p1', version: 1, property_number: 'VS-P-1', display_label: '1 BHK apartment', configuration_label: '1 BHK', city: 'Pune',
    derived_bedroom_count: 1, derived_toilet_count: 1, derived_level_count: 1, derived_measured_floor_area_sqft_centi: 45000,
    latest_verified_set: { id: 's1', revision_no: 1 }, spaces };
  const visit = { id: 'v1', version: 1, visit_number: 'VS-V-1', property_id: 'p1', status: 'SCHEDULED', survey_level_code: 'FULL',
    scheduled_start_on: '2026-10-14T05:30:00Z', assigned_to: { id: 'u1', display_name: 'Surveyor One' }, allowed_transitions: ['IN_PROGRESS', 'CANCELLED'] };
  const wall = { wall_index: 1, length_mm: 3600, wall_type_code: 'MASONRY', usable_for_code: ['WARDROBE'], obstructions: [], openings: [] };
  const measured = { id: 'm1', version: 1, space_id: 'b1', shape_code: 'RECTANGULAR', length_mm: 3600, width_mm: 3000, ceiling_height_mm: 2900,
    derived_floor_area_sqft_centi: 11625, derived_wall_area_net_sqft_centi: 30000, derived_perimeter_mm: 13200, walls: [wall], electrical_points: [] };
  const set = (id: string, revision: number, status: string) => ({ id, version: 1, property_id: 'p1', revision_no: revision, status, survey_level_code: 'FULL',
    method_code: 'LASER', unit_system_code: 'FT_IN', captured_by: 'u2', rejection_reason: null, snapshot_sha256: null,
    summary: { total_floor_area_sqft_centi: 11625 }, spaces: [measured], notes: [] });
  const templates = { template_version: '2026.10.1', space_templates: {}, property_templates: {
    APARTMENT_3BHK: { property_type_code: 'APARTMENT', configuration_label: '3 BHK', spaces: [{ ref: 'living', label: 'Living' }, { ref: 'study', label: 'Study', optional: true }] } } };
  const checks = { survey_level: 'FULL', ready_to_submit: true, ready_to_verify: true, usable_segments: {}, submit_problems: [],
    verify_problems: [{ pointer: '/spaces/b1', code: 'CEILING_UNUSUAL', message: 'The ceiling is unusually high.', acknowledgeable: true }] };

  function serve() {
    window.fetch = async (input: RequestInfo | URL) => {
      const path = new URL(String(input), location.href).pathname;
      const body = path.endsWith('/mtq/templates') ? templates
        : path.endsWith('/measurement-visits') ? [visit]
        : path.endsWith('/measurement-sets') ? [set('s1', 1, 'VERIFIED'), set('s2', 2, 'DRAFT')]
        : path.endsWith('/checks') ? checks
        : path.includes('/diff/') ? { spaces: [{ space_id: 'b1', change: 'CHANGED', fields: { length_mm: { from: 3500, to: 3600 } }, walls: { 1: { from: 3500, to: 3600 } } }] }
        : path.includes('/attachments') ? []
        : path === '/api/v1/measurement-sets/s2' ? set('s2', 2, 'DRAFT')
        : path.startsWith('/api/v1/measurement-sets/') ? set('s3', 3, 'SUBMITTED')
        : path === '/api/v1/properties' ? [property]
        : property;
      return new Response(JSON.stringify({ data: body }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    };
  }

  /** Mounts a page at 360 px under a session that holds every site permission (the pages read it through context). */
  async function mount(tag: string, location: { params: Record<string, string>; search?: string }, ready: string): Promise<HTMLElement> {
    serve();
    const host = await fixture<HTMLDivElement>(html`<div style="width: 360px"></div>`);
    new ContextProvider(host, { context: sessionContext, initialValue: { status: 'authenticated',
      me: { id: 'u1', permissions: Object.fromEntries(PERMS.map((p) => [p, 'ALL'])) } as unknown as Me } });
    const page = document.createElement(tag) as HTMLElement & { location: unknown };
    page.location = location;
    host.append(page);
    await waitUntil(() => page.shadowRoot?.querySelector(ready), `${tag} rendered`);
    return page;
  }

  it('site home: visits, properties and the new-property form', async () => {
    const page = await mount('vs-site-home-page', { params: {} }, '#new');
    await waitUntil(() => page.shadowRoot!.textContent!.includes('VS-V-1') && page.shadowRoot!.textContent!.includes('VS-P-1'), 'lists loaded');
    await expect(page).to.be.accessible();
    expect(smallTargets(page.shadowRoot!), 'touch targets (B1-PE-04)').to.deep.equal([]);
  });

  it('property: spaces, visits and revisions', async () => {
    const page = await mount('vs-property-page', { params: { id: 'p1' } }, '#spaces');
    await waitUntil(() => page.shadowRoot!.textContent!.includes('Rev 2'), 'revisions loaded');
    await expect(page).to.be.accessible();
    expect(smallTargets(page.shadowRoot!), 'touch targets (B1-PE-04)').to.deep.equal([]);
  });

  it('review: checks with an acknowledgement, the comparison and the measured spaces', async () => {
    const page = await mount('vs-review-page', { params: { id: 's3' }, search: '?compare=s2' }, '#checks');
    await waitUntil(() => page.shadowRoot!.querySelector('#diff'), 'comparison loaded');
    await expect(page).to.be.accessible();
    expect(smallTargets(page.shadowRoot!), 'touch targets (B1-PE-04)').to.deep.equal([]);
  });

  it('capture: the photo buttons show the focus ring when their hidden file input has focus', async () => {
    const page = await mount('vs-capture-page', { params: { id: 's2' } }, '#room-title');
    const input = page.shadowRoot!.querySelector<HTMLInputElement>('label.btn input[type="file"]')!;
    const label = input.closest('label')!;
    expect(getComputedStyle(label).outlineStyle).to.equal('none');
    input.focus();
    expect(getComputedStyle(label).outlineStyle).to.equal('solid');
    expect(getComputedStyle(label).outlineWidth).to.equal('2px');
  });
});

describe('site touch targets at phone width (B1-PE-04)', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; });

  async function capturePage(): Promise<HTMLElement> {
    const set = { id: 'set1', version: 1, property_id: 'p1', revision_no: 1, status: 'DRAFT', survey_level_code: 'FULL', method_code: 'LASER',
      unit_system_code: 'MM', captured_by: 'u1', summary: {}, property_capture: {}, notes: [], spaces: [{ id: 'm1', version: 1, space_id: 'k1',
        shape_code: 'L_SHAPE', length_mm: 3000, width_mm: 2400, ceiling_height_mm: 2900, confidence_code: 'HIGH', is_complete: false, attributes: {},
        walls: [{ id: 'w1', wall_index: 1, length_mm: 3000, wall_type_code: 'PARTITION', usable_for_code: ['KITCHEN_RUN'],
          obstructions: [{ kind: 'SWITCHBOARD', offset_mm: 300, width_mm: 150 }],
          openings: [{ client_ref: 'o1', opening_type_code: 'WINDOW', width_mm: 1200, height_mm: 1200, sill_height_mm: 900 }] }],
        electrical_points: [{ client_ref: 'e1', point_type_code: 'SOCKET_15A', status_code: 'SHIFT', wall_index: 1, from_offset_mm: 400 }] }] };
    const property = { id: 'p1', version: 1, property_number: 'VS-P-1', display_label: '1 BHK apartment', spaces: [
      { id: 'k1', version: 1, label: 'Kitchen', space_type_code: 'KITCHEN', is_in_scope: true, zone_code: 'INDOOR', level_index: 0, sort_order: 10 },
      { id: 'b1', version: 1, label: 'Bedroom', space_type_code: 'BEDROOM', is_in_scope: true, zone_code: 'INDOOR', level_index: 0, sort_order: 20 },
    ] };
    const templates = { template_version: '2026.10.1', property_templates: {}, space_templates: {
      KITCHEN_DEFAULT: { space_types: ['KITCHEN'], full_required: ['FL', 'ATTR:has_gas_line'], checklist: [] } } };
    const checks = { survey_level: 'FULL', ready_to_submit: false, ready_to_verify: false, verify_problems: [], usable_segments: {}, submit_problems: [] };
    window.fetch = async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes('/checks') ? checks : url.includes('/mtq/templates') ? templates : url.includes('/properties/') ? property : set;
      return new Response(JSON.stringify({ data: body }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    };
    const el = await fixture(html`<div style="width: 360px"><vs-capture-page .location=${{ params: { id: 'set1' } }}></vs-capture-page></div>`);
    const page = el.querySelector<HTMLElement>('vs-capture-page')!;
    await waitUntil(() => page.shadowRoot!.querySelector('#room-title'), 'room editor');
    return page;
  }

  it('makes every control on the capture page at least 44 × 44 px', async () => {
    const page = await capturePage();
    const root = page.shadowRoot!;
    await (page as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    expect(root.querySelectorAll('.tags label').length, 'wall tags rendered').to.be.greaterThan(10);
    expect(root.querySelectorAll('label.btn input[type="file"]').length, 'room and wall photo buttons rendered').to.equal(2);
    expect(root.querySelectorAll('.btn.small').length, 'small buttons rendered').to.be.greaterThan(5);
    expect(smallTargets(root)).to.deep.equal([]);
  });
});
