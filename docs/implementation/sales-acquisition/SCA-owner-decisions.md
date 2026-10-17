# Sales & Customer Acquisition Experience: owner decisions and open items

None of the items below blocks the merge; each blocks a later step and is listed with its safe default.

| # | Question | Affected capability | Repository-supported choices | Safe behaviour until decided | Consequence of leaving it |
|---|---|---|---|---|---|
| SCA-OD-01 | Does the privacy notice at `/privacy` (version 2026-09-v1, written from what the code does) pass the owner's legal review as the notice the consent box refers to? | Enquiry consent (the form already cites this version), the site | Approve as written; amend the text and keep the version; amend and publish a new version (the API's published-versions list and the form's meta then change together) | The page exists only on the staging site; the production site is unchanged and still links to a missing page | Consent on staging refers to an unreviewed notice; production keeps its broken link |
| SCA-OD-02 | Enable `VEDA_SALES_EXPERIENCE_ENABLED` in staging? | Staff pipeline, funnel, demo; the site's beacon (`STAGING_SALES_EXPERIENCE=on` in the Pages build) | The existing staging enablement mechanism (an approved enablement record in `infra/config`, the flag in `staging-platform.json`, one plan/apply, then `12-deploy`) | Off everywhere; every route answers 404; the site sends nothing | Sales staff cannot use the pipeline; the funnel's site stages stay NOT_TRACKED |
| SCA-OD-03 | Production: none requested. The anonymous beacon route exists in code only; under ADR-011 it would need the intake host to forward `POST /api/v1/public/acquisition/events` before any production use | Production | A later ADR-011 enablement, by the owner | Production refuses the flag at start-up | None now |

Engineering choices that are **not** owner decisions (made here, documented in the [design](SCA-design.md)): a logged MEETING counts as a consultation; a staff status with no record is shown as a claim; the lost step excludes DUPLICATE and SPAM closures; the quiet threshold is 14 days; the beacon de-duplication is in memory.
