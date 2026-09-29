import { svg, type SVGTemplateResult } from 'lit';

/** 1.5 px stroke line icons (Lucide-style, self-hosted, 09 §2.4). */
const paths: Record<string, SVGTemplateResult> = {
  home: svg`<path d="M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3z"/>`,
  users: svg`<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.5 3.4-5.5 6.5-5.5s5.7 2 6.5 5.5"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14.5c2 .7 3.2 2.6 3.5 5.5"/>`,
  user: svg`<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4.2-6.5 8-6.5s7 2.5 8 6.5"/>`,
  calendar: svg`<rect x="3.5" y="5" width="17" height="15.5" rx="1"/><path d="M3.5 10h17M8 3v4M16 3v4"/>`,
  check: svg`<path d="m4.5 12.5 5 5 10-11"/>`,
  shield: svg`<path d="M12 3 4.5 6v5.5c0 4.5 3.2 8.2 7.5 9.5 4.3-1.3 7.5-5 7.5-9.5V6z"/>`,
  key: svg`<circle cx="8" cy="15" r="4"/><path d="m11 12 8.5-8.5M16 7l2.5 2.5M14 9l2 2"/>`,
  star: svg`<path d="m12 3 2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 16.8l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8z"/>`,
  list: svg`<path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>`,
  settings: svg`<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>`,
  bell: svg`<path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15zM10 20.5a2 2 0 0 0 4 0"/>`,
  search: svg`<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>`,
  plus: svg`<path d="M12 5v14M5 12h14"/>`,
  x: svg`<path d="M6 6l12 12M18 6 6 18"/>`,
  phone: svg`<path d="M5 3.5h3.5l1.5 4.5-2 1.5a11 11 0 0 0 6 6l1.5-2 4.5 1.5V19a1.5 1.5 0 0 1-1.5 1.5A16.5 16.5 0 0 1 3.5 5 1.5 1.5 0 0 1 5 3.5z"/>`,
  message: svg`<path d="M20.5 11.7a8.4 8.4 0 0 1-12.4 7.4L4 20.2l1.1-4a8.4 8.4 0 1 1 15.4-4.5z"/>`,
  alert: svg`<path d="M12 3.5 2.5 20h19zM12 10v4.5M12 17.5h.01"/>`,
  info: svg`<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.5h.01"/>`,
  more: svg`<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>`,
  logout: svg`<path d="M15 4.5h3.5v15H15M10 8l-4 4 4 4M6 12h10"/>`,
  lock: svg`<rect x="5" y="10.5" width="14" height="10" rx="1"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>`,
  arrowLeft: svg`<path d="M19 12H5M11 6l-6 6 6 6"/>`,
  arrowRight: svg`<path d="M5 12h14M13 6l6 6-6 6"/>`,
  copy: svg`<rect x="8.5" y="8.5" width="12" height="12" rx="1"/><path d="M15.5 8.5V3.5h-12v12h5"/>`,
};

export function icon(name: string, label?: string): SVGTemplateResult {
  const body = paths[name] ?? paths.info;
  return svg`<svg class="icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" role=${label ? 'img' : 'presentation'}
    aria-hidden=${label ? 'false' : 'true'} aria-label=${label ?? ''} focusable="false">${body}</svg>`;
}
