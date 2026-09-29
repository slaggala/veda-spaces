# Merge-safety plan: implementation branch vs. the live site (OD-5)

> **Status: PLAN ONLY. The owner's merge-safety decision is PENDING.**
> - Nothing in this document has been executed: no merge, no deployment, and no DNS or Cloudflare change.
> - Intake has not been enabled.
> - Reviewed implementation: `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`. Live site: `main` at `13276a0`.

## 1. The hazard

- **A merge to `main` is a production site release.**
  - Cloudflare Pages publishes `dist/` from `main` to `https://www.vedaspaces.com` about a minute after any push or merge (`README.md` "Deploy with Cloudflare Pages", `deployment.md`).
  - The build command is `exit 0`, so no gate sits between a merge and production.
- **What the branch changes in `dist/` compared with the live site** (`git diff --stat origin/main -- dist/`):

  | File | Change |
  |---|---|
  | `dist/_headers` | Adds a site-wide **Content-Security-Policy**. The live site sends **no CSP today**; its other security headers are unchanged. |
  | `dist/index.html` | Enquiry-form markup, empty intake metas, and hidden consent and verification blocks. |
  | `dist/assets/app.js` | Progressive-enhancement intake, plus the flag-off validation from RR-11. |
  | `dist/assets/enhancements.css` | Form styles. |
  | `dist/404.html` and the new `dist/assets/404.css` | 404 styles moved to a stylesheet (RR-01). |

- The API and the SPA are **not** deployed by a merge: no pipeline exists for them.

## 2. Preconditions for any merge (all options)

All of these must hold before any merge. None holds yet unless it says so.

1. The final targeted check verdict is recorded: CERTIFIED WITH TECHNICAL CONDITIONS, at `56c20ba`. **This holds.**
2. The document-level check of this closure increment has passed.
3. **TG-01 is PASS.** The gate registry marks it as blocking the merge (FC-A03).
4. **TG-08** is PASS, as the owner requires.
5. The owner has decided every amendment required before merge (see the owner decision package): AM-1…AM-7 and AM-11…AM-13, including acceptance of AM-4's labelled gaps. OD-2 and OD-3 are confirmed in a decision record.
6. The owner has chosen and approved an option below.
7. The intake metas `veda-api-base` and `veda-turnstile-sitekey` are empty in the merged `dist/index.html`.
8. The public enquiry API stays disabled. The WhatsApp fallback keeps working.
9. The custom domains, DNS and redirect rules are untouched.

## 3. Options (none executed)

### Option A: release the site change first, then merge

The site change goes out as its own reviewed release. The later implementation merge then carries no `dist/` change.

- **Preconditions:** §2, plus owner approval to change the live site. This includes the new CSP and the new form behaviour.
- **Repository changes:**
  1. Create a `site/p0-csp-404-form-validation` branch from `origin/main`.
  2. Run `git checkout <reviewed-sha> -- dist/` on it and commit.
  3. Merge that branch to `main` as the site release.
  4. Later, merge the implementation. `git diff main -- dist/` must be empty at that point.
- **Cloudflare:** the first merge deploys the new `dist/` to production. That deployment is intended. No settings change.
- **Verification:**
  - On the preview deployment:
    - `app/e2e/site.e2e.mjs`;
    - 0 CSP violations on `/`, `/404.html` and a missing path;
    - HTTP 404 for the missing path;
    - the flag-off form validation;
    - WhatsApp opens;
    - a phone check.
  - After the site release:
    - the `deployment.md` post-deployment checks;
    - `git diff main -- dist/` is empty before the second merge.
- **Rollback:** Cloudflare "Rollback to this deployment", then `git revert` the site commit on `main`.
- **Risks:** the live site's behaviour changes: a CSP is added for the first time, and the form now validates. A CSP mistake would break the live site; the preview check mitigates this.
- **Owner action:** approve a production site release.
- **Evidence required:**
  - the preview URL and E2E output;
  - the post-deployment validation;
  - the Pages deployment id.

