# 09 — UI/UX Design: Veda Workspace

Governing decisions: [ADR-005](decisions/ADR-005-lead-required-fields.md) · [ADR-006](decisions/ADR-006-mfa-policy.md) · [ADR-007](decisions/ADR-007-technology-stack.md)

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
| `--vs-copper-strong` | `#7A4E2E` | `#E0B394` | Primary button background (white text 7.0:1) |
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

These corrections are made **in the design tokens themselves**, so no component can reintroduce the failures. Ratios were computed with the WCAG 2.x relative-luminance formula.

| ID | Token | Problem found | Decision | Ratio on `--vs-paper` `#FBF7EF` |
|---|---|---|---|---|
| A11Y-T1 | `--vs-copper` `#A46D42` | The brand copper is 3.8:1 on the site paper `#F3F0E9` and 4.1:1 on the workspace paper. It fails AA (4.5:1) for normal text. | Restricted to fills, focus rings, icons and text ≥ 24 px (or ≥ 18.66 px bold), where 3:1 applies | 4.1:1 |
| A11Y-T2 | `--vs-copper-text` `#8C5B37` | Copper-colored text was needed | New token, mandatory for copper text and links | 5.4:1 |
| A11Y-T3 | `--vs-copper-strong` `#7A4E2E` | White text on brand copper fails | New token for primary button backgrounds | White text 7.1:1 |
| A11Y-T4 | `--vs-warning` `#8A5E0F` | The first proposal `#9A6A12` was 4.4:1 and failed | Darkened | 5.3:1 |
| A11Y-T5 | Status chip pairs (§2.2) | — | All seven pairs verified | 5.3:1 – 7.9:1 on their chip backgrounds |
| A11Y-T6 | `--vs-focus-ring` = 2 px `--vs-copper` + 2 px offset | Focus visibility | Non-text contrast ≥ 3:1 against paper and surface | 4.1:1 |

A design-system lint rejects raw hex colors in components. Only tokens are allowed.

## 3. Application shell and patterns

### 3.1 Shell layout

> Traces: NOTIF-001, UI-012

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

> Traces: PLAT-007

| Pattern | Spec |
|---|---|
| Command palette (⌘K / Ctrl-K) | Jump to lead by number, name or phone. Navigate to pages. "New lead". Permission-filtered. |
| Drawers | Create and edit forms and details for admin entities open in a right drawer (560 px). This keeps list context. They are full screen on mobile. |
| Toasts | Bottom-center, 4 s, with undo where reversible (for example "Note deleted · Undo" within 8 s, which calls restore) |
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

> Traces: RBAC-012

- `<vs-can permission="lead.assign">…</vs-can>` renders its slot only if the effective map contains the code. An optional `scope-for=${lead}` evaluates OWN ownership client-side.
- **Hide vs disable:**
  - Hide actions the user can never perform.
  - Disable, with a tooltip, those blocked by state ("Mark as Lost — requires a lost reason").
- Lead action menus use the server's `allowed_transitions`, so the UI never duplicates state-machine rules.
- Route guards redirect to a designed **"You don't have access"** page. It shows the missing permission's name and "Ask an administrator".

## 4. Screens

### 4.1 Login (UI-001)

> Traces: AUTH-001

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
- After 3 failures, a hint appears: "Locked out? Reset your password."
- `?next=` is honored (only relative paths allowed).
- If the response status is `MFA_REQUIRED` or `MFA_ENROLLMENT_REQUIRED`, the app routes to the MFA screens (§4.10).
- If `must_change_password`, the app routes to a Change password screen with the same layout.
- A "Session expired, please sign in again" banner shows when redirected by 401 `SESSION_INVALID`.

### 4.2 Forgot password and reset (UI-002)

> Traces: AUTH-003, AUTH-008, AUTH-011

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

> Traces: LEAD-013, LEAD-015

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

### 4.4 Lead details (UI-004, ACT-005)

> Traces: ACT-001, ACT-002, LEAD-005, LEAD-007, LEAD-024, NOTE-001, NOTE-003

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

### 4.5 Lead create and edit (UI-005)

> Traces: LEAD-003, LEAD-010

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

> Traces: AUTH-016, MFA-003, MFA-007, RBAC-006, RBAC-016, USER-001, USER-006

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
⏱ = time-bound assignment (tooltip: "until 15 Oct")

