import type { ElectricalPoint, Opening, SpaceMeasurement, Wall } from './api.js';
import { newRef } from './offline-queue.js';
import { formatLength, parseLength, type UnitSystem } from './units.js';

/**
 * The capture page's editable model. Lengths stay as the surveyor typed them (feet-inches or millimetres) until the
 * room is saved; `toPayload` converts every one to integer millimetres and reports what could not be read, so
 * nothing ambiguous is ever queued.
 */
export interface ObstructionDraft { kind: string; offset: string; width: string; heightFromFloor: string }
export interface OpeningDraft {
  client_ref: string; type: string; width: string; height: string; sill: string; offset: string; swing: string;
  purpose: string; depth: string; deducts: boolean; existing: boolean;
}
export interface WallDraft {
  wall_index: number; length: string; height: string; type: string; external: boolean; proposed: boolean;
  tags: string[]; obstructions: ObstructionDraft[]; openings: OpeningDraft[];
}
export interface PointDraft {
  client_ref: string; type: string; status: string; wall_index: string; from_offset: string; from_height: string;
  to_wall_index: string; to_offset: string; to_height: string; sensor: string; switching: string; location: string; quantity: string;
}
export interface RoomDraft {
  space_id: string; client_ref: string; base_version: number | null; shape: string;
  length: string; width: string; ceiling: string; beam: string; lintel: string; stated_area: string;
  flooring: string; condition: string; confidence: string; complete: boolean;
  attrs: Record<string, string>; legs: { turn: string; la: string; wa: string; lb: string; wb: string };
  stair: Record<string, string>; walls: WallDraft[]; points: PointDraft[];
}

export const STAIR_FIELDS = ['from_level', 'to_level', 'turn_type_code', 'flight_count', 'run_length_mm', 'width_mm', 'riser_count',
  'riser_height_mm', 'tread_depth_mm', 'headroom_mm', 'landing_l_mm', 'landing_w_mm', 'largest_panel_mm', 'handrail_wall_index'] as const;
const STAIR_LENGTHS = new Set(['run_length_mm', 'width_mm', 'riser_height_mm', 'tread_depth_mm', 'headroom_mm', 'landing_l_mm', 'landing_w_mm', 'largest_panel_mm']);
const STAIR_CODES = new Set(['turn_type_code']);
export const ATTRIBUTE_FIELDS = ['ac_type', 'ac_point_count', 'fan_point_count', 'has_gas_line', 'has_water_inlet', 'has_drain',
  'counter_existing', 'railing_height_mm', 'exposure_code'] as const;
const BOOL_ATTRS = new Set(['has_gas_line', 'has_water_inlet', 'has_drain', 'counter_existing']);
const INT_ATTRS = new Set(['ac_point_count', 'fan_point_count']);
const LEN_ATTRS = new Set(['railing_height_mm']);

const L = (mm: number | null | undefined, u: UnitSystem) => formatLength(mm ?? null, u);

export function emptyRoom(spaceId: string): RoomDraft {
  return {
    space_id: spaceId, client_ref: newRef('sm'), base_version: null, shape: 'RECTANGULAR', length: '', width: '', ceiling: '',
    beam: '', lintel: '', stated_area: '', flooring: '', condition: '', confidence: 'HIGH', complete: false, attrs: {},
    legs: { turn: 'RIGHT', la: '', wa: '', lb: '', wb: '' }, stair: {},
    walls: [1, 2, 3, 4].map((i) => emptyWall(i)), points: [],
  };
}

export function emptyWall(index: number): WallDraft {
  return { wall_index: index, length: '', height: '', type: index === 0 ? 'OPEN' : 'MASONRY', external: false, proposed: false, tags: [], obstructions: [], openings: [] };
}

export function emptyOpening(): OpeningDraft {
  return { client_ref: newRef('op'), type: 'DOOR', width: '', height: '', sill: '', offset: '', swing: '', purpose: '', depth: '', deducts: true, existing: true };
}

export function emptyPoint(): PointDraft {
  return { client_ref: newRef('ep'), type: 'SOCKET_5A', status: 'EXISTING', wall_index: '', from_offset: '', from_height: '', to_wall_index: '',
    to_offset: '', to_height: '', sensor: '', switching: '', location: '', quantity: '1' };
}

