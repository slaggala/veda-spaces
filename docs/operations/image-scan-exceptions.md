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

## Current exceptions (approved by the owner on 2026-10-06; staging only; expire 2026-12-31)

| Vulnerability | Package (ECR) | Debian status | Why it isn't reachable |
|---|---|---|---|
| CVE-2026-95619 | `gcc-14` 14.2.0-19 (`libstdc++6`) | Unfixed in every release; fixed in upstream GCC | Needs C++ code passing attacker-controlled sizes to aligned `operator new`. The API is Python |
| CVE-2026-102010 | `gcc-14` 14.2.0-19 (`libstdc++6`) | Unfixed; `no-dsa` (minor issue) for trixie | Needs `erase_if` on a priority queue with request input. Nothing in the image does this |
| CVE-2026-85091 | `zlib` 1.3.dfsg+really1.3.1-1 (`zlib1g`) | Unfixed (bug 1146895); fixed upstream | Needs `gzprintf()`/`gzvprintf()`. CPython's `zlib` and `gzip` use the deflate stream API |

**Compensating controls:**
- the container runs as the unprivileged `veda` user, with no added capabilities;
- there is no inbound path;
- every other HIGH or CRITICAL finding still blocks the deploy;
- staging holds no production data.

**After expiry:** on 2026-12-31 these findings block the staging deploy again, unless the exception is re-reviewed or
Debian ships fixes.
