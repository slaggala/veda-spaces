# Homeowner validation dashboard

**Live dashboard:** https://claude.ai/artifact/PxmUMRweTzPFxTxgYeHWTx (private to its owner until shared from its
Share menu).

**State:** no sessions held, so every measure shows "No sessions yet". The dashboard reads two files and computes every
figure from them. It holds no example or invented data.

## Measures

| Measure | Definition | Target (validation plan §10) |
|---|---|---|
| Estimate comprehension | Sessions scoring 2 on both Q1 (what the range is) and Q2 (not a final quotation) | 10 of 12; the gate itself uses Q2 alone |
| Package understanding | Q3 scored 2: the Site Execution & Handover Package is included, not extra | 10 of 12 (reported, not a gate condition) |
| Allowance understanding | Q4 scored 2: the Design Personalisation Allowance is not an automatic extra charge | 9 of 12 |
| Warranty understanding | Q6 scored 2: separates the manufacturer warranty from Veda Spaces one-year service support | 8 of 12 |
| Trust score | Median Q5 trust in the promised materials (1–5) | Median 4 of 5 |
| Quotation intent | Median Q10 likelihood (0–10), among existing customers and new prospects | Reported |
| Overall conversion signal | Customers and prospects who rated 7 or more, or asked for a real quotation at the debrief | 5 of 9 |
| Release gate (also shown) | Unassisted completion; not a quotation; open Critical; unresolved High | 11 of 12; 10 of 12; none; none |

**Statuses:**
- **Met:** the target is reached.
- **In progress:** not reached yet, but the remaining planned sessions could still reach it.
- **Not met:** it can no longer be reached.
- **On track / Below target:** the trust median before all 12 sessions are in.
- **Blocking:** an open Critical or unresolved High finding.

The page also shows the measures by round and the findings table.

## Data (codes only; no names or contact details)

**`validation-sessions.csv`**, one row per session:

| Column | Meaning |
|---|---|
| `participant_code` | P01–P12 |
| `round` | 1, 2 or 3 |
| `segment` | `friends_family`, `existing_customer` or `new_prospect` |
| `device` | `phone` or `laptop` |
| `scenario` | 1–10 |
| `session_date` | Date of the session |
| `unassisted` | `Y` or `N` |
| `seconds_to_estimate` | Time to the first estimate |
| `q1`…`q8` | Teach-back scores, 0, 1 or 2 |
| `q5_trust` | Trust in the materials, 1–5 |
| `overall_trust` | Overall trust, 1–5 |
| `q10_intent` | Likelihood of requesting a quotation, 0–10 |
| `debrief_quotation` | `Y` or `N` |
| `mobile_barrier`, `accessibility_barrier` | Short text, or `none` |

**`validation-findings.csv`**, one row per grouped finding:
- `finding_id`
- `round`
- `severity`: `Critical`, `High`, `Medium` or `Low`
- `status`: `open`, `investigating`, `resolved`, `disproven` or `accepted`
- `participant_count`
- `screen`
- `summary`

## Updating

After each session day, the research lead adds the day's rows to both files. They come from the observation sheets
and the issue log, using the same codes. Then either ask Claude to replace the dashboard's files with the new ones, or
use the dashboard's Sources panel. Anyone who can open the dashboard can read its attached files, which is why they
hold codes only.

The dashboard reports the validation conditions only. The governance conditions (sales decisions, named owners,
confirmed promises, owner approval) are tracked in the
[owner approval package](ESSENTIAL-1.1-OWNER-APPROVAL-PACKAGE.md).
