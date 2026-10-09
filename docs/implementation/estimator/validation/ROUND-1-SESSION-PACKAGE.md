# Round 1 session package

**Status: ROUND 1 READY TO RUN.** No participant has been invited or seen, and no result exists. Everything below is
preparation. Nothing is simulated.

**Not approved by this package:** ESSENTIAL-1.1 activation, UX V2 activation, public intake, production use, and the
Part 2 activation approval. Staging stays on `STAGING_ESTIMATOR_UX=v1`.

## 1. Participants

| Code | Who | Screen | Scenario | Recorded? |
|---|---|---|---|---|
| P01 | Friend or family member who owns, or is buying, a flat | Phone-sized (Chrome device toolbar, 360 × 800) | 1 New flat, first home | Only if Part 1 is signed and P01 consents |
| P02 | Friend or family member who owns, or is buying, a flat | Phone-sized (360 × 800) | 5 Worried about materials | As above |
| P03 | Friend or family member who owns, or is buying, a flat | Laptop or desktop | 2 Comparing a cheaper quote | As above |

**Rules:**
- **Friends or family only.** Nobody is treated or described as a customer or prospect, and nobody is promised work
  or a price.
- **Codes only** on every sheet and in the dashboard. The code-to-name list stays with the research lead, outside the
  repository.
- **Synthetic contact details only:** "Participant P0x" and `90000 0000x`. A real name, phone or email is never typed.
- **No real lead.** The session stack keeps enquiries in a throwaway local database, runs no worker (nothing is sent)
  and deletes everything on shutdown. Nothing touches the staging or production lead workflow.
- **No exposure of the private card.** The page shows estimate ranges and room amounts, never rates. Do not take
  screenshots or share the screen beyond the session; never put amounts from a session into notes, the dashboard or
  the repository. Findings are recorded as words.
- **Recording:** only if the [Part 1 approval](../activation/ESSENTIAL-1.1-PART-1-CONTENT-APPROVAL.md) is signed **and**
  the participant consents; screen and voice only. If Part 1 is not signed, the session is **notes only**.

## 2. Assignments

| Role | Name | Confirmed by owner (date) |
|---|---|---|
| Moderator | [OWNER TO FILL] | |
| Note-taker | [OWNER TO FILL] | |
| Research lead (keeps the code list, receives Critical findings the same day) | [OWNER TO FILL] | |

The moderator and the note-taker are **different people**. The moderator speaks and follows the script; the note-taker
writes everything and never speaks during tasks.

## 3. Private session environment (verified 2026-10-09)

Verified on the owner's laptop on `main` after the PR #63 merge, with `app/e2e/session-stack.sh`:

