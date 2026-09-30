# 09 — UI/UX Design: Veda Workspace

Governing decisions: [ADR-005](decisions/ADR-005-lead-required-fields.md) · [ADR-006](decisions/ADR-006-mfa-policy.md) · [ADR-007](decisions/ADR-007-technology-stack.md) · [ADR-010](decisions/ADR-010-account-control-and-privileged-protection.md)

"Veda Workspace" is a working name for the staff app at `app.vedaspaces.com`.

## 1. Design intent

The public site sells calm, crafted, warm interiors: generous whitespace, a serif display face, warm neutrals and a single copper accent. The workspace should feel like **the studio behind that showroom**. It keeps the same materials, but they are tuned for speed and density.

| Principle | Meaning in practice |
|---|---|
| Quiet luxury | Warm paper backgrounds, hairline rules instead of heavy boxes. Copper used sparingly, for the one primary action and the active state. |
| Serif for moments, sans for work | Cormorant Garamond only for page titles, lead names and big KPI numerals. Manrope for everything interactive and tabular. |
| Calm density | Tables at 44 px rows by default (40 px compact option). No zebra striping; hairline separators. |
| One primary action per view | For example "New lead", "Save", "Move to Site visit" |
| Mobile-first for Sales | The lead list, lead details and logging an activity are designed at 360 px first (UI-012) |
| Honest system states | Every screen has designed empty, loading (skeleton), error (with request id) and no-permission states |

## 2. Design tokens (UI-010)

These are derived from the live site (`dist/assets/styles.css`, `enhancements.css`). Contrast ratios were checked against WCAG 2.2.

### 2.1 Color

