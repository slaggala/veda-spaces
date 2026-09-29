# Merge-safety plan: implementation branch vs. the live site (OD-5)

> **Status: PLAN ONLY. Nothing in this document has been executed.** It asks the owner to choose and approve one
> option. No merge, deployment, DNS change, Cloudflare change, or intake activation has happened.

## 1. The hazard

- Cloudflare Pages publishes `dist/` from `main` to `https://www.vedaspaces.com` within about a minute of any push
  or merge. The details are in `README.md` "Deploy with Cloudflare Pages" and `deployment.md`.
- The Pages build command is `exit 0`. There is no gate between a merge and production.
- The implementation branch `implementation/p0-foundation` changes `dist/`:
  - `dist/index.html`: form markup, intake metas (empty), and the consent and verification blocks (hidden while intake is off);
  - `dist/assets/app.js`: progressive-enhancement intake, and the flag-off validation added by RR-11;
  - `dist/assets/enhancements.css`;
  - `dist/_headers`: the site-wide CSP;
  - `dist/404.html` and `dist/assets/404.css` (RR-01).
- **Merging the implementation branch is therefore a production site release.** The API and the SPA are not deployed
  by a merge: they have no deployment pipeline yet (TG gates pending).

## 2. What must hold before any merge

1. Final targeted independent check passed. The owner records its outcome.
2. The site diff (`git diff main...implementation/p0-foundation -- dist/`) has been reviewed as a site release.
3. The site release checklist in `deployment.md` has been run against a **preview deployment** of the branch.
   Record:
   - 0 CSP violations on `/`, `/404.html` and a missing path;
   - an HTTP 404 status for a missing path;
   - the flag-off WhatsApp validation;
   - a phone check.
4. The intake metas `veda-api-base` and `veda-turnstile-sitekey` are **empty** in `dist/index.html`. This keeps the
   public enquiry API disabled. `connect-src` still names `https://api.vedaspaces.com`, which is harmless while
   nothing calls it.
5. No privacy or consent behaviour is visible while intake is off. The consent block and the Privacy Notice link are
   hidden; the browser test `site.e2e.mjs` asserts this. Publishing either one needs owner approval (Privacy Notice, IR-17).
6. TG-01 and TG-08 remain **PENDING**. A merge does not complete or imply either gate.

## 3. Options (choose one; none executed)

| Option | How | Effect | Trade-offs |
|---|---|---|---|
| **A. Separate site release first (recommended)** | Cherry-pick only the `dist/` changes to a short `site/*` branch. Check its preview. Merge it to `main` as a deliberate site release. Then merge the implementation branch. At that point `dist/` is identical on both sides, so the site deploys nothing new. | The site change is reviewed and released on its own. The implementation merge becomes a no-op for the site. | Two merges. The site release must happen first. |
| **B. Pause production auto-deploy** | In Cloudflare Pages → Settings → Builds & deployments, set production branch deployments to *paused* (or disable automatic production deployments). Merge. Promote the chosen deployment manually after a preview check. Then re-enable. | No merge can reach production unattended. | It is a Cloudflare setting change, which needs owner approval and is not made here. Someone must remember to re-enable it. |
| **C. Merge without the site changes** | Before merging, revert the `dist/` changes on a merge-prep branch, so `git diff main -- dist/` is empty. Merge. Release the site later with option A. | The implementation lands; the live site is unchanged. | The site fixes (RR-01, RR-11, CSP) ship later. The API-side intake code still expects the new form, but intake is off. |
| **D. Move the site to its own deploy branch** | Set the Pages production branch to a dedicated `site-production` branch. `main` then only produces previews. | Code merges never deploy the site. | A permanent workflow change. It needs owner approval, and `README.md` and `deployment.md` must be updated. |

**Recommendation:** Option A. It needs no infrastructure change, gives the site change its own review and rollback
point, and makes the implementation merge a no-op for production. Combine it with option B for the implementation
merge if the owner wants a second safeguard.

## 4. Safe sequence for option A (for the owner's approval; not executed)

1. Final targeted independent check of this branch → pass recorded.
2. `git switch -c site/p0-csp-404-form-validation origin/main`
3. `git checkout implementation/p0-foundation -- dist/`
4. Check that the only changes are the reviewed site changes: `git diff --stat origin/main`.
5. Push the branch. Cloudflare builds a preview.
6. Run `app/e2e/site.e2e.mjs` against the preview. Run the `deployment.md` checklist and do a phone check.
7. Owner approves the site release. Merge to `main`. Run post-deployment validation. Rollback is the Cloudflare
   "Rollback to this deployment" step in `deployment.md`.
8. Later, and only when authorised: merge `implementation/p0-foundation`. Before merging, `git diff main -- dist/`
   must be empty.
9. None of these steps enables intake. Enabling it is a separate, gated change:
   - Turnstile keys, API origin, CORS and CSP connect-src review;
   - the Privacy Notice, and staging verification of IR-18 and IR-31;
   - production approval.

## 5. Rollback

- **Site:** follow `deployment.md` → Rollback procedure. Rollback is instant, to the previous Pages deployment. Then revert the commit on `main`.
- **API:** there is no deployed API, so nothing to roll back. When one exists, follow `docs/operations/api-runbooks.md` §2. Rollback floor: `0009_mfa_challenge_binding`. Rolling back to `9236aa3` is prohibited.
