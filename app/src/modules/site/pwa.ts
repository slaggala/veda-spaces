/**
 * Offline shell for site capture (MTQ B1-T10). Registered only after the site API has answered (the feature is on
 * here) and scoped to `/site/`, so no other page of the workspace is ever controlled by it. API calls are never cached:
 * capture data lives in the device queue (offline-queue.ts), not in the worker.
 */
let registered = false;

export function registerSiteWorker(): void {
  if (registered || typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return;
  if (location.protocol !== 'https:' && location.hostname !== 'localhost') return;
  registered = true;
  navigator.serviceWorker.register('/site-sw.js', { scope: '/site/' }).catch(() => { registered = false; });
}
