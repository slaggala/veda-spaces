# Round 1: readiness review and moderator checklist

**Review date:** 2026-10-09, on `main` at the PR #62 merge (`c94af47`).

**Verdict: READY FOR ROUND 1**, once the four owner actions in §2 are done on the day of booking. No session has been
held and no result exists.

## 1. Readiness review

| Area | What was verified | Result |
|---|---|---|
| Moderator setup | `app/e2e/session-stack.sh` with the real draft-4 card (SHA-256 identical to staging's active card): ESSENTIAL-1.1 active locally only; V2 served; the Turnstile test widget passes by itself; an estimate with room promises on 9 rooms; a quotation request with synthetic details stays in the local database (notification never sent, no mail); Ctrl+C deletes the database and mail. Re-verified after the final code change; `main` is identical to that code | Pass |
| Scripts | [Validation plan](HOMEOWNER-VALIDATION-PLAN.md) §7: consent, warm-up, tasks T1–T8 mapped to Q1–Q10, neutral probes, wrap-up, debrief; §8: 10 scenarios (round 1 uses 1, 5 and 2) | Pass |
| Observation forms | [Observation sheet](OBSERVATION-SHEET.md): session fields, the eight tasks (outcome, time, ease, disclosures opened), Q1–Q10 with score and misconception, trust, mobile and accessibility, confusion log, wrap-up, debrief | Pass |
| Scoring sheets | `observations-template.csv` (one row per observation), `issues-log-template.csv` (now with the stricter-policy columns), and the [validation dashboard](../activation/HOMEOWNER-VALIDATION-DASHBOARD.md) for per-session scores and the gate | Pass |
| Severity handling | Plan §9: one Critical blocks activation and is reported the same day; every High is investigated at once (resolve, disprove or owner-accept, with evidence); Medium at 3 or more; Low as preference | Pass |
| Retention process | Plan §4: codes only; synthetic contact details; recordings of screen and voice only, with consent; deletion 30 days after the final synthesis. **The owner approves this rule in the approval package, Part 1** | Pending: owner signature |
| Lead isolation | The session stack has no worker; enquiries stay local and are deleted with the database | Pass |
| Accessibility of the build | e2e on `main`: axe on all V2 screens, keyboard and screen-reader checks, 360 px | Pass |

## 2. Owner actions before the first session

- [ ] Sign the [approval package, Part 1](../activation/ESSENTIAL-1.1-OWNER-APPROVAL-PACKAGE.md), including the
      retention rule. Until then, run sessions **without recordings** (notes only).
- [ ] Name the moderator and the note-taker (two different people).
- [ ] Choose the session laptop. It needs the repository, the API environment, Node and Internet access, plus the private
      card, which stays outside the repository. The card is private: run on the owner's laptop, or approve copying it.
- [ ] Recruit P01–P03 (plan §3 screening). Keep the code-to-name list outside the repository.

## 3. Moderator checklist

### The day before

- [ ] Scenario cards 1 (P01), 5 (P02) and 2 (P03) printed; three [observation sheets](OBSERVATION-SHEET.md) labelled P01–P03.
- [ ] Consent statement (plan §7.1) printed; recording set to screen and audio only.
- [ ] Synthetic details ready: "Participant P0x" and `90000 0000x`.
- [ ] Dry run: start the stack, complete one estimate yourself in a private window, stop the stack (Ctrl+C) and see
      "local database and captured mail deleted".

### On the day, before each session

- [ ] Stack running: `API_PYTHON=api/.venv/bin/python app/e2e/session-stack.sh <card>`, showing `ready: …`.
- [ ] A new private window at `http://localhost:8000/estimate?ux=v2`. For P01 and P02, Chrome device toolbar at
      360 × 800.
- [ ] The Turnstile box ticks itself. If asked about the red "For testing only" note: "that's part of the test setup".
- [ ] Recording on only with consent (and only if the retention rule is signed).

### During the session

- [ ] Follow the script word for word. Probe neutrally; never explain the page or say "most people …".
- [ ] Note-taker: record verbatim confusion points as they happen, score Q1–Q8 at once (0, 1 or 2), and record the
      Q5 trust rating, Q9 verbatim and the Q10 likelihood.
- [ ] Note the time to the first estimate and whether it was unassisted.
- [ ] Record mobile and accessibility barriers.
- [ ] At T8, use the synthetic details only. No real lead can be created.

### Straight after each session

- [ ] Debrief (plan §7.4). Correct any Critical misconception before the participant leaves. Record the debrief "yes"
      to a real quotation, and hand it to sales outside the tool.
- [ ] **Critical finding:** tell the research lead today; it blocks activation. **High finding:** open an investigation
      today (replay the recording, check the cause, record the evidence).
- [ ] Enter the session in the [validation dashboard](../activation/HOMEOWNER-VALIDATION-DASHBOARD.md) (codes only).

### End of the day

- [ ] Ctrl+C on the stack. Confirm "local database and captured mail deleted".
- [ ] Move recordings to the owner-controlled private folder (outside the repository), and log the deletion date
      (final synthesis + 30 days).
- [ ] Copy the sheets into `observations-template.csv`. Group the issues in `issues-log-template.csv`.

### After round 1

- [ ] Synthesis within two working days (plan §11). Round 2 starts only after it is reviewed.
- [ ] No estimator change during the round. Changes are proposed after synthesis under plan §9 and go through review.
