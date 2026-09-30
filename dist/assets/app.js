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

document.querySelector('#contact-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const data = new FormData(event.currentTarget);
  const lines = [
    'Hello Veda Spaces, I would like to discuss my home interiors.',
    '',
    `Name: ${data.get('name')}`,
    `Phone: ${data.get('phone')}`,
    `Email: ${data.get('email') || 'Not provided'}`,
    `Property: ${data.get('property')}`,
    `Service: ${data.get('service')}`,
    `Location: ${data.get('location') || 'Not provided'}`,
    `Requirements: ${data.get('brief') || 'Not provided'}`,
  ];
  window.open(`https://wa.me/919515125153?text=${encodeURIComponent(lines.join('\n'))}`, '_blank', 'noopener');
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
