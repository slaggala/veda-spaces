import { css, html, nothing } from 'lit';
import { api } from '../../core/api/client.js';
import type { ApiProblem } from '../../core/api/problem.js';
import type { AuditEntry, CursorMeta, SecurityEvent } from '../../core/api/types.js';
import { SessionElement } from '../../core/authz/session-element.js';
import { formatFull, humanize } from '../../core/format/format.js';
import { pageStyles, shared, tableStyles } from '../../design-system/styles.js';

const AUDIT_FILTERS = ['entity_type', 'entity_id', 'action', 'performed_by', 'performed_via', 'from', 'to', 'transaction_id', 'request_id'] as const;
const SEC_FILTERS = ['event_type', 'event_category', 'outcome', 'severity', 'subject_user_id', 'ip', 'from', 'to'] as const;

function daysAgoIso(days: number): string {
  return new Date(Date.now() - days * 86_400_000).toISOString();
}

/**
 * Audit log viewer (09 §4.9, AUDIT-008) and Security events tab (SEVT-005). Read-only. The Security
 * events tab renders only with security_event.read; chain and hash columns are never shown.
 */
export class VsAuditPage extends SessionElement {
  static override properties = {
    tab: { state: true }, audit: { state: true }, events: { state: true }, cursor: { state: true }, problem: { state: true }, loading: { state: true },
    filters: { state: true }, detail: { state: true }, eventDetail: { state: true },
  };
  declare tab: 'audit' | 'security';
  declare audit: AuditEntry[];
  declare events: SecurityEvent[];
  declare cursor: string | null;
  declare problem: ApiProblem | null;
  declare loading: boolean;
  declare filters: Record<string, string>;
  declare detail: AuditEntry | null;
  declare eventDetail: SecurityEvent | null;
  static override styles = [...shared, pageStyles, tableStyles, css`.filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: flex-end; } .filters input, .filters select { min-width: 150px; } dl { display: grid; grid-template-columns: 120px 1fr; gap: 6px 12px; margin: 0; } dt { color: var(--vs-ink-muted); } dd { margin: 0; word-break: break-word; } pre { font-family: var(--vs-font-mono); font-size: 12px; white-space: pre-wrap; background: var(--vs-cream); padding: 12px; border-radius: 8px; }`];

  constructor() {
    super();
    const q = new URLSearchParams(window.location.search);
    this.tab = q.get('tab') === 'security' ? 'security' : 'audit';
    this.audit = [];
    this.events = [];
    this.cursor = null;
    this.problem = null;
    this.loading = false;
    this.filters = {};
    for (const [k, v] of q.entries()) if (k !== 'tab') this.filters[k] = v;
    this.detail = null;
    this.eventDetail = null;
  }

  override connectedCallback() {
    super.connectedCallback();
    if (this.tab === 'security' && !this.can('security_event.read')) this.tab = 'audit';
    if (this.tab === 'audit' && !this.can('audit.read')) this.tab = 'security';
    void this.load(true);
  }

  private query(): Record<string, string> {
    const allowed: readonly string[] = this.tab === 'audit' ? AUDIT_FILTERS : SEC_FILTERS;
    const q: Record<string, string> = {};
    for (const [k, v] of Object.entries(this.filters)) if (v && allowed.includes(k)) q[k] = v;
    if (this.tab === 'audit' && q.entity_id && !q.include_children) q.include_children = 'true';
    // Unfiltered security-event queries over more than 31 days need a time range (SEVT-008).
    if (this.tab === 'security' && !q.from) q.from = daysAgoIso(7);
    return q;
  }

  private async load(reset: boolean) {
    this.loading = true;
    this.problem = null;
    const path = this.tab === 'audit' ? '/api/v1/audit-logs' : '/api/v1/security-events';
    try {
      const r = await api.get<Array<AuditEntry | SecurityEvent>>(path, { ...this.query(), limit: 50, cursor: reset ? undefined : this.cursor ?? undefined });
      const meta = r.meta as unknown as CursorMeta;
      this.cursor = meta.has_more ? meta.next_cursor : null;
      if (this.tab === 'audit') this.audit = reset ? (r.data as AuditEntry[]) : [...this.audit, ...(r.data as AuditEntry[])];
      else this.events = reset ? (r.data as SecurityEvent[]) : [...this.events, ...(r.data as SecurityEvent[])];
    } catch (e) {
      this.problem = e as ApiProblem;
    } finally {
      this.loading = false;
    }
  }

  private setFilter(key: string, value: string) {
    this.filters = { ...this.filters, [key]: value };
    const qs = new URLSearchParams({ ...(this.tab === 'security' ? { tab: 'security' } : {}), ...Object.fromEntries(Object.entries(this.filters).filter(([, v]) => v)) });
    history.replaceState(null, '', `/audit${qs.toString() ? `?${qs}` : ''}`);
    void this.load(true);
  }

