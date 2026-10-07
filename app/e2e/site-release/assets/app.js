document.documentElement.classList.add('js');

const header = document.querySelector('.site-header');
const menuButton = document.querySelector('.menu-button');
const mobileLinks = document.querySelectorAll('.mobile-nav a');

const syncHeader = () => header.classList.toggle('scrolled', window.scrollY > 40);
window.addEventListener('scroll', syncHeader, { passive: true });
syncHeader();

menuButton.addEventListener('click', () => {
  const open = document.body.classList.toggle('menu-open');
  menuButton.setAttribute('aria-expanded', String(open));
  menuButton.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
});

mobileLinks.forEach((link) => link.addEventListener('click', () => {
  document.body.classList.remove('menu-open');
  menuButton.setAttribute('aria-expanded', 'false');
  menuButton.setAttribute('aria-label', 'Open navigation');
}));

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape' || !document.body.classList.contains('menu-open')) return;
  document.body.classList.remove('menu-open');
  menuButton.setAttribute('aria-expanded', 'false');
  menuButton.setAttribute('aria-label', 'Open navigation');
  menuButton.focus();
});

const modal = document.querySelector('#project-modal');
const projectImages = document.querySelectorAll('.project-image');
let lastProjectTrigger = null;

const showProject = (button) => {
  lastProjectTrigger = button;
  const image = button.querySelector('img');
  modal.querySelector('img').src = image.src;
  modal.querySelector('img').alt = image.alt;
  modal.querySelector('p').textContent = button.dataset.room;
  modal.querySelector('h3').textContent = button.dataset.project;
  modal.showModal();
};

projectImages.forEach((button) => button.addEventListener('click', () => showProject(button)));
modal.querySelector('.modal-close').addEventListener('click', () => modal.close());
modal.addEventListener('click', (event) => {
  if (event.target === modal) modal.close();
});
modal.addEventListener('close', () => lastProjectTrigger?.focus());

// --- Enquiry form (LEAD-001, LEAD-019, 04 §5.1, 09 §4.11) -------------------------------------
// Progressive enhancement: the form posts to the API only when both <meta name="veda-api-base"> and the
// Turnstile site key are set. Otherwise it keeps the original WhatsApp hand-off, and the consent and
// verification blocks stay hidden (fail safe; IR-18, IR-32).
const contactForm = document.querySelector('#contact-form');
const meta = (name) => document.querySelector(`meta[name="${name}"]`)?.content?.trim() || '';
const apiBase = meta('veda-api-base') && meta('veda-turnstile-sitekey') ? meta('veda-api-base') : '';
if (meta('veda-api-base') && !apiBase) console.warn('veda: intake disabled — veda-turnstile-sitekey is not set');
const WHATSAPP = 'https://wa.me/919515125153';
const labels = { property: '#cf-property', service: '#cf-service', budget: '#cf-budget' };
let idempotencyKey = null;

const optionText = (sel) => {
  const el = document.querySelector(sel);
  return el && el.value ? el.options[el.selectedIndex].text : 'Not provided';
};

// Built only from visitor-entered fields (trimmed) and the selected option labels; the honeypot, consent and any
// API configuration never enter the message. encodeURIComponent below makes every value safe in the URL (RR-11).
const field = (data, name) => (data.get(name) || '').trim();
const whatsappText = (data) => [
  'Hello Veda Spaces, I would like to discuss my home interiors.',
  '',
  `Name: ${field(data, 'name')}`,
  `Phone: ${field(data, 'phone')}`,
  `Email: ${field(data, 'email') || 'Not provided'}`,
  `Property: ${optionText(labels.property)}`,
  `Service: ${optionText(labels.service)}`,
  `Budget: ${optionText(labels.budget)}`,
  `Location: ${field(data, 'location') || 'Not provided'}`,
  `Requirements: ${field(data, 'brief') || 'Not provided'}`,
].join('\n');

const whatsappUrl = (data) => `${WHATSAPP}?text=${encodeURIComponent(whatsappText(data))}`;

