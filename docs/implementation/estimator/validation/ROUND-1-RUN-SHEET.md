# Round 1 run sheet (friends and family)

**Status: ROUND 1 READY TO RUN.** No session has been held. Results are recorded only from real sessions; nothing here
is simulated.

**Plan:** [HOMEOWNER-VALIDATION-PLAN.md](HOMEOWNER-VALIDATION-PLAN.md), using the stricter severity policy (§9) and
questions Q1–Q10 (§6).

## Participants

| Code | Segment | Screen | Scenario | Mode | Date and time | Moderator / note-taker | Consent recorded |
|---|---|---|---|---|---|---|---|
| P01 | Friends and family | Phone-sized (360 × 800) | 1 New flat, first home | In person | | | |
| P02 | Friends and family | Phone-sized (360 × 800) | 5 Worried about materials | In person | | | |
| P03 | Friends and family | Laptop | 2 Comparing a cheaper quote | In person or remote with control | | | |

At least two of the three are on a phone-sized screen. Names and contact details stay with the research lead, outside
the repository; only codes appear on the sheets.

## Before the day

- [ ] Three participants recruited with the one-line script (plan §3), none excluded by the screening rules.
- [ ] Consent statement printed (plan §7.1); recording consent asked for each person.
- [ ] Scenario cards 1, 5 and 2 printed.
- [ ] Three blank [observation sheets](OBSERVATION-SHEET.md), one per code.
- [ ] Synthetic contact details ready: "Participant P01" / `90000 00001`, "Participant P02" / `90000 00002`, "Participant P03" / `90000 00003`.

## On the day

1. Start the verified session stack (plan §5):
   `API_PYTHON=api/.venv/bin/python app/e2e/session-stack.sh <card outside the repository>`. Wait for `ready:`.
2. For each participant, open a **new private window** at `http://localhost:8000/estimate?ux=v2` (device toolbar at
   360 × 800 for P01 and P02).
3. Run the 45-minute script. Record the verbatim confusion points, the Q1–Q10 scores, time to the first estimate,
   unassisted completion, trust ratings, mobile and accessibility observations, and quotation intent.
4. **Critical finding** (plan §9): tell the research lead the same day. It blocks activation.
   **High finding:** start the investigation at once.
5. At the end of the day, press Ctrl+C. The stack deletes its local database and any captured mail. No lead reaches
   staging, production or the lead workflow.

## After the day

- [ ] Copy each sheet into `observations-template.csv` (codes only), and group the confusion points in `issues-log-template.csv`.
- [ ] Round 1 synthesis within two working days (plan §11). Round 2 (existing customers) starts only after it is reviewed.
- [ ] Recordings and the code-to-name list deleted 30 days after the final synthesis (plan §4, subject to the owner's retention approval on the approval sheet).