| Token | Light | Dark | Use |
|---|---|---|---|
| `--vs-paper` | `#FBF7EF` | `#171614` | App background |
| `--vs-surface` | `#FFFFFF` | `#201F1C` | Cards, tables, drawers |
| `--vs-cream` | `#F0E4D4` | `#2A2723` | Subtle fills, selected rows, chips |
| `--vs-ink` | `#1E1D1A` | `#F3F0E9` | Primary text (15.8:1 on paper) |
| `--vs-ink-muted` | `#5D574F` | `#B8B0A5` | Secondary text (6.6:1 on paper) |
| `--vs-line` | `rgba(30,29,26,.14)` | `rgba(243,240,233,.14)` | Hairlines |
| `--vs-copper` | `#A46D42` | `#C8906A` | Accent fills, focus ring, large text, icons (4.1:1: **non-text/large text only**) |
| `--vs-copper-text` | `#8C5B37` | `#D9A583` | Copper **text** and links (5.4:1 on paper, passes AA) |
| `--vs-copper-strong` | `#7A4E2E` | `#E0B394` | Primary button background. **Always paired with `--vs-on-copper-strong`.** |
| `--vs-on-copper-strong` | `#FFFFFF` | `#171614` | Text and icons on primary buttons (light 7.1:1, dark 9.5:1) (F-14) |
| `--vs-on-danger` | `#FFFFFF` | `#171614` | Text on destructive buttons (`--vs-danger` background): light 6.6:1, dark 6.2:1 |
| `--vs-focus-ring` | `#A46D42` | `#C8906A` | 2 px focus outline with 2 px offset: light 4.1:1 on paper, dark 6.6:1 on paper and 6.0:1 on surface |
| `--vs-sidebar` | `#201F1C` | `#121110` | Navigation rail (from the site's dark sections) |
| `--vs-danger` | `#A23B2A` | `#E07A67` | Destructive actions, errors |
| `--vs-success` | `#3F6B4A` | `#86B894` | Success, WON |
| `--vs-warning` | `#8A5E0F` | `#E0B45C` | Overdue, suspected duplicate |

**Finding:** the site's copper `#A46D42` is **3.8:1** on the site's paper (`#F3F0E9`) and 4.1:1 on the workspace paper, so it fails AA (4.5:1) for body text. The workspace keeps it for accents and uses `--vs-copper-text` for copper-colored text.

### 2.2 Pipeline status colors

Each status has an earthy hue and is always paired with a text label and a stepper position, so color is never the only signal.

| Status | Chip bg / text (light) | Semantics |
|---|---|---|
| NEW | `#E8ECEF` / `#34495A` | Slate: untouched |
| CONTACTED | `#E4EEEA` / `#2F5D50` | Teal-green: conversation started |
| SITE_VISIT | `#F3EAD7` / `#7A5A12` | Ochre: in the field |
| QUOTATION_SENT | `#F2E3D8` / `#7A4E2E` | Copper: proposal out |
| NEGOTIATION | `#EDE3EC` / `#5E3D5B` | Plum: closing |
| WON | `#E2EFE5` / `#2E5A3A` | Green |
| LOST | `#EFE6E4` / `#6E4A44` | Muted clay |

### 2.3 Typography

| Token | Font | Size / line height | Use |
|---|---|---|---|
| `--vs-display` | Cormorant Garamond 500 | 40/44 (mobile 32/36) | Page titles ("Leads"), login headline |
| `--vs-title` | Cormorant Garamond 500 | 28/32 | Lead name on details, drawer titles |
| `--vs-kpi` | Cormorant Garamond 500 | 44/44, tabular lining numerals | Dashboard numbers |
| `--vs-eyebrow` | Manrope 600 | 11/16, uppercase, tracking .18em | Section labels (the site's `.eyebrow`) |
| `--vs-body` | Manrope 400 | 14/22 | Default UI text |
| `--vs-body-strong` | Manrope 600 | 14/22 | Table primary column, labels |
| `--vs-small` | Manrope 500 | 12/18 | Meta, timestamps |
| `--vs-mono` | ui-monospace | 12/18 | IDs, request ids, JSON diffs |

Fonts are the same Google Fonts families the site already loads. Body minimum is 14 px, and 16 px for inputs, which avoids iOS zoom.

### 2.4 Space, shape, motion

| Item | Values |
|---|---|
| Spacing scale | 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 |
| Radius | 2 px (inputs, buttons: architectural, matching the site's square buttons) · 8 px (cards, drawers) · 999 px (chips, avatars) |
| Elevation | Shadows are rare: `0 12px 32px rgba(30,20,12,.12)` for drawers and menus only |
| Motion | 160 ms ease-out for state changes, 240 ms for drawers. `prefers-reduced-motion` disables transforms. |
| Iconography | 1.5 px stroke line icons (Lucide set, self-hosted SVG sprite) |
| Imagery | The login screen reuses site photography (`warm-hero.jpg`, `soft-kitchen.jpg`) with the site's dark gradient overlay |

### 2.5 Accessibility token decisions (UI-014)

These corrections are made **in the design tokens themselves**, so no component can reintroduce the failures. Ratios were computed with the WCAG 2.x relative-luminance formula and are re-checked automatically for **both themes** (12 §4.8).

**Light theme** (paper `#FBF7EF`, surface `#FFFFFF`):

| ID | Token | Problem found | Decision | Ratio |
|---|---|---|---|---|
| A11Y-T1 | `--vs-copper` `#A46D42` | Brand copper is 3.8:1 on the site paper and 4.1:1 on the workspace paper, so it fails AA for text | Fills, focus rings, icons and large text only | 4.1:1 |
| A11Y-T2 | `--vs-copper-text` `#8C5B37` | Copper-colored text was needed | Mandatory for copper text and links | 5.4:1 |
| A11Y-T3 | `--vs-copper-strong` `#7A4E2E` + `--vs-on-copper-strong` `#FFFFFF` | White text on brand copper fails | Primary button pair | 7.1:1 |
| A11Y-T4 | `--vs-warning` `#8A5E0F` | The first proposal `#9A6A12` was 4.4:1 | Darkened | 5.3:1 |
| A11Y-T5 | Status chip pairs (§2.2) | — | Each pair is self-contained (chip background + chip text) and **used unchanged in both themes** | 5.3:1 – 7.9:1 |
| A11Y-T6 | `--vs-focus-ring` | Focus visibility | Non-text ≥ 3:1 against paper and surface | 4.1:1 |

**Dark theme** (paper `#171614`, surface `#201F1C`):

| ID | Token | Problem found | Decision | Ratio (paper / surface) |
|---|---|---|---|---|
| A11Y-T7 | `--vs-copper-strong` `#E0B394` + `--vs-on-copper-strong` `#171614` | **F-14:** white text on `#E0B394` is 1.9:1 | Primary buttons use the dark on-color, never white | 9.5:1 |
| A11Y-T8 | `--vs-ink` `#F3F0E9` · `--vs-ink-muted` `#B8B0A5` | Verified | — | 15.9 / 14.5 · 8.4 / 7.7 |
| A11Y-T9 | `--vs-copper-text` `#D9A583` | Verified | — | 8.3 / 7.6 |
| A11Y-T10 | `--vs-danger` `#E07A67` · `--vs-success` `#86B894` · `--vs-warning` `#E0B45C` | Verified as text | — | 6.2 / 5.6 · 8.0 / 7.3 · 9.4 / 8.5 |
| A11Y-T11 | `--vs-focus-ring` `#C8906A` | Verified | — | 6.6 / 6.0 |
| A11Y-T12 | `--vs-on-danger` `#171614` on `--vs-danger` `#E07A67` | Destructive buttons | Dark on-color | 6.2:1 |

**Rules:**

- A design-system lint rejects raw hex colors in components, so only tokens are allowed.
- Every background token used for a control has a declared `--vs-on-*` pair.
- The automated contrast test iterates every (on-token, background-token) pair in both themes, and fails below 4.5:1 for text or 3:1 for non-text.

## 3. Application shell and patterns

### 3.1 Shell layout

```
Desktop ≥ 1200px
┌──────────┬──────────────────────────────────────────────────────────────────────────────┐
│ VEDA     │  Leads                                           🔍 Search  (⌘K)   🔔3   (PS) ▾ │
│ SPACES   ├──────────────────────────────────────────────────────────────────────────────┤
│          │                                                                              │
│ ◉ Dashboard                                                                             │
│ ○ Leads  │                         page content (max-width 1440, gutters 32)            │
│ ○ Follow-ups                                                                            │
│          │                                                                              │
│ ADMIN    │                                                                              │
│ ○ Users  │                                                                              │
│ ○ Roles  │                                                                              │
│ ○ Permissions                                                                           │
│ ○ Audit log                                                                             │
│          │                                                                              │
│ ─────    │                                                                              │
│ ⚙ Profile│                                                                              │
└──────────┴──────────────────────────────────────────────────────────────────────────────┘
  sidebar 240px, #201F1C, cream text; active item = copper 2px left rule + cream text

Tablet 768–1199: sidebar collapses to 72px icon rail (tooltips).
Mobile < 768: top bar + bottom tab bar [Dashboard · Leads · + · Follow-ups · More]; "+" = New lead / Log activity sheet.
```

Nav items render only if the user holds the item's permission. For example, the ADMIN group appears only with `user.read`, `role.read`, `permission.read` or `audit.read`.

### 3.2 Global patterns

| Pattern | Spec |
|---|---|
| Command palette (⌘K / Ctrl-K) | Jump to lead by number, name or phone. Navigate to pages. "New lead". Permission-filtered. |
| Drawers | Create and edit forms and details for admin entities open in a right drawer (560 px). This keeps list context. They are full screen on mobile. |
| Toasts | Bottom-center, 4 s, `role="status"`. There is **no Undo** in P0 (F-20). Destructive actions are confirmed beforehand instead, for example "Delete this note?". |
| Confirmations | Only for destructive or sensitive actions. The dialog names the object ("Delete lead VS-L-2026-000123?"). Sensitive permissions need a reason field. |
| Version conflict | A modal lists changed fields (from a fresh GET vs local edits) with "Reload theirs" or "Re-apply mine" |
| Errors | Inline under fields (server `errors[]` mapped by `field`). Page-level problem banner shows `request_id` with a copy button. |
| Empty states | Serif one-liner plus helpful action. For example "No leads yet. Share your enquiry form or add one manually." |
| Loading | Skeleton rows matching the final layout, never spinners on full pages |
| Dates | Relative for < 7 days ("2 h ago", "Tomorrow 11:00"), absolute otherwise (`29 Sep 2026, 3:32 pm` IST). Hover shows full timestamp. |
| Phone | Displayed `+91 98765 43210`. Tap-to-call and WhatsApp icon buttons. |
| Currency | `₹18,50,000` (Indian grouping) via `Intl.NumberFormat('en-IN')` |

### 3.3 Component inventory (design-system)

`vs-app-shell`, `vs-nav`, `vs-top-bar`, `vs-command-palette`, `vs-button` (primary/secondary/ghost/danger; sizes), `vs-icon-button`, `vs-field` (label, hint, error), `vs-input`, `vs-textarea`, `vs-select`, `vs-lookup-select` (bound to `/lookups`), `vs-user-picker`, `vs-date-time-picker`, `vs-checkbox`, `vs-switch`, `vs-segmented`, `vs-chip`, `vs-status-pill`, `vs-status-stepper`, `vs-avatar`, `vs-data-table` (sort, column chooser, sticky header, row actions, keyboard nav, responsive card mode), `vs-filter-bar`, `vs-pagination`, `vs-kpi-tile`, `vs-bar-list`, `vs-timeline`, `vs-drawer`, `vs-dialog`, `vs-toast`, `vs-banner`, `vs-tabs`, `vs-empty-state`, `vs-skeleton`, `vs-diff-viewer`, `vs-permission-matrix`, `vs-can`.

### 3.4 Permission-aware rendering (UI-013)

- `<vs-can permission="lead.assign">…</vs-can>` renders its slot only if the effective map contains the code. An optional `scope-for=${lead}` evaluates OWN ownership client-side.
- **Hide vs disable:**
  - Hide actions the user can never perform.
  - Disable, with a tooltip, those blocked by state ("Mark as Lost — requires a lost reason").
- Lead action menus use the server's `allowed_transitions`, so the UI never duplicates state-machine rules.
- Route guards redirect to a designed **"You don't have access"** page. It shows the missing permission's name and "Ask an administrator".

## 4. Screens

### 4.1 Login (UI-001)

```
┌──────────────────────────────────────────────┬─────────────────────────────────────────┐
│                                              │                                         │
│   [warm-hero.jpg, dark gradient overlay]     │   VEDA SPACES           (wordmark)      │
│                                              │                                         │
│   STUDIO WORKSPACE        (eyebrow, cream)   │   Welcome back          (display serif) │
│                                              │   Sign in to continue.  (muted)         │
│   Designing homes,                           │                                         │
│   one relationship at a time.  (serif, 48)   │   EMAIL                                 │
│                                              │   ┌───────────────────────────────────┐ │
│                                              │   │ you@vedaspaces.com                │ │
│                                              │   └───────────────────────────────────┘ │
│                                              │   PASSWORD                  Show        │
│                                              │   ┌───────────────────────────────────┐ │
│                                              │   │ ••••••••••••                      │ │
│                                              │   └───────────────────────────────────┘ │
│                                              │                    Forgot password?     │
│                                              │   ┌───────────────────────────────────┐ │
│                                              │   │          Sign in  →               │ │ copper-strong
│                                              │   └───────────────────────────────────┘ │
│                                              │   ⚠ Email or password is incorrect.     │ (aria-live)
│                                              │                                         │
│                                              │   Staff access only · Privacy           │
└──────────────────────────────────────────────┴─────────────────────────────────────────┘
Mobile: image becomes a 160px banner; form full width.
```

**Behavior:**

- `autocomplete="username"` and `"current-password"`.
- Enter submits. The button shows progress and disables during the request.
- The generic error keeps focus in the password field.
- After 3 failures, a hint appears: "Trouble signing in? Reset your password." After repeated failures from this network, a Turnstile challenge appears (05 §4).
- `?next=` is honored (only relative paths allowed).
- If the response status is `MFA_REQUIRED`, the app routes to the MFA challenge (§4.10). If it is `MFA_ENROLLMENT_EMAIL_SENT`, the app shows the "Check your email" screen (§4.10). No enrollment is possible from the login screen.
- If `must_change_password`, the app routes to a Change password screen with the same layout.
- A "Session expired, please sign in again" banner shows when redirected by 401 `SESSION_INVALID`.

### 4.2 Forgot password and reset (UI-002)

```
Forgot password                          Check your email                       Set a new password
─────────────────                        ─────────────────                      ───────────────────
Enter your work email and we'll          If an account exists for               NEW PASSWORD            Show
send a reset link.                       p***@vedaspaces.com, a link is on      [••••••••••••••     ]
EMAIL [                    ]             its way. It expires in 30 minutes.     ▓▓▓▓▓▓░░ Strong
[ Send reset link → ]                    Didn't get it? Check spam or           ✓ 12+ characters
← Back to sign in                        [Resend] (enabled after 60s)           ✓ Not a common password
                                                                                ✓ Doesn't contain your name
                                                                                CONFIRM   [••••••••••••••     ]
                                                                                [ Update password → ]
Invalid/expired token → "This link has expired or was already used." + [Request a new link]
Success → /login with banner "Password updated. Sign in with your new password."
```

The accept-invite screen reuses the "Set a new password" layout with the title "Welcome to Veda Spaces, Ravi" and an optional name confirmation.

### 4.3 Lead dashboard (UI-003, LEAD-014)

```
Desktop
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ OVERVIEW                                                  [ Last 30 days ▾ ]  [+ New lead]  │
│ Good morning, Priya                                     (display serif)                     │
├──────────────┬──────────────┬──────────────┬──────────────┬─────────────────────────────────┤
│ NEW LEADS    │ FOLLOW-UPS   │ OVERDUE      │ CONVERSION   │ FIRST CONTACT (median)          │
│ 38           │ 6 today      │ 2            │ 30%          │ 3.5 h                           │
│ ▲ 31% vs prev│ View →       │ View → (amber)│ 3 won · 7 lost│ target < 4 h                  │
├──────────────┴──────────────┴──────────────┴──────────────┴─────────────────────────────────┤
│ PIPELINE                                                                                    │
│ New 12 ▕██████████████▏ Contacted 9 ▕██████████▏ Site visit 5 ▕██████▏ Quote 4 ▕████▏ Neg 3 ▕███▏│
│ (click a segment → Leads list filtered)                                                     │
├────────────────────────────────────────────────┬────────────────────────────────────────────┤
│ MY FOLLOW-UPS                         See all → │ UNASSIGNED (4)            <vs-can lead.assign>│
│ ● 11:00  Site measurement · Anita Reddy        │ Rahul M · Full home · Kondapur · 2h  [Assign▾]│
│          VS-L-2026-000123 · Gachibowli  [✓][⋯] │ …                                          │
│ ● 15:30  Call back · S. Iyer    OVERDUE (amber) │                                            │
├────────────────────────────────────────────────┼────────────────────────────────────────────┤
│ RECENT LEADS                                   │ LEADS BY SOURCE                             │
│ table: # · Name · Type · Status · Owner · Age  │ Website ██████████ 21                       │
│                                                │ Referral ████ 9 · Instagram ███ 6 · …       │
└────────────────────────────────────────────────┴────────────────────────────────────────────┘
Mobile: KPI tiles become a 2×2 swipeable grid; Follow-ups first (primary Sales job); pipeline as a vertical bar list.
```

**Leads list (dashboard → "Leads"):**

```
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ Leads                                                  [Board | List]         [+ New lead]    │
│ [🔍 Search name, phone, email, VS-L-…     ] [Status ▾][Owner: Me ▾][Type ▾][Budget ▾][Source ▾]│
│ [Follow-up: Overdue ✕] [Clear all]                                    Saved view: My open ▾   │
├───┬───────────────────┬──────────────────┬──────────────┬─────────────┬────────┬───────┬──────┤
│ ☐ │ LEAD              │ PROJECT          │ STATUS       │ NEXT        │ OWNER  │ SOURCE│ AGE  │
├───┼───────────────────┼──────────────────┼──────────────┼─────────────┼────────┼───────┼──────┤
│ ☐ │ Anita Reddy       │ Modular Kitchen  │ ● Site visit │ Tomorrow 11 │ (PS)   │ Web   │ 4d   │
│   │ VS-L-…0123 · Gachibowli · ₹5–10 L    │              │             │        │       │      │
│ ☐ │ Rahul Menon  ⚠dup │ Full home        │ ● New        │ —           │ Unassigned│Ref │ 2h   │
└───┴───────────────────┴──────────────────┴──────────────┴─────────────┴────────┴───────┴──────┘
  25 per page · 1–25 of 132 · ‹ 1 2 3 … 6 ›
Board view: columns per open status (drag = status change → opens transition dialog when inputs required).
Mobile: rows become cards (name, status pill, project, next follow-up, call/WhatsApp buttons).
```

Filters sync to the URL query (shareable, back-button friendly) and map 1:1 to API params (08 §8.2).

**Spam review queue (LEAD-018).** A "Spam review (n)" chip appears for holders of `lead.update` at ALL scope. It lists `spam_status = SUSPECTED` leads with [Not spam] and [Confirm spam] actions (04 §5.5). Quarantined leads never appear in normal lists or dashboard counts.

### 4.4 Lead details (UI-004, ACT-005)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ ← Leads   VS-L-2026-000123                                             [⋯ Delete · Copy link]│
│ Anita Reddy                               (title serif)       ● HIGH   Owner (PS) Priya ▾   │
│ +91 98765 43210 [📞][WhatsApp] · anita@example.com · Gachibowli, Hyderabad                  │
│                                                                                             │
│  NEW ─── CONTACTED ─── ◉ SITE VISIT ─── QUOTATION SENT ─── NEGOTIATION ─── WON              │
│  [ Move to Quotation sent → ]   [ Mark as Lost ]                     (allowed_transitions)   │
├───────────────────────────────┬─────────────────────────────────────────┬───────────────────┤
│ DETAILS              [Edit]   │ [Timeline] [Notes 4] [History*]         │ NEXT UP           │
│ Project   Modular Kitchen     │ ┌─────────────────────────────────────┐ │ ● Tomorrow 11:00  │
│ Property  Apartment / Flat    │ │ Log: [Call][WhatsApp][Meeting][Visit]│ │ Site measurement │
│ Budget    ₹5–10 L             │ │      [Plan follow-up]               │ │ [Complete][⋯]     │
│ City      Hyderabad           │ └─────────────────────────────────────┘ │ ─────────────     │
│ Source    Website · instagram │ 28 Sep · Priya · CALL · Outbound 12m    │ ⚠ POSSIBLE        │
│           / diwali-2026       │   Discussed scope… Outcome: Visit sched.│ DUPLICATE         │
│ Created   25 Sep, 7:32 pm     │ 27 Sep · Priya · Status Contacted →     │ VS-L-…0098 (Lost) │
│           by Website          │   Site visit                            │ [Review]          │
│ Consent   ✓ 25 Sep (v1)       │ 26 Sep · Ravi → assigned to Priya       │ ─────────────     │
│                               │ 25 Sep · Website · Enquiry received     │ ENQUIRY MESSAGE   │
│ PINNED NOTE                   │   "3BHK handover in December…"          │ "3BHK handover…"  │
│ Wants handle-less shutters…   │                                         │                   │
└───────────────────────────────┴─────────────────────────────────────────┴───────────────────┘
* History tab only with audit.read (audit diffs of lead + notes + activities)
Mobile: header + stepper (horizontal scroll) + sticky bottom action bar [Call][WhatsApp][Log][Move ▸];
        sections become accordion: Next up → Timeline → Details → Notes.
```

**Interactions:**

- **Status transition dialog.** It asks only for required inputs per 04 §3: lost reason (select) plus note, or a comment for backward moves. It shows what will happen ("3 planned follow-ups will be cancelled").
- **Call / WhatsApp buttons.** They open `tel:` or `https://wa.me/<e164>`. On return (visibility change), a **quick-log sheet** slides up prefilled (type, outbound, now) with outcome chips. One tap saves (ACT-005).
- **Plan follow-up.** Quick picks (Later today · Tomorrow 11:00 · In 3 days · Next week), a custom date-time, and an owner (defaults to the lead owner).
- **Inline editing** of details happens in a drawer, with `If-Match` conflict handling.
- **Consent withdrawn (LEAD-027).** A persistent "Do not contact" banner appears. The Call and WhatsApp buttons require an acknowledgment, and planning contact activities is blocked. [Record withdrawal…] sits in the ⋯ menu (`lead.update`).
- **Erase personal data (LEAD-029).** In the ⋯ menu for `lead.erase` holders. It requires step-up, a request reference and typing the lead number. This cannot be undone.
- **Unmapped intake values.** If `intake_unmapped` is present, an info chip reads "Website sent an unrecognized property type: 'Farmhouse'", with a quick-fix picker (LEAD-030).

### 4.5 Lead create and edit (UI-005)

```
┌──────────────────────── New lead (drawer 560px / full-screen mobile) ──────────────────────┐
│ CONTACT                                                                                     │
│ Full name *        [                                  ]                                     │
│ Phone *            [ +91 ▾ ][ 98765 43210            ]   ⚠ Possible duplicate:              │
│ Email              [                                  ]     VS-L-2026-000098 · Anita R ·     │
│                                                              Lost · 2 months ago [Open]     │
│ PROJECT                                                                                     │
│ Project type       [ Modular Kitchen            ▾ ]   Property type [ Apartment / Flat ▾ ]  │
│ Budget range       [ ₹5–10 L                    ▾ ]                                          │
│ City               [ Hyderabad                  ▾ ]   Area / locality [ Gachibowli       ]  │
│ Message / brief    [                                                                    ]   │
│                                                                                             │
│ SOURCE & OWNERSHIP                                                                          │
│ Source *           [ Referral ▾ ]   Detail [ Mr. Rao (existing client)                 ]   │
│ Priority           ( High ) ( Medium ) ( Low )                                              │
│ Assign to          [ Me (Priya) ▾ ]      <vs-can lead.assign> else fixed to "Me" </vs-can>  │
│ First note         [ Prefers calls after 6pm                                            ]   │
│                                                                                             │
│                                                      [ Cancel ]   [ Create lead → ]         │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Behavior:**

- The duplicate check runs on phone or email blur (`GET /leads/duplicates`). It warns but never blocks.
- Edit mode uses the same form, without the "First note" and "Assign to" fields (assignment has its own action). Status isn't editable here.
- Unsaved-changes guard on close.
- Field errors map from `errors[].field`.

### 4.6 User management (UI-006)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ ADMIN                                                                                       │
│ Users                                                                   [+ Invite user]     │
│ [🔍 Search name or email ] [Status: Active ▾] [Role ▾]                       Show deleted ☐ │
├──────────────────────────────┬──────────────────┬───────────┬──────────────┬────────────────┤
│ USER                         │ ROLES            │ STATUS    │ LAST SIGN-IN │ MFA            │
├──────────────────────────────┼──────────────────┼───────────┼──────────────┼────────────────┤
│ (PS) Priya Sharma            │ Sales            │ ● Active  │ 2 h ago      │ ✓ On  ⋯        │
│      priya@vedaspaces.com    │                  │           │              │                │
│ (RK) Ravi Kumar              │ Sales, Admin⏱    │ ○ Invited │ —            │ Required ⋯     │
│ (AN) Anand N                 │ Admin            │ 🔒 Locked │ 1 d ago      │ ✓ On  ⋯        │
└──────────────────────────────┴──────────────────┴───────────┴──────────────┴────────────────┘
⏱ = time-bound assignment. This is a **P1 surface** (RBAC-007), hidden in P0. ★ = FOUNDER-protected account.

User drawer
┌──────────────────────────────── Priya Sharma ──────────────────── [⋯] ┐
│ [Profile] [Access] [Security] [Sessions] [Activity]                   │
│ Access tab:                                                           │
│  ROLES                                              [Edit roles]      │
│   Sales                         since 1 Sep                           │
│  DIRECT PERMISSIONS                                 [+ Add exception] │
│   GRANT lead.read · ALL · "Covering for Ravi"                  [✕]    │
│   DENY  lead.export                  · "Policy"                [✕]    │
│  EFFECTIVE PERMISSIONS (explain)                                      │
│   lead.read  ALL   ← Sales (OWN), Direct grant (ALL)                  │
│   …                                                                   │
│ Security tab (account-control actions; each shown only with its      │
│ permission, and disabled with a reason when a guard applies):        │
│   Sign-in email: priya@vedaspaces.com  ✓ verified                    │
│     [Change email…] (user.email.change · step-up · verification      │
│      sent to the NEW address · alert to the current address;         │
│      privileged target → "Needs approval")                           │
│   Status: Active   [Deactivate…] (user.status.manage · step-up)      │
│   MFA: ✓ enrolled (Authenticator app, since 2 Sep)                   │
│     Required by: role policy · [Require MFA for this user ☑]         │
│     (user.mfa.require)                                                │
│     [Reset MFA…] (user.mfa.reset · step-up · reason · privileged     │
│      target → approval by a second admin)                            │
│   Sensitive permissions: 2 ⚠ Pending MFA (suspended until enrolled)  │
│   Security events for this user (only with security_event.read)      │
│ Sessions tab: device, location, last seen [Revoke] · [Revoke all]    │
│ Activity tab: audit entries performed_by this user (needs audit.read) │
│ ⋯ menu: Send password reset (to verified email) · Delete (user.delete)│
└───────────────────────────────────────────────────────────────────────┘
```

**Guards in the UI:**

- Your own row shows "You can't change your own access" on the Access tab (G3).
- Roles the actor can't grant are shown disabled with "Includes permissions you don't have" (G1/G2).
- Deactivating the last administrator shows a server `LAST_ADMINISTRATOR` explanation dialog (G4).
- **Reset MFA** opens a dialog with an identity-verification checklist and a required reason, after step-up (G10).
  - It is disabled with an explanation for your own account (G3), for accounts holding permissions you lack (G9) and for Founder accounts: "Founder accounts use the Founder workflow" (G11).
  - For a privileged target, the confirmation reads "This request needs approval by another administrator" and ends in the Approvals inbox (§4.12).
- **Deactivate** is not available on your own row (G3) or on Founder rows (G11). For the last Founder or the last recovery administrator, the server explains `LAST_FOUNDER` / `LAST_ADMINISTRATOR` (G4).
- **Change email** never edits the address in place. The dialog explains the two emails that will be sent, and the row shows "Email change pending" until verification.
- Profile fields (name, display name, phone, timezone, locale) are edited on the Profile tab with `user.profile.update`. That form has no email, status, role or MFA fields.
- The MFA column shows **Required** (policy requires it, not enrolled yet), **✓ On** (enrolled), **Optional** (not required, not enrolled) or **✓ On (optional)**.

### 4.7 Role management (UI-007)

```
┌──────────────────────┬──────────────────────────────────────────────────────────────────────┐
│ Roles     [+ New]    │ Sales                               SYSTEM ROLE      [Save changes]  │
│                      │ Sales & design consultants · 4 users [View users]                    │
│ ● Founder   (1) SYS  │ [🔍 Filter permissions ]  [Module: All ▾]  ☐ Show only granted      │
│ ● Admin     (1) SYS  ├───────────────────────────────┬────────┬──────────────────────────────┤
│ ◉ Sales     (4) SYS  │ PERMISSION                    │ GRANT  │ SCOPE                        │
│ ○ Sales Mgr (0)      ├───────────────────────────────┼────────┼──────────────────────────────┤
│                      │ CRM › LEADS                                                          │
│                      │ Create leads   lead.create    │  [✓]   │ —                            │
│                      │ View leads     lead.read      │  [✓]   │ ( All ) (•Own) ( Team ⊘ )    │
│                      │ Edit leads     lead.update    │  [✓]   │ ( All ) (•Own)               │
│                      │ Assign leads   lead.assign    │  [ ]   │                              │
│                      │ Delete leads 🔒 lead.delete   │  [ ]   │                              │
│                      │ PLATFORM › USERS                                                     │
│                      │ …                                                                    │
│                      ├──────────────────────────────────────────────────────────────────────┤
│                      │ 2 unsaved changes: + lead.assign (All), lead.read Own → All          │
│                      │ Reason *  [ Promote Sales to handle intake queue during Diwali ]     │
│                      │                                         [Discard]  [Save changes]    │
└──────────────────────┴──────────────────────────────────────────────────────────────────────┘
```

**Behavior:**

- The matrix is grouped by module › resource, with human names first and codes secondary (mono).
- Changes are staged and saved as one `PUT` with a diff summary.
- Sensitive permissions (🔒) and scope escalations require a reason.
- Team scope is shown disabled with the tooltip "Available when teams are introduced".
- Codes the actor doesn't hold are disabled (G2).
- A "Compare roles" view (P1) shows a side-by-side matrix.

### 4.8 Permission management (UI-008)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ Permissions                              Permissions are defined by the platform. You can   │
│                                          edit descriptions and see who has access.          │
│ [🔍 Search ] [Module ▾] [Sensitive only ☐]                                                  │
├──────────────────────────┬─────────────────────────────┬────────┬──────────────┬────────────┤
│ PERMISSION               │ CODE                        │ SCOPE  │ ROLES        │ REQ        │
├──────────────────────────┼─────────────────────────────┼────────┼──────────────┼────────────┤
│ Change lead status       │ lead.status.change          │ Yes    │ F·A·S        │ LEAD-005   │
│ Delete leads 🔒          │ lead.delete                 │ Yes    │ F·A          │ LEAD-016   │
└──────────────────────────┴─────────────────────────────┴────────┴──────────────┴────────────┘
Detail drawer: description [Edit — needs permission.manage] · granted to roles (scope) ·
               effective holders (user, scope, via role/direct) · direct exceptions list · recent changes (audit)
```

### 4.9 Audit log viewer (UI-009, AUDIT-008)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ Audit log                                                                  [Security events]│
│ [Entity: Lead ▾][🔍 Record id / VS-L-… ][Action ▾][By: Anyone ▾][Via ▾][ 1 Sep – 29 Sep ▾] │
├────────────────────┬──────────────────┬─────────┬───────────────────────────┬───────────────┤
│ WHEN               │ WHO              │ ACTION  │ RECORD                    │ CHANGES       │
├────────────────────┼──────────────────┼─────────┼───────────────────────────┼───────────────┤
│ 29 Sep, 3:32:11 pm │ Priya            │ UPDATE  │ Lead VS-L-…0123 Anita R.  │ status, lost… │
│ 29 Sep, 3:32:11 pm │ Priya            │ CREATE  │ Activity on VS-L-…0123    │ Status change │
│ 29 Sep, 3:10:02 pm │ Website (system) │ CREATE  │ Lead VS-L-…0131           │ 14 fields     │
│ 28 Sep, 9:02:40 am │ Anand            │ UPDATE  │ Role Sales                │ permissions   │
└────────────────────┴──────────────────┴─────────┴───────────────────────────┴───────────────┘
                                   [ Load more ]  (cursor)

Detail panel (right drawer)
┌───────────────────────────── UPDATE · Lead VS-L-2026-000123 ─────────────────────────────┐
│ By Priya Sharma · 29 Sep 2026, 3:32:11.004 pm IST · via API                               │
│ Request 8c2f1e0a9b7d4c3e [copy] · Transaction 0192a50e… [view all 3 changes]              │
│ IP 49.205.x.x · Chrome 129 on Android                                                     │
│ Reason: Client chose competitor                                                           │
│ ┌────────────────────┬──────────────────────────┬──────────────────────────┐              │
│ │ FIELD              │ BEFORE                   │ AFTER                    │              │
│ ├────────────────────┼──────────────────────────┼──────────────────────────┤              │
│ │ Status             │ Negotiation              │ Lost                     │ (red/green   │
│ │ Lost reason        │ —                        │ Chose competitor         │  tinted, plus│
│ │ Lost on            │ —                        │ 29 Sep 2026, 3:32 pm     │  − / + marks)│
│ └────────────────────┴──────────────────────────┴──────────────────────────┘              │
│ [Open record →]                                          [View raw JSON]                  │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

**Behavior:**

- Field names are shown in human form, with lookup ids resolved to labels.
- Redacted values show as "•••• (changed)".
- The "Security events" tab (`security_event_log`) is shown with `security_event.read` at scope ALL. It has its own filters (event type, outcome, severity, subject, IP) and never displays hashes or chain columns.
- It is read-only. There are no actions that mutate.
- Deep links (`/audit?entity_type=lead&entity_id=…`) are used by the "History" tab and the user Activity tab.

### 4.10 MFA challenge, enrollment and recovery (UI-015, MFA-001, MFA-005, MFA-013, MFA-014)

```
Two-step verification                         Set up two-step verification
──────────────────────                        ─────────────────────────────
Enter the 6-digit code from your              Reached by: invite acceptance · the emailed setup link
authenticator app.                            (after password re-entry) · Profile › Security
CODE [ ______ ] (one field; autocomplete=     (after "Confirm your password") · recovery session
      one-time-code, inputmode=numeric)       1 Install an authenticator app
[ Verify → ]                                  2 Scan ┌──────┐  Can't scan? Key shown once
Lost your authenticator? Use a recovery code        └──────┘
⚠ That code didn't work. 3 attempts left.     3 Enter code [ ______ ]   [ Confirm → ]
  (aria-live=assertive; focus returns to input)

Check your email (MFA required, no authenticator yet)
"We've sent a secure setup link to p***@vedaspaces.com. It expires in 30 minutes."
(No setup is possible on this screen: a password alone never enrolls an authenticator.)

Recover your account                          Recovery mode (restricted)
────────────────────                          ──────────────────────────
Re-enter your password  [ •••••••• ]          Banner: "You're in recovery mode. You can only set up a
Recovery code           [ XXXXX-XXXXX ]       new authenticator. All your other sessions were signed out,
[ Recover → ]                                 and we've emailed you about this."
Uniform error: "Password or recovery          [ Set up new authenticator → ]   [ Sign out ]
code is incorrect."

Save your new recovery codes (shown once)     After recovery (cooling-off banner, role="status")
K7M3Q-9TDXR  P2W8N-4HJCQ  … (10)              "For your security, email, password and access changes
[Download .txt] [Copy] [Print]                 are locked until 30 Sep, 11:02 am."
☐ I have saved these codes   [ Continue → ]
```

**Behavior:**

- A single code field, so paste and password managers work.
- Recovery requires **both** password re-entry and a recovery code (owner Decision 2).
- The recovery-mode shell shows only the setup action and sign-out. Navigation and data screens aren't rendered.
- Step-up reuses the challenge component in a modal titled "Confirm it's you". For users without MFA, the "Confirm your password" modal is used instead.
- Profile › Security shows own MFA status, lets the user regenerate recovery codes (step-up, not during cooling-off), and allows removing the factor only when policy doesn't require it.
- **It shows no security-event history for users without `security_event.read`** (owner Decision 1). The standard Sales profile has no such panel.

### 4.11 Public enquiry form states (website, LEAD-026, ADR-005)

This design is for the live site's contact form when LEAD-001 is implemented. It keeps the site's existing styling.

| State | Behavior |
|---|---|
| Fields | Required: Name, Phone, the consent checkbox. Optional, labelled "(optional)": Email, City, Service Required, **Property Type** (Apartment / Flat, Independent House, Villa, Office, Retail / Shop, Other), Budget, Message. |
| Required marking | "Required" in text plus `aria-required="true"` |
| Labels | Every control has a visible `<label>` bound by `for`/`id`. Selects start with a "Choose…" option that is not submitted. |
| Honeypot | Field `company_website_url`, off-screen, `tabindex="-1"`, `autocomplete="off"`, `aria-hidden="true"` (04 §5.1). It never receives focus and is never announced. |
| Consent | Unchecked by default. "I agree to be contacted by Veda Spaces about my enquiry, as described in the Privacy Notice (v2026-09-v1)." |
| Client validation | On submit. It mirrors server codes. |
| Error state (field-level 422) | 1. An error summary at the top (`role="alert"`, "Please fix 2 things") linking to each field. 2. Focus moves to the summary. 3. Inline text per field with `aria-invalid` and `aria-describedby`. 4. Text plus icon, not color alone. |
| CAPTCHA failure, rate limit, 428/413, 5xx, network error or 8-second timeout | A message plus a **prominent WhatsApp button** with the prefilled enquiry (LEAD-019, F-05). Nothing ends without a stored lead or a WhatsApp route. |
| Submitting | The button is disabled with "Sending…", and the form sets `aria-busy="true"` |
| Success | The panel replaces the form (`role="status"`, focus on its heading): "Thank you. Your reference is **K7M3-Q9TD**…" plus an optional WhatsApp link. The success view is identical for every 201. |

### 4.12 Approvals inbox (RBAC-021, MFA-015)

```
Approvals                                                   [Pending for me (2)] [Requested by me]
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ MFA reset · Anand N (Admin, privileged)  · requested by Ravi · 2 h ago · expires in 22 h      │
│   Reason: "Lost phone; verified by video call"                     [Deny…]  [Approve…]         │
│ Email change · Priya S → p***@gmail.com · requested by Ravi · 10 min ago                      │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Behavior:**

- Approve and deny require step-up and a reason.
- Your own requests and requests about you show "You can't decide this request" (06 §7.4).
- Founder-level requests appear only to users eligible to decide them under 06 §7.2.3. They are never shown as approvable to the requester or the target.
- The request dialog shows the operating mode. In single-Founder mode it reads "Approval by a break-glass custodian; executes no earlier than …".
- **The role editor and user Access tab show the FOUNDER role and `user.founder.manage` as locked** ("Founder governance only"), with a link to the Founder-actions page (G13).
- A top-bar badge shows the pending count, from the `approvals` endpoint (08 §5.11).

### 4.13 Email change, self-service (USER-007)

- Profile › Sign-in email › [Change…] opens step-up (MFA, or password for non-MFA users), then asks for the new address.
- A confirmation panel explains: "We've sent a verification link to the new address. Your current address p***@… stays active for sign-in and password recovery until you verify. We've also alerted your current address."
- The pending state shows on the profile with [Cancel change].
- Completion signs out all sessions, with a banner on the next sign-in.
- During cooling-off the action is disabled, with the end time shown.

## 5. Accessibility (UI-011, UI-016)

Standard: WCAG 2.2 AA. Every criterion below is **testable** and mapped to a test in 12 §4.8.

| ID | Area | Testable criterion | How verified |
|---|---|---|---|
| AX-01 | Keyboard navigation | Every interactive element is reachable and operable by keyboard in a logical order. There are no keyboard traps except modal focus-traps, which release on close and `Esc`. Tables support arrow-key row navigation. | Playwright keyboard-only journeys: login, MFA challenge, recovery, enrollment, lead create, lead status change, public form |
| AX-02 | Visible focus | Focus indicator = `--vs-focus-ring` 2 px + 2 px offset, ≥ 3:1 against adjacent colors in both themes, never obscured by sticky headers (2.4.11) | Token contrast test + visual check in E2E screenshots |
| AX-03 | Error announcements | Form errors: summary with `role="alert"`, focus moved to the summary, and each field linked with `aria-describedby`. Async results use `aria-live` (polite for status, assertive for MFA failures). | axe + a scripted assertion of `aria-*` attributes and focus location after a failed submit |
| AX-04 | Form labels | Every input has a programmatic label. Required fields use `aria-required` plus text. Autocomplete tokens: `username`, `current-password`, `new-password`, `one-time-code`, `email`, `tel`. | axe `label` rules + attribute assertions |
| AX-05 | Contrast | Text ≥ 4.5:1 and non-text ≥ 3:1 for every token pair in **light and dark** themes (§2.5) | Automated token-pair contrast test (fails the build) |
| AX-06 | Mobile | Lead list, lead details, activity logging, login, MFA and the public form are fully usable at 320–360 px width without horizontal scroll. Targets ≥ 44×44 px (≥ 24 px minimum per 2.5.8). Works at 200% zoom. | Playwright at 360×800 (Android Chrome) and 390×844 (iOS Safari/WebKit) + target-size assertion |
| AX-07 | Login and MFA flows | The code field uses `inputmode="numeric"` and `autocomplete="one-time-code"`. Remaining attempts are announced. Time-outs are announced before expiry. Recovery and enrollment are operable by screen reader. | axe + NVDA/VoiceOver manual script, once per release |
| AX-08 | Public lead form | AX-01…AX-05 apply. The honeypot is never focusable or announced. Success and fallback panels receive focus and are announced. | axe on the form's idle, error, success and fallback states + keyboard journey |
| AX-09 | Admin lead workflow | Status stepper exposed as an ordered list with `aria-current`. Transition dialog labelled. Drag-and-drop on the board has a keyboard alternative (move menu). | axe + keyboard journey on board and detail |
| AX-10 | Motion and language | `prefers-reduced-motion` respected. `lang="en-IN"`. Dates and numbers use Intl in the user's timezone (03 §2.2). | Unit tests on formatting + a reduced-motion snapshot |

## 6. Screen → API → permission map

| Screen | Primary APIs | Permissions to see / act |
|---|---|---|
| Login / forgot / reset / invite | 08 §4 | public |
| Dashboard | `/leads/summary`, `/activities?owner=me`, `/leads?assigned_to=unassigned` | `lead.read` · act: `lead.assign`, `lead_activity.update` |
| Leads list / board | `/leads` | `lead.read` · `lead.create` · board drag: `lead.status.change` |
| Lead details | `/leads/{id}`, `/notes`, `/activities`, `/history` | `lead.read` · per action: `lead.update`, `lead.status.change`, `lead.assign`, `lead.delete`, `lead_note.*`, `lead_activity.*`, `audit.read` |
| Lead create / edit | `POST/PATCH /leads`, `/leads/duplicates`, `/lookups`, `/users/assignable` | `lead.create` / `lead.update` |
| Users | `/users*` | `user.read` · actions per 08 §5 |
| Roles | `/roles*`, `/permissions` | `role.read` · `role.manage` |
| Permissions | `/permissions*` | `permission.read` · `permission.manage` |
| Audit viewer | `/audit-logs`, `/security-events` | `audit.read` · `security_event.read` (Founder, Admin; never standard Sales) |
| Approvals inbox | `/approvals*` | the action's permission (06 §7.4) |
| Email change (self) | `/auth/me/email`, `/auth/email/*` | own account (RBX-003/004) |
| MFA challenge / enrollment | `/auth/mfa/*` | challenge token or own session (06 §11) |
| Public enquiry form (website) | `/public/leads` | public (RBX-005) |
