import { expect } from '@open-wc/testing';
import {
  formatAbsolute, formatDate, formatINR, formatPhone, formatRelative, instantToLocalInput, localInputToInstant, maskEmail,
} from '../src/core/format/format.js';

describe('formatting in the user timezone (PLAT-007, AX-10)', () => {
  const iso = '2026-09-29T10:02:11.004Z'; // 15:32 IST, 06:02 New York

  it('renders instants in the given IANA zone, not the device zone', () => {
    expect(formatAbsolute(iso, 'Asia/Kolkata')).to.match(/^29 Sept? 2026, 3:32 pm$/);
    expect(formatAbsolute(iso, 'America/New_York')).to.match(/^29 Sept? 2026, 6:02 am$/);
  });

  it('uses relative wording within a week, computed on calendar days of the user zone', () => {
    const now = new Date('2026-09-29T12:00:00Z'); // 17:30 IST
    expect(formatRelative('2026-09-29T10:00:00Z', now, 'Asia/Kolkata')).to.equal('2 h ago');
    expect(formatRelative('2026-09-30T05:30:00Z', now, 'Asia/Kolkata')).to.equal('Tomorrow 11:00');
    expect(formatRelative('2026-09-29T13:00:00Z', now, 'Asia/Kolkata')).to.equal('Today 18:30');
    // 20:00 UTC is already the next calendar day in IST but still "today" in New York.
    expect(formatRelative('2026-09-29T20:00:00Z', now, 'Asia/Kolkata')).to.equal('Tomorrow 01:30');
    expect(formatRelative('2026-09-29T20:00:00Z', now, 'America/New_York')).to.equal('Today 16:00');
    expect(formatRelative('2026-09-01T10:00:00Z', now, 'Asia/Kolkata')).to.match(/^1 Sept? 2026/);
  });

  it('never shifts calendar DATE values', () => {
    expect(formatDate('2026-10-20')).to.match(/^20 Oct 2026$/);
  });

  it('formats INR with Indian digit grouping', () => {
    expect(formatINR('1850000.00')).to.equal('₹18,50,000');
    expect(formatINR(125000)).to.equal('₹1,25,000');
    expect(formatINR(null)).to.equal('—');
  });

  it('formats phones and masks emails', () => {
    expect(formatPhone('+919876543210')).to.equal('+91 98765 43210');
    expect(formatPhone('+14155552671')).to.equal('+14155552671');
    expect(maskEmail('priya@vedaspaces.com')).to.equal('p***@vedaspaces.com');
  });

  it('converts datetime-local input in the user zone to an instant and back', () => {
    expect(localInputToInstant('2026-09-30T11:00', 'Asia/Kolkata')).to.equal('2026-09-30T05:30:00.000Z');
    expect(localInputToInstant('2026-09-30T11:00', 'America/New_York')).to.equal('2026-09-30T15:00:00.000Z');
    expect(instantToLocalInput('2026-09-30T05:30:00.000Z', 'Asia/Kolkata')).to.equal('2026-09-30T11:00');
  });
});
