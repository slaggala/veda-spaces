/**
 * `?next=` sanitizer (A-08, 12 §4.8): only same-origin relative paths are honoured, i.e. values that
 * match ^/(?![/\\]). `//evil.com`, `/\evil.com`, absolute URLs and anything else fall back.
 */
export function sanitizeNext(raw: string | null | undefined, fallback = '/'): string {
  if (!raw) return fallback;
  let value = raw;
  try {
    value = decodeURIComponent(raw);
  } catch {
    return fallback;
  }
  if (!/^\/(?![/\\])/.test(value)) return fallback;
  if (/[\u0000-\u001f]/.test(value)) return fallback;
  if (value.startsWith('/login')) return fallback;
  return value;
}

/** Navigate within the SPA (Vaadin Router listens to this event). */
export function navigate(url: string): void {
  const u = new URL(url, window.location.origin);
  window.dispatchEvent(
    new CustomEvent('vaadin-router-go', { detail: { pathname: u.pathname, search: u.search, hash: u.hash } }),
  );
}

/** Read a token from the URL fragment (`#token=…`), which is never sent to servers or logged. */
export function fragmentParam(name: string, hash = window.location.hash): string | null {
  const params = new URLSearchParams(hash.replace(/^#/, ''));
  return params.get(name);
}
