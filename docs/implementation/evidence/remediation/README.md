# Remediation evidence (clean environment)

Raw output of `evidence_run` for the independent-review remediation. `summary.tsv` lists every step: name, exit
code, directory, duration and the exact command. Paths are shortened: `<clean-copy>` is a fresh copy of exactly
the files to be committed (verified byte-identical with `source-manifest.sha256`), `<scratch>` the session's
scratch directory, `~` the home directory. The run used the uncommitted working tree on top of `9236aa3`
(`environment.txt` prints that parent); the report, registers, amendments and this folder were written after it.

| File | What |
|---|---|
| `summary.tsv` | final run: 28 steps, every exit code 0 |
| `summary-run1.tsv` | first run on the same day: it found an unformatted tool file, new SHAs not yet in the secrets baseline, and one PostgreSQL 16 failure (`test_IR04_concurrent_promotion_and_standard_approval`). The test's ordering assumption was wrong and approvals did not re-read the request after the governance lock; both were fixed before the final run |
| `ir01-prefix-*.txt`, `ir02-prefix-sqlite.txt`, `prefix-9236aa3-sqlite.txt` | the new regression suites run against the reviewed commit `9236aa3` (defects reproduced). Access tokens, recovery codes, TOTP secrets and opaque tokens printed by the exploit responses (throwaway test databases, development keys) are redacted as `<access-token>`, `<recovery-code>`, `<totp-secret>`, `<token>` |
| `secret-scan-final.txt` | secret scan after the documents and this folder were written |
| `pytest-*.txt/.xml` | full backend suite per engine (SQLite, PostgreSQL 16.4, PostgreSQL 18.4) |
| `security-regressions-*.txt` | the remediation suites, verbose, SQLite and PostgreSQL 16.4 |
| `migrations-*.txt` | migration evidence JSON (`../migration_evidence.py`) |
| `api-*.txt`, `app-*.txt`, `secret-scan.txt` | tooling, audits, frontend gates |
| `e2e.txt` | browser journeys and axe (screenshots, logs and the throwaway TOTP secret are not committed) |
