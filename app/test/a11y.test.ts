import { expect, fixture, html, oneEvent, waitUntil } from '@open-wc/testing';
import { ApiProblem } from '../src/core/api/problem.js';
import '../src/design-system/components.js';
import type { VsTabs } from '../src/design-system/components.js';
import '../src/shell/account-menu.js';
import type { VsAccountMenu } from '../src/shell/account-menu.js';
import '../src/shell/command-palette.js';
import type { VsCommandPalette } from '../src/shell/command-palette.js';
import '../src/shell/step-up-dialog.js';
import { VsStepUpDialog } from '../src/shell/step-up-dialog.js';

/**
 * RR-18: accessibility remnants (UI-011; UI-016 AX-01, AX-03, AX-07, AX-09). Each block checks the ARIA contract
 * of one component, its keyboard and pointer behaviour, and an axe-core scan of the rendered state.
 */

const key = (el: Element, k: string) =>
  el.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, composed: true, cancelable: true }));
const settle = (el: { updateComplete: Promise<unknown> }) => el.updateComplete;

// --- vs-tabs: tablist, tab and tabpanel wiring (AX-01, AX-09) -------------------------------------------------

describe('<vs-tabs> (RR-18)', () => {
  const tabs = [{ id: 'a', label: 'Timeline' }, { id: 'b', label: 'Notes' }, { id: 'h', label: 'Hidden', hidden: true }, { id: 'c', label: 'History' }];

  async function render(selected = 'a') {
    const el = await fixture<VsTabs>(html`<vs-tabs label="Lead records" .tabs=${tabs} .selected=${selected}
      @tab-change=${(e: CustomEvent<string>) => ((e.currentTarget as VsTabs).selected = e.detail)}><p>Panel ${selected}</p></vs-tabs>`);
    return { el, root: el.shadowRoot! };
  }

  it('names the tab list and wires every tab to the panel in the same root', async () => {
    const { el, root } = await render('b');
    const list = root.querySelector('[role="tablist"]')!;
    expect(list.getAttribute('aria-label')).to.equal('Lead records');
    const tabEls = [...root.querySelectorAll('[role="tab"]')];
    expect(tabEls.map((t) => t.textContent)).to.deep.equal(['Timeline', 'Notes', 'History'], 'hidden tabs are not rendered');
    const panel = root.querySelector('[role="tabpanel"]')!;
    for (const t of tabEls) expect(root.getElementById(t.getAttribute('aria-controls')!)).to.equal(panel);
    expect(root.getElementById(panel.getAttribute('aria-labelledby')!)!.textContent).to.equal('Notes');
    expect(panel.getAttribute('tabindex')).to.equal('0');
    // The page content is projected into the panel, so it is the panel's content for assistive technology.
    const slot = panel.querySelector('slot')!;
    expect(slot.assignedElements()[0].textContent).to.equal('Panel b');
    await expect(el).to.be.accessible();
  });

  it('roves focus with arrow keys, Home and End, skipping hidden tabs', async () => {
    const { el, root } = await render('a');
    const list = root.querySelector('[role="tablist"]')!;
    const selected = () => root.querySelector('[aria-selected="true"]')!.textContent;
    key(list, 'ArrowRight'); await settle(el);
    expect(selected()).to.equal('Notes');
    key(list, 'ArrowRight'); await settle(el);
    expect(selected()).to.equal('History', 'the hidden tab is skipped');
    key(list, 'ArrowRight'); await settle(el);
    expect(selected()).to.equal('Timeline', 'wraps');
    key(list, 'End'); await settle(el);
    expect(selected()).to.equal('History');
    key(list, 'Home'); await settle(el);
    expect(selected()).to.equal('Timeline');
    expect(root.activeElement?.textContent).to.equal('Timeline', 'focus follows the selection');
    expect([...root.querySelectorAll('[role="tab"]')].filter((t) => t.getAttribute('tabindex') === '0')).to.have.length(1);
  });
});

// --- command palette: combobox with listbox popup (AX-01) -----------------------------------------------------

