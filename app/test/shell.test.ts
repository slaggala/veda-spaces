import { expect, waitUntil } from '@open-wc/testing';

describe('<vs-app> boot', () => {
  it('restores the session via refresh and routes anonymous users to the login page', async () => {
    const calls: string[] = [];
    window.fetch = async (input: RequestInfo | URL) => {
      calls.push(String(input));
      return new Response(JSON.stringify({ code: 'SESSION_INVALID', status: 401 }), { status: 401, headers: { 'Content-Type': 'application/problem+json' } });
    };
    history.replaceState(null, '', '/leads?status=NEW');
    await import('../src/design-system/components.js');
    await import('../src/core/authz/can.js');
    await import('../src/shell/app.js');
    const app = document.createElement('vs-app');
    document.body.append(app);
    await waitUntil(() => app.shadowRoot?.querySelector('vs-login-page'), 'login page rendered', { timeout: 4000 });
    expect(calls[0]).to.contain('/api/v1/auth/refresh');
    expect(window.location.pathname).to.equal('/login');
    expect(new URLSearchParams(window.location.search).get('next')).to.equal('/leads?status=NEW');
    // The shell chrome (navigation) must not render for anonymous users.
    expect(app.shadowRoot!.querySelector('nav.side')).to.not.exist;
    const login = app.shadowRoot!.querySelector('vs-login-page')!;
    await (login as unknown as { updateComplete: Promise<unknown> }).updateComplete;
    const layout = login.shadowRoot!.querySelector('vs-auth-layout');
    expect(layout).to.exist;
    expect(login.shadowRoot!.querySelector('input[autocomplete="username"]')).to.exist;
    expect(login.shadowRoot!.querySelector('input[autocomplete="current-password"]')).to.exist;
  });
});
