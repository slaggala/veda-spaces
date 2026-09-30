import { expect } from '@open-wc/testing';
import { ApiClient } from '../src/core/api/client.js';
import { ApiProblem, parseProblem } from '../src/core/api/problem.js';

function json(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  const type = status >= 400 ? 'application/problem+json' : 'application/json';
  return new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { 'Content-Type': type, ...headers } });
}

describe('ApiClient', () => {
  it('performs a single-flight refresh on concurrent TOKEN_EXPIRED and retries each request once', async () => {
    let refreshCalls = 0;
    const seen: string[] = [];
    const fetchImpl = async (url: string, init?: RequestInit) => {
      const auth = (init?.headers as Record<string, string>)?.Authorization ?? '';
      if (url.endsWith('/api/v1/auth/refresh')) {
        refreshCalls += 1;
        expect((init?.headers as Record<string, string>)['X-Requested-With']).to.equal('veda-workspace');
        await new Promise((r) => setTimeout(r, 20));
        return json(200, { data: { access_token: 'new-token' } });
      }
      seen.push(`${url}|${auth}`);
      if (auth === 'Bearer old-token') return json(401, { code: 'TOKEN_EXPIRED', title: 'Token expired', status: 401 });
      return json(200, { data: { ok: url } });
    };
    const client = new ApiClient('', fetchImpl);
    client.setAccessToken('old-token');
    const [a, b] = await Promise.all([client.get<{ ok: string }>('/api/v1/leads'), client.get<{ ok: string }>('/api/v1/auth/me')]);
    expect(refreshCalls).to.equal(1);
    expect(a.data.ok).to.equal('/api/v1/leads');
    expect(b.data.ok).to.equal('/api/v1/auth/me');
    expect(seen.filter((s) => s.endsWith('Bearer new-token'))).to.have.length(2);
    expect(client.token).to.equal('new-token');
  });

  it('retries only once and reports session loss when refresh fails', async () => {
    let lost = 0;
    const client = new ApiClient('', async (url) =>
      url.endsWith('/refresh') ? json(401, { code: 'SESSION_INVALID' }) : json(401, { code: 'TOKEN_EXPIRED' }));
    client.hooks.onSessionLost = () => (lost += 1);
    client.setAccessToken('t');
    let problem: ApiProblem | null = null;
    try {
      await client.get('/api/v1/leads');
    } catch (e) {
      problem = e as ApiProblem;
    }
    expect(problem?.code).to.equal('TOKEN_EXPIRED');
    expect(lost).to.equal(1);
    expect(client.token).to.equal(null);
  });

  it('sends If-Match, Idempotency-Key and credentials', async () => {
    let captured: RequestInit | undefined;
    const client = new ApiClient('https://api.example', async (_u, init) => {
      captured = init;
      return json(200, { data: {} }, { ETag: '"5"' });
    });
    const r = await client.patch('/api/v1/leads/x', { priority: 'HIGH' }, { ifMatch: 4, idempotencyKey: 'k'.repeat(20) });
    const h = captured!.headers as Record<string, string>;
    expect(h['If-Match']).to.equal('"4"');
    expect(h['Idempotency-Key']).to.equal('k'.repeat(20));
    expect(captured!.credentials).to.equal('include');
    expect(r.etag).to.equal('"5"');
  });

  it('asks for step-up on STEP_UP_REQUIRED and retries once after success', async () => {
    let calls = 0;
    const client = new ApiClient('', async () => {
      calls += 1;
      return calls === 1
        ? json(403, { code: 'STEP_UP_REQUIRED', kind: 'mfa', mfa_token: 'tok' })
        : new Response(null, { status: 204 });
    });
    let seenKind: string | undefined;
    client.hooks.onStepUp = async (p) => {
      seenKind = p.ext<string>('kind');
      return true;
    };
    const r = await client.post('/api/v1/users/x/sessions/revoke', { reason: 'r' });
    expect(seenKind).to.equal('mfa');
    expect(r.status).to.equal(204);
    expect(calls).to.equal(2);
  });

  it('notifies on X-Authz-Version change and PERMISSION_DENIED', async () => {
    const versions: number[] = [];
    let denied = 0;
    let n = 0;
    const client = new ApiClient('', async () => {
      n += 1;
      if (n === 3) return json(403, { code: 'PERMISSION_DENIED' }, { 'X-Authz-Version': '8' });
      return json(200, { data: {} }, { 'X-Authz-Version': n === 1 ? '7' : '8' });
    });
    client.hooks.onAuthzVersion = (v) => versions.push(v);
    client.hooks.onPermissionDenied = () => (denied += 1);
    await client.get('/a');
    await client.get('/b');
    await client.get('/c').catch(() => undefined);
    expect(versions).to.deep.equal([8]);
    expect(denied).to.equal(1);
  });

  it('converts network failures into NETWORK_ERROR problems', async () => {
    const client = new ApiClient('', async () => {
      throw new TypeError('Failed to fetch');
    });
    const p = (await client.get('/x').catch((e) => e)) as ApiProblem;
    expect(p).to.be.instanceOf(ApiProblem);
    expect(p.isNetwork).to.equal(true);
  });
});

describe('parseProblem', () => {
  it('parses RFC 9457 bodies with field errors and extension members', async () => {
    const p = await parseProblem(json(409, {
      type: 'https://api.vedaspaces.com/problems/version-conflict', title: 'Conflict', status: 409, code: 'VERSION_CONFLICT',
      request_id: 'req-1', current_version: 7, updated_by: { id: 'u', display_name: 'Ravi' },
      errors: [{ field: 'phone', code: 'INVALID_PHONE', message: 'Enter a valid phone number.' }],
    }));
    expect(p.code).to.equal('VERSION_CONFLICT');
    expect(p.requestId).to.equal('req-1');
    expect(p.ext<number>('current_version')).to.equal(7);
    expect(p.fieldError('phone')?.code).to.equal('INVALID_PHONE');
  });

  it('tolerates non-JSON error bodies and keeps the X-Request-ID', async () => {
    const p = await parseProblem(new Response('<html>Bad gateway</html>', { status: 502, headers: { 'X-Request-ID': 'abc' } }));
    expect(p.code).to.equal('INTERNAL_ERROR');
    expect(p.requestId).to.equal('abc');
    const r = await parseProblem(new Response('', { status: 429 }));
    expect(r.code).to.equal('RATE_LIMITED');
  });
});
