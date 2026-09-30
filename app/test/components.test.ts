import { expect, fixture, html } from '@open-wc/testing';
import type { Lead } from '../src/core/api/types.js';
import '../src/design-system/components.js';
import '../src/core/authz/can.js';
import type { VsCan } from '../src/core/authz/can.js';
import '../src/modules/leads/status-dialog.js';
import type { VsStatusDialog } from '../src/modules/leads/status-dialog.js';
import { makeMe } from './router.test.js';

describe('<vs-can>', () => {
  it('renders its slot only when the effective permission map has the code', async () => {
    const me = makeMe({ 'lead.assign': 'ALL' });
    const yes = await fixture<VsCan>(html`<vs-can permission="lead.assign" .meOverride=${me}><button>Assign</button></vs-can>`);
    expect(yes.allowed).to.equal(true);
    expect(yes.shadowRoot!.querySelector('slot:not([name])')).to.exist;
    const no = await fixture<VsCan>(html`<vs-can permission="lead.delete" .meOverride=${me}><button>Delete</button><span slot="fallback">x</span></vs-can>`);
    expect(no.allowed).to.equal(false);
    expect(no.shadowRoot!.querySelector('slot:not([name])')).to.not.exist;
    expect(no.shadowRoot!.querySelector('slot[name="fallback"]')).to.exist;
  });
  it('supports any/all and OWN-scope evaluation for a row', async () => {
    const me = makeMe({ 'lead.update': 'OWN', 'audit.read': 'ALL' });
    const any = await fixture<VsCan>(html`<vs-can any="user.read audit.read" .meOverride=${me}>x</vs-can>`);
    expect(any.allowed).to.equal(true);
    const all = await fixture<VsCan>(html`<vs-can all="user.read audit.read" .meOverride=${me}>x</vs-can>`);
    expect(all.allowed).to.equal(false);
    const own = await fixture<VsCan>(html`<vs-can permission="lead.update" .scopeFor=${{ assigned_to: { id: me.id } }} .meOverride=${me}>x</vs-can>`);
    expect(own.allowed).to.equal(true);
    const other = await fixture<VsCan>(html`<vs-can permission="lead.update" .scopeFor=${{ assigned_to: { id: 'zz' }, created_by: { id: 'yy' } }} .meOverride=${me}>x</vs-can>`);
    expect(other.allowed).to.equal(false);
  });
});

describe('<vs-status-dialog>', () => {
  const lead = { id: '0192a4f1c3b27e8d9f10a2b3c4d5e6f7', lead_number: 'VS-L-2026-000123', status: 'SITE_VISIT', version: 4, allowed_transitions: ['QUOTATION_SENT', 'CONTACTED', 'LOST'] } as unknown as Lead;

  it('asks for a lost reason and refuses to submit without it (no request sent)', async () => {
    const originalFetch = window.fetch;
    let calls = 0;
    window.fetch = async () => { calls += 1; return new Response('{}'); };
    try {
      const el = await fixture<VsStatusDialog>(html`<vs-status-dialog .lead=${lead} to="LOST" .open=${true} .plannedCount=${3}></vs-status-dialog>`);
      const root = el.shadowRoot!;
      expect(root.querySelector('select[name="lost_reason_code"]')).to.exist;
      expect(root.textContent).to.contain('3 planned follow-ups will be cancelled');
      (root.querySelector('form') as HTMLFormElement).requestSubmit();
      await el.updateComplete;
      expect(el.errors).to.have.property('lost_reason_code');
      expect(calls).to.equal(0);
    } finally {
      window.fetch = originalFetch;
    }
  });

  it('requires a comment when moving back one step', async () => {
    const el = await fixture<VsStatusDialog>(html`<vs-status-dialog .lead=${lead} to="CONTACTED" .open=${true}></vs-status-dialog>`);
    const root = el.shadowRoot!;
    expect(root.querySelector('select[name="lost_reason_code"]')).to.not.exist;
    const comment = root.querySelector('textarea[name="comment"]') as HTMLTextAreaElement;
    expect(comment.getAttribute('aria-required')).to.equal('true');
    (root.querySelector('form') as HTMLFormElement).requestSubmit();
    await el.updateComplete;
    expect(el.errors).to.have.property('comment');
  });

  it('posts the transition with If-Match when inputs are valid', async () => {
    const originalFetch = window.fetch;
    let sent: { url: string; init?: RequestInit } | null = null;
    window.fetch = async (url: RequestInfo | URL, init?: RequestInit) => {
      sent = { url: String(url), init };
      return new Response(JSON.stringify({ data: { ...lead, status: 'QUOTATION_SENT', version: 5 } }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    };
    try {
      const el = await fixture<VsStatusDialog>(html`<vs-status-dialog .lead=${lead} to="QUOTATION_SENT" .open=${true}></vs-status-dialog>`);
      let updated: Lead | null = null;
      el.addEventListener('lead-updated', (e) => (updated = (e as CustomEvent<Lead>).detail));
      (el.shadowRoot!.querySelector('form') as HTMLFormElement).requestSubmit();
      await new Promise((r) => setTimeout(r, 20));
      expect(sent!.url).to.contain(`/api/v1/leads/${lead.id}/status`);
      expect((sent!.init!.headers as Record<string, string>)['If-Match']).to.equal('"4"');
      expect(JSON.parse(String(sent!.init!.body))).to.deep.equal({ to_status: 'QUOTATION_SENT' });
      expect(updated!.version).to.equal(5);
    } finally {
      window.fetch = originalFetch;
    }
  });
});
