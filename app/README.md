# Veda Workspace (staff SPA)

Lit 3 + TypeScript + Vite single-page app for `app.vedaspaces.com`, built to the certified P0 architecture:
02 §2 (frontend architecture), 09 (UI/UX), 08 (API contract), 05/06 (auth, MFA, RBAC behaviour).

## Run locally

```bash
cd app
nvm use                # Node 22 LTS (.nvmrc; engines ^22.13.0, engine-strict)
npm ci                 # from the public npm registry (.npmrc)
npm run dev            # http://localhost:5173 — proxies /api and /health to http://127.0.0.1:5000
```

Start the Flask API (`api/`) on port 5000 first. The Vite proxy keeps the app same-origin in development, so the
`vs_rt` refresh cookie (`Path=/api/v1/auth`, `SameSite=Strict`) works without CORS.

| Env var | Default | Purpose |
|---|---|---|
| `VITE_API_BASE` | `''` (same origin / dev proxy) | API origin in deployed builds, e.g. `https://api.vedaspaces.com` |
| `VITE_TURNSTILE_SITE_KEY` | unset | Cloudflare Turnstile site key for the login challenge after repeated failures (05 §4). Unset = no widget. |
| `VEDA_API_PROXY` | `http://127.0.0.1:5000` | Dev-server proxy target (dev only) |

## Scripts

| Script | What it does |
|---|---|
| `npm run dev` | Vite dev server with API proxy |
| `npm run build` | `tsc --noEmit` then production build to `dist/` (route-level code splitting) |
| `npm run typecheck` | TypeScript strict type check |
| `npm run lint` | ESLint (typescript-eslint, lit, wc; bans unsafeHTML/unsafeSVG, innerHTML-style sinks, eval) |
| `npm test` | Web Test Runner in headless Chromium (Playwright launcher) |
| `npm run lint:tokens` | Fails on raw colour values outside `src/design-system/tokens.css` (09 §2.5) |
| `npm run test:contrast` | WCAG contrast of every on/background token pair in light and dark themes; fails < 4.5:1 text, < 3:1 non-text (AX-05, F-14) |

Tooling: Node 22 LTS, TypeScript 5.9, Vite 7.3, `@web/test-runner` 1.0, ESLint 10. The first test run needs
`npx playwright install chromium`. Browser journeys (workspace, access control, website intake under the production
CSP, axe) run against a live local stack with `API_PYTHON=../api/.venv/bin/python e2e/run-all.sh`; CI runs the same
script.

## Structure (02 §2.2)

```
app/
├── index.html
├── public/_headers          CSP, HSTS, noindex, cache rules (02 §11.2)   · _redirects  SPA fallback
├── scripts/                 lint-tokens.mjs, contrast.mjs
├── test/                    WTR unit/component tests
└── src/
    ├── main.ts              bootstraps tokens, design system, shell
    ├── core/
    │   ├── api/             ApiClient (single-flight refresh, problem+json, If-Match, step-up hook), DTO types, lookups
    │   ├── auth/            SessionController (refresh on boot, /auth/me, BroadcastChannel sync), step-up coordinator
    │   ├── authz/           @lit/context contexts, permission helpers, <vs-can>, SessionElement base
    │   ├── router/          route table (lazy module chunks), pure guard, ?next= sanitizer
    │   ├── format/          Intl dates in the user's IANA zone, INR, phone
    │   ├── i18n/            externalized strings (English in P0)
    │   └── telemetry/       request-id capture, error reporting hook
    ├── design-system/       tokens.css, shared styles, icons, vs-* primitives
    ├── modules/
    │   ├── auth/            login, MFA challenge/recovery/enrollment (paths A–D), forgot/reset, invite, email verify/cancel, profile
    │   ├── leads/           dashboard, list/board, detail, create/edit drawer, status & activity dialogs, follow-ups
    │   ├── admin/           users (+ account-control drawer), roles matrix, permissions, approvals, Founder actions
    │   └── audit/           audit log + security events viewer
    └── shell/               <vs-app> (context providers, router outlet, nav, top bar), notifications tray,
                             command palette (⌘K), step-up dialog, version-conflict dialog
```

## Behaviour notes

- The access token lives in memory only. On boot the app calls `POST /api/v1/auth/refresh` (cookie) then
  `GET /api/v1/auth/me`. A 401 `TOKEN_EXPIRED` triggers one shared refresh and a single retry.
- UI permission checks are hints; the server is authoritative (RBAC-012). Navigation and routes are gated by the
  effective permission map from `/auth/me`. `X-Authz-Version` changes and 403 `PERMISSION_DENIED` refetch it.
- 403 `STEP_UP_REQUIRED` opens "Confirm it's you" (MFA code or password, per `kind`) and retries the call once.
- 409 `VERSION_CONFLICT` on lead edits opens the conflict dialog (Reload theirs / Re-apply mine).
- RECOVERY sessions render only "Set up new authenticator" and "Sign out".
- Tokens in email links are read from the URL fragment (`#token=…`) and removed from history immediately.
