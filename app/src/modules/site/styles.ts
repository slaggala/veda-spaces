import { css } from 'lit';

/**
 * Touch targets for the site module (B1-PE-04): surveyors work one-handed, often gloved, on a ladder, so every control
 * on these pages is at least 44 × 44 px (--vs-target). Scoped to the site pages; the shared design system is unchanged.
 */
export const siteTargets = css`
  .btn.small { min-height: var(--vs-target); min-width: var(--vs-target); }
  summary { line-height: 24px; padding: 10px 0; cursor: pointer; }
  td a:not(.btn) { display: inline-flex; align-items: center; min-height: var(--vs-target); }
  .hit { display: inline-flex; align-items: center; justify-content: center; min-width: var(--vs-target); min-height: var(--vs-target); cursor: pointer; }
`;