describe('<vs-command-palette> (RR-18)', () => {
  const perms = { 'lead.read': 'ALL', 'lead.create': 'ALL', 'user.read': 'ALL', 'audit.read': 'ALL' } as const;

  async function open() {
    const el = await fixture<VsCommandPalette>(html`<vs-command-palette .perms=${perms}></vs-command-palette>`);
    el.show();
    await settle(el);
    await new Promise((r) => requestAnimationFrame(r));
    const root = el.shadowRoot!;
    return { el, root, input: root.querySelector('input')!, list: root.querySelector('[role="listbox"]')! };
  }

  it('exposes the input as a combobox that controls a listbox of plain options', async () => {
    const { el, root, input, list } = await open();
    expect(input.getAttribute('role')).to.equal('combobox');
    expect(input.getAttribute('aria-autocomplete')).to.equal('list');
    expect(root.getElementById(input.getAttribute('aria-controls')!)).to.equal(list);
    expect(input.getAttribute('aria-expanded')).to.equal('true');
    const options = [...list.querySelectorAll('[role="option"]')];
    expect(options.length).to.be.greaterThan(1);
    expect(list.querySelectorAll('button, a, input, [tabindex]'), 'no interactive content inside options').to.have.length(0);
    expect(options.every((o) => o.parentElement === list)).to.equal(true);
    expect(input.getAttribute('aria-activedescendant')).to.equal(options[0].id);
    expect(options[0].getAttribute('aria-selected')).to.equal('true');
    expect(root.querySelector('[role="status"]')!.textContent).to.equal(`${options.length} results`);
    await expect(el).to.be.accessible();
  });

  it('moves the active option with arrow keys while focus stays in the input, and Enter opens it', async () => {
    const { el, root, input, list } = await open();
    input.focus();
    const options = () => [...list.querySelectorAll('[role="option"]')];
    key(input, 'ArrowDown'); await settle(el);
    expect(input.getAttribute('aria-activedescendant')).to.equal(options()[1].id);
    expect(options()[1].getAttribute('aria-selected')).to.equal('true');
    expect(options().filter((o) => o.getAttribute('aria-selected') === 'true')).to.have.length(1);
    key(input, 'ArrowUp'); key(input, 'ArrowUp'); await settle(el);
    expect(input.getAttribute('aria-activedescendant')).to.equal(options()[options().length - 1].id, 'wraps to the last');
    expect(root.activeElement).to.equal(input);
    const go = oneEvent(window, 'vaadin-router-go');
    key(input, 'Enter');
    const ev = (await go) as CustomEvent<{ pathname: string; search: string }>;
    // The last entry is the "New lead" action (permission lead.create).
    expect(ev.detail.pathname + ev.detail.search).to.equal('/leads?new=1');
    expect(el.open).to.equal(false);
  });

  it('announces when nothing matches and clears the active descendant', async () => {
    const realFetch = window.fetch;
    window.fetch = async () => new Response(JSON.stringify({ data: [], meta: {} }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    const { el, root, input } = await open();
    input.value = 'zz';
    input.dispatchEvent(new Event('input'));
    await waitUntil(() => !root.querySelector('[role="option"]'), 'lead search settled');
    window.fetch = realFetch;
    await settle(el);
    expect(input.hasAttribute('aria-activedescendant')).to.equal(false);
    expect(input.getAttribute('aria-expanded')).to.equal('false');
    expect(root.querySelector('[role="status"]')!.textContent).to.equal('0 results');
  });
});

// --- account menu: disclosure that closes on outside press, focus loss and Escape (AX-01) ----------------------

describe('<vs-account-menu> (RR-18)', () => {
  async function render() {
    const wrap = await fixture<HTMLDivElement>(html`<div><button id="before">Before</button>
      <vs-account-menu name="Priya Sharma" initials="PS"></vs-account-menu><button id="after">After</button></div>`);
    const menu = wrap.querySelector('vs-account-menu') as VsAccountMenu;
    const toggle = menu.shadowRoot!.querySelector('.toggle') as HTMLButtonElement;
    toggle.click();
    await settle(menu);
    return { wrap, menu, toggle };
  }

  it('is a labelled disclosure that controls its panel', async () => {
    const { menu, toggle } = await render();
    expect(toggle.getAttribute('aria-label')).to.equal('Account menu');
    expect(toggle.getAttribute('aria-expanded')).to.equal('true');
    expect(menu.shadowRoot!.getElementById(toggle.getAttribute('aria-controls')!)).to.exist;
    await expect(menu).to.be.accessible();
  });

  it('closes on a pointer press outside, but not on one inside', async () => {
    const { wrap, menu, toggle } = await render();
    menu.shadowRoot!.querySelector('.panel')!.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, composed: true }));
    await settle(menu);
    expect(menu.open).to.equal(true, 'a press inside the panel keeps it open');
    wrap.querySelector('#after')!.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, composed: true }));
    await settle(menu);
    expect(menu.open).to.equal(false);
    expect(toggle.getAttribute('aria-expanded')).to.equal('false');
    document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, composed: true }));
    expect(menu.open).to.equal(false, 'no effect once closed');
  });

  it('closes when keyboard focus leaves it, and stays open while focus moves inside', async () => {
    const { wrap, menu, toggle } = await render();
    toggle.focus();
    (menu.shadowRoot!.querySelector('.panel a') as HTMLElement).focus();
    await settle(menu);
    expect(menu.open).to.equal(true);
    (wrap.querySelector('#after') as HTMLElement).focus();
    await settle(menu);
    expect(menu.open).to.equal(false);
  });

  it('closes on Escape from the toggle or the panel and returns focus to the toggle', async () => {
    for (const from of ['toggle', 'panel'] as const) {
      const { menu, toggle } = await render();
      const start = from === 'toggle' ? toggle : (menu.shadowRoot!.querySelector('.panel a') as HTMLElement);
      start.focus();
      key(start, 'Escape');
      await settle(menu);
      await settle(menu);
      expect(menu.open, from).to.equal(false);
      expect(menu.shadowRoot!.activeElement, from).to.equal(toggle);
    }
  });

  it('reports Sign out to the shell and closes', async () => {
    const { menu } = await render();
    const out = oneEvent(menu, 'sign-out');
    (menu.shadowRoot!.querySelector('.panel button') as HTMLButtonElement).click();
    await out;
    expect(menu.open).to.equal(false);
  });
});