export function fromMeasurement(sm: SpaceMeasurement, u: UnitSystem): RoomDraft {
  const a = (sm.attributes ?? {}) as Record<string, unknown>;
  const legs = (a.l_shape ?? null) as { turn_code: string; leg_a: { l_mm: number; w_mm: number }; leg_b: { l_mm: number; w_mm: number } } | null;
  const stair = (a.staircase ?? {}) as Record<string, unknown>;
  const attrs: Record<string, string> = {};
  for (const k of ATTRIBUTE_FIELDS) {
    const v = a[k];
    if (v === undefined || v === null) continue;
    attrs[k] = LEN_ATTRS.has(k) ? L(v as number, u) : String(v);
  }
  return {
    space_id: sm.space_id, client_ref: sm.client_ref ?? newRef('sm'), base_version: sm.version, shape: sm.shape_code,
    length: L(sm.length_mm, u), width: L(sm.width_mm, u), ceiling: L(sm.ceiling_height_mm, u), beam: L(sm.beam_bottom_height_mm, u),
    lintel: L(sm.floor_to_lintel_mm, u), stated_area: sm.stated_floor_area_sqft_centi ? String(sm.stated_floor_area_sqft_centi / 100) : '',
    flooring: sm.flooring_code ?? '', condition: sm.existing_condition_code ?? '', confidence: sm.confidence_code, complete: sm.is_complete,
    attrs,
    legs: legs ? { turn: legs.turn_code, la: L(legs.leg_a.l_mm, u), wa: L(legs.leg_a.w_mm, u), lb: L(legs.leg_b.l_mm, u), wb: L(legs.leg_b.w_mm, u) }
      : { turn: 'RIGHT', la: '', wa: '', lb: '', wb: '' },
    stair: Object.fromEntries(Object.entries(stair).map(([k, v]) => [k, STAIR_LENGTHS.has(k) ? L(v as number, u) : String(v)])),
    walls: sm.walls.map((w) => wallDraft(w, u)),
    points: (sm.electrical_points ?? []).map((p) => pointDraft(p, u)),
  };
}

function wallDraft(w: Wall, u: UnitSystem): WallDraft {
  return {
    wall_index: w.wall_index, length: L(w.length_mm, u), height: L(w.height_mm, u), type: w.wall_type_code, external: !!w.is_external,
    proposed: !!w.is_proposed, tags: [...w.usable_for_code],
    obstructions: w.obstructions.map((o) => ({ kind: o.kind, offset: L(o.offset_mm, u), width: L(o.width_mm, u), heightFromFloor: L(o.height_from_floor_mm, u) })),
    openings: w.openings.map((o: Opening) => ({
      client_ref: o.client_ref, type: o.opening_type_code, width: L(o.width_mm, u), height: L(o.height_mm, u), sill: L(o.sill_height_mm, u),
      offset: L(o.offset_from_wall_start_mm, u), swing: o.swing_code ?? '', purpose: o.purpose_code ?? '', depth: L(o.depth_mm, u),
      deducts: o.deducts_from_wall_area ?? true, existing: o.is_existing ?? true,
    })),
  };
}

function pointDraft(p: ElectricalPoint, u: UnitSystem): PointDraft {
  const s = (v: unknown) => (v === null || v === undefined ? '' : String(v));
  return {
    client_ref: p.client_ref, type: p.point_type_code, status: p.status_code, wall_index: s(p.wall_index), from_offset: L(p.from_offset_mm, u),
    from_height: L(p.from_height_mm, u), to_wall_index: s(p.to_wall_index), to_offset: L(p.to_offset_mm, u), to_height: L(p.to_height_mm, u),
    sensor: s(p.sensor_type_code), switching: s(p.switching_code), location: s(p.location_code), quantity: s(p.quantity ?? 1),
  };
}

export interface PayloadResult { payload: Record<string, unknown> | null; errors: string[] }

