# Frontend dependency audit: exceptions policy

CI's `security` job audits the frontend (`app/`) in two steps:

| Step | Scope | Rule |
|---|---|---|
| `npm audit --omit=dev` | Production dependencies: everything that can ship in the workspace bundle | **Strict.** Any advisory fails CI. No exceptions, ever. |
| `node scripts/audit-dev.mjs` | All dependencies, including development and test tooling | Any **high** or **critical** advisory fails CI, unless `app/audit-exceptions.json` covers it with a valid exception. |

The checker's own tests (`node --test scripts/audit-dev.test.mjs`) run in the same step.

## When an exception may be granted

Only when all of these are true:

1. The advisory affects a **development-only** dependency. The strict production audit proves this on every run.
2. **No fixed version** exists, and no upgrade of the direct dependency removes the vulnerable package. A downgrade to an old, unmaintained major does not count as a fix.
3. The vulnerable code is **not reachable with untrusted input** in how the tooling is used, and it is not present in any deployed artefact.
4. A permanent fix is identified and tracked: an upgrade when one appears, or replacement of the tooling.

## What an exception must contain

Each entry in `app/audit-exceptions.json`:

- matches exactly one advisory (`advisory`, a GHSA id), one `package` and one vulnerable `range`;
- has `scope: "development"`;
- has a `reason`, `compensating_controls`, `approved_on` and `expires`;
- expires **at most 90 days** after approval.

Adding or extending an exception is a code change, so it goes through pull-request review; merging the PR is the approval. On the expiry date, CI fails until the exception is re-reviewed (a new PR with a new date and reasoning) or removed. When the advisory no longer appears, CI warns that the exception should be removed.

## Current exceptions

### GHSA-vfj7-8cjw-p6xm: `braces` ≤ 3.0.3 (high, CWE-674, CVSS 7.5)

*Stack-exhaustion denial of service through deeply nested brace patterns.* Published 2026-09-18. **No patched version**: `braces` 3.0.3 is the latest release.

**Dependency paths** (from `app/`; all `devDependencies`):

```
@web/test-runner@1.0.0 (dev)
└─ globby@11.1.0 ─ fast-glob@3.3.3 ─ micromatch@4.0.8 ─ braces@3.0.3
@web/test-runner-playwright@1.0.0 (dev) ─ @web/test-runner-core@1.0.0 ─ globby@11.1.0 (same copy)
@open-wc/testing@5 (dev) ─ @open-wc/semantic-dom-diff ─ @web/test-runner-commands ─ @web/test-runner-core ─ (same)
```

`npm audit` reports 13 high findings. They are all this one advisory, propagated up these chains.

**No upgrade path (2026-10-03).** The latest releases of `@web/test-runner` and `@web/test-runner-core` (1.0.0) still require `globby@^11`. The latest `globby` (16.x), `fast-glob` (3.3.3) and `micromatch` (4.0.8) all still depend on `braces`. npm's only suggested "fix" is a major downgrade to `@web/test-runner@0.7.31` (2020), which is rejected.

**Production impact: none.**

- `npm audit --omit=dev`: 0 vulnerabilities. None of the four production dependencies (`lit`, `@lit/context`, `@vaadin/router`, `qrcode-generator`) reaches `braces`.
- Workspace SPA: a fresh `vite build` contains no `braces`, `micromatch`, `fast-glob` or `globby` code (checked for strings unique to `braces`). No file in `app/src` imports them.
- Cloudflare Pages: the build command is `exit 0`. It publishes the committed root `dist/` (the static marketing site) and installs no npm packages. `dist/` contains none of this code.
- API container image: Python only. It is built from `api/` and has no Node dependencies.

**Reachability.** `braces` runs only inside `npm test` (Web Test Runner), developer machines and CI. It expands the glob patterns in the committed `app/web-test-runner.config.mjs` (`test/**/*.test.ts`) and CLI arguments. No untrusted input reaches it. The worst case is a crashed test process, caused by a pattern that someone committed and reviewers approved.

**Compensating controls:** the strict production audit; an exception narrowed to this advisory, package and range; expiry on 2026-12-31; and the tracked permanent fix below.

**Permanent fix (tracked):** replace `@web/test-runner` and `@open-wc/testing` with a runner that does not depend on `braces`. Vitest browser mode uses `tinyglobby`/`picomatch`. That means porting the 6 test files in `app/test/` off `@open-wc/testing` fixtures and assertions. Alternatively, upgrade as soon as `braces` or the `@web/*` packages ship a fix.
