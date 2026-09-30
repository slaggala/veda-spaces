# Merge-safety plan: implementation branch vs. the live site (OD-5)

> **Status: the owner APPROVED option C on 2026-09-30, to be recorded only. It is NOT executed** ([decision record](P0-owner-decision-record.md)). Execution needs a separate owner instruction, and the preconditions in [P0-merge-readiness-report.md](P0-merge-readiness-report.md) must be met first.
> - Nothing in this document has been executed: no merge, no deployment, and no DNS or Cloudflare change.
> - Intake has not been enabled.
> - Implementation logic: `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`. Reviewed tree: `3f5920b17d21214b39414d080d34246746c8c40d`. Live site: `main` at `13276a0`.

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
2. The document-level check has been done (`093cfa6`: READY WITH DOCUMENT CONDITIONS). Its document conditions are addressed by the document-conditions commit, and a confirmation check is pending.
3. **Gate TG-01 must pass** before any merge; the gate registry marks it merge-blocking (FC-A03). Current status: **APPROVED** by the owner on 2026-09-30; the registry evidence entry is outstanding.
4. **Gate TG-08 must pass**, as the owner requires. Current status: **APPROVED** by the owner on 2026-09-30; the registry evidence entry is outstanding.
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
  2. Run `git restore --source="$APPROVED" --staged --worktree -- dist` on it (`APPROVED` as defined in option C), then commit.
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

### Option C: merge with the live site's `dist/` (recommended), executable procedure

This is corrected after the document-level check (DC-01). Every git step below was run in a throwaway clone
against `3f5920b` and the live `main` (`13276a0`); nothing was pushed. That simulation passed all six checks in
steps C4, C7 and C8.

**Variables:**

- `APPROVED` is the implementation head the owner approves. It is the head of `implementation/p0-foundation` after
  the document-conditions commit, as reported with that commit. It is **not** `6ec2e76`, and branching from an older
  commit would drop later work.
- `MAIN` is `origin/main`, the live site: `13276a0` at the time of writing.

**Preconditions:**

- Everything in §2.
- CI is green on `APPROVED`.
- `git fetch origin` has been run.
- The working tree is clean.

**Why the CI needs a treatment.** The browser journeys (`app/e2e/run-all.sh` lines 32–33) serve the repository's
`dist/`. The site checks (`site.e2e.mjs`, the site part of `axe.e2e.mjs`, the website step of `workspace.e2e.mjs`)
and `test_governance_docs.py::test_public_intake_disabled` all assume the new site. With the live `dist/` in place,
they would fail on `merge-prep`, and then on `main`. Option C therefore keeps the pending site release as a test
fixture and points those checks at it. The fixture is a copy under `app/e2e/`, which Pages never publishes.

**Procedure** (run by an authorised engineer after the owner approves option C):

1. **C1: branch.**
   `git switch -c merge-prep/p0-foundation "$APPROVED"`
2. **C2: restore the live site exactly.**
   `git restore --source="$MAIN" --staged --worktree -- dist`

   This also deletes files the live site does not have, such as `dist/assets/404.css`.
   Do not use `git checkout "$MAIN" -- dist`: that command leaves extra files behind.
3. **C3: keep the pending site release as the test fixture, and point the checks at it.**
   1. `mkdir -p app/e2e/site-release && git archive "$APPROVED" dist | tar -x --strip-components=1 -C app/e2e/site-release`
   2. In `app/e2e/run-all.sh`, lines 32–33: replace `"$ROOT/dist"` with `"$APP/e2e/site-release"`.
   3. In `api/tests/unit/test_governance_docs.py::test_public_intake_disabled`: read `app/e2e/site-release/index.html`
      instead of `dist/index.html`. The live `dist/index.html` has no intake metas at all, so intake stays disabled.
   4. `git add -A && git commit -m "Keep live site unchanged for the implementation merge"`
   5. Record this commit as `KEEP`.
