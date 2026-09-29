/** Client-side password hints mirroring the server policy (05 §2.3). The server stays authoritative. */
const COMMON = new Set([
  'password1234', 'password12345', '123456789012', 'qwertyuiop12', 'iloveyou1234', 'welcome12345', 'letmein12345',
  'administrator', 'passwordpassword', '111111111111', '000000000000', 'abcdefghijkl', 'qwertyqwerty', 'changeme1234',
]);

export interface PolicyCheck { id: string; label: string; ok: boolean }

export function passwordChecks(password: string, personal: string[] = []): PolicyCheck[] {
  const normalized = password.normalize('NFKC');
  const lower = normalized.toLowerCase();
  const tokens = ['veda', 'vedaspaces', ...personal.flatMap((p) => p.toLowerCase().split(/[\s@._-]+/))].filter((t) => t.length >= 3);
  return [
    { id: 'TOO_SHORT', label: '12+ characters', ok: normalized.length >= 12 && normalized.length <= 128 },
    { id: 'TOO_COMMON', label: 'Not a common password', ok: normalized.length > 0 && !COMMON.has(lower) && !/^(.)\1+$/.test(lower) },
    { id: 'CONTAINS_PERSONAL_INFO', label: "Doesn't contain your name or email", ok: normalized.length > 0 && !tokens.some((t) => lower.includes(t)) },
  ];
}

export function strength(password: string): { score: number; label: string } {
  let score = 0;
  if (password.length >= 12) score += 1;
  if (password.length >= 16) score += 1;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score += 1;
  if (/\d/.test(password) || /[^\w\s]/.test(password)) score += 1;
  return { score, label: ['Too short', 'Weak', 'Fair', 'Good', 'Strong'][score] };
}

export const POLICY_MESSAGES: Record<string, string> = {
  TOO_SHORT: 'Use at least 12 characters.',
  TOO_LONG: 'Use at most 128 characters.',
  TOO_COMMON: 'That password is too common.',
  CONTAINS_PERSONAL_INFO: "Don't include your name or email.",
  PASSWORD_REUSED: "You can't reuse your current password.",
};
