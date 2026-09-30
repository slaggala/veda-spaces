import { css } from 'lit';

/** Shared constructable stylesheets (02 §2.1). Components consume tokens only (09 §2.5). */
export const baseStyles = css`
  :host { box-sizing: border-box; font-family: var(--vs-font-sans); color: var(--vs-ink); }
  *, *::before, *::after { box-sizing: inherit; }
  [hidden] { display: none !important; }
  :focus-visible { outline: 2px solid var(--vs-focus-ring); outline-offset: 2px; }
  a { color: var(--vs-copper-text); text-underline-offset: 3px; }
  h1, h2, h3, h4 { margin: 0; font-weight: 500; }
  p { margin: 0; }
  .display { font-family: var(--vs-font-serif); font-weight: 500; font-size: 40px; line-height: 44px; }
  .title { font-family: var(--vs-font-serif); font-weight: 500; font-size: 28px; line-height: 32px; }
  .eyebrow { font-size: 11px; line-height: 16px; font-weight: 600; letter-spacing: .18em; text-transform: uppercase; color: var(--vs-ink-muted); }
  .muted { color: var(--vs-ink-muted); }
  .small { font-size: 12px; line-height: 18px; font-weight: 500; }
  .mono { font-family: var(--vs-font-mono); font-size: 12px; line-height: 18px; }
  .strong { font-weight: 600; }
  .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
  .row { display: flex; align-items: center; gap: var(--vs-space-3); flex-wrap: wrap; }
  .stack { display: flex; flex-direction: column; gap: var(--vs-space-3); }
  .spacer { flex: 1; }
  .card { background: var(--vs-surface); border: 1px solid var(--vs-line); border-radius: var(--vs-radius-card); padding: var(--vs-space-5); }
  .hairline { border: 0; border-top: 1px solid var(--vs-line); margin: var(--vs-space-4) 0; }
  .danger-text { color: var(--vs-danger); }
  .warning-text { color: var(--vs-warning); }
  .success-text { color: var(--vs-success); }
  @media (max-width: 767px) { .display { font-size: 32px; line-height: 36px; } }
`;

export const controlStyles = css`
  .btn {
    display: inline-flex; align-items: center; justify-content: center; gap: var(--vs-space-2);
    min-height: var(--vs-target); padding: 0 var(--vs-space-4); border-radius: var(--vs-radius-control);
    font: 600 14px/22px var(--vs-font-sans); cursor: pointer; text-decoration: none;
    border: 1px solid var(--vs-line); background: var(--vs-surface); color: var(--vs-ink);
    transition: background var(--vs-motion-fast) ease-out, border-color var(--vs-motion-fast) ease-out;
  }
  .btn:hover { border-color: var(--vs-ink-muted); }
  .btn[disabled], .btn[aria-disabled='true'] { opacity: .55; cursor: not-allowed; }
  .btn.primary { background: var(--vs-copper-strong); color: var(--vs-on-copper-strong); border-color: var(--vs-copper-strong); }
  .btn.danger { background: var(--vs-danger); color: var(--vs-on-danger); border-color: var(--vs-danger); }
  .btn.ghost { background: transparent; border-color: transparent; color: var(--vs-copper-text); }
  .btn.ghost:hover { border-color: var(--vs-line); }
  .btn.small { min-height: 36px; padding: 0 var(--vs-space-3); font-size: 13px; }
  .btn.block { width: 100%; }
  .icon-btn { min-width: var(--vs-target); padding: 0; }
  label.field, .field { display: flex; flex-direction: column; gap: var(--vs-space-1); }
  .label, .field > .label { font-size: 11px; line-height: 16px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--vs-ink-muted); }
  .field .hint { font-size: 12px; color: var(--vs-ink-muted); }
  .field .error { font-size: 12px; color: var(--vs-danger); display: flex; gap: 4px; align-items: center; }
  input, select, textarea {
    font: 400 16px/22px var(--vs-font-sans); color: var(--vs-ink); background: var(--vs-surface);
    border: 1px solid var(--vs-line); border-radius: var(--vs-radius-control); padding: 10px 12px; min-height: var(--vs-target);
    width: 100%;
  }
  input[type='checkbox'], input[type='radio'] { width: 20px; height: 20px; min-height: 0; accent-color: var(--vs-copper); }
  textarea { min-height: 88px; resize: vertical; }
  input[aria-invalid='true'], select[aria-invalid='true'], textarea[aria-invalid='true'] { border-color: var(--vs-danger); }
  .check { display: flex; align-items: center; gap: var(--vs-space-2); min-height: var(--vs-target); }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: var(--vs-space-4); }
  @media (max-width: 767px) { .grid-2 { grid-template-columns: 1fr; } }
  .chip {
    display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px; border-radius: var(--vs-radius-pill);
    background: var(--vs-cream); color: var(--vs-ink); font-size: 12px; line-height: 18px; font-weight: 600; white-space: nowrap;
  }
  .chip.warning { color: var(--vs-warning); }
  .chip.danger { color: var(--vs-danger); }
  .chip.success { color: var(--vs-success); }
  .chip button { background: none; border: 0; color: inherit; cursor: pointer; padding: 0 2px; font: inherit; }
`;

export const tableStyles = css`
  .table-wrap { overflow-x: auto; background: var(--vs-surface); border: 1px solid var(--vs-line); border-radius: var(--vs-radius-card); }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--vs-ink-muted); font-weight: 600; padding: 10px 12px; border-bottom: 1px solid var(--vs-line); white-space: nowrap; position: sticky; top: 0; background: var(--vs-surface); }
  td { padding: 10px 12px; border-bottom: 1px solid var(--vs-line); height: var(--vs-row-height); vertical-align: middle; }
  tbody tr:last-child td { border-bottom: 0; }
  tbody tr.clickable { cursor: pointer; }
  tbody tr.clickable:hover, tbody tr:focus-within { background: var(--vs-cream); }
  td .primary-cell { font-weight: 600; }
  @media (max-width: 767px) {
    table.cards thead { display: none; }
    table.cards tr { display: block; padding: var(--vs-space-3); border-bottom: 1px solid var(--vs-line); }
    table.cards td { display: flex; justify-content: space-between; gap: var(--vs-space-3); border: 0; height: auto; padding: 4px 0; }
    table.cards td::before { content: attr(data-label); font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--vs-ink-muted); }
  }
`;

export const pageStyles = css`
  :host { display: block; }
  .page { max-width: 1440px; margin: 0 auto; padding: var(--vs-space-6); display: flex; flex-direction: column; gap: var(--vs-space-5); }
  .page-head { display: flex; align-items: flex-end; gap: var(--vs-space-4); flex-wrap: wrap; }
  .page-head .spacer { flex: 1; }
  @media (max-width: 767px) { .page { padding: var(--vs-space-4); gap: var(--vs-space-4); } }
`;

export const shared = [baseStyles, controlStyles];
