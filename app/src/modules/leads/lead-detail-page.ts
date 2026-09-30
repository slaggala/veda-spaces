import { css, html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { AuditEntry, CursorMeta, Lead, LeadActivity, LeadNote, LeadStatus, UserRef } from '../../core/api/types.js';
import { canOnRow } from '../../core/authz/permissions.js';
import { formatAbsolute, formatDate, formatFull, formatPhone, formatRelative, humanize, whatsappUrl } from '../../core/format/format.js';
import { statusLabel } from '../../core/i18n/strings.js';
import { navigate } from '../../core/router/next.js';
import { toast } from '../../design-system/components.js';
import { icon } from '../../design-system/icons.js';
import { pageStyles, shared } from '../../design-system/styles.js';
import { activityTypeLabel } from './activity-dialog.js';
import './activity-dialog.js';
import type { ActivityMode } from './activity-dialog.js';
import { loadAssignees } from './assignees.js';
import { LookupAwareElement } from './base.js';
import './lead-form.js';
import './status-dialog.js';
import { primaryTransition } from './transitions.js';

type Dialog = '' | 'delete' | 'consent' | 'erase' | 'duplicate' | 'note-delete' | 'assign';

/** Lead details (09 §4.4, UI-004). All actions honour allowed_transitions and permission scope. */
export class VsLeadDetailPage extends LookupAwareElement {
  static override properties = {
    location: { attribute: false }, lead: { state: true }, problem: { state: true }, actionProblem: { state: true }, loading: { state: true },
    tab: { state: true }, activities: { state: true }, notes: { state: true }, history: { state: true }, historyCursor: { state: true },
    assignees: { state: true }, statusTo: { state: true }, editOpen: { state: true }, activityMode: { state: true }, activityTarget: { state: true },
    activityPreset: { state: true }, activityOpen: { state: true }, dialog: { state: true }, noteEditing: { state: true }, noteTarget: { state: true }, busy: { state: true },
  };
  declare location: { params: Record<string, string> } | undefined;
  declare lead: Lead | null;
  declare problem: ApiProblem | null;
  declare actionProblem: ApiProblem | null;
  declare loading: boolean;
  declare tab: 'timeline' | 'notes' | 'history';
  declare activities: LeadActivity[] | null;
  declare notes: LeadNote[] | null;
  declare history: AuditEntry[] | null;
  declare historyCursor: string | null;
  declare assignees: UserRef[];
  declare statusTo: LeadStatus | '';
  declare editOpen: boolean;
  declare activityMode: ActivityMode;
  declare activityTarget: LeadActivity | null;
  declare activityPreset: { activity_type?: string; direction?: string } | null;
  declare activityOpen: boolean;
  declare dialog: Dialog;
  declare noteEditing: string;
  declare noteTarget: LeadNote | null;
  declare busy: boolean;
  private pendingQuickLog: string | null = null;
  private onVisible = () => {
    if (document.visibilityState === 'visible' && this.pendingQuickLog) {
      this.openActivity('log', null, { activity_type: this.pendingQuickLog, direction: 'OUTBOUND' });
      this.pendingQuickLog = null;
    }
  };

  static override styles = [
    ...shared, pageStyles,
    css`
      .head { display: flex; flex-direction: column; gap: 12px; }
      .contact { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; }
      .grid { display: grid; grid-template-columns: 300px 1fr 280px; gap: 16px; align-items: start; }
      dl { display: grid; grid-template-columns: 90px 1fr; gap: 6px 12px; margin: 0; }
      dt { color: var(--vs-ink-muted); font-size: 12px; }
      dd { margin: 0; }
      .empty-field { color: var(--vs-copper-text); background: none; border: 0; padding: 0; cursor: pointer; font: inherit; text-decoration: underline; }
      .timeline { list-style: none; margin: 0; padding: 0; }
      .timeline li { padding: 12px 0; border-bottom: 1px solid var(--vs-line); display: flex; flex-direction: column; gap: 4px; }
      .timeline .meta { font-size: 12px; color: var(--vs-ink-muted); }
      .timeline .planned { border-left: 3px solid var(--vs-copper); padding-left: 10px; }
      .timeline .cancelled { opacity: .7; text-decoration: line-through; }
      .overdue { color: var(--vs-warning); font-weight: 600; }
      .note { padding: 12px; border: 1px solid var(--vs-line); border-radius: 8px; background: var(--vs-surface); display: flex; flex-direction: column; gap: 6px; white-space: pre-wrap; }
      .note.pinned { border-color: var(--vs-copper); }
      .quick { display: flex; flex-wrap: wrap; gap: 8px; }
      .actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
      .message { white-space: pre-wrap; font-style: italic; }
      .chip.wrap { white-space: normal; }
      details.more { position: relative; }
      details.more summary { list-style: none; cursor: pointer; }
      details.more summary::-webkit-details-marker { display: none; }
      details.more .menu { position: absolute; right: 0; top: 48px; background: var(--vs-surface); border: 1px solid var(--vs-line); border-radius: 8px; box-shadow: var(--vs-shadow); padding: 6px; z-index: 20; min-width: 240px; display: flex; flex-direction: column; }
      details.more .menu button { text-align: left; background: none; border: 0; min-height: 44px; padding: 0 12px; font: inherit; color: var(--vs-ink); cursor: pointer; }
      .mobile-bar { display: none; }
      @media (max-width: 1199px) { .grid { grid-template-columns: 1fr 1fr; } .side { grid-column: 1 / -1; } }
      @media (max-width: 767px) {
        .grid { grid-template-columns: 1fr; }
        .next-up { order: -1; }
        .mobile-bar { display: flex; position: fixed; left: 0; right: 0; bottom: 56px; gap: 8px; padding: 8px 12px; background: var(--vs-surface); border-top: 1px solid var(--vs-line); z-index: 25; }
        .mobile-bar .btn { flex: 1; }
      }
    `,
  ];

  constructor() {
    super();
    this.lead = null;
    this.problem = null;
    this.actionProblem = null;
    this.loading = true;
    this.tab = 'timeline';
    this.activities = null;
    this.notes = null;
    this.history = null;
    this.historyCursor = null;
    this.assignees = [];
    this.statusTo = '';
    this.editOpen = false;
    this.activityMode = 'log';
    this.activityTarget = null;
    this.activityPreset = null;
    this.activityOpen = false;
    this.dialog = '';
    this.noteEditing = '';
    this.noteTarget = null;
    this.busy = false;
  }

  private get leadId(): string {
    return this.location?.params?.id ?? window.location.pathname.split('/').pop() ?? '';
  }

  override connectedCallback() {
    super.connectedCallback();
    document.addEventListener('visibilitychange', this.onVisible);
    void this.load();
    void loadAssignees(this.me).then((a) => (this.assignees = a));
  }
  override disconnectedCallback() {
    document.removeEventListener('visibilitychange', this.onVisible);
    super.disconnectedCallback();
  }

  private async load() {
    this.loading = true;
    try {
      const r = await api.get<Lead>(`/api/v1/leads/${this.leadId}`, this.can('lead.restore') ? { include_deleted: 'true' } : undefined);
      this.lead = r.data;
      this.problem = null;
      void this.loadActivities();
      if (this.can('lead_note.read')) void this.loadNotes();
    } catch (e) {
      this.problem = e as ApiProblem;
    } finally {
      this.loading = false;
    }
  }

  private async loadActivities() {
    if (!this.can('lead_activity.read')) return;
    try {
      this.activities = (await api.get<LeadActivity[]>(`/api/v1/leads/${this.leadId}/activities`, { limit: 100 })).data;
    } catch {
      this.activities = [];
    }
  }
  private async loadNotes() {
    try {
      this.notes = (await api.get<LeadNote[]>(`/api/v1/leads/${this.leadId}/notes`, { page_size: 100 })).data;
    } catch {
      this.notes = [];
    }
  }
  private async loadHistory(more = false) {
    try {
      const r = await api.get<AuditEntry[]>(`/api/v1/leads/${this.leadId}/history`, { cursor: more ? this.historyCursor ?? undefined : undefined, limit: 50 });
      this.history = more ? [...(this.history ?? []), ...r.data] : r.data;
      const m = r.meta as unknown as CursorMeta;
      this.historyCursor = m.has_more ? m.next_cursor : null;
    } catch (e) {
      this.actionProblem = e as ApiProblem;
    }
  }

  private updated_(lead: Lead) {
    this.lead = lead;
    void this.loadActivities();
  }

  private async act(fn: () => Promise<unknown>, success?: string) {
    this.busy = true;
    this.actionProblem = null;
    try {
      await fn();
      if (success) toast(success, 'success');
      this.dialog = '';
      await this.load();
    } catch (e) {
      const p = e as ApiProblem;
      this.actionProblem = p;
      if (p.code === 'VERSION_CONFLICT') {
        toast('This lead changed meanwhile. Reloaded the latest version.', 'error');
        await this.load();
      }
    } finally {
      this.busy = false;
    }
  }

  private openActivity(mode: ActivityMode, target: LeadActivity | null, preset: { activity_type?: string; direction?: string } | null = null) {
    this.activityMode = mode;
    this.activityTarget = target;
    this.activityPreset = preset;
    this.activityOpen = true;
  }

  private contact(kind: 'CALL' | 'WHATSAPP') {
    const lead = this.lead!;
    if (lead.consent?.withdrawn_on && !confirm('This person asked not to be contacted. Continue anyway?')) return;
    this.pendingQuickLog = kind;
    if (kind === 'CALL') window.location.href = `tel:${lead.phone}`;
    else window.open(whatsappUrl(lead.phone), '_blank', 'noopener');
  }

  private field(label: string, value: unknown, empty?: string) {
    const shown = value === null || value === undefined || value === '' ? null : value;
    return html`<dt>${label}</dt><dd>${shown ?? (empty && this.canUpdate ? html`<button class="empty-field" @click=${() => (this.editOpen = true)}>${empty}</button>` : '—')}</dd>`;
  }

  private get canUpdate(): boolean {
    return canOnRow(this.perms, 'lead.update', this.me?.id, this.lead);
  }

  private renderHeader(lead: Lead) {
    const primary = primaryTransition(lead.status, lead.allowed_transitions ?? []);
    const others = (lead.allowed_transitions ?? []).filter((s) => s !== primary && s !== 'LOST');
    const canLose = (lead.allowed_transitions ?? []).includes('LOST');
    const canAssign = canOnRow(this.perms, 'lead.assign', this.me?.id, lead);
    return html`<div class="head">
      <div class="row"><a href="/leads">${icon('arrowLeft')} Leads</a><span class="mono">${lead.lead_number}</span><span class="spacer"></span>
        <details class="more"><summary class="btn icon-btn" aria-label="More actions">${icon('more')}</summary><div class="menu" role="menu">
          <button role="menuitem" @click=${() => navigator.clipboard?.writeText(window.location.href).then(() => toast('Link copied'))}>Copy link</button>
          ${this.canUpdate && lead.consent?.contact && !lead.consent.withdrawn_on ? html`<button role="menuitem" @click=${() => (this.dialog = 'consent')}>Record consent withdrawal…</button>` : nothing}
          ${canOnRow(this.perms, 'lead.delete', this.me?.id, lead) && !lead.is_deleted ? html`<button role="menuitem" class="danger-text" @click=${() => (this.dialog = 'delete')}>Delete lead…</button>` : nothing}
          ${this.can('lead.erase') && !lead.anonymized_on ? html`<button role="menuitem" class="danger-text" @click=${() => (this.dialog = 'erase')}>Erase personal data…</button>` : nothing}
        </div></details></div>
      ${lead.is_deleted ? html`<vs-banner kind="danger">This lead is deleted. ${this.can('lead.restore') ? html`<button class="btn small" @click=${() => this.act(() => api.post(`/api/v1/leads/${lead.id}/restore`, {}, { ifMatch: lead.version }), 'Lead restored')}>Restore</button>` : nothing}</vs-banner>` : nothing}
      ${lead.consent?.withdrawn_on ? html`<vs-banner kind="danger"><strong>Do not contact.</strong> Consent withdrawn ${formatAbsolute(lead.consent.withdrawn_on)} (${humanize(lead.consent.withdrawal_channel)}).</vs-banner>` : nothing}
      ${lead.spam_status === 'SUSPECTED' ? html`<vs-banner kind="warning">This enquiry is in the spam review queue.
        ${this.canUpdate ? html`<span class="row"><button class="btn small" @click=${() => this.act(() => api.post(`/api/v1/leads/${lead.id}/spam-resolution`, { resolution: 'NOT_SPAM' }, { ifMatch: lead.version }), 'Released to the pipeline')}>Not spam</button>
          <button class="btn small danger" @click=${() => this.act(() => api.post(`/api/v1/leads/${lead.id}/spam-resolution`, { resolution: 'CONFIRMED_SPAM' }, { ifMatch: lead.version }), 'Marked as spam')}>Confirm spam</button></span>` : nothing}</vs-banner>` : nothing}
      ${lead.erasure ? html`<vs-banner kind="info">Personal data erased. Audit history anonymization: ${humanize(lead.erasure.audit_status)}.</vs-banner>` : nothing}
      <div class="row"><h1 class="title">${lead.name}</h1><span class="spacer"></span>
        <span class="chip ${lead.priority === 'HIGH' ? 'warning' : ''}">${humanize(lead.priority)}</span>
        ${canAssign ? html`<label class="row small">Owner <select aria-label="Owner" @change=${(e: Event) => this.assign((e.target as HTMLSelectElement).value)}>
            <option value="" ?selected=${!lead.assigned_to}>Unassigned</option>
            ${lead.assigned_to && !this.assignees.some((a) => a.id === lead.assigned_to!.id) ? html`<option value=${lead.assigned_to.id} selected>${lead.assigned_to.display_name}</option>` : nothing}
            ${this.assignees.map((u) => html`<option value=${u.id} ?selected=${u.id === lead.assigned_to?.id}>${u.display_name}</option>`)}</select></label>`
          : html`<span class="small">Owner: <strong>${lead.assigned_to?.display_name ?? 'Unassigned'}</strong></span>`}
      </div>
      <div class="contact">
        <span>${formatPhone(lead.phone)}</span>
        <a class="btn small icon-btn" href=${`tel:${lead.phone}`} @click=${(e: Event) => { e.preventDefault(); this.contact('CALL'); }} aria-label="Call">${icon('phone')}</a>
        <a class="btn small icon-btn" href=${whatsappUrl(lead.phone)} @click=${(e: Event) => { e.preventDefault(); this.contact('WHATSAPP'); }} aria-label="WhatsApp">${icon('message')}</a>
        ${lead.email ? html`<a href=${`mailto:${lead.email}`}>${lead.email}</a>` : nothing}
        <span class="muted">${[lead.locality, lead.city].filter(Boolean).join(', ')}</span>
      </div>
      <vs-status-stepper status=${lead.status}></vs-status-stepper>
      <div class="actions">
        ${primary ? html`<button class="btn primary" @click=${() => (this.statusTo = primary)}>Move to ${statusLabel(primary)} →</button>` : nothing}
        ${others.map((s) => html`<button class="btn" @click=${() => (this.statusTo = s)}>${lead.status === 'WON' || lead.status === 'LOST' ? `Reopen as ${statusLabel(s)}` : statusLabel(s)}</button>`)}
        ${canLose ? html`<button class="btn" @click=${() => (this.statusTo = 'LOST')}>Mark as Lost</button>` : nothing}
      </div>
      <vs-problem-banner .problem=${this.actionProblem}></vs-problem-banner>
    </div>`;
  }

  private async assign(userId: string) {
    const lead = this.lead!;
    if ((lead.assigned_to?.id ?? '') === userId) return;
    await this.act(() => api.post(`/api/v1/leads/${lead.id}/assign`, { assigned_to: userId || null }, { ifMatch: lead.version }), userId ? 'Lead assigned' : 'Lead unassigned');
  }

  private renderDetails(lead: Lead) {
    const attr = lead.attribution;
    const pinned = this.notes?.find((n) => n.is_pinned);
    return html`<section class="card stack" aria-labelledby="det-h">
      <div class="row"><h2 id="det-h" class="eyebrow">Details</h2><span class="spacer"></span>${this.canUpdate ? html`<button class="btn small" @click=${() => (this.editOpen = true)}>Edit</button>` : nothing}</div>
      <dl>
        ${this.field('Project', lead.project_type?.label, 'Add project type')}
        ${this.field('Property', lead.property_type?.label, 'Add property type')}
        ${this.field('Budget', lead.budget_range?.label, 'Add budget')}
        ${this.field('City', lead.city, 'Add city')}
        ${this.field('Locality', lead.locality, 'Add locality')}
        ${this.field('Close by', lead.expected_close_on ? formatDate(lead.expected_close_on) : null)}
        ${this.field('Source', [lead.source?.label, lead.source_detail, attr?.utm_source, attr?.utm_campaign].filter(Boolean).join(' · '))}
        ${this.field('Created', html`<span title=${formatFull(lead.created_on)}>${formatAbsolute(lead.created_on)}</span> by ${lead.created_by?.display_name ?? '—'}`)}
        ${this.field('Consent', lead.consent?.contact ? `✓ ${formatDate(lead.consent.captured_on?.slice(0, 10))} (${lead.consent.policy_version ?? ''})` : lead.consent?.withdrawn_on ? 'Withdrawn' : 'Not recorded')}
        ${lead.status === 'LOST' ? this.field('Lost reason', [lead.lost_reason?.label, lead.lost_reason_note].filter(Boolean).join(' — ')) : nothing}
        ${lead.status === 'WON' ? this.field('Won on', formatAbsolute(lead.won_on)) : nothing}
      </dl>
      ${lead.intake_unmapped && Object.keys(lead.intake_unmapped).length
        ? html`${Object.entries(lead.intake_unmapped).map(([k, v]) => html`<span class="chip wrap">Website sent an unrecognized ${k.replace(/_code$/, '').replace(/_/g, ' ')}: '${v}'</span>`)}
          ${this.canUpdate ? html`<button class="btn small" @click=${() => (this.editOpen = true)}>Fix</button>` : nothing}` : nothing}
      ${pinned ? html`<div><p class="eyebrow">Pinned note</p><p>${pinned.body}</p></div>` : nothing}
    </section>`;
  }

  private renderTimeline(lead: Lead) {
    const canCreate = this.can('lead_activity.create') && !lead.is_deleted;
    const closed = lead.status === 'WON' || lead.status === 'LOST';
    return html`<div class="stack">
      ${canCreate ? html`<div class="card quick"><span class="small muted">Log:</span>
        ${['CALL', 'WHATSAPP', 'MEETING', 'SITE_VISIT'].map((t) => html`<button class="btn small" @click=${() => this.openActivity('log', null, { activity_type: t })}>${activityTypeLabel(t)}</button>`)}
        ${closed ? nothing : html`<button class="btn small primary" @click=${() => this.openActivity('plan', null, { activity_type: 'FOLLOW_UP' })}>Plan follow-up</button>`}</div>` : nothing}
      ${!this.activities ? html`<vs-skeleton rows="5"></vs-skeleton>` : this.activities.length ? html`<ul class="timeline">${this.activities.map((a) => {
        const editable = !a.is_system_generated && a.can_edit;
        return html`<li class=${a.activity_status === 'PLANNED' ? 'planned' : a.activity_status === 'CANCELLED' ? 'cancelled' : ''}>
          <div class="meta">${formatRelative(a.completed_on ?? a.scheduled_on ?? a.created_on)} · ${a.owner?.display_name ?? '—'} · ${activityTypeLabel(a.activity_type)}${a.direction ? ` · ${humanize(a.direction)}` : ''}${a.duration_minutes ? ` ${a.duration_minutes}m` : ''}
            ${a.activity_status === 'PLANNED' ? html` · <span class=${a.is_overdue ? 'overdue' : ''}>${a.is_overdue ? 'OVERDUE' : 'Planned'}</span>` : nothing}</div>
          <div class="strong">${a.subject}</div>
          ${a.description ? html`<div>${a.description}</div>` : nothing}
          ${a.outcome ? html`<div class="small">Outcome: ${a.outcome.label}</div>` : nothing}
          ${a.location ? html`<div class="small muted">${a.location}</div>` : nothing}
          ${editable && a.activity_status === 'PLANNED' ? html`<div class="row">
            <button class="btn small" @click=${() => this.openActivity('complete', a)}>Complete</button>
            <button class="btn small" @click=${() => this.openActivity('edit', a)}>Reschedule</button>
            <button class="btn small ghost" @click=${() => this.openActivity('cancel', a)}>Cancel</button></div>` : nothing}
          ${editable && this.can('lead_activity.delete') ? html`<div><button class="btn ghost small" @click=${() => {
            if (confirm('Delete this activity?')) void this.act(() => api.delete(`/api/v1/leads/${lead.id}/activities/${a.id}`, { ifMatch: a.version }), 'Activity deleted');
          }}>Delete</button></div>` : nothing}
        </li>`;
      })}</ul>` : html`<p class="muted">No activity yet.</p>`}
    </div>`;
  }

  private renderNotes(lead: Lead) {
    return html`<div class="stack">
      ${this.can('lead_note.create') && !lead.is_deleted ? html`<form class="card stack" @submit=${async (e: Event) => {
        e.preventDefault();
        const f = e.target as HTMLFormElement;
        const body = (f.elements.namedItem('body') as HTMLTextAreaElement).value.trim();
        const pinned = (f.elements.namedItem('is_pinned') as HTMLInputElement).checked;
        if (!body) return;
        await this.act(() => api.post(`/api/v1/leads/${lead.id}/notes`, { body, is_pinned: pinned }), 'Note added');
        f.reset();
      }}>
        <label class="field"><span class="label">Add a note</span><textarea name="body" maxlength="10000" required></textarea></label>
        <div class="row"><label class="check"><input type="checkbox" name="is_pinned" /> Pin</label><span class="spacer"></span><button class="btn primary small">Add note</button></div>
      </form>` : nothing}
      ${!this.notes ? html`<vs-skeleton rows="3"></vs-skeleton>` : this.notes.length ? this.notes.map((n) => html`<article class="note ${n.is_pinned ? 'pinned' : ''}">
        <div class="small muted">${n.created_by.display_name} · ${formatRelative(n.created_on)}${n.is_edited ? ' · edited' : ''}${n.is_pinned ? ' · pinned' : ''}</div>
        ${this.noteEditing === n.id ? html`<form class="stack" @submit=${async (e: Event) => {
            e.preventDefault();
            const body = ((e.target as HTMLFormElement).elements.namedItem('body') as HTMLTextAreaElement).value.trim();
            await this.act(() => api.patch(`/api/v1/leads/${lead.id}/notes/${n.id}`, { body }, { ifMatch: n.version }), 'Note saved');
            this.noteEditing = '';
          }}><label class="field"><span class="sr-only">Note</span><textarea name="body" maxlength="10000" .value=${n.body}></textarea></label>
            <div class="row"><button type="button" class="btn small" @click=${() => (this.noteEditing = '')}>Cancel</button><button class="btn small primary">Save</button></div></form>`
          : html`<div>${n.body}</div>`}
        <div class="row">${n.can_edit && this.noteEditing !== n.id ? html`<button class="btn ghost small" @click=${() => (this.noteEditing = n.id)}>Edit</button>
            <button class="btn ghost small" @click=${() => this.act(() => api.patch(`/api/v1/leads/${lead.id}/notes/${n.id}`, { is_pinned: !n.is_pinned }, { ifMatch: n.version }))}>${n.is_pinned ? 'Unpin' : 'Pin'}</button>` : nothing}
          ${n.can_delete ? html`<button class="btn ghost small" @click=${() => { this.noteTarget = n; this.dialog = 'note-delete'; }}>Delete</button>` : nothing}</div>
      </article>`) : html`<p class="muted">No notes yet.</p>`}
    </div>`;
  }

  private renderHistory() {
    if (!this.history) return html`<vs-skeleton rows="4"></vs-skeleton>`;
    if (!this.history.length) return html`<p class="muted">No history recorded.</p>`;
    return html`<div class="stack">${this.history.map((h) => html`<article class="card stack">
      <div class="small muted">${formatFull(h.performed_on)} · ${h.performed_by?.display_name ?? '—'} · ${h.action} · ${humanize(h.entity_type)}${h.reason ? ` · "${h.reason}"` : ''}</div>
      <vs-diff-viewer .oldValue=${h.old_value} .newValue=${h.new_value} .fields=${h.action === 'UPDATE' ? h.changed_fields : null}></vs-diff-viewer>
    </article>`)}
      ${this.historyCursor ? html`<button class="btn" @click=${() => this.loadHistory(true)}>Load more</button>` : nothing}</div>`;
  }

  private renderSide(lead: Lead) {
    const next = this.activities?.filter((a) => a.activity_status === 'PLANNED').sort((a, b) => (a.scheduled_on ?? '').localeCompare(b.scheduled_on ?? ''))[0];
    return html`<aside class="side stack">
      <section class="card stack next-up"><h2 class="eyebrow">Next up</h2>
        ${next ? html`<div class=${next.is_overdue ? 'overdue' : 'strong'}>${formatRelative(next.scheduled_on)}</div><div>${next.subject}</div>
          ${next.can_edit ? html`<div class="row"><button class="btn small" @click=${() => this.openActivity('complete', next)}>Complete</button></div>` : nothing}`
          : html`<p class="muted">Nothing planned.</p>`}
      </section>
      ${lead.duplicate_status === 'SUSPECTED' ? html`<section class="card stack"><h2 class="eyebrow warning-text">⚠ Possible duplicate</h2>
        ${lead.duplicate_of ? html`<a href=${`/leads/${lead.duplicate_of.id}`}>${lead.duplicate_of.lead_number}${lead.duplicate_of.status ? ` (${statusLabel(lead.duplicate_of.status)})` : ''}</a>` : nothing}
        ${this.canUpdate ? html`<button class="btn small" @click=${() => (this.dialog = 'duplicate')}>Review</button>` : nothing}</section>` : nothing}
      ${lead.message ? html`<section class="card stack"><h2 class="eyebrow">Enquiry message</h2><p class="message">"${lead.message}"</p></section>` : nothing}
    </aside>`;
  }

  private renderDialogs(lead: Lead) {
    const planned = this.activities?.filter((a) => a.activity_status === 'PLANNED').length ?? 0;
    return html`
      <vs-status-dialog .open=${Boolean(this.statusTo)} .lead=${lead} .to=${this.statusTo} .plannedCount=${planned}
        @close=${() => (this.statusTo = '')} @lead-updated=${(e: CustomEvent<Lead>) => { this.updated_(e.detail); toast(`Moved to ${statusLabel(e.detail.status)}`, 'success'); }}
        @conflict=${() => void this.load()}></vs-status-dialog>
      <vs-lead-form .open=${this.editOpen} .lead=${lead} .assignees=${this.assignees} @close=${() => (this.editOpen = false)} @lead-saved=${(e: CustomEvent<Lead>) => (this.lead = e.detail)}></vs-lead-form>
      <vs-activity-dialog .open=${this.activityOpen} .mode=${this.activityMode} .leadId=${lead.id} .activity=${this.activityTarget} .preset=${this.activityPreset}
        .assignees=${this.assignees} .defaultOwner=${lead.assigned_to?.id ?? this.me?.id ?? ''} .consentWithdrawn=${Boolean(lead.consent?.withdrawn_on)}
        @close=${() => (this.activityOpen = false)} @activity-saved=${() => void this.load()}></vs-activity-dialog>
      <vs-dialog .open=${this.dialog === 'delete'} heading=${`Delete lead ${lead.lead_number}?`} @close=${() => (this.dialog = '')}>
        <p>The lead is hidden from lists. Someone with restore permission can bring it back.</p>
        <label class="field"><span class="label">Reason (optional)</span><input id="del-reason" maxlength="500" /></label>
        <div slot="actions"><button class="btn" @click=${() => (this.dialog = '')}>Cancel</button>
          <button class="btn danger" ?disabled=${this.busy} @click=${async () => {
            const reason = (this.renderRoot.querySelector('#del-reason') as HTMLInputElement).value.trim();
            this.busy = true;
            try {
              await api.request(`/api/v1/leads/${lead.id}`, { method: 'DELETE', ifMatch: lead.version, body: reason ? { reason } : undefined });
              toast('Lead deleted', 'success');
              navigate('/leads');
            } catch (e) { this.actionProblem = e as ApiProblem; this.dialog = ''; } finally { this.busy = false; }
          }}>Delete lead</button></div>
      </vs-dialog>
      <vs-dialog .open=${this.dialog === 'note-delete'} heading="Delete this note?" @close=${() => (this.dialog = '')}>
        <p>This can't be undone.</p>
        <div slot="actions"><button class="btn" @click=${() => (this.dialog = '')}>Cancel</button>
          <button class="btn danger" @click=${() => this.noteTarget && this.act(() => api.delete(`/api/v1/leads/${lead.id}/notes/${this.noteTarget!.id}`, { ifMatch: this.noteTarget!.version }), 'Note deleted')}>Delete note</button></div>
      </vs-dialog>
      <vs-dialog .open=${this.dialog === 'consent'} heading="Record consent withdrawal" @close=${() => (this.dialog = '')}>
        <p>Planned contact activities will be cancelled and this lead will show "Do not contact".</p>
        <form id="cf" class="stack" @submit=${(e: Event) => {
          e.preventDefault();
          const f = e.target as HTMLFormElement;
          const channel = (f.elements.namedItem('channel') as HTMLSelectElement).value;
          const note = (f.elements.namedItem('note') as HTMLInputElement).value.trim();
          void this.act(() => api.post(`/api/v1/leads/${lead.id}/consent/withdraw`, { channel, note: note || undefined }, { ifMatch: lead.version }), 'Consent withdrawal recorded');
        }}>
          <label class="field"><span class="label">How was it withdrawn? *</span><select name="channel">
            ${['PHONE_VERBAL', 'IN_PERSON', 'WHATSAPP', 'EMAIL', 'WEBSITE'].map((c) => html`<option value=${c}>${humanize(c)}</option>`)}</select></label>
          <label class="field"><span class="label">Note</span><input name="note" maxlength="500" /></label>
        </form>
        <div slot="actions"><button class="btn" @click=${() => (this.dialog = '')}>Cancel</button><button class="btn primary" form="cf">Record withdrawal</button></div>
      </vs-dialog>
      <vs-dialog .open=${this.dialog === 'duplicate'} heading="Review possible duplicate" @close=${() => (this.dialog = '')}>
        <form id="df" class="stack" @submit=${(e: Event) => {
          e.preventDefault();
          const f = e.target as HTMLFormElement;
          const resolution = (f.elements.namedItem('resolution') as RadioNodeList).value;
          const of = (f.elements.namedItem('duplicate_of_lead_id') as HTMLInputElement).value.trim();
          void this.act(() => api.post(`/api/v1/leads/${lead.id}/duplicate-resolution`, { resolution, ...(resolution === 'CONFIRMED' && of ? { duplicate_of_lead_id: of } : {}) }, { ifMatch: lead.version }), 'Duplicate review saved');
        }}>
          <label class="check"><input type="radio" name="resolution" value="NOT_DUPLICATE" checked /> Not a duplicate</label>
          <label class="check"><input type="radio" name="resolution" value="CONFIRMED" /> Confirmed duplicate (then mark it Lost with reason Duplicate)</label>
          <label class="field"><span class="label">Duplicate of (lead id)</span><input name="duplicate_of_lead_id" .value=${lead.duplicate_of?.id ?? ''} class="mono" /></label>
        </form>
        <div slot="actions"><button class="btn" @click=${() => (this.dialog = '')}>Cancel</button><button class="btn primary" form="df">Save</button></div>
      </vs-dialog>
      <vs-dialog .open=${this.dialog === 'erase'} heading="Erase personal data" @close=${() => (this.dialog = '')}>
        <vs-banner kind="danger">This cannot be undone. Name, phone, email, message and notes are anonymized, including in the audit history.</vs-banner>
        <form id="ef" class="stack" @submit=${(e: Event) => {
          e.preventDefault();
          const f = e.target as HTMLFormElement;
          const v = (n: string) => (f.elements.namedItem(n) as HTMLInputElement).value.trim();
          if (v('confirm_number') !== lead.lead_number) return void toast(`Type ${lead.lead_number} to confirm`, 'error');
          if (!v('request_ref') || !v('legal_basis')) return void toast('Request reference and legal basis are required', 'error');
          void this.act(() => api.post(`/api/v1/leads/${lead.id}/erasure`, { request_ref: v('request_ref'), legal_basis: v('legal_basis'), reason: v('reason') || undefined }, { ifMatch: lead.version }), 'Personal data erased');
        }}>
          <label class="field"><span class="label">Request reference *</span><input name="request_ref" maxlength="100" placeholder="DPR-2026-004" /></label>
          <label class="field"><span class="label">Legal basis *</span><input name="legal_basis" maxlength="200" value="DPDP s.12 erasure" /></label>
          <label class="field"><span class="label">Reason</span><input name="reason" maxlength="500" /></label>
          <label class="field"><span class="label">Type ${lead.lead_number} to confirm *</span><input name="confirm_number" autocomplete="off" /></label>
        </form>
        <div slot="actions"><button class="btn" @click=${() => (this.dialog = '')}>Cancel</button><button class="btn danger" form="ef" ?disabled=${this.busy}>Erase permanently</button></div>
      </vs-dialog>`;
  }

  override render() {
    if (this.loading && !this.lead) return html`<div class="page"><div class="card"><vs-skeleton rows="10"></vs-skeleton></div></div>`;
    if (this.problem || !this.lead) {
      const notFound = this.problem?.status === 404 || this.problem?.code === 'INVALID_ID';
      return html`<div class="page">${notFound
        ? html`<vs-empty-state heading="This lead doesn't exist or isn't visible to you."><a class="btn" href="/leads">Back to leads</a></vs-empty-state>`
        : html`<vs-problem-banner .problem=${this.problem}></vs-problem-banner>`}</div>`;
    }
    const lead = this.lead;
    const showHistory = this.can('audit.read');
    return html`<div class="page">
      ${this.renderHeader(lead)}
      <div class="grid">
        ${this.renderDetails(lead)}
        <section class="stack">
          <vs-tabs .tabs=${[{ id: 'timeline', label: 'Timeline' }, { id: 'notes', label: `Notes${this.notes ? ` ${this.notes.length}` : ''}`, hidden: !this.can('lead_note.read') }, { id: 'history', label: 'History', hidden: !showHistory }]}
            .selected=${this.tab} @tab-change=${(e: CustomEvent<'timeline' | 'notes' | 'history'>) => { this.tab = e.detail; if (e.detail === 'history' && !this.history) void this.loadHistory(); }}></vs-tabs>
          ${this.tab === 'timeline' ? this.renderTimeline(lead) : this.tab === 'notes' ? this.renderNotes(lead) : this.renderHistory()}
        </section>
        ${this.renderSide(lead)}
      </div>
      <div class="mobile-bar">
        <button class="btn" @click=${() => this.contact('CALL')}>Call</button>
        <button class="btn" @click=${() => this.contact('WHATSAPP')}>WhatsApp</button>
        ${this.can('lead_activity.create') ? html`<button class="btn" @click=${() => this.openActivity('log', null, { activity_type: 'CALL' })}>Log</button>` : nothing}
      </div>
      ${this.renderDialogs(lead)}
    </div>`;
  }
}
customElements.define('vs-lead-detail-page', VsLeadDetailPage);