  private text(key: string, label: string, placeholder = '') {
    return html`<label class="field"><span class="label">${label}</span><input .value=${this.filters[key] ?? ''} placeholder=${placeholder}
      @change=${(e: Event) => this.setFilter(key, (e.target as HTMLInputElement).value.trim())} /></label>`;
  }
  private select(key: string, label: string, options: string[]) {
    return html`<label class="field"><span class="label">${label}</span><select @change=${(e: Event) => this.setFilter(key, (e.target as HTMLSelectElement).value)}>
      <option value="">Any</option>${options.map((o) => html`<option value=${o} ?selected=${this.filters[key] === o}>${humanize(o)}</option>`)}</select></label>`;
  }
  private dateRange() {
    const toIso = (v: string) => (v ? new Date(`${v}T00:00:00`).toISOString() : '');
    return html`<label class="field"><span class="label">From</span><input type="date" @change=${(e: Event) => this.setFilter('from', toIso((e.target as HTMLInputElement).value))} /></label>
      <label class="field"><span class="label">To</span><input type="date" @change=${(e: Event) => this.setFilter('to', toIso((e.target as HTMLInputElement).value))} /></label>`;
  }

  private renderAudit() {
    return html`<div class="filters" role="search">
        ${this.select('entity_type', 'Entity', ['lead', 'lead_note', 'lead_activity', 'app_user', 'role', 'role_permission', 'user_role', 'user_permission', 'permission', 'lookup_value', 'admin_approval_request', 'user_mfa_factor'])}
        ${this.text('entity_id', 'Record id')}
        ${this.select('action', 'Action', ['CREATE', 'UPDATE', 'DELETE', 'RESTORE', 'HARD_DELETE', 'EXPORT', 'ANONYMIZE'])}
        ${this.text('performed_by', 'By (user id or "system")')}
        ${this.select('performed_via', 'Via', ['API', 'PUBLIC_FORM', 'SYSTEM_JOB', 'MIGRATION', 'CLI'])}
        ${this.dateRange()}
      </div>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      ${this.loading && !this.audit.length ? html`<div class="card"><vs-skeleton rows="8"></vs-skeleton></div>` : !this.audit.length ? html`<div class="card"><vs-empty-state heading="No audit entries match."></vs-empty-state></div>`
        : html`<div class="table-wrap"><table class="cards"><thead><tr><th>When</th><th>Who</th><th>Action</th><th>Record</th><th>Changes</th></tr></thead>
          <tbody>${this.audit.map((a) => html`<tr class="clickable" tabindex="0" @click=${() => (this.detail = a)} @keydown=${(e: KeyboardEvent) => e.key === 'Enter' && (this.detail = a)}>
            <td data-label="When">${formatFull(a.performed_on)}</td><td data-label="Who">${a.performed_by?.display_name ?? '—'}</td><td data-label="Action">${a.action}</td>
            <td data-label="Record">${humanize(a.entity_type)} ${a.entity_label ?? html`<span class="mono">${a.entity_id.slice(0, 8)}…</span>`}</td>
            <td data-label="Changes">${a.action === 'CREATE' ? `${Object.keys(a.new_value ?? {}).length} fields` : (a.changed_fields ?? []).slice(0, 3).join(', ') || '—'}</td></tr>`)}</tbody></table></div>`}
      ${this.cursor ? html`<button class="btn" @click=${() => this.load(false)}>Load more</button>` : nothing}`;
  }

  private renderSecurity() {
    return html`<div class="filters" role="search">
        ${this.text('event_type', 'Event type', 'LOGIN')}
        ${this.select('event_category', 'Category', ['AUTHENTICATION', 'SESSION', 'PASSWORD', 'MFA', 'ACCOUNT', 'AUTHORIZATION', 'PUBLIC_INTAKE'])}
        ${this.select('outcome', 'Outcome', ['SUCCESS', 'FAILURE', 'BLOCKED'])}
        ${this.select('severity', 'Severity', ['INFO', 'WARNING', 'CRITICAL'])}
        ${this.text('subject_user_id', 'Subject user id')}
        ${this.text('ip', 'IP')}
        ${this.dateRange()}
      </div>
      <p class="small muted">Showing the last 7 days unless a range is chosen.</p>
      <vs-problem-banner .problem=${this.problem}></vs-problem-banner>
      ${this.loading && !this.events.length ? html`<div class="card"><vs-skeleton rows="8"></vs-skeleton></div>` : !this.events.length ? html`<div class="card"><vs-empty-state heading="No security events match."></vs-empty-state></div>`
        : html`<div class="table-wrap"><table class="cards"><thead><tr><th>When</th><th>Event</th><th>Outcome</th><th>Subject</th><th>IP</th></tr></thead>
          <tbody>${this.events.map((ev) => html`<tr class="clickable" tabindex="0" @click=${() => (this.eventDetail = ev)} @keydown=${(e: KeyboardEvent) => e.key === 'Enter' && (this.eventDetail = ev)}>
            <td data-label="When">${formatFull(ev.occurred_on)}</td><td data-label="Event">${ev.event_type}</td>
            <td data-label="Outcome"><span class="chip ${ev.outcome === 'SUCCESS' ? 'success' : ev.severity === 'CRITICAL' ? 'danger' : 'warning'}">${ev.outcome}${ev.failure_reason ? ` · ${ev.failure_reason}` : ''}</span></td>
            <td data-label="Subject">${ev.subject_user?.display_name ?? '—'}</td><td data-label="IP">${ev.ip_address ?? '—'}</td></tr>`)}</tbody></table></div>`}
      ${this.cursor ? html`<button class="btn" @click=${() => this.load(false)}>Load more</button>` : nothing}`;
  }

