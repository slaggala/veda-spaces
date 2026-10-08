// Estimator UX V2 prototype: customer-facing specification data in the proposed schema
// (veda.estimator.customer-spec/1, docs/implementation/estimator/ESTIMATOR-UX-V2-TRUST.md §6). Customer-facing text
// only: no rates, no price ceilings, no supplier costs.
//
// The two historical Essential specifications conflict (owner decision T1). The prototype therefore carries:
//   baseline           — only what both documents agree on (default: nothing conflicting is promised)
//   candidate-oct-2026 — the October 2026 quotation specification
//   candidate-jun-2026 — the June 2026 quotation specification
// A facilitator can switch with ?spec=oct or ?spec=jun. Nothing here is approved for publication.
'use strict';

const COMMON = {
  doors: { promise: 'Doors and shutters in branded block board', grade: '18–19 mm block board', brands: ['Sylvan Primo Plus'] },
  surface: { promise: 'Laminate finish in your choice of colours', grade: '1.0 mm outer laminate', brands: ['Merino', 'Century', 'Greenlam', 'Royal Touch', 'Stylam', 'Plain Art', 'Dazzle Berry', 'Airolam'] },
  hinges: { promise: 'Soft-close hinges', brands: ['Hettich'] },
  tandems: { promise: 'Soft-close kitchen drawers', brands: ['Hettich'] },
  handles: { promise: 'Handles chosen by you from a standard range', grade: '1 ft, 1.5 ft or 2 ft lengths' },
  accessories: { promise: 'Wicker baskets, rolling shutters and pantry pull-outs where your design includes them', brands: ['Nimmi', 'Hettich', 'Samsung Irex', 'Olive'] },
  ceiling: { promise: 'Gypsum false ceiling on steel channels', grade: 'Gypsum board on Bright 04/06 channels', brands: ['Saint-Gobain'] },
  lights: { promise: 'LED panel, profile and spot lights, installed', brands: ['Philips', 'Wipro', 'Crompton', 'Avion'] },
  wiring: { promise: 'Branded copper wiring (optional electrical work)', brands: ['Polycab', 'Finolex'] },
  painting: { promise: 'Premium emulsion paint, one colour (optional painting)', brands: ['Asian Paints Premium', 'Birla or Asian putty'] },
  edgeOuter: { promise: 'Sealed edges on every visible side', grade: '2 mm outer edge banding', brands: ['Solid Edge', 'E3', 'URO', 'Red Star'] },
};

const CATEGORIES = [
  // id, customer label, summary (customer language), applies to rooms
  { id: 'structure', label: 'Cabinet structure', rooms: ['kitchen', 'living', 'dining', 'master', 'bed2', 'bed3', 'pooja', 'utility'] },
  { id: 'doors', label: 'Doors and shutters', rooms: ['kitchen', 'living', 'dining', 'master', 'bed2', 'bed3', 'pooja', 'utility'] },
  { id: 'surface', label: 'Surface finish', rooms: ['kitchen', 'living', 'dining', 'master', 'bed2', 'bed3', 'pooja', 'utility'] },
  { id: 'edges', label: 'Edges', rooms: ['kitchen', 'living', 'dining', 'master', 'bed2', 'bed3', 'pooja', 'utility'] },
  { id: 'hardware', label: 'Hardware', rooms: ['kitchen', 'living', 'dining', 'master', 'bed2', 'bed3', 'pooja', 'utility'] },
  { id: 'handles', label: 'Handles', rooms: ['kitchen', 'living', 'dining', 'master', 'bed2', 'bed3', 'pooja', 'utility'] },
  { id: 'accessories', label: 'Kitchen accessories', rooms: ['kitchen'] },
  { id: 'ceiling', label: 'Ceiling and lighting', rooms: ['whole'] },
  { id: 'optional', label: 'Optional electrical and painting', rooms: ['whole'] },
];

function spec(id, title, status, parts) {
  return { schema: 'veda.estimator.customer-spec/1', id, package: 'ESSENTIAL', title, status, effectiveOn: '2026-10-08',
    orEquivalent: 'Named brand or an approved equivalent of the same grade', categories: CATEGORIES.map((c) => ({ ...c, ...parts[c.id] })) };
}

