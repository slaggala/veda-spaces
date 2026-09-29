# Document-conditions closure evidence

This folder records the document-conditions closure. It responds to the document-level check at `093cfa6`, which
reviewed tree `3f5920b`. As the brief required, only document, amendment and SHA validation ran here, plus CI after the push.

| File | What |
|---|---|
| `changed-files.txt` | No change under `api/veda`, `api/migrations`, `api/deploy`, `app/src` or `dist` since `3f5920b`. The full list of files changed. |
| `governance-docs-full-history.txt` | `test_governance_docs.py` with git history: 27 passed. It covers amendment format and status, no implied owner decision, and the SHA checks: known commits, recorded subjects, role references and planted invalid SHAs. |
| `governance-docs-fresh-copy.txt` | The same test in a copy without git history. With `CI=true` the history check **fails**, because CI must use full history. Without CI it skips. |
| `option-c-simulation.txt`, `option-c-simulation.sh.txt` | The merge-safety option C procedure (steps C1–C8), run in a throwaway clone against `3f5920b` and the live `main`. Nothing was pushed. Every check passed. |
| `ruff.txt`, `secret-scan.txt` | Lint and format of the changed test, and the secret scan. Git SHAs were baselined as false positives. |

CI runs after the push. Its run id is reported with the commit.
