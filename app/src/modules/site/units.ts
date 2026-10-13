/**
 * Site measurement units (MTQ B1, blueprint §6.1 (1); AR-16). Surveyors type feet-inches or millimetres; the client
 * converts every entry to integer millimetres before it is sent, and the server never stores fractional feet.
 * `unit_system_code` on a set is only the default entry unit.
 */
export type UnitSystem = 'FT_IN' | 'MM';

const MM_PER_INCH = 25.4;

/**
 * Parse a typed length to integer millimetres, or null when it is empty or not a length.
 * Accepted: `3600`, `3600mm`, `3.6m`, `11'10"`, `11' 10.5"`, `11ft 10in`, `142"`, `11.5'` and, in FT_IN mode, a bare
 * `11 10` (feet then inches). A bare number means millimetres in MM mode and feet in FT_IN mode.
 */
export function parseLength(raw: string, mode: UnitSystem): number | null {
  const s = raw.trim().toLowerCase().replace(/\s+/g, ' ');
  if (!s) return null;
  let m = /^(\d+(?:\.\d+)?)\s*mm$/.exec(s);
  if (m) return Math.round(Number(m[1]));
  m = /^(\d+(?:\.\d+)?)\s*m$/.exec(s);
  if (m) return Math.round(Number(m[1]) * 1000);
  m = /^(\d+(?:\.\d+)?)\s*(?:'|ft)\s*(?:(\d+(?:\.\d+)?)\s*(?:"|in)?)?$/.exec(s);
  if (m) return Math.round((Number(m[1]) * 12 + Number(m[2] ?? 0)) * MM_PER_INCH);
  m = /^(\d+(?:\.\d+)?)\s*(?:"|in)$/.exec(s);
  if (m) return Math.round(Number(m[1]) * MM_PER_INCH);
  if (mode === 'FT_IN') {
    m = /^(\d+)\s+(\d+(?:\.\d+)?)$/.exec(s);
    if (m) return Math.round((Number(m[1]) * 12 + Number(m[2])) * MM_PER_INCH);
    m = /^(\d+(?:\.\d+)?)$/.exec(s);
    if (m) return Math.round(Number(m[1]) * 12 * MM_PER_INCH);
    return null;
  }
  m = /^(\d+(?:\.\d+)?)$/.exec(s);
  return m ? Math.round(Number(m[1])) : null;
}

/** Millimetres for display in the surveyor's unit: `11' 9 3/4"` (to the nearest quarter inch) or `3600 mm`. */
export function formatLength(mm: number | null | undefined, mode: UnitSystem): string {
  if (mm === null || mm === undefined) return '';
  if (mode === 'MM') return `${mm} mm`;
  const quarters = Math.round((mm / MM_PER_INCH) * 4);
  const feet = Math.floor(quarters / 48);
  const rest = quarters - feet * 48;
  const inches = Math.floor(rest / 4);
  const frac = ['', ' 1/4', ' 1/2', ' 3/4'][rest % 4];
  return `${feet}' ${inches}${frac}"`;
}

/** Hundredths of a square foot for display: `104.63 sq ft`. */
export function formatArea(centi: number | null | undefined): string {
  if (centi === null || centi === undefined) return '';
  return `${(centi / 100).toFixed(2)} sq ft`;
}
