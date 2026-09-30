// Token-pair contrast test (09 §2.5, AX-05, F-14). Fails the build when any text pair is below 4.5:1 or
// any non-text pair is below 3:1, in either theme. Values are read from tokens.css, the single source.
import { readFileSync } from 'node:fs';

const css = readFileSync(new URL('../src/design-system/tokens.css', import.meta.url), 'utf8');

function block(selectorRegex) {
  const m = css.match(selectorRegex);
  if (!m) throw new Error(`token block not found: ${selectorRegex}`);
  const out = {};
  for (const [, name, value] of m[1].matchAll(/(--vs-[\w-]+)\s*:\s*([^;]+);/g)) out[name] = value.trim();
  return out;
}

const light = block(/^:root\s*\{([\s\S]*?)\n\}/m);
const dark = { ...light, ...block(/:root\[data-theme='dark'\]\s*\{([\s\S]*?)\n\}/) };
const darkMedia = block(/:root:not\(\[data-theme='light'\]\)\s*\{([\s\S]*?)\n\s*\}/);
for (const [k, v] of Object.entries(darkMedia)) {
  if (dark[k] !== v) throw new Error(`dark tokens differ between media query and [data-theme=dark]: ${k}`);
}

function rgb(hex) {
  const h = hex.replace('#', '');
  const full = h.length === 3 ? [...h].map((c) => c + c).join('') : h;
  return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16) / 255);
}
function luminance(hex) {
  const [r, g, b] = rgb(hex).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
export function ratio(a, b) {
  const [l1, l2] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
}

const TEXT = 4.5;
const NON_TEXT = 3;
const pairs = [
  ['--vs-ink', '--vs-paper', TEXT], ['--vs-ink', '--vs-surface', TEXT], ['--vs-ink', '--vs-cream', TEXT],
  ['--vs-ink-muted', '--vs-paper', TEXT], ['--vs-ink-muted', '--vs-surface', TEXT],
  ['--vs-copper-text', '--vs-paper', TEXT], ['--vs-copper-text', '--vs-surface', TEXT],
  ['--vs-on-copper-strong', '--vs-copper-strong', TEXT],
  ['--vs-on-danger', '--vs-danger', TEXT],
  ['--vs-danger', '--vs-paper', TEXT], ['--vs-danger', '--vs-surface', TEXT],
  ['--vs-success', '--vs-paper', TEXT], ['--vs-success', '--vs-surface', TEXT],
  ['--vs-warning', '--vs-paper', TEXT], ['--vs-warning', '--vs-surface', TEXT],
  ['--vs-on-sidebar', '--vs-sidebar', TEXT], ['--vs-on-sidebar-muted', '--vs-sidebar', TEXT],
  ['--vs-copper', '--vs-paper', NON_TEXT], ['--vs-copper', '--vs-surface', NON_TEXT],
  ['--vs-focus-ring', '--vs-paper', NON_TEXT], ['--vs-focus-ring', '--vs-surface', NON_TEXT],
  ['--vs-copper', '--vs-sidebar', NON_TEXT],
];
for (const s of ['new', 'contacted', 'site_visit', 'quotation_sent', 'negotiation', 'won', 'lost']) {
  pairs.push([`--vs-status-${s}-fg`, `--vs-status-${s}-bg`, TEXT]);
}

let failed = 0;
for (const [theme, tokens] of [['light', light], ['dark', dark]]) {
  for (const [fg, bg, min] of pairs) {
    const r = ratio(tokens[fg], tokens[bg]);
    const ok = r >= min;
    if (!ok) failed += 1;
    console.log(`${ok ? 'PASS' : 'FAIL'} ${theme.padEnd(5)} ${fg} on ${bg}: ${r.toFixed(2)}:1 (min ${min}:1)`);
  }
}
if (failed) {
  console.error(`\ntest:contrast failed: ${failed} pair(s) below threshold`);
  process.exit(1);
}
console.log(`\ntest:contrast passed: ${pairs.length * 2} pairs across light and dark themes`);
