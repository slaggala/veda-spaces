/**
 * Formatting helpers (09 §3.2, PLAT-007, AX-10). Instants are rendered in the viewing user's IANA
 * timezone (app_user.timezone), never the device zone. Currency uses Indian digit grouping.
 */
export const DEFAULT_TZ = 'Asia/Kolkata';
const LOCALE = 'en-IN';

let userTimeZone = DEFAULT_TZ;
export function setUserTimeZone(tz: string | null | undefined): void {
  userTimeZone = tz || DEFAULT_TZ;
}
export function getUserTimeZone(): string {
  return userTimeZone;
}

function parts(date: Date, tz: string): Record<string, string> {
  const fmt = new Intl.DateTimeFormat('en-GB', {
    timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  });
  const out: Record<string, string> = {};
  for (const p of fmt.formatToParts(date)) out[p.type] = p.value;
  return out;
}

/** Calendar day (YYYY-MM-DD) of an instant in a timezone. */
export function dayKey(date: Date, tz = userTimeZone): string {
  const p = parts(date, tz);
  return `${p.year}-${p.month}-${p.day}`;
}

function dayDiff(a: Date, b: Date, tz: string): number {
  const ka = Date.parse(`${dayKey(a, tz)}T00:00:00Z`);
  const kb = Date.parse(`${dayKey(b, tz)}T00:00:00Z`);
  return Math.round((ka - kb) / 86_400_000);
}

/** Absolute: `29 Sep 2026, 3:32 pm`. */
export function formatAbsolute(iso: string | null | undefined, tz = userTimeZone): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const date = new Intl.DateTimeFormat(LOCALE, { timeZone: tz, day: 'numeric', month: 'short', year: 'numeric' }).format(d);
  const time = new Intl.DateTimeFormat(LOCALE, { timeZone: tz, hour: 'numeric', minute: '2-digit', hour12: true })
    .format(d)
    .replace(/\s?(AM|PM)$/i, (m) => ` ${m.trim().toLowerCase()}`);
  return `${date}, ${time}`;
}

/** Full timestamp with zone, for hover titles and the audit viewer. */
export function formatFull(iso: string | null | undefined, tz = userTimeZone): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return new Intl.DateTimeFormat(LOCALE, {
    timeZone: tz, day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit',
    hour12: true, timeZoneName: 'short',
  }).format(d);
}

function hhmm(d: Date, tz: string): string {
  const p = parts(d, tz);
  return `${p.hour}:${p.minute}`;
}

/**
 * Relative for < 7 days ("2 h ago", "Tomorrow 11:00", "Today 15:30"), absolute otherwise (09 §3.2).
 */
export function formatRelative(iso: string | null | undefined, now: Date = new Date(), tz = userTimeZone): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const deltaMs = d.getTime() - now.getTime();
  const absMin = Math.abs(deltaMs) / 60_000;
  if (absMin >= 7 * 24 * 60) return formatAbsolute(iso, tz);
  if (deltaMs <= 0) {
    if (absMin < 1) return 'Just now';
    if (absMin < 60) return `${Math.floor(absMin)} min ago`;
    if (absMin < 24 * 60) return `${Math.floor(absMin / 60)} h ago`;
    const days = -dayDiff(d, now, tz);
    return days === 1 ? `Yesterday ${hhmm(d, tz)}` : `${days} d ago`;
  }
  const days = dayDiff(d, now, tz);
  if (days === 0) return `Today ${hhmm(d, tz)}`;
  if (days === 1) return `Tomorrow ${hhmm(d, tz)}`;
  const weekday = new Intl.DateTimeFormat(LOCALE, { timeZone: tz, weekday: 'short' }).format(d);
  return `${weekday} ${hhmm(d, tz)}`;
}

/** Short age for tables: 2h, 4d, 3w. */
export function formatAge(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return '—';
  const min = Math.max(0, (now.getTime() - new Date(iso).getTime()) / 60_000);
  if (min < 60) return `${Math.floor(min)}m`;
  if (min < 1440) return `${Math.floor(min / 60)}h`;
  if (min < 1440 * 14) return `${Math.floor(min / 1440)}d`;
  return `${Math.floor(min / 10080)}w`;
}

/** `YYYY-MM-DD` calendar dates are never timezone-shifted. */
export function formatDate(date: string | null | undefined): string {
  if (!date) return '—';
  const [y, m, d] = date.split('-').map(Number);
  if (!y || !m || !d) return date;
  return new Intl.DateTimeFormat(LOCALE, { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' }).format(
    new Date(Date.UTC(y, m - 1, d)),
  );
}

/** ₹18,50,000 — accepts a decimal string or number (08 §2.2 money is a decimal string). */
export function formatINR(amount: string | number | null | undefined): string {
  if (amount === null || amount === undefined || amount === '') return '—';
  const n = typeof amount === 'number' ? amount : Number(amount);
  if (!Number.isFinite(n)) return '—';
  return new Intl.NumberFormat(LOCALE, { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);
}

/** +91 98765 43210 for Indian numbers; other E.164 numbers are returned unchanged. */
export function formatPhone(e164: string | null | undefined): string {
  if (!e164) return '—';
  const m = /^\+91(\d{5})(\d{5})$/.exec(e164);
  return m ? `+91 ${m[1]} ${m[2]}` : e164;
}

export function whatsappUrl(e164: string, text?: string): string {
  const digits = e164.replace(/\D/g, '');
  return `https://wa.me/${digits}${text ? `?text=${encodeURIComponent(text)}` : ''}`;
}

/** Convert an <input type="datetime-local"> value in the user's zone into an RFC 3339 instant with offset. */
export function localInputToInstant(value: string, tz = userTimeZone): string {
  const [datePart, timePart = '00:00'] = value.split('T');
  const [y, mo, d] = datePart.split('-').map(Number);
  const [h, mi] = timePart.split(':').map(Number);
  const guess = Date.UTC(y, mo - 1, d, h, mi);
  const p = parts(new Date(guess), tz);
  const asIfUtc = Date.UTC(Number(p.year), Number(p.month) - 1, Number(p.day), Number(p.hour), Number(p.minute));
  const offset = asIfUtc - guess;
  return new Date(guess - offset).toISOString();
}

/** Instant → value for <input type="datetime-local"> in the user's zone. */
export function instantToLocalInput(iso: string | null | undefined, tz = userTimeZone): string {
  if (!iso) return '';
  const p = parts(new Date(iso), tz);
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

export function maskEmail(email: string): string {
  const [local, domain] = email.split('@');
  if (!domain) return email;
  return `${local.slice(0, 1)}***@${domain}`;
}

export function initials(name: string | null | undefined): string {
  if (!name) return '?';
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join('');
}

export function humanize(code: string | null | undefined): string {
  if (!code) return '—';
  const s = code.toLowerCase().replace(/_/g, ' ');
  return s.charAt(0).toUpperCase() + s.slice(1);
}