| Check | Result |
|---|---|
| Rate card | ESS-2026-10-PRIVATE-DRAFT-4, SHA-256 `2c7b503c57eefcaa1aa09d895c5e393105ee0e5e2a1eb810a258e74c49248e3d` (identical to staging's active card). The file stays in `~/veda-private` (mode 600), outside Git, and was not copied |
| Specification | ESSENTIAL-1.1 ACTIVE **locally only**, SHA-256 `6f798ef6cd3cea06f491041a4143e35776900107e73e6c953fbed4bd37ad286d`. It is inactive on staging |
| V2 page | `http://localhost:8000/estimate?ux=v2` returns 200, with UX v2 and the customer copy loaded |
| Turnstile testing behaviour | The page uses Cloudflare's always-pass test key. The local API accepts the test token (estimate 201, ESSENTIAL-1.1, card draft 4, registered text approved) and refuses a failing token (422 `CAPTCHA_FAILED`) |
| Quotation request | Synthetic details gave 201 and a local reference. 1 lead in the **local** database only |
| No outbound notification | The notification is left PENDING in the local outbox. No worker or scheduler running. 0 mail files |
| Teardown | Stopping the stack deleted the local database and captured mail |

**The card is not copied to any other machine without the owner's explicit permission.** If sessions must run on
another laptop, the owner decides first.

## 4. Day-before checklist

- [ ] Moderator and note-taker named (§2); research lead named.
- [ ] P01–P03 recruited with the one-line script (plan §3); screening checked; code list kept outside the repository.
- [ ] Part 1 signed? Yes: prepare recording, screen and voice only. No: notes only, and remove any recorder from the room.
- [ ] Printed: consent statement (§6.1), scenario cards 1, 5 and 2, three [observation sheets](OBSERVATION-SHEET.md) labelled P01–P03.
- [ ] Dry run on the session laptop: start the stack, complete one estimate, stop it, and see "local database and
      captured mail deleted".

## 5. Start-of-session checklist (every participant)

- [ ] Stack running: `API_PYTHON=api/.venv/bin/python app/e2e/session-stack.sh ~/veda-private/estimator-2026-10/rate-cards/rate-card-essential-2026-10-draft-4.json` → `ready: …`.
- [ ] **A new private window** at `http://localhost:8000/estimate?ux=v2`. For P01 and P02, device toolbar at 360 × 800.
- [ ] No other windows, notes or tools visible on the screen.
- [ ] Recording on only if Part 1 is signed and this participant consented.
- [ ] The observation sheet is filled with code, segment (friends and family), device, scenario and time.

## 6. Neutral interview script (about 50 minutes)

### 6.1 Welcome and consent (5 min)

> "Thank you for helping. We're testing a new online budget estimator for home interiors. We're testing the page, not
> you, and there are no wrong answers; honest confusion is the most useful thing you can give us. This is a prototype
> on my laptop. Nothing you see is a quotation or an offer, and nobody will contact you because of it. When a form asks
> for your name and number, please use the made-up details on this card.
> [If recording:] May I record the screen and our voices? Only the research team hears it, and it is deleted within
> 30 days of the end of the study. [If not recording:] We're not recording; my colleague will take notes.
> Please think aloud. I may not answer questions straight away, because I want to see what the page tells you on its own."

### 6.2 Warm-up (5 min)

- "Tell me about your home, or the one you're planning for."
- "Have you collected interiors quotations before? What was hard about comparing them?"

### 6.3 Task sequence (25 min)

Hand over the scenario card. Use the tasks and questions exactly as written.

| # | Task (say exactly) | Then ask (teach-back) | Measures |
|---|---|---|---|
| T1 | "Using this page, get a budget for the home on your card." | (Help only after 2 minutes stuck; mark "assisted"; note the time.) | 1 Unassisted first estimate |
| T2 | "Look at what you got. Tell me what you see." | Q1 "In your own words, what is this range?" · Q2 "Is this a final quotation?" | 2 Range · 3 Not a quotation |
| T3 | "Is there anything here you'd worry about paying extra for?" | Q3 "Is the Site Execution & Handover Package included, or extra?" · Q4 "Is the Design Personalisation Allowance an automatic extra charge?" | 4 Package · 5 Allowance |
| T4 | "Your card says what matters most to you. Find out what you'd get." | Q5 "What materials and hardware would you get, for example in your kitchen? What if that brand isn't available?" · "How much do you trust that, 1 to 5?" | 6 Materials and hardware |
| T5 | "What isn't covered?" | Q7 "What isn't included? Who supplies the sink?" | 8 Exclusions |
| T6 | "Your card has a warranty question. Find the answer." | Q6 "If a hinge breaks 18 months after handover, what happens? How is the manufacturer's warranty different from Veda Spaces support?" | 7 Warranty separation |
| T7 | "If you wanted a more accurate number, what would you do? Go ahead." | "What changed? What didn't?" | 2 Range (narrowing) |
| T8 | "What would you do now, if this were real?" Use the synthetic details only. | Q8 "What happens next, if you go ahead?" · Q10 "Would you request a detailed quotation? How likely, 0 to 10? What would stop you?" | 9 Next steps · 10 Quotation intent |

### 6.4 Market-trust question (5 min), new for Round 1

> **Q11:** "If another interior company gave you a quotation that was ₹2 lakh lower, what would you check before
> deciding which company to choose?"

Neutral follow-ups only, as needed:
- "Tell me more about that."
- "Where would you look for that?"
- "What else, if anything?"
- "How would you know if the two were comparable?"

**Do not:**
- point to "How to compare this estimate";
- suggest what to check;
- praise or criticise the other company;
- say anything that steers the participant towards Veda Spaces.

Record the answer verbatim, in order, and note whether they mention scope, materials, brands, hardware, inclusions,
exclusions, GST, warranty or installation **unprompted**.

### 6.5 Wrap-up (10 min)

1. "In one sentence, what is this estimate?"
2. Q9: "What information would make this estimate more trustworthy for you?"
3. "What, if anything, was confusing or untrustworthy?"
4. Overall trust in the estimate for planning, 1 to 5.
5. Debrief: "Just to be clear, nothing you saw is an offer and nothing was sent anywhere." If the participant holds a
   Critical misconception (for example that the range is a fixed price), correct it now, after the questions.
   Friends and family are not passed to sales.

**Neutral probes throughout:**
- "What did you expect?"
- "What makes you say that?"
- "Where would you look for that?"
- "What does that word mean to you?"

**Never:**
- explain the page;
- say "most people …" or "it's just …";
- ask leading questions such as "Did you see …?".

## 7. Observation instructions (note-taker)

- **Write verbatim**, with the time, for every hesitation, wrong click, re-read, question or misreading. Give the screen
  and section for each.
- **Score Q1–Q8 immediately** on the observation sheet:
  - 2: correct without help;
  - 1: correct after re-finding it, or partly correct;
  - 0: wrong or a misconception, written word for word.
- **Record:**
  - the Q5 trust rating;
  - Q9 and Q11 verbatim;
  - the Q10 likelihood;
  - time to the first estimate;
  - unassisted (Y/N);
  - mobile and accessibility barriers.
- Never correct the participant during tasks, and never enter amounts.

## 8. Severity classification

| Severity | Examples in this study | Rule |
|---|---|---|
| **Critical** | Believes the range is a fixed price or a contract; believes the package or the allowance is an extra charge on top; believes the maximum allowance will be charged; believes a named brand is guaranteed; believes Veda Spaces warrants materials for years; believes "everything is included" | **One occurrence blocks activation immediately.** Tell the research lead the same day |
| **High** | Cannot say why it is a range; misreads materials, the package, the allowance or the next steps; says it looks like a sales trick; would abandon | **One occurrence needs investigation** (replay the recording or notes, decide whether the page, scenario, moderator or setup caused it) and then resolution, evidence-based disproof, or explicit owner acceptance with evidence, before release |
| **Medium** | Gets there only after hesitation, re-reading or a probe | Change only when **3 or more participants** show it (across rounds) |
| **Low** | Wording or visual preference | Treated as a preference unless repeated |

No estimator change is made during or between individual sessions. Changes are proposed after the round's synthesis
and go through review.

## 9. Post-session checklist

- [ ] Debrief done; any Critical misconception corrected.
- [ ] Critical: research lead told today. High: investigation opened today (finding id, recording time or note).
- [ ] Observation sheet complete (codes only, no amounts).
- [ ] Private window closed. A new private window for the next participant.

## 10. Data-retention checklist

- [ ] Recordings (only if Part 1 is signed) moved the same day to the owner-controlled private folder, outside the
      repository and outside any shared drive.
- [ ] The deletion date is logged: final synthesis date + 30 days.
- [ ] The code-to-name list is kept by the research lead only, and deleted on the same date.
- [ ] Observation sheets and CSVs hold codes and words only: no names, contact details, amounts or screenshots.
- [ ] On the deletion date, the recordings and code list are deleted and the deletion is noted in the synthesis record.

## 11. Shutdown and deletion verification (end of every session day)

1. Ctrl+C in the session-stack terminal.
2. Confirm the line `session stack stopped; local database and captured mail deleted`.
3. Confirm no servers remain: `pgrep -fl "flask --app wsgi|static-server.mjs"` prints nothing.
4. Confirm no local data remains: `ls api/var` shows no `e2e.db` and no `mail`.
5. Note the shutdown time on the day's record.

## 12. After Round 1

- Enter the sessions and findings in the [validation dashboard](../activation/HOMEOWNER-VALIDATION-DASHBOARD.md)
  (codes only). Synthesis within two working days (plan §11).
- Round 2 (existing customers) starts only after the Round 1 synthesis is reviewed. Round 3 waits for the sales and
  operations approval of the promises.