  override render() {
    const d = this.detail;
    const ev = this.eventDetail;
    return html`<div class="page">
      <div class="page-head"><div><p class="eyebrow">Admin</p><h1 class="display">${this.tab === 'audit' ? 'Audit log' : 'Security events'}</h1></div></div>
      <vs-tabs label="Logs" .tabs=${[{ id: 'audit', label: 'Audit log', hidden: !this.can('audit.read') }, { id: 'security', label: 'Security events', hidden: !this.can('security_event.read') }]}
        .selected=${this.tab} @tab-change=${(e: CustomEvent<'audit' | 'security'>) => { this.tab = e.detail; this.filters = {}; this.cursor = null; history.replaceState(null, '', e.detail === 'security' ? '/audit?tab=security' : '/audit'); void this.load(true); }}>
        ${this.tab === 'audit' ? this.renderAudit() : this.renderSecurity()}
      </vs-tabs>
      <vs-drawer wide .open=${Boolean(d)} heading=${d ? `${d.action} · ${humanize(d.entity_type)}${d.entity_label ? ` ${d.entity_label}` : ''}` : ''} @close=${() => (this.detail = null)}>
        ${d ? html`<dl>
            <dt>By</dt><dd>${d.performed_by?.display_name ?? '—'} · ${formatFull(d.performed_on)} · via ${d.performed_via}</dd>
            <dt>Request</dt><dd class="mono">${d.request_id ?? '—'} <button class="btn ghost small" @click=${() => navigator.clipboard?.writeText(d.request_id ?? '')}>Copy</button></dd>
            <dt>Transaction</dt><dd class="mono">${d.transaction_id} <button class="btn ghost small" @click=${() => { this.detail = null; this.setFilter('transaction_id', d.transaction_id); }}>View all changes</button></dd>
            <dt>IP</dt><dd>${d.ip_address ?? '—'}</dd>
            ${d.user_agent ? html`<dt>Device</dt><dd>${d.user_agent}</dd>` : nothing}
            ${d.reason ? html`<dt>Reason</dt><dd>${d.reason}</dd>` : nothing}
            ${d.parent_entity_type ? html`<dt>Parent</dt><dd>${humanize(d.parent_entity_type)} <span class="mono">${d.parent_entity_id}</span></dd>` : nothing}
          </dl>
          <vs-diff-viewer .oldValue=${d.old_value} .newValue=${d.new_value} .fields=${d.action === 'UPDATE' ? d.changed_fields : null}></vs-diff-viewer>
          ${d.entity_type === 'lead' ? html`<a href=${`/leads/${d.entity_id}`}>Open record →</a>` : d.parent_entity_type === 'lead' ? html`<a href=${`/leads/${d.parent_entity_id}`}>Open lead →</a>` : nothing}
          <details><summary>View raw JSON</summary><pre>${JSON.stringify(d, null, 2)}</pre></details>` : nothing}
      </vs-drawer>
      <vs-drawer .open=${Boolean(ev)} heading=${ev?.event_type ?? ''} @close=${() => (this.eventDetail = null)}>
        ${ev ? html`<dl>
          <dt>When</dt><dd>${formatFull(ev.occurred_on)}</dd><dt>Category</dt><dd>${ev.event_category}</dd>
          <dt>Outcome</dt><dd>${ev.outcome} · ${ev.severity}${ev.failure_reason ? ` · ${ev.failure_reason}` : ''}</dd>
          <dt>Subject</dt><dd>${ev.subject_user?.display_name ?? '—'}</dd><dt>Actor</dt><dd>${ev.actor?.display_name ?? '—'}</dd>
          ${ev.permission_code ? html`<dt>Permission</dt><dd class="mono">${ev.permission_code}</dd>` : nothing}
          <dt>IP</dt><dd>${ev.ip_address ?? '—'}</dd><dt>Device</dt><dd>${ev.user_agent ?? '—'}</dd><dt>Request</dt><dd class="mono">${ev.request_id ?? '—'}</dd>
        </dl>${ev.detail ? html`<pre>${JSON.stringify(ev.detail, null, 2)}</pre>` : nothing}` : nothing}
      </vs-drawer>
    </div>`;
  }
}
customElements.define('vs-audit-page', VsAuditPage);