User drawer
┌──────────────────────────────── Priya Sharma ──────────────────── [⋯] ┐
│ [Profile] [Access] [Security] [Sessions] [Activity]                   │
│ Access tab:                                                           │
│  ROLES                                              [Edit roles]      │
│   Sales                         since 1 Sep                           │
│  DIRECT PERMISSIONS                                 [+ Add exception] │
│   GRANT lead.read · ALL · until 15 Oct · "Covering for Ravi"   [✕]    │
│   DENY  lead.export                  · "Policy"                [✕]    │
│  EFFECTIVE PERMISSIONS (explain)                                      │
│   lead.read  ALL   ← Sales (OWN), Direct grant (ALL)                  │
│   …                                                                   │
│ Security tab: MFA ✓ enrolled (Authenticator app, since 2 Sep)         │
│   Required by: role policy · [Require MFA for this user ☑]            │
│   [Reset MFA…] (user.mfa.manage + step-up, reason required)          │
│   Recent sign-in activity (security_event.read)                      │
│ Sessions tab: device, location, last seen [Revoke] · [Revoke all]    │
│ Activity tab: audit entries performed_by this user (needs audit.read) │
│ ⋯ menu: Send password reset · Deactivate · Delete (user.delete)       │
└───────────────────────────────────────────────────────────────────────┘
```

**Guards in the UI:**

- Your own row shows "You can't change your own access" on the Access tab (G3).
- Roles the actor can't grant are shown disabled with "Includes permissions you don't have" (G1/G2).
- Deactivating the last administrator shows a server `LAST_ADMINISTRATOR` explanation dialog (G4).
- **Reset MFA** opens a dialog with an identity-verification checklist and a required reason. It triggers step-up first (G10). It is disabled with an explanation for your own account (G3), and for accounts holding permissions you lack (G9).
- The MFA column shows **Required** (policy requires it, not enrolled yet), **✓ On** (enrolled), **Optional** (not required, not enrolled) or **✓ On (optional)**.

### 4.7 Role management (UI-007)

> Traces: RBAC-008

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

> Traces: SEVT-005

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

### 4.10 MFA challenge and enrollment (UI-015, MFA-001, MFA-005)

> Traces: AUTH-015

```
Two-step verification                         Set up two-step verification (required for your account)
──────────────────────                        ──────────────────────────────────────────────────────────
Enter the 6-digit code from your              1  Install an authenticator app (Google Authenticator,
authenticator app.                                Microsoft Authenticator, 1Password, …)
CODE  [ _ _ _   _ _ _ ]  (autocomplete=        2  Scan this code          ┌──────────┐
      one-time-code, inputmode=numeric)                                   │ QR CODE  │   Can't scan?
[ Verify → ]                                                              └──────────┘   Key: JBSW Y3DP …
Use a recovery code instead                   3  Enter the 6-digit code   [ _ _ _   _ _ _ ]
⚠ That code didn't work. 3 attempts left.     [ Confirm → ]
  (aria-live=assertive; focus returns to input)

Save your recovery codes (shown once)
K7M3Q-9TDXR   P2W8N-4HJCQ   …  (10)
[Download .txt] [Copy] [Print]
☐ I have saved these codes somewhere safe      [ Continue → ]  (disabled until checked)
```

**Behavior:**

- The code input is a single field (not six boxes), so paste and password managers work.
- On a 401, the error names the remaining attempts. On an exhausted challenge, the app returns to sign in.
- The step-up dialog reuses the challenge component in a modal, titled "Confirm it's you".
- Profile › Security lets the user view their MFA status, regenerate recovery codes (with step-up), and remove the factor only when the policy doesn't require it.

### 4.11 Public enquiry form states (website, LEAD-026, ADR-005)

> Traces: LEAD-012, LEAD-023

This design is for the live site's contact form when LEAD-001 is implemented. It keeps the site's existing styling.

| State | Behavior |
|---|---|
| Required fields | Name, Phone and the consent checkbox are marked "Required" in text, not only with an asterisk, and set `aria-required="true"`. All other fields are labelled "(optional)". |
| Consent | Checkbox: "I agree to be contacted by Veda Spaces about my enquiry, as described in the Privacy Notice." It links to the versioned notice. It is unchecked by default. |
| Client validation | Runs on submit, not on each keystroke. It mirrors server codes. |
| Error state | 1. An error summary box at the top of the form (`role="alert"`, heading "Please fix 2 things") that links to each invalid field. 2. Focus moves to the summary. 3. Each invalid field gets inline text ("Enter a valid phone number, e.g. 98765 43210"), `aria-invalid="true"` and `aria-describedby`. 4. Errors are conveyed by text and an icon, not color alone, using `--vs-danger` at ≥ 4.5:1. |
| CAPTCHA failure | Message: "We couldn't verify you're human. Please try again, or message us on WhatsApp." It includes a WhatsApp link. |
| Rate limited | "Too many attempts. Please wait a minute, or message us on WhatsApp." |
| Submitting | The button is disabled with "Sending…". The form sets `aria-busy="true"`. |
| Success | The form is replaced by a confirmation panel (`role="status"`, focus moved to its heading): "Thank you. Your reference is **K7M3-Q9TD**. Our design team will call you within one working day." It offers an optional "Continue on WhatsApp" link. No internal data is shown. |
| API unavailable | A network error, 5xx or an 8 s timeout triggers the **existing WhatsApp hand-off** with prefilled text (LEAD-019). A polite live-region note explains: "We're opening WhatsApp so your enquiry reaches us." |

## 5. Accessibility (UI-011)

| Area | Commitment |
|---|---|
| Standard | WCAG 2.2 AA. axe-core checks in Playwright for every screen (CI gate). |
| Contrast | Tokens in §2 meet 4.5:1 text and 3:1 non-text. Copper text uses `--vs-copper-text`. |
| Keyboard | Everything is reachable. Visible focus ring: 2 px `--vs-copper` + 2 px offset. Tables support arrow-key row navigation. Drawers and dialogs trap focus and restore it on close. `Esc` closes. |
| Screen readers | Web components expose roles and labels. Form errors use `aria-describedby` plus a live region summary. Status pills include text. Timeline is an ordered list. |
| Target size | ≥ 44×44 px on touch (≥ 24 px minimum per 2.5.8) |
| Motion | `prefers-reduced-motion` respected |
| Language | `lang="en-IN"`. Dates and numbers use Intl with the Indian locale. |
| Zoom | Layout works at 200% and on 320 px widths without horizontal scroll |

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
| Audit viewer | `/audit-logs`, `/security-events` | `audit.read` · `security_event.read` |
| MFA challenge / enrollment | `/auth/mfa/*` | challenge token or own session (06 §11) |
| Public enquiry form (website) | `/public/leads` | public (RBX-005) |