### Option B: pause production auto-deployment around the merge

- **Preconditions:** §2, plus owner approval of a Cloudflare setting change and someone responsible for re-enabling it.
- **Repository changes:** none before the merge.
- **Cloudflare:**
  1. Pages → Settings → Builds & deployments. Pause automatic production deployments for the `main` branch.
  2. Merge.
  3. Either promote the merged deployment manually after a preview check, or keep the previous deployment live.
  4. Re-enable automatic deployments.
- **Verification:**
  - Pages shows no new production deployment after the merge.
  - The live site's response headers and `404.html` are unchanged.
  - The setting is recorded as re-enabled.
- **Rollback:** re-enable the setting. The live deployment is untouched unless someone promotes the new one.
- **Risks:**
  - If nobody re-enables the setting, later fixes to `main` never reach production.
  - Anyone who can promote could ship the untested site.
  - The approach depends on Cloudflare UI behaviour that has not been checked here.
- **Owner action:** approve and perform the setting change; decide separately whether to promote.
- **Evidence required:**
  - screenshots or an audit-log entry of the setting before, during and after;
  - the Pages deployment list showing no unintended production deployment.

### Option C: merge without the branch's `dist/` changes (recommended)

- **Preconditions:** §2.
- **Repository changes:**
  1. Create a `merge-prep/p0-foundation` branch from the reviewed implementation commit.
  2. Run `git checkout origin/main -- dist/` so `dist/` is byte-identical to the live site.
  3. Commit "Keep live site unchanged for the implementation merge".
  4. Check that `git diff origin/main -- dist/` is **empty**.
  5. Merge `merge-prep` to `main`.
  6. Release the site changes (RR-01, RR-11 and the CSP) later, with option A, as a separate owner-approved release.
- **Cloudflare:**
  - The merge triggers a Pages deployment whose `dist/` is identical to the live one.
  - This is the only Cloudflare activity; no setting changes.
- **Verification:**
  - Before the merge:
    - `git diff origin/main -- dist/` is empty;
    - the checksums of `dist/` match `origin/main`;
    - CI passes on `merge-prep`.
  - After the merge, the live responses are unchanged:
    - `/` returns the same body hash;
    - `/404.html` still uses the inline style, as live today;
    - the headers still have no CSP;
    - the form still hands off to WhatsApp.
- **Rollback:** `git revert` the merge. The site is unaffected either way.
- **Risks:**
  - The site fixes (RR-01, RR-11) and the CSP wait for their own release.
  - The browser tests of the implementation branch describe the new site, not the live one. They must run against the site release when it happens.
  - **Integrity:** the tree that is merged is no longer byte-identical to the reviewed tree. The only difference is `dist/`, restored to `main`'s content, so the check is that `git diff 6ec2e76 merge-prep -- ':!dist'` is empty, plus the closure commit.
- **Owner action:** approve option C and, later, the separate site release.
- **Evidence required:**
  - the empty `dist/` diff;
  - the CI run on `merge-prep`;
  - the before and after comparison of the live site.

## 4. Recommendation

**Option C.** It is the only option that meets all of these at once:
- the current public website stays exactly as it is, with no header change;
- the lead API stays disabled;
- the WhatsApp fallback keeps working;
- the custom domain is untouched;
- there is no production release by accident;
- no Cloudflare setting changes.

The site improvements then follow as a deliberate option A release that the owner approves on its own merits.

I recommend option C but have not executed it. The merge-safety decision is **PENDING**.

## 5. Rollback reference

- **Site:** `deployment.md` → Rollback procedure. It is instant, to the previous Pages deployment. Then revert the commit on `main`.
- **API:** nothing is deployed. When it is, follow `docs/operations/api-runbooks.md` §2. The floors are `RELEASE_FLOOR=3` and `0009_mfa_challenge_binding`, enforced in every mode. `9236aa3` and `2f6b59a` can never be deployed.
