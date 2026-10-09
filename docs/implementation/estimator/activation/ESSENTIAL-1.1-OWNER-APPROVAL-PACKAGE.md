# Essential Specification 1.1: owner approval package (for signature)

**Prepared:** 2026-10-09, from `main` at the PR #62 merge (`c94af47`), where both digests below were recomputed and
verified.

**What this package is.** It has two signature parts:
- **Part 1 (content approval)** can be signed now. It approves what customers will be promised.
- **Part 2 (activation approval)** is signed only after sales and operations have recorded their decisions. It
  authorises protected staging activation.

**Neither part enables public intake, production or V1's removal.**

**Why two parts.** The activation gate fails closed unless the approval carries the *current* digests. Recording a
sales decision or an operations owner changes the promise matrix, and with it the matrix digest. Part 2 must
therefore carry the digests that `veda estimator activation-check` prints at that time, not the ones below.

---

## Part 1: content approval (sign now)

### What you are approving

| Item | Value |
|---|---|
| Specification | Essential Specification 1.1 (`ESSENTIAL-1.1`), [rendered for review](../specifications/ESSENTIAL-SPECIFICATION-v1.1.md) |
| **Specification digest** | `6f798ef6cd3cea06f491041a4143e35776900107e73e6c953fbed4bd37ad286d` |
| Customer-promise matrix | Version 1: 54 visible promises, [rendered](../specifications/essential-1.1-promise-matrix.md) |
| **Promise-matrix digest** (version 1, before any confirmation) | `ed3b14e0afadecfbb350d022f3bbd028407f7b3f790ff4ec85f0aacf53bbcb3b` |
| Sales-decision record | Version 1, ten items, **none decided**: `4aefa90ae5ab225ad395b9871cf1c97620e8279d5153d1af35542c9ba1283863` |
| Customer copy (V2 page text) | `8bf40f41c26a4b4af3d7a146c8faf53c30738899d0cbbfacddafef0e75e552f8` |
| Warranty copy | `9837f67c9e60f7510d3c5f43a097b41444e58fb8facda72802601d37f88a4785` |
| Commit | Merge of PR #62, `c94af47700cc107a8524bac5994e577d82b065a2` |

### By signing Part 1, the owner confirms

- [ ] The ESSENTIAL-1.1 material promises: room promises that follow the priced lines; the brand examples with the
      approved-equivalent rule; final selection in the detailed quotation; and no material warranty duration.
- [ ] The customer wording in the 54 promises, **as wording**. Each promise still needs sales and operations
      confirmation before activation.
- [ ] The warranty split: manufacturer-backed protection for the exact documented product, and Veda Spaces
      workmanship and fitment support for one year from handover, subject to the policy.
- [ ] The scope: protected staging behind Cloudflare Access, Essential only, 3 BHK apartments, V1 kept available,
      **no public intake**.
- [ ] The validation retention rule: recordings and the participant code list are deleted 30 days after the final
      synthesis (validation plan §4).

**Part 1 does not authorise activation.** The gate still refuses while any promise is unconfirmed (today: 54 of 54).

| Owner name | Signature | Date |
|---|---|---|
| | | |

---

## Part 2: activation approval (sign only when every precondition is met)

### Preconditions (none met yet)

| # | Precondition | Evidence | Status |
|---|---|---|---|
| 1 | All ten sales decisions recorded (APPROVE, named, dated); any CHANGE has produced a new specification version, approved again from Part 1 | [Sales decision sheet](ESSENTIAL-1.1-SALES-DECISION-SHEET.md), merged record | Not met: 0 of 10 |
| 2 | All 54 promises `OPERATIONALLY_CONFIRMED`, with a named accountable person, a named backup and a date | [Operations owner sheet](ESSENTIAL-1.1-OPERATIONS-OWNER-SHEET.md), [suggested ownership](OWNERSHIP-STRUCTURE.md), merged record | Not met: 0 of 54 |
| 3 | Real-card equivalence passed on the reviewed commit, against the card active on staging | `app/e2e/run-real-card.sh` output (check names and card SHA-256 only) | To run on that commit |
| 4 | Homeowner validation release gate met (12 sessions, no open Critical, no unresolved High) | [Validation dashboard](HOMEOWNER-VALIDATION-DASHBOARD.md) | Not started |
| 5 | `activation-check` reports `ready: true` on staging, except for the approval record itself | Host output | Not run |

### Values to enter (copy from `activation-check` on the reviewed commit)

| Field in `essential-1.1-approval.json` | Value |
|---|---|
| `specification_sha256` | `6f798ef6cd3cea06f491041a4143e35776900107e73e6c953fbed4bd37ad286d`, unless a sales CHANGE created a new version |
| `promise_matrix_sha256` | **New value** after the operations confirmations (not `ed3b14e0…`) |
| `sales_decisions_sha256`, `sales_decisions_version` | New value after the sales decisions |
| `operations_confirmation_version` | The matrix `version` after the confirmations |
| `customer_copy_sha256`, `warranty_copy_sha256` | From `activation-check` (unchanged unless a decision changed the copy) |
| `reviewed_commit` | The merge commit that carries the confirmed records |
| `real_card_equivalence` | Card version, card SHA-256 (it must equal staging's active card), `PASS`, date, commit |
| `scope` | `{"environments": ["staging"], "package": "ESSENTIAL", "ux": "v2", "public_intake": false}` |
| `approval_reference` | The exact text to be passed as `--approval` |
| `approved_on`, `owner`, `status` | Date; owner identity; `APPROVED` |

| Owner name | Signature | Date | Approval reference (exact text) |
|---|---|---|---|
| | | | |

The signed Part 2 is entered into `api/veda/modules/estimator/approved/essential-1.1-approval.json` through a reviewed
pull request. Activation then follows runbook §6.8.
