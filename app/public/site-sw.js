/* global self, caches, fetch, URL */
/* Offline shell for the site-capture pages (MTQ B1-T10). Scope: /site/ only (see src/modules/site/pwa.ts).
 * - Navigations under /site/: network first; offline, the cached app shell.
 * - Hashed build assets (/assets/*): cache first (they never change under the same name).
 * - Everything else, and every /api request, goes to the network untouched. */
const CACHE = 'veda-site-shell-v1';

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(['/'])).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k.startsWith('veda-site-shell-') && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
  if (event.request.mode === 'navigate' && url.pathname.startsWith('/site/')) {
    event.respondWith(
      fetch(event.request)
        .then((r) => { const copy = r.clone(); caches.open(CACHE).then((c) => c.put('/', copy)); return r; })
        .catch(() => caches.match('/')),
    );
    return;
  }
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(caches.match(event.request).then((hit) => hit || fetch(event.request).then((r) => {
      if (r.ok) { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(event.request, copy)); }
      return r;
    })));
  }
});