window.VEDA_SPECS = {
  baseline: spec('baseline', 'Agreed in both historical specifications', 'DRAFT', {
    structure: { summary: 'Branded plywood structure', promise: 'Cabinet bodies in branded plywood', details: ['18 mm plywood for cabinet bodies', '9 mm back panels', '12 mm behind the TV', 'Brand: Sylvan (grade per the final specification)'] },
    doors: { summary: 'Branded block-board doors', promise: COMMON.doors.promise, details: [`${COMMON.doors.grade}`, `Brand: ${COMMON.doors.brands.join(', ')}`] },
    surface: { summary: 'Laminate finish', promise: COMMON.surface.promise, details: [COMMON.surface.grade, 'Inner laminate: standard colour selected by Veda Spaces', `Brands: ${COMMON.surface.brands.join(', ')}`] },
    edges: { summary: 'Sealed edges', promise: COMMON.edgeOuter.promise, details: [COMMON.edgeOuter.grade, 'Inner edge banding per the final specification', `Brands: ${COMMON.edgeOuter.brands.join(', ')}`] },
    hardware: { summary: 'Soft-close hardware', promise: 'Soft-close hinges and drawers', details: [`Hinges: ${COMMON.hinges.brands.join(', ')}`, `Kitchen drawers: ${COMMON.tandems.brands.join(', ')}`, 'Drawer channels: branded, per the final specification', 'Sliding-door channels: Nimmi or Hettich'] },
    handles: { summary: 'Standard handles', promise: COMMON.handles.promise, details: [COMMON.handles.grade] },
    accessories: { summary: 'Kitchen accessories', promise: COMMON.accessories.promise, details: [`Brands: ${COMMON.accessories.brands.join(', ')}`] },
    ceiling: { summary: 'Gypsum ceiling, LED lights', promise: `${COMMON.ceiling.promise}; ${COMMON.lights.promise.toLowerCase()}`, details: [COMMON.ceiling.grade, `Gypsum: ${COMMON.ceiling.brands.join(', ')}`, `Lights: ${COMMON.lights.brands.join(', ')}`] },
    optional: { summary: 'Branded wiring and paint', promise: 'If you add them: branded wiring and premium emulsion paint', details: [`Wiring: ${COMMON.wiring.brands.join(', ')}`, `Paint: ${COMMON.painting.brands.join(', ')}; one colour`] },
  }),
  'candidate-oct-2026': spec('candidate-oct-2026', 'October 2026 quotation specification (candidate)', 'CANDIDATE', {
    structure: { summary: 'Sylvan Blu plywood structure', promise: 'Cabinet bodies in Sylvan Blu plywood', details: ['18 mm Sylvan Blu for cabinet bodies; 9 mm back panels; 12 mm behind the TV', 'Manufacturer warranty per Sylvan’s terms for the supplied grade'] },
    doors: { summary: 'Branded block-board doors', promise: COMMON.doors.promise, details: [COMMON.doors.grade, 'Brand: Sylvan Primo Plus'] },
    surface: { summary: 'Laminate finish', promise: COMMON.surface.promise, details: [COMMON.surface.grade, '0.8 mm inner laminate, standard selection', `Brands: ${COMMON.surface.brands.join(', ')}`] },
    edges: { summary: 'Sealed edges', promise: COMMON.edgeOuter.promise, details: ['2 mm outer, 0.8 mm inner edge banding', `Brands: ${COMMON.edgeOuter.brands.join(', ')}`] },
    hardware: { summary: 'Hettich and Blum soft-close hardware', promise: 'Soft-close hinges, drawers and channels', details: ['Hinges: Hettich', 'Kitchen drawers: Hettich', 'Channels: Blum', 'Sliding channels: Nimmi or Hettich', 'Folding channels: Ebco or Hettich'] },
    handles: { summary: 'Standard handles', promise: COMMON.handles.promise, details: [COMMON.handles.grade] },
    accessories: { summary: 'Kitchen accessories', promise: COMMON.accessories.promise, details: [`Brands: ${COMMON.accessories.brands.join(', ')}`] },
    ceiling: { summary: 'Saint-Gobain ceiling, branded LED lights', promise: `${COMMON.ceiling.promise}; LED lights installed`, details: [COMMON.ceiling.grade, 'Panel lights: Philips; COB and spot lights: Wipro; profile lights: Crompton or Avion'] },
    optional: { summary: 'Branded wiring and paint', promise: 'If you add them: branded wiring and premium emulsion paint', details: [`Wiring: ${COMMON.wiring.brands.join(', ')}`, `Paint: ${COMMON.painting.brands.join(', ')}; one colour`] },
  }),
  'candidate-jun-2026': spec('candidate-jun-2026', 'June 2026 quotation specification (candidate)', 'CANDIDATE', {
    structure: { summary: 'Sylvan plywood structure', promise: 'Cabinet bodies in Sylvan plywood', details: ['18 mm Sylvan plywood for cabinet bodies; 9 mm back panels; 12 mm behind the TV', 'Manufacturer warranty per Sylvan’s terms for the supplied grade'] },
    doors: { summary: 'Branded block-board doors', promise: COMMON.doors.promise, details: [COMMON.doors.grade, 'Brand: Sylvan Primo Plus'] },
    surface: { summary: 'Laminate finish', promise: COMMON.surface.promise, details: [COMMON.surface.grade, '0.72 mm inner laminate in a standard colour', `Brands: ${[...COMMON.surface.brands, 'Velmica'].join(', ')}`] },
    edges: { summary: 'Sealed edges', promise: COMMON.edgeOuter.promise, details: ['2 mm outer, 1.3 mm inner edge banding', `Brands: ${COMMON.edgeOuter.brands.join(', ')}`] },
    hardware: { summary: 'Hettich soft-close hardware', promise: 'Soft-close hinges, drawers and channels', details: ['Hinges: Hettich', 'Kitchen drawers: Hettich', 'Channels: Hettich', 'Sliding channels: Nimmi or Hettich'] },
    handles: { summary: 'Standard handles', promise: COMMON.handles.promise, details: [COMMON.handles.grade] },
    accessories: { summary: 'Kitchen accessories', promise: COMMON.accessories.promise, details: [`Brands: ${COMMON.accessories.brands.join(', ')}`] },
    ceiling: { summary: 'Saint-Gobain ceiling, branded LED lights', promise: `${COMMON.ceiling.promise}; LED lights installed`, details: [COMMON.ceiling.grade, 'Panel lights: Wipro; COB lights: Philips; spot lights: Wipro; profile lights: Crompton or Avion'] },
    optional: { summary: 'Branded wiring and paint', promise: 'If you add them: branded wiring and premium emulsion paint', details: [`Wiring: ${COMMON.wiring.brands.join(', ')}`, `Paint: ${COMMON.painting.brands.join(', ')}; one colour`] },
  }),
};
