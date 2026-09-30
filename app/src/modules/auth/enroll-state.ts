/** Invite-flow enrollment context (05 §11.3 path B), held in memory between accept and enroll. */
let inviteContext: string | null = null;
export function setInviteContext(value: string | null): void {
  inviteContext = value;
}
export function takeInviteContext(): string | null {
  return inviteContext;
}
