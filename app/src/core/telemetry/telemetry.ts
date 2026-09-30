/**
 * Minimal error reporting with request-id capture (02 §2.2 core/telemetry). No PII is sent: only the
 * error code, route template and request id. A Sentry transport can be plugged in via setReporter().
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

function routeTemplate(): string {
  return window.location.pathname.replace(/[0-9a-f]{32}/g, ':id');
}

export function reportProblem(code: string, requestId?: string): void {
  captureRequestId(requestId);
  reporter({ kind: 'api-problem', code, requestId, route: routeTemplate() });
}

export function installGlobalHandlers(): void {
  window.addEventListener('error', (e) => reporter({ kind: 'error', route: routeTemplate(), message: String(e.message).slice(0, 200) }));
  window.addEventListener('unhandledrejection', (e) => {
    const reason = e.reason as { code?: string; requestId?: string } | undefined;
    if (reason?.code) reportProblem(reason.code, reason.requestId);
    else reporter({ kind: 'error', route: routeTemplate(), message: 'unhandled rejection' });
  });
}
