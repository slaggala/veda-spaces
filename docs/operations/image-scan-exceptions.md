# Image scan gate: exceptions policy (12-deploy)

`12-deploy` refuses an image when its ECR scan has a **HIGH or CRITICAL** finding. `infra/scripts/check-image-scan.sh`
applies the gate, called by `infra/scripts/deploy.sh` once the scan completes. An exception in
`infra/config/image-scan-exceptions.json` can let one specific finding through, under these rules.

## When an exception may be granted

All of the following must hold:
- **No fix is available.** The vulnerability is unfixed in the base image's distribution, so neither a newer base image
  nor a package upgrade in the Dockerfile removes it.
- **It isn't reachable.** The vulnerable code can't be reached through the API's inputs.
- **The owner approved this specific vulnerability.** The approval is per vulnerability, never for a severity or a
  package as a whole.

## What an exception must contain

The script checks each of these. A malformed exception refuses every deploy.

| Field | Rule |
|---|---|
| `environment` | `staging`. **Production has no exceptions**: an exception for any other environment refuses the deploy |
| `vulnerability` | The exact CVE or GHSA ID ECR reports |
| `package`, `version` | The exact `package_name` and `package_version` ECR reports. A different version or package is not covered |
| `severity` | `HIGH` or `CRITICAL` |
| `reason`, `compensating_controls` | Why it isn't reachable, and what limits the impact |
| `approved_on`, `expires` | Expiry 1 to 90 days after approval. **The exception covers the finding until the day before it expires** |

**Also refused:**
- any other HIGH or CRITICAL finding;
- a finding without package attributes;
- severity counts that disagree with the findings list.

**An exception that matches no finding is reported,** so it can be removed once the distribution ships a fix.

## Current exceptions (staging only; expire 2026-12-31)

| Vulnerability | Package (ECR) | Debian status | Why it isn't reachable | Approved by the owner on |
|---|---|---|---|---|
| CVE-2026-85091 | `zlib` 1.3.dfsg+really1.3.1-1 (`zlib1g`) | Unfixed (bug 1146895); fixed upstream | Needs `gzprintf()`/`gzvprintf()`. CPython's `zlib` and `gzip` use the deflate stream API | 2026-10-06 |
| CVE-2026-5435 | `glibc` 2.41-12+deb13u4 (`libc6`) | Unfixed in trixie (no-dsa, "Minor issue"); fixed only in forky/sid 2.43-7 | Needs the deprecated resolver printing functions `ns_printrrf()`, `ns_printrr()` or `fp_nquery()`. CPython resolves through `getaddrinfo()` and never calls them; no dependency of the API wraps them | 2026-10-12 (the reviewed merge of the pull request that added it) |
| CVE-2026-19499 | `glibc` 2.41-12+deb13u4 (`libc6`) | Unfixed in trixie (no-dsa, "Minor issue"); fixed only in forky/sid 2.43-7 | Needs `strfmon()`/`strfmon_l()` with right-justified width padding into a buffer sized for the padding only. CPython's `locale` module does not expose `strfmon`; no C extension of the locked dependency set formats money with it. The upstream advisory records no known network-facing impact | 2026-10-12 (the reviewed merge of the pull request that added it) |

The two glibc findings appeared on 2026-10-12, when `12-deploy` run 38252332555 (the scanner deploy) refused the image
built from the unchanged API code: the scan had new HIGH findings for the base image's glibc. The deploy stopped at
its step 2, before any bundle upload or host action. A newer `python:3.13-slim` digest would not clear them: trixie
ships the same glibc, and the tracker lists no fix for it.

**Removed 2026-10-12:** CVE-2026-95619 (`gcc-14` 14.2.0-19). The image no longer reports it, and `12-deploy` run
38252332555 warned that the exception matched no finding. If it reappears, it blocks the deploy until re-reviewed.

**Removed 2026-10-07:** CVE-2026-102010 (`gcc-14`). The image no longer reports it, and `12-deploy` warned that the
exception matched no finding (AUT-201 evidence, finding A3). If it reappears, it blocks the deploy until re-reviewed.

**Compensating controls:**
- the container runs as the unprivileged `veda` user, with no added capabilities;
- there is no inbound path;
- every other HIGH or CRITICAL finding still blocks the deploy;
- staging holds no production data.

**After expiry:** on 2026-12-31 these findings block the staging deploy again, unless the exception is re-reviewed or
Debian ships fixes.
