import { expect } from '@open-wc/testing';
import { reportBrowserError, routeTemplate, scrubMessage, setReporter, type TelemetryEvent } from '../src/core/telemetry/telemetry.js';

describe('browser telemetry carries no personal data (RR-13)', () => {
  it('reports the path with ids replaced, never the query string or fragment', () => {
    expect(routeTemplate('/leads/0192f5a2b7c87d3e9a1b2c3d4e5f6a7b')).to.equal('/leads/:id');
    expect(routeTemplate('/leads?q=priya.sharma%40example.com')).to.equal('/leads');
    expect(routeTemplate('/leads#q=priya')).to.equal('/leads');
  });

  it('scrubs query strings, emails and phone numbers from error messages', () => {
    const msg = scrubMessage(
      'Failed to fetch https://api.vedaspaces.com/api/v1/leads?q=priya.sharma%40example.com for priya.sharma@example.com, +91 98765 43210',
    );
    expect(msg).to.not.match(/priya|sharma|example\.com|98765|43210|q=/i);
    expect(msg).to.contain('https://api.vedaspaces.com/api/v1/leads');
    expect(msg).to.contain('[email]').and.to.contain('[phone]');
    expect(scrubMessage('TypeError: x is undefined')).to.equal('TypeError: x is undefined');
    expect(scrubMessage('a'.repeat(500))).to.have.length(200);
  });

  it('the global error handler passes only the scrubbed message to the reporter', () => {
    const seen: TelemetryEvent[] = [];
    setReporter((e) => seen.push(e));
    reportBrowserError('bad input priya@example.com at /leads?q=priya');
    expect(seen).to.have.length(1);
    expect(JSON.stringify(seen)).to.not.match(/priya|example\.com|q=/);
  });
});