const newKey = () => (crypto.randomUUID ? crypto.randomUUID().replace(/-/g, '') : `${Date.now()}${Math.random()}`.replace(/\D/g, '')).slice(0, 40);
contactForm.addEventListener('input', () => { idempotencyKey = idempotencyKey || newKey(); }, { once: true });

const FIELD_IDS = { name: 'cf-name', phone: 'cf-phone', email: 'cf-email', 'consent.acknowledged': 'cf-consent', 'consent.policy_version': 'cf-consent' };

function clearErrors() {
  contactForm.querySelectorAll('[aria-invalid="true"]').forEach((el) => el.setAttribute('aria-invalid', 'false'));
  contactForm.querySelectorAll('.field-error').forEach((el) => { el.textContent = ''; });
  const summary = document.querySelector('#form-summary');
  summary.hidden = true;
  summary.textContent = '';
}

function showErrors(errors) {
  // Built with DOM nodes and textContent: server strings never reach innerHTML (IR-32).
  const summary = document.querySelector('#form-summary');
  const list = document.createElement('ul');
  for (const err of errors) {
    const id = FIELD_IDS[err.field];
    if (!id) continue;
    const input = document.getElementById(id);
    input.setAttribute('aria-invalid', 'true');
    document.getElementById(`${id}-err`).textContent = err.message;
    const item = document.createElement('li');
    const link = document.createElement('a');
    link.href = `#${id}`;
    link.textContent = err.message;
    item.append(link);
    list.append(item);
  }
  const heading = document.createElement('strong');
  const count = list.children.length;
  heading.textContent = `Please fix ${count} thing${count === 1 ? '' : 's'}`;
  summary.replaceChildren(heading, list);
  summary.hidden = false;
  summary.focus();
}

// Runs before every hand-off. The consent checkbox exists only when intake is enabled, so it is checked only then:
// the WhatsApp fallback never asks for, records or claims consent (RR-11).
function clientValidate(data, { consent }) {
  const errors = [];
  if (field(data, 'name').length < 2) errors.push({ field: 'name', message: 'Enter your name.' });
  const phone = field(data, 'phone');
  const digits = phone.replace(/\D/g, '');
  if (!/^\+?[\d\s().-]+$/.test(phone) || digits.length < 10 || digits.length > 15) {
    errors.push({ field: 'phone', message: 'Enter a valid phone number.' });
  }
  const email = field(data, 'email');
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.push({ field: 'email', message: 'Enter a valid email address.' });
  if (consent && !data.get('consent')) errors.push({ field: 'consent.acknowledged', message: 'Please agree to be contacted.' });
  return errors;
}

function showPanel(id, focus = true) {
  contactForm.hidden = true;
  const panel = document.getElementById(id);
  panel.hidden = false;
  if (focus) panel.focus();
}

function fallback(data, message) {
  document.querySelector('#fallback-message').textContent = `${message} Please continue on WhatsApp — your details are already filled in.`;
  document.querySelector('#fallback-whatsapp').href = whatsappUrl(data);
  showPanel('form-fallback');
}

let widgetId = null;
const turnstileToken = () => (window.turnstile && widgetId !== null ? window.turnstile.getResponse(widgetId) : '') || '';
// A Turnstile token is single use: after any response other than 201 the widget is reset for a new one (IR-18).
const resetTurnstile = () => { if (window.turnstile && widgetId !== null) window.turnstile.reset(widgetId); };

if (apiBase) {
  contactForm.querySelectorAll('[data-intake-only]').forEach((el) => { el.hidden = false; });
  const script = document.createElement('script');
  script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js';
  script.async = true;
  script.onload = () => { widgetId = window.turnstile?.render('#cf-turnstile', { sitekey: meta('veda-turnstile-sitekey') }) ?? null; };
  document.head.appendChild(script);
  document.querySelector('#form-note').textContent = 'We’ll call you within one working day. Prefer WhatsApp? Use the button on the left.';
}

contactForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = new FormData(contactForm);
  clearErrors();
  const errors = clientValidate(data, { consent: Boolean(apiBase) });
  if (errors.length) { showErrors(errors); return; }
  if (!apiBase) {
    window.open(whatsappUrl(data), '_blank', 'noopener');
    return;
  }
  const token = turnstileToken();
  if (!token) {
    // No verification token yet (widget still loading, or blocked): never submit without one.
    fallback(data, 'We couldn’t verify this submission.');
    return;
  }
  idempotencyKey = idempotencyKey || newKey();
  const params = new URLSearchParams(window.location.search);
  const body = {
    name: data.get('name').trim(),
    phone: data.get('phone').trim(),
    consent: { acknowledged: true, policy_version: meta('veda-policy-version') },
    email: (data.get('email') || '').trim() || null,
    city: (data.get('location') || '').trim() || null,
    project_type_code: data.get('service') || null,
    property_type_code: data.get('property') || null,
    budget_range_code: data.get('budget') || null,
    message: (data.get('brief') || '').trim() || null,
    attribution: {
      utm_source: params.get('utm_source'), utm_medium: params.get('utm_medium'), utm_campaign: params.get('utm_campaign'),
      utm_term: params.get('utm_term'), utm_content: params.get('utm_content'),
      landing_page: window.location.pathname + window.location.search, referrer_url: document.referrer || null,
      form_page: `${window.location.pathname}#contact`,
    },
    turnstile_token: token,
    company_website_url: data.get('company_website_url') || '',
  };
  contactForm.setAttribute('aria-busy', 'true');
  const button = contactForm.querySelector('button[type="submit"]');
  const label = button.textContent;
  button.disabled = true;
  button.textContent = 'Sending…';
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const res = await fetch(`${apiBase}/api/v1/public/leads`, {
      method: 'POST', signal: controller.signal,
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey },
      // Staging only (behind Cloudflare Access): send the API host's Access cookie. Production sends none.
      credentials: meta('veda-api-credentials') === 'include' ? 'include' : 'same-origin',
      body: JSON.stringify(body),
    });
    const payload = await res.json().catch(() => ({}));
    if (res.status === 201) {
      document.querySelector('#form-reference').textContent = payload.data.reference;
      document.querySelector('#success-whatsapp').href = whatsappUrl(data);
      showPanel('form-success');
      return;
    }
    resetTurnstile();
    // UNKNOWN_POLICY_VERSION is not the visitor's mistake: the page is out of date, so it is never a field error (IR-31).
    const fieldLevel = res.status === 422 && ['VALIDATION_FAILED', 'CONSENT_REQUIRED'].includes(payload.code);
    if (fieldLevel && Array.isArray(payload.errors) && payload.errors.some((e) => FIELD_IDS[e.field])) {
      showErrors(payload.errors);
      return;
    }
    const messages = {
      CAPTCHA_FAILED: 'We couldn’t verify this submission.', RATE_LIMITED: 'We’re receiving a lot of enquiries right now.',
      UNKNOWN_POLICY_VERSION: 'This page is out of date — please reload it.',
    };
    fallback(data, messages[payload.code] || 'Something went wrong on our side.');
  } catch (err) {
    resetTurnstile();
    fallback(data, err.name === 'AbortError' ? 'This is taking longer than expected.' : 'You appear to be offline.');
  } finally {
    clearTimeout(timer);
    contactForm.removeAttribute('aria-busy');
    button.disabled = false;
    button.textContent = label;
  }
});

const revealTargets = document.querySelectorAll(
  '.about-copy, .about-art, .service-card, .portfolio-head, .case-study, .process-heading, .process-grid article, .why-images, .why-copy, .execution-copy, .execution-grid article, .nri-panel, .contact-copy, .contact-form'
);

revealTargets.forEach((element) => element.classList.add('reveal-target'));

if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const revealObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      observer.unobserve(entry.target);
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: .08 });

  revealTargets.forEach((element) => revealObserver.observe(element));
} else {
  revealTargets.forEach((element) => element.classList.add('is-visible'));
}
