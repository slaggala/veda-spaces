# Final merge-blocker remediation evidence (clean environment)

This folder holds the raw output of the evidence run for the final merge-blocker remediation (targeted re-review
`15d25a7`).

- **`summary.tsv`** lists every step: name, exit code, directory, duration and exact command.
- **Paths are shortened:**
  - `<clean-copy>` is a fresh copy of exactly the files to be committed. It was verified byte-identical with `source-manifest.sha256`.
  - `<scratch>` is the session scratch directory.
  - `<host>` is the machine name.
  - `~` is the home directory.
- **When the run happened:** the run used the uncommitted working tree on top of `2f6b59a`, which `environment.txt` prints as the parent. This README and the report section were written afterwards.

| File | What |
|---|---|
| `summary.tsv` | Final run: 29 steps, every exit code 0. |
| `summary-run1.tsv`, `run1-pytest-pg16.txt`, `run1-pytest-pg18.txt` | First run. It found three problems, all fixed before the final run. See the note below the table. |
| `prefix-2f6b59a-*.txt` | The new suites run against the previous head `2f6b59a`. The defects reproduce: 15 failures in `test_final_merge_blockers`, 12 in `test_layered_limiter`, 15 in `test_archive_ordering` and 17 in `test_mypy_ratchet`. |
| `pytest-*.txt/.xml` | Full backend suite per engine: SQLite, PostgreSQL 16.4 and PostgreSQL 18.4. |
| `security-regressions-*.txt` | The remediation and security suites, verbose, on SQLite and PostgreSQL 16.4. |
| `api-mypy-ratchet-without-mypy.txt` | The ratchet run with an interpreter that lacks mypy. It fails closed, and the step asserts exit code 2. |
| `migrations-*.txt` | Migration evidence. |
| `api-*.txt`, `app-*.txt`, `secret-scan.txt` | Tooling, audits and frontend gates. |
| `e2e.txt` | Browser journeys, the site under production headers (including 404 and flag-off form checks), and axe. Screenshots, logs and the throwaway `founder.json` are not committed. |

**First-run failures, all fixed before the final run:**

1. **Secret scan:** it flagged three false positives:
   - a test password;
   - a placeholder PEM string;
   - a git SHA.

   All three were reviewed and added to `.secrets.baseline`.
2. **PostgreSQL concurrency defect,** in the new OD-3 code. It showed up in two ways:
   - PostgreSQL 16 and 18: `test_RR03_concurrent_promotion_and_verification` got a 503 caused by a deadlock between email verification and a concurrent promotion.
   - PostgreSQL 18: `test_IR04_concurrent_promotion_and_standard_approval` got a `CheckViolation` on `user_action_token.updated_on`.

   Two changes fixed it:
   - verification now takes the governance lock before touching any row;
   - a unit of work that has written nothing takes its clock reading when it acquires the governance lock.

   The three concurrency tests were then looped 20 times on PostgreSQL 16 with no failure.

**Not evidenced here:**

- real S3 Object Lock;
- a Cloudflare Pages preview;
- a staging host;
- a rollback rehearsal;
- CI, which runs after the push.