/** Build the closed capture payload; any length that cannot be read is reported and nothing is produced. */
export function toPayload(d: RoomDraft, u: UnitSystem, spaceType: string): PayloadResult {
  const errors: string[] = [];
  const len = (raw: string, what: string, required = false): number | undefined => {
    if (!raw.trim()) {
      if (required) errors.push(`${what} is required`);
      return undefined;
    }
    const mm = parseLength(raw, u);
    if (mm === null || mm <= 0) { errors.push(`${what}: "${raw}" is not a length`); return undefined; }
    return mm;
  };
  const offset = (raw: string, what: string): number | undefined => {
    if (!raw.trim()) return undefined;
    const mm = parseLength(raw, u);
    if (mm === null || mm < 0) { errors.push(`${what}: "${raw}" is not a length`); return undefined; }
    return mm;
  };
  const int = (raw: string, what: string): number | undefined => {
    if (!raw.trim()) return undefined;
    const n = Number(raw);
    if (!Number.isInteger(n)) { errors.push(`${what}: "${raw}" is not a whole number`); return undefined; }
    return n;
  };
  const attributes: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(d.attrs)) {
    if (v === '') continue;
    if (BOOL_ATTRS.has(k)) attributes[k] = v === 'true';
    else if (INT_ATTRS.has(k)) attributes[k] = int(v, k.replace(/_/g, ' '));
    else if (LEN_ATTRS.has(k)) attributes[k] = len(v, k.replace(/_/g, ' '));
    else attributes[k] = v;
  }
  if (d.shape === 'L_SHAPE' && [d.legs.la, d.legs.wa, d.legs.lb, d.legs.wb].some((x) => x.trim())) {
    attributes.l_shape = {
      turn_code: d.legs.turn,
      leg_a: { l_mm: len(d.legs.la, 'leg A length', true), w_mm: len(d.legs.wa, 'leg A width', true) },
      leg_b: { l_mm: len(d.legs.lb, 'leg B length', true), w_mm: len(d.legs.wb, 'leg B depth', true) },
    };
  }
  if (spaceType === 'STAIRCASE' && Object.values(d.stair).some((x) => x && x.trim())) {
    const st: Record<string, unknown> = {};
    for (const k of STAIR_FIELDS) {
      const raw = d.stair[k] ?? '';
      if (!raw.trim()) continue;
      st[k] = STAIR_LENGTHS.has(k) ? len(raw, k.replace(/_mm$/, '').replace(/_/g, ' ')) : STAIR_CODES.has(k) ? raw : int(raw, k.replace(/_/g, ' '));
    }
    attributes.staircase = st;
  }
  const walls = d.walls.map((w) => ({
    wall_index: w.wall_index,
    length_mm: len(w.length, `W${w.wall_index} length`, true),
    height_mm: len(w.height, `W${w.wall_index} height`),
    wall_type_code: w.type,
    is_external: w.external,
    is_proposed: w.proposed,
    usable_for_code: w.tags,
    obstructions: w.obstructions.map((o) => ({
      kind: o.kind, offset_mm: offset(o.offset, `W${w.wall_index} obstruction offset`), width_mm: len(o.width, 'obstruction width'),
      height_from_floor_mm: offset(o.heightFromFloor, 'obstruction height from floor'),
    })),
    openings: w.openings.map((o) => ({
      client_ref: o.client_ref, opening_type_code: o.type, width_mm: len(o.width, `W${w.wall_index} opening width`, true),
      height_mm: len(o.height, `W${w.wall_index} opening height`, true), sill_height_mm: offset(o.sill, 'sill height'),
      offset_from_wall_start_mm: offset(o.offset, 'opening offset'), swing_code: o.swing || undefined,
      purpose_code: o.purpose || undefined, depth_mm: len(o.depth, 'niche depth'), deducts_from_wall_area: o.deducts, is_existing: o.existing,
    })),
  }));
  const points = d.points.map((p) => ({
    client_ref: p.client_ref, point_type_code: p.type, status_code: p.status,
    wall_index: p.wall_index === '' ? undefined : Number(p.wall_index),
    from_offset_mm: offset(p.from_offset, 'point position'), from_height_mm: offset(p.from_height, 'point height'),
    to_wall_index: p.to_wall_index === '' ? undefined : Number(p.to_wall_index),
    to_offset_mm: offset(p.to_offset, 'new position'), to_height_mm: offset(p.to_height, 'new height'),
    sensor_type_code: p.sensor || undefined, switching_code: p.switching || undefined, location_code: p.location || undefined,
    quantity: int(p.quantity || '1', 'quantity') ?? 1,
  }));
  const payload: Record<string, unknown> = {
    client_ref: d.client_ref, shape_code: d.shape,
    length_mm: len(d.length, 'length'), width_mm: len(d.width, 'width'), ceiling_height_mm: len(d.ceiling, 'ceiling height'),
    beam_bottom_height_mm: len(d.beam, 'beam bottom'), floor_to_lintel_mm: len(d.lintel, 'floor to lintel'),
    flooring_code: d.flooring || undefined, existing_condition_code: d.condition || undefined, confidence_code: d.confidence,
    is_complete: d.complete, attributes, walls, electrical_points: points,
  };
  if (d.shape === 'FREEFORM') {
    const area = Number(d.stated_area);
    if (!d.stated_area || !Number.isFinite(area) || area <= 0) errors.push('stated area (sq ft) is required for a freeform space');
    else payload.stated_floor_area_sqft_centi = Math.round(area * 100);
    payload.confidence_code = 'LOW';
  }
  if (d.base_version !== null) payload.base_version = d.base_version;
  return { payload: errors.length ? null : JSON.parse(JSON.stringify(payload)), errors };
}
