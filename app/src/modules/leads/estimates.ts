import type { EstimateRange, EstimateSelection } from '../../core/api/types.js';
import { formatINR } from '../../core/format/format.js';

/** Paise → ₹ with Indian grouping (the API returns integer paise). */
export function rupees(minor: number | null | undefined): string {
  return minor === null || minor === undefined ? '—' : formatINR(Math.round(minor / 100));
}

export function rangeText(range: EstimateRange): string {
  return `${rupees(range.low_minor)} – ${rupees(range.high_minor)}`;
}

/** Packages a staff revision can price. Luxury is never priced: it is a design consultation (ADR-012 D2). */
export const PACKAGES = ['ESSENTIAL', 'PREMIUM'] as const;

/** The API unit for an assumption's unit text ("ft", "sq ft", "nos"). */
export function apiUnit(unit: string): string {
  return unit === 'sq ft' ? 'sqft' : unit === 'nos' ? 'nos' : 'ft';
}

/**
 * A revision request: the original selections with the staff's measurement edits applied. An edit with an empty or
 * non-positive value removes that measurement, so the engine uses (and labels) the typical size again.
 */
export function revisedSelections(
  selections: EstimateSelection[],
  edits: Record<string, string>,
): EstimateSelection[] {
  return selections.map((sel, i) => {
    const measurements = { ...sel.measurements };
    for (const [key, raw] of Object.entries(edits)) {
      const [index, name, unit] = key.split('|');
      if (Number(index) !== i) continue;
      const value = Number(raw);
      if (raw.trim() === '' || !(value > 0)) delete measurements[name];
      else measurements[name] = { value, unit: unit || measurements[name]?.unit || 'ft' };
    }
    return { ...sel, measurements, options: { ...sel.options } };
  });
}

/**
 * Measurement keys of a selection's product as shown in the revision form: entered values plus typical ones. A typical
 * input keeps its own kind of unit (sq ft for an area, nos for a count), so a revised value is accepted by the engine.
 */
export function measurementRows(sel: EstimateSelection, typicalInputs: (string | { name: string; unit: string })[]): { name: string; value: string; unit: string; typical: boolean }[] {
  const entered = Object.entries(sel.measurements).map(([name, m]) => ({ name, value: String(m.value), unit: m.unit, typical: false }));
  const typical = typicalInputs
    .map((t) => (typeof t === 'string' ? { name: t, unit: 'ft' } : t))
    .filter((t) => !(t.name in sel.measurements))
    .map((t) => ({ name: t.name, value: '', unit: t.unit, typical: true }));
  return [...entered, ...typical];
}
