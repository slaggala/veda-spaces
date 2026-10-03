/**
 * Minimal error reporting with request-id capture (02 §2.2 core/telemetry). No PII is sent: only the
 * error code, route template and request id. A Sentry transport can be plugged in via setReporter().
 *
 * RR-13: the route is the path only (never the query string, which carries lead searches) with ids
 * replaced, and an error message is scrubbed of URLs' query strings, emails and phone numbers before any
 * reporter sees it, because browser error messages can quote the values that caused them.
 */
export interface TelemetryEvent {
  kind: 'api-problem' | 'error';
  code?: string;
  requestId?: string;
  route: string;
  message?: string;
}

type Reporter = (event: TelemetryEvent) => void;
let reporter: Reporter = (event) => {
  if ((import.meta as { env?: { DEV?: boolean } }).env?.DEV) console.debug('[telemetry]', event);
};
let lastRequestId: string | undefined;

export function setReporter(fn: Reporter): void {
  reporter = fn;
}

export function captureRequestId(id: string | null | undefined): void {
  if (id) lastRequestId = id;
}

export function getLastRequestId(): string | undefined {
  return lastRequestId;
}

export function routeTemplate(pathname: string = window.location.pathname): string {
  return pathname.split(/[?#]/, 1)[0].replace(/[0-9a-f]{32}/g, ':id');
}

const QUERY = /(\bhttps?:\/\/[^\s?#]*|\/[^\s?#]*)[?#][^\s]*/g;
const EMAIL = /[A-Za-z0-9._%+-]+(?:@|%40)[A-Za-z0-9.-]+/gi;
const PHONE = /\+?\d[\d\s-]{8,}\d/g;

/** A message safe to report: no query strings, emails or phone numbers, at most 200 characters. */
export function scrubMessage(message: unknown): string {
  return String(message).replace(QUERY, '$1').replace(EMAIL, '[email]').replace(PHONE, '[phone]').slice(0, 200);
}

export function reportProblem(code: string, requestId?: string): void {
  captureRequestId(requestId);
  reporter({ kind: 'api-problem', code, requestId, route: routeTemplate() });
}

/** Report a browser error: the reporter only ever sees the scrubbed message (RR-13). */
export function reportBrowserError(message: unknown): void {
  reporter({ kind: 'error', route: routeTemplate(), message: scrubMessage(message) });
}

export function installGlobalHandlers(): void {
  window.addEventListener('error', (e) => reportBrowserError(e.message));
  window.addEventListener('unhandledrejection', (e) => {
    const reason = e.reason as { code?: string; requestId?: string } | undefined;
    if (reason?.code) reportProblem(reason.code, reason.requestId);
    else reporter({ kind: 'error', route: routeTemplate(), message: 'unhandled rejection' });
  });
}