4. **C4: integrity checks.** All must pass.
   - `git diff --quiet "$MAIN" HEAD -- dist`: the live site is byte-identical.
   - `git diff --quiet "$APPROVED:dist" "HEAD:app/e2e/site-release"`: the fixture is the reviewed site.
   - `git diff --name-only "$APPROVED" HEAD -- . ':!dist' ':!app/e2e/site-release'` lists exactly
     `api/tests/unit/test_governance_docs.py` and `app/e2e/run-all.sh`.
5. **C5: CI on `merge-prep`.** Push `merge-prep/p0-foundation`. It is not `main`, so Pages builds only a preview.
   The full CI workflow must pass: api (sqlite, postgresql), app, security, and browser + axe against the fixture.
   Record the run id.
6. **C6: review and merge.**
   1. Open a pull request from `merge-prep/p0-foundation` into `main`.
   2. The reviewer checks the C4 outputs and the CI run.
   3. Merge with a merge commit, with the owner's approval. Pages deploys a `dist/` identical to the live one.
7. **C7: after the merge.** Check:
   - `git diff --quiet "$MAIN" origin/main -- dist`;
   - CI on `main` is green (same tree as C5);
   - the live site is unchanged: same body hash for `/`; `/404.html` still uses its inline style; no CSP header;
     the form still hands off to WhatsApp.
8. **C8: the later site release** (option A, with its own owner approval).
   1. `git switch -c site/p0-release origin/main`
   2. `git revert "$KEEP"`

   The revert restores `dist/` to the reviewed site (including `404.css`), removes the fixture, and points the tests
   back at `dist/`. In the simulation the result was identical to `APPROVED`.
   3. Then follow option A from its preview check onward.

**Branch hygiene:**

- After C6, `implementation/p0-foundation` is frozen.
- Do not merge `main` back into it. That would pull in `KEEP` and strip the site changes from the branch.
- New work branches from `main`.
- Do not revert the C6 merge commit to undo the site restore. Only reverting `KEEP` (C8) reintroduces the site
  changes. A revert of the merge would remove the whole implementation.

**Cloudflare:**

- C5 creates a preview deployment only.
- C6 triggers one production deployment whose `dist/` is identical to the live one.
- No settings change.

**Rollback:**

- Before C6: delete the `merge-prep` branch.
- After C6, if the implementation must be withdrawn: `git revert -m 1 <merge-commit>` on `main`, as a reviewed
  pull request. `dist/` is unchanged either way, so the site is unaffected.

**Risks:**

- The site fixes (RR-01, RR-11) and the CSP wait for C8.
- The fixture duplicates `dist/` under `app/e2e/` until C8.
- C3 changes two test-harness lines. These changes are reviewed in C6, and C8 removes them.

**Owner action:**

- Approve option C.
- Approve the C6 merge.
- Later, approve C8 separately.

**Evidence required:**

- The C4 outputs and the `KEEP` SHA.
- The C5 CI run id and the pull request link.
- The C7 before/after comparison of the live site.
- For C8: the preview checks of option A.

## 4. Recommendation

**Option C.** It is the only option that meets all of these at once:
- the current public website stays exactly as it is, with no header change;
- the lead API stays disabled;
- the WhatsApp fallback keeps working;
- the custom domain is untouched;
- there is no production release by accident;
- no Cloudflare setting changes.

The site improvements then follow as a deliberate option A release that the owner approves on its own merits.

The owner approved option C on 2026-09-30. It has not been executed.

## 5. Rollback reference

- **Site:** `deployment.md` → Rollback procedure. It is instant, to the previous Pages deployment. Then revert the commit on `main`.
- **API:** nothing is deployed. When it is, follow `docs/operations/api-runbooks.md` §2. The floors are `RELEASE_FLOOR=3` and `0009_mfa_challenge_binding`, enforced in every mode. `9236aa3` and `2f6b59a` can never be deployed.