// --- step-up dialog: expiry stated, warned and enforced; attempts announced (AX-07) ---------------------------

describe('<vs-step-up-dialog> (RR-18)', () => {
  const realFetch = window.fetch;
  const realWarn = VsStepUpDialog.warnBeforeMs;
  afterEach(() => {
    window.fetch = realFetch;
    VsStepUpDialog.warnBeforeMs = realWarn;
  });

  function problem(extra: Record<string, unknown>) {
    return new ApiProblem(403, { code: 'STEP_UP_REQUIRED', kind: 'mfa', mfa_token: 't', ...extra });
  }
  async function present(extra: Record<string, unknown>) {
    const el = await fixture<VsStepUpDialog>(html`<vs-step-up-dialog></vs-step-up-dialog>`);
    const result = el.present(problem(extra));
    await settle(el);
    const root = el.shadowRoot!;
    return { el, root, result, input: root.querySelector('input')!, confirm: root.querySelector('button.primary') as HTMLButtonElement };
  }
  function answer(status: number, body: Record<string, unknown>) {
    window.fetch = async () =>
      new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { 'Content-Type': 'application/problem+json' } });
  }

  it('states when the request expires and links the help text to the field', async () => {
    const { el, root, input } = await present({ expires_in: 300 });
    expect(root.querySelector('#su-help')!.textContent).to.contain('expires in 5 minutes');
    expect(input.getAttribute('aria-describedby')).to.equal('su-help su-err');
    expect(input.getAttribute('autocomplete')).to.equal('one-time-code');
    expect(input.getAttribute('inputmode')).to.equal('numeric');
    await expect(el).to.be.accessible();
    el.remove();
  });

  it('announces a warning before expiry, politely', async () => {
    VsStepUpDialog.warnBeforeMs = 60_000;
    const { el, root } = await present({ expires_in: 61 }); // the warning is due after one second
    const status = root.querySelector('[role="status"]')!;
    expect(status.getAttribute('aria-live')).to.equal('polite');
    expect(status.textContent).to.equal('');
    await waitUntil(() => status.textContent === 'This confirmation expires in 1 minute.', 'warning announced', { timeout: 3000 });
    el.remove();
  });

  it('switches to an expired state that cannot be submitted, announced assertively', async () => {
    const { el, root, input, confirm, result } = await present({ expires_in: 1 });
    await waitUntil(() => el.expired, 'expired', { timeout: 3000 });
    await settle(el);
    expect(root.querySelector('#su-err')!.getAttribute('aria-live')).to.equal('assertive');
    expect(root.querySelector('#su-err')!.textContent).to.contain('expired');
    expect(confirm.disabled).to.equal(true);
    expect(input.disabled).to.equal(true);
    expect(root.querySelector('[role="status"]')!.textContent).to.equal('', 'no stale warning');
    (root.querySelector('button.btn:not(.primary)') as HTMLButtonElement).click();
    expect(await result).to.equal(false, 'cancelling resolves the pending action as not confirmed');
  });

  it('announces the attempts left after a wrong code and refocuses the cleared field', async () => {
    const { el, root, input } = await present({ expires_in: 300 });
    answer(401, { code: 'MFA_CODE_INVALID', status: 401, attempts_remaining: 3 });
    input.value = '123456';
    root.querySelector('form')!.requestSubmit();
    await waitUntil(() => el.error, 'error shown');
    await settle(el);
    expect(root.querySelector('#su-err')!.textContent).to.equal("That code didn't work. 3 attempts left.");
    expect(input.getAttribute('aria-invalid')).to.equal('true');
    expect(input.value).to.equal('');
    expect(root.activeElement).to.equal(input);
    answer(401, { code: 'MFA_CODE_INVALID', status: 401, attempts_remaining: 1 });
    input.value = '123456';
    root.querySelector('form')!.requestSubmit();
    await waitUntil(() => el.error.includes('1 attempt left'), 'singular');
    el.remove();
  });

  it('treats a challenge the server reports expired as expired', async () => {
    const { el, root, input, confirm } = await present({ expires_in: 300 });
    answer(401, { code: 'MFA_CHALLENGE_INVALID', status: 401 });
    input.value = '123456';
    root.querySelector('form')!.requestSubmit();
    await waitUntil(() => el.expired, 'expired');
    await settle(el);
    expect(confirm.disabled).to.equal(true);
    el.remove();
  });

  it('has no timers for password re-entry, which has no challenge', async () => {
    const el = await fixture<VsStepUpDialog>(html`<vs-step-up-dialog></vs-step-up-dialog>`);
    void el.present(new ApiProblem(403, { code: 'STEP_UP_REQUIRED', kind: 'password' }));
    await settle(el);
    expect(el.expiresInMinutes).to.equal(0);
    expect(el.shadowRoot!.querySelector('#su-help')!.textContent).to.equal('Re-enter your password to continue.');
    el.remove();
  });
});
