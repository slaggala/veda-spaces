# Technical-conditions closure evidence (clean environment)

This folder holds the raw output of the focused validation for the technical-conditions closure, which followed
the final targeted check `56c20ba`.

- **`summary.tsv`** lists every step: name, exit code, directory, duration and exact command.
- **Paths are shortened:**
  - `<clean-copy>` is a fresh copy of exactly the files to be committed, verified with `source-manifest.sha256`.
  - `<scratch>` is the session scratch directory.
  - `<host>` is the machine name.
  - `~` is the home directory.
- **What was run:** the uncommitted tree on top of `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`.

| File | What |
|---|---|
| `summary.tsv` | Final run: 23 steps, every exit code 0. |
| `summary-run1.tsv`, `run1-secret-scan.txt` | First run. It had two problems, both fixed before the final run. See the note below the table. |
| `repo-checks.txt` | Certified architecture unchanged since `778aa8f`; review branch at `56c20ba` with its artifacts unchanged; no review files on the implementation branch; both intake metas empty. |
| `focused-*.txt` | The focused suites on SQLite and PostgreSQL 16.4: metric redaction, auth modes, ratchet bypasses, deploy floors, governance documents, the timestamp race, plus the earlier merge-blocker suites. |
| `pytest-*.txt` | The full backend suite on SQLite and PostgreSQL 16.4. |
| `api-mypy-ratchet-without-mypy.txt` | The ratchet run with an interpreter that has no mypy. It fails closed; the step asserts exit code 2. |
| `e2e.txt` | Browser journeys, the site under production headers (404 and CSP checks), and axe. |

**First-run problems, both fixed before the final run:**

1. The new SHA-existence test failed in the fresh copy, which has no project history. It now skips when the history is unavailable. It runs and passes in a full checkout.
2. The secret scan flagged git SHAs in the new governance documents as false positives. They were reviewed and added to `.secrets.baseline`.

**Skips:**
- The SHA-existence test, in the fresh copy.
- On PostgreSQL, the SQLite-only snapshot tests.

**Not evidenced here:**
- CI, which runs after the push.
- Real alarm routing and test-fire (RG-5).
- Real S3.
- Cloudflare.
- A rollback rehearsal.
