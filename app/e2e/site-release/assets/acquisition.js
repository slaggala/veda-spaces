// Sales & Customer Acquisition (SCA): first-party funnel beacons, first-touch attribution and the estimator call to
// action. Plain JavaScript, no inline code (production CSP), nothing personal.
//
// - The estimator link (`[data-estimator-only]`) shows only when <meta name="veda-estimator"> is "on", so no visitor
//   is sent to a "coming soon" page.
// - First-touch attribution: the campaign parameters and referrer of the first page of this browser session are kept
//   in sessionStorage, so an enquiry sent from a later page still carries where the visit came from.
// - Beacons: POST /api/v1/public/acquisition/events with {event, client, utm_source?, utm_medium?, referrer_host?}.
//   Sent only when <meta name="veda-acquisition-analytics"> is "on" and an API base is set; once per event per browser
//   session (sessionStorage); never when the browser asks not to be tracked (Global Privacy Control or Do Not Track).
//   The client token is random, kept for the session only, and the server stores counts, never the token.
(() => {
  'use strict';
  const meta = (name) => document.querySelector(`meta[name="${name}"]`)?.content?.trim() || '';
  const store = {
    get(key) { try { return sessionStorage.getItem(key); } catch { return null; } },
    set(key, value) { try { sessionStorage.setItem(key, value); } catch { /* storage unavailable: session-only behaviour degrades to per-page */ } },
  };

  // --- estimator call to action ----------------------------------------------------------------------------------
  if (meta('veda-estimator') === 'on') {
    document.querySelectorAll('[data-estimator-only]').forEach((el) => { el.hidden = false; });
  }

  // --- first-touch attribution ------------------------------------------------------------------------------------
  const params = new URLSearchParams(window.location.search);
  const host = (url) => { try { return url ? new URL(url).hostname.replace(/^www\./, '') : ''; } catch { return ''; } };
  const ownHost = window.location.hostname.replace(/^www\./, '');
  const hasCampaign = ['utm_source', 'utm_medium', 'utm_campaign'].some((k) => params.get(k));
  let stored = null;
  try { stored = JSON.parse(store.get('veda-first-touch') || 'null'); } catch { stored = null; }
  const storedCampaign = Boolean(stored && (stored.utm_source || stored.utm_medium || stored.utm_campaign));
  // The first page of the session is the touch that counts; it is replaced only when it carried no campaign and a
  // later page does (a visitor who came back through a campaign link), never field by field.
  if (!stored || (hasCampaign && !storedCampaign)) {
    const referrerHost = host(document.referrer);
    store.set('veda-first-touch', JSON.stringify({
      utm_source: params.get('utm_source') || null, utm_medium: params.get('utm_medium') || null,
      utm_campaign: params.get('utm_campaign') || null, utm_term: params.get('utm_term') || null,
      utm_content: params.get('utm_content') || null,
      landing_page: window.location.pathname + window.location.search,
      referrer_url: referrerHost && referrerHost !== ownHost ? document.referrer : null,
    }));
  }
  window.vedaFirstTouch = () => { try { return JSON.parse(store.get('veda-first-touch') || 'null'); } catch { return null; } };

  // --- beacons ----------------------------------------------------------------------------------------------------
  const apiBase = meta('veda-api-base');
  const enabled = meta('veda-acquisition-analytics') === 'on' && Boolean(apiBase);
  const optedOut = navigator.globalPrivacyControl === true || navigator.doNotTrack === '1' || window.doNotTrack === '1';
  const clientToken = () => {
    let token = store.get('veda-client'); // the same per-session token the estimator uses as its rate-limit key
    if (!token || !/^[A-Za-z0-9_-]{16,64}$/.test(token)) {
      token = (crypto.randomUUID ? crypto.randomUUID().replace(/-/g, '') : `${Date.now()}${Math.random()}`.replace(/\D/g, '')).slice(0, 32);
      store.set('veda-client', token);
    }
    return token;
  };
  const sent = () => { try { return JSON.parse(store.get('veda-acq-sent') || '[]'); } catch { return []; } };
  const clean = (value) => (typeof value === 'string' && /^[A-Za-z0-9._:%+-]{1,100}$/.test(value) ? value : null);

  function beacon(event) {
    if (!enabled || optedOut) return;
    const done = sent();
    if (done.includes(event)) return;
    done.push(event);
    store.set('veda-acq-sent', JSON.stringify(done));
    const first = window.vedaFirstTouch() || {};
    const body = { event, client: clientToken() };
    if (clean(first.utm_source)) body.utm_source = clean(first.utm_source);
    if (clean(first.utm_medium)) body.utm_medium = clean(first.utm_medium);
    const referrerHost = clean(host(first.referrer_url));
    if (referrerHost) body.referrer_host = referrerHost;
    fetch(`${apiBase}/api/v1/public/acquisition/events`, {
      method: 'POST', keepalive: true, headers: { 'Content-Type': 'application/json' },
      credentials: meta('veda-api-credentials') === 'include' ? 'include' : 'same-origin', // staging: the Access cookie
      body: JSON.stringify(body),
    }).catch(() => { /* a lost beacon is never retried: counts are indicative */ });
  }
  window.vedaBeacon = beacon;

  const page = document.body.dataset.acquisitionPage || '';
  if (page === 'home') beacon('site_visit');
  if (page === 'journey') beacon('journey_viewed');
  if (page === 'estimate') {
    const app = document.getElementById('est-app') || document.getElementById('est-v2') || document.body;
    const start = () => beacon('estimator_started');
    ['change', 'click'].forEach((type) => app.addEventListener(type, start, { once: true, passive: true }));
  }
  const form = document.getElementById('contact-form');
  if (form) form.addEventListener('input', () => beacon('enquiry_started'), { once: true, passive: true });
})();
