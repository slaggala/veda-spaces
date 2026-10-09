# Estimator V2: moderated homeowner validation plan

**Goal:** before any public release, find out whether homeowners understand the estimate, trust it and act on it. We
learn by watching people use it and asking them to explain it back, not by asking whether they like it.

**Rules for this workstream:**
- **Do not:** change estimator code, change pricing, enable public intake, activate anything on staging or remove V1.
- **Approving this plan is not approval to release the estimator.**
- **Severity follows the stricter policy in §9:** one Critical finding blocks activation; every High finding is
  investigated individually; Medium findings lead to a change when 3 or more participants show them.

**Companion files:**
- [observation sheet](OBSERVATION-SHEET.md), one per session;
- [observations-template.csv](observations-template.csv), one row per observation, for synthesis;
- [issues-log-template.csv](issues-log-template.csv), the ranked issue log.

---

## 1. What we are validating

Every participant explains, in their own words, the answers to ten validation questions (§6):

1. What is the displayed estimated range?
2. Is the estimate a final quotation?
3. Is the Site Execution & Handover Package included?
4. Is the Design Personalisation Allowance an automatic extra charge?
5. What materials and hardware are promised?
6. How do the manufacturer warranty and Veda Spaces service support differ?
7. What is excluded?
8. What happens next?
9. What information would make the estimate more trustworthy?
10. Would they request a detailed quotation?
11. If another interior company quoted ₹2 lakh lower, what would they check before choosing? (Added for Round 1;
    neutral follow-ups only; see the [Round 1 session package](ROUND-1-SESSION-PACKAGE.md) §6.4.)

**Measured for every participant:**
- unassisted completion and time to the first estimate;
- trust rating and comprehension score (Q1–Q8);
- intent to request a quotation (Q10, and the debrief);
- every confusion point;
- mobile usability and any accessibility barrier;
- verbatim statements.

## 2. What participants see

**The build:**
- Estimator V2 as merged on `main` (after #60), with ESSENTIAL-1.1 and the real draft-4 rate card.
- 3 BHK apartments, Essential only. Premium shows "Pricing coming soon"; Luxury leads to a consultation.

**Where it runs:** a local **session stack** on the moderator's laptop (§5), never staging and never the public site.
- Staging keeps `STAGING_ESTIMATOR_UX=v1` and ESSENTIAL-1.1 stays inactive there, as the pre-activation guards require.
- The session stack is local, so nothing reaches staging, production or the lead workflow. Enquiries land in a throwaway local database.

**Material promises are still awaiting sales and operations confirmation.** Every participant is told the page is a
prototype being tested, and that no figure, brand or timing on it is an offer (§4). Sessions with **new prospects**
start only after sales and operations have approved the material promises
([decision sheets](GOVERNANCE-DECISION-SHEETS.md)), because prospects may act on what they see.
**No session may create a real lead:** the session stack's enquiries stay in a local database that is deleted when the
stack stops.

## 3. Participants and rounds

**Target:** 12 sessions in three rounds. Five to six sessions per round find most repeated problems; three rounds
let us check whether a change actually helped.

| Round | Who | Sessions | Purpose | Starts when |
|---|---|---|---|---|
| 1. Pilot | Friends and family who own, or are buying, a flat | 3 | Shake out the script and setup; first comprehension signal | Now |
| 2 | Existing Veda Spaces customers (another flat, a relative's flat, or recalling their own decision) | 4 | Compare V2 with a real quotation experience | After round 1 synthesis |
| 3 | New prospects (current enquiries not yet quoted, or referrals) | 5 | Real purchase intent: trust and conversion | Only after sales **and operations** approve the material promises (every matrix row confirmed), and after any change that rounds 1 and 2 justified (§9) |

**Screening (all rounds):**
- Owns, or is buying, a 2 to 4 BHK apartment, and takes or shares the interiors decision.
- At least half do the session **on a phone-sized screen**; the rest on a laptop.
- A mix of first-time buyers and renovators, and of ages (include at least two people over 50).
- Mixed familiarity with interiors pricing (at least two who have collected quotations recently).

**Excluded:**
- Veda Spaces staff;
- anyone who saw earlier prototypes;
- interior designers and contractors;
- for round 3, anyone whose quotation is already being prepared (the session must not influence a live negotiation).

**Recruiting script (one line):** "We're testing a new online budget estimator and would value 45 minutes of your
honest reactions. It isn't a sales meeting, and nothing you see is an offer."

## 4. Consent, privacy and fairness

**Before the session:** read the consent statement (script §7.1). Record only with explicit agreement: screen and
audio, never faces. Name **one** contact for questions.

**Personal data:**
- Participants are recorded as codes (P01–P12) on every sheet. The code-to-name list stays with the research lead, outside the repository.
- No real personal data goes into the tool. If they reach the quotation form, they type a made-up name and number; the local stack sends nothing.

**Retention:** recordings and the code list are deleted 30 days after the final synthesis. Only anonymised findings are kept.

**Not an offer:** say it before and after. If an existing customer or prospect asks for a real price, note it as a
conversion signal and hand over to sales **after** the session, not during it.

**Thank-you gesture:** if the owner approves one, it is the same for everyone and does not depend on what they say.

## 5. Session setup (moderator's laptop)

**Roles:** a moderator, who speaks and follows the script, and a note-taker, who fills the observation sheet live. Both
stay neutral: no explaining, no defending, no leading.

**Start the session stack** (repository root; the card stays outside the repository):

```bash
API_PYTHON=api/.venv/bin/python app/e2e/session-stack.sh ~/veda-private/estimator-2026-10/rate-cards/rate-card-essential-2026-10-draft-4.json
```

The script:
1. resets a throwaway local database;
2. loads the card and activates ESSENTIAL-1.1, locally only;
3. starts the API and the site;
4. prints `ready: http://localhost:8000/estimate?ux=v2`.

Ctrl+C ends the day and **deletes the local database and any captured mail**. Enquiries never leave the laptop: no
worker runs, so nothing is sent.

**Verified on 2026-10-09** with the real draft-4 card (the same SHA-256 as staging):
- the page served V2;
- the package picker shows the safe subtitle;
- the Turnstile test widget passed by itself;
- the estimate was created with ESSENTIAL-1.1, with room promises on all 9 rooms and the full list of package components;
- a quotation request with synthetic details reached the confirmation screen;
- the enquiry existed only in the local database, its notification stayed unsent, and no mail was captured;
- stopping the stack deleted the database and mail.

**Pre-session checklist:**
- [ ] A new private (incognito) window for every participant, so no earlier answers are carried over.
- [ ] Phone participants (at least half of all sessions): Chrome device toolbar at 360 × 800, or the participant uses
      the laptop at that size.
- [ ] The Turnstile box ticks itself. Cloudflare's test key shows a small red "For testing only" note under it. If a
      participant asks, say "that's part of the test setup" and log it as Low (setup, not product).
- [ ] Synthetic contact details ready for the quotation form: "Participant P0x" and `90000 0000x`. Never real details.
- [ ] Recording on (with consent); observation sheet ready with the participant code, segment, device and scenario.
- [ ] The moderator has the scenario card printed, and does **not** show the plan or the answers.

**Remote sessions:** share the moderator's screen and give the participant remote control (for example Zoom remote
control), so that they do the clicking. "Tell me where to click" sessions are a fallback and are marked as such.

## 6. Measures and scoring

Each question is asked as a **teach-back**: the participant explains in their own words. Score Q1–Q8 immediately:
- **2:** correct without help.
- **1:** correct only after finding it on the page again, or partly correct.
- **0:** wrong, or a misconception. Write the misconception down verbatim.

A 0 that matches a Critical misconception is logged at once as a Critical finding (§9).

| Q | Ask (after the related task) | A 2 sounds like | Misconceptions to listen for (severity) |
|---|---|---|---|
| Q1 | "In your own words, what is this range?" | A preliminary planning range for their selected rooms, from typical sizes; GST extra | "That's the exact price" (Critical); "GST is included" (High) |
| Q2 | "Is this a final quotation?" | No: preliminary and not an offer; the detailed quotation follows the site measurement | "Yes, this is what I'll pay" or "it's a contract" (Critical) |
| Q3 | "Is the Site Execution & Handover Package included, or extra?" | Included in the range | "It's an extra charge" (Critical: hidden-cost interpretation) |
| Q4 | "Is the Design Personalisation Allowance an automatic extra charge?" | No: included in the range; planning money; replaced by the items they approve | "Extra on top" or "I'll be charged the maximum" (Critical) |
| Q5 | "What materials and hardware would you get, for example in your kitchen? What if that brand isn't available?" Then trust (1–5) | Branded plywood, laminate, soft-close kitchen hardware; an approved equivalent of the same grade, confirmed in the quotation | "I'm guaranteed that brand" (Critical: false expectation); "every room has soft-close" (High) |
| Q6 | "If a hinge breaks 18 months after handover, what happens? How is the manufacturer warranty different from Veda Spaces support?" | Manufacturer warranty for that exact product, on its terms; Veda Spaces service support one year from handover, under the policy | "Veda Spaces warrants everything for years" (Critical: warranty misunderstanding); "nothing after a year" (High) |
| Q7 | "What isn't included? Who supplies the sink?" | For example civil or plumbing changes, appliances, loose furniture; sink, tiles, granite and taps from them; GST extra | "Everything is included" (Critical: hidden cost) |
| Q8 | "What happens next, if you go ahead?" | Narrow the estimate or request a consultation, then site measurement, confirm design and materials, detailed quotation, approve scope before work | Wrong next step, for example "work starts now" (High) |
| Q9 | "What information would make this estimate more trustworthy for you?" | (Open: record verbatim; no score) | — |
| Q10 | "Would you request a detailed quotation? How likely, 0–10? What would stop you?" | (Intent: record the answer, the rating and the reason) | Distrust ("a sales trick") (High) |
| Q11 | "If another interior company gave you a quotation that was ₹2 lakh lower, what would you check before deciding which company to choose?" | (Open: record verbatim, and which checks were unprompted; no score) | Never suggest what to check or steer towards Veda Spaces |

**Also recorded:**
- **Per task:** outcome (unaided, assisted or failed), time, Single Ease Question (1–7), and which disclosures were opened.
- **Per session:** overall trust (1–5); mobile usability problems (tap targets, scrolling, reading on the phone); any
  accessibility barrier (zoom, contrast, keyboard or screen reader if the participant uses one); verbatim statements.

## 7. Interview script (45 minutes)

### 7.1 Welcome and consent (5 min)

> "Thank you for helping. We're testing a new online budget estimator for home interiors. We're testing the page, not
> you; there are no wrong answers, and honest confusion is the most useful thing you can give us.
> This is a prototype on my laptop. The figures, brands and timings you'll see are for testing; nothing here is a
> quotation or an offer, and no one will contact you because of it.
> May I record the screen and our voices? Only the research team hears it, and we delete it within 30 days.
> Please think aloud: say what you're looking at, what you expect and what surprises you. I may not answer questions
> straight away, because I want to see what the page tells you on its own."

### 7.2 Warm-up (5 min)

- "Tell me about your home, or the one you're planning for. Where are you in the interiors decision?"
- "Have you collected any quotations? What was hardest about comparing them?"
- "What would make you trust an interiors company's estimate?"

### 7.3 Scenario and tasks (25 min)

Read the scenario card (§8) and hand it over. Then the tasks, in order. Use the neutral probes only.

| # | Task (say exactly) | Then ask |
|---|---|---|
| T1 | "Using this page, get a budget for the home on your card." | (Do not help unless stuck for 2 minutes; mark "assisted". Note the time to the first estimate.) |
| T2 | "Look at what you got. Tell me what you see." | Q1, Q2 |
| T3 | "Is there anything in this estimate you'd worry about paying extra for?" | Q3, Q4 |
| T4 | "Your card says what matters most to you. Find out what you'd get for that." | Q5 (with the trust rating) |
| T5 | "What isn't covered?" | Q7 |
| T6 | "Your card has a warranty question. Find the answer." | Q6 |
| T7 | "If you wanted a more accurate number, what would you do? Go ahead." (Use the measurements on the card, if any.) | "What changed? What didn't?" |
| T8 | "What would you do now, if this were real?" Let them follow it to the form, and use the synthetic details from the checklist. | Q8, Q10 |

**Neutral probes:**
- "What did you expect to happen?"
- "What makes you say that?"
- "Where would you look for that?"
- "What does that word mean to you?"
- "Tell me more."

**Never say:**
- "Did you see…?"
- "It's just…"
- "Most people…"
- anything that explains the page.

### 7.4 Wrap-up (10 min)

1. "In one sentence, what is this estimate?" (a second reading of Q1 and Q2)
2. Q9: "What information would make this estimate more trustworthy for you?"
3. "What, if anything, did you find confusing or untrustworthy?"
4. "Compared with how you'd get a quotation today, is this better, worse or about the same? Why?"
5. Overall trust: "How much would you trust this estimate when planning your budget?" (1–5)
6. Debrief: "Just to be clear, nothing you saw is an offer and nothing was sent. If you'd like a real quotation, I can
   pass your details to our team after today. Would you like that?" Record yes or no; this is the real conversion
   signal. A "yes" is passed to sales **outside** the tool.

## 8. Ten homeowner scenarios

Each card is read to the participant and handed over. Every scenario is a **3 BHK apartment**, the only size V2
prices today. Spread the scenarios across segments, with scenarios 1 to 3 used twice.

| # | Scenario card (read aloud) | What it exercises |
|---|---|---|
| 1 | **New flat, first home.** "You've just received the keys to a new 3 BHK. You want the whole home done, but money is tight, and you need a number to tell your family." | First estimate; reading the range; package and allowance as included (Q1–Q4) |
| 2 | **Comparing a cheaper quote.** "Another company quoted ₹2 lakh less than you expected for the same flat. You want to know whether this estimate is fair to compare with it." | "How to compare this estimate", "Not included", "Included in your estimated range" (Q1, Q2, Q7) |
| 3 | **Lived-in renovation.** "You've lived in your 3 BHK for eight years. You only want to redo the kitchen and the master bedroom." | Turning rooms off; room subtotals; package scope (Q1, Q3) |
| 4 | **Has measurements.** "Your builder's plan says the kitchen counter is 14 ft and the master wardrobe 7 ft. You want the tightest number you can get before calling anyone." | "Personalise and narrow my estimate"; what changes and what doesn't, including the allowance (Q1, Q4) |
| 5 | **Worried about materials.** "A neighbour's kitchen swelled with water within two years. You want to know exactly what your kitchen and bathroom vanity would be made of." | Room promise, "View inclusions & materials", the equivalent rule, final selection (Q5) |
| 6 | **Burned before on service.** "A previous contractor disappeared after handover. If a hinge breaks after 18 months, you want to know who fixes it." | Warranty split and the policy link (Q6) |
| 7 | **Design-forward.** "You want feature walls, a veneer arch, profile lighting and a partition. You care about looks more than the lowest price." | Extras, the decorative final-selection statement, allowance examples (Q4, Q5) |
| 8 | **Ceiling and painting only.** "Your carpentry is already done. You only need the false ceiling, lights and painting." | Ceiling-only scope; the package lists only what applies; optional items in the build-up (Q3, Q7) |
| 9 | **Wants the best.** "You'd like premium finishes and wonder what a luxury fit-out would cost." | Premium "Pricing coming soon", the Luxury consultation, staying with Essential (Q5, Q10) |
| 10 | **Buying from abroad.** "You live overseas, your parents will live in the flat, and you want a designer to call you on WhatsApp to explain options." | "Talk to a designer", "What happens next?", the reference, the callback promise (Q8, Q10) |

## 9. Confusion points and severity (stricter policy)

**Capture every confusion point** on the observation sheet:
- where (screen and section);
- what the participant did or said, verbatim;
- what they expected;
- the misconception, if any;
- a proposed severity.

The note-taker logs it; the moderator never corrects it during the session (the debrief corrects any Critical
misconception before the participant leaves).

| Severity | Definition | Rule |
|---|---|---|
| **Critical** | A misunderstanding that could cause financial harm, a materially false expectation, a warranty misunderstanding, a hidden-cost interpretation, or a belief that the estimate is a contractual quotation | **One Critical finding is an immediate activation blocker.** Report it to the owner the same day. It stays open until a change is made and re-tested in a later round with no recurrence |
| **High** | A misunderstanding that materially damages trust, causes likely abandonment, or misrepresents scope, materials, the package, the allowance or the next steps | **Every High finding is investigated at once, without waiting for repetition.** Before release it must be resolved (changed and re-tested), disproven (evidence that the page was not the cause, for example a moderator prompt or a setup artefact), or explicitly accepted by the owner with evidence |
| **Medium** | Gets there only after hesitation, re-reading or a probe; finds information only by searching | A change is recommended when **3 or more participants** show it |
| **Low** | Wording or visual preference, with no effect on understanding or the decision | Treated as a preference unless repeated (3 or more); otherwise bundled with a justified change on the same screen |

**Investigating a Critical or High finding:**
1. Replay the recording.
2. Decide whether the page, the scenario card, the moderator or the setup caused it.
3. Check the same moment in the other sessions.
4. Record the decision (resolve, disprove or accept) in the issue log with the evidence.

**Changes:**
- Changes are proposed between rounds, never during sessions, and go through the normal review.
- Wording changes to promises also update the promise matrix and, where needed, a new specification version.
- Pricing never changes as a result of this study.

## 10. Release gate for protected staging activation

Estimator V2 may be recommended for **protected staging activation** (behind Cloudflare Access, with V1 kept) only
when all of these hold.

**Governance:**
- PR #60 is certified and merged.
- Essential Specification 1.1 has owner approval of its digest.
- The sales decisions are complete.
- Operations owners are named.
- No visible promise is unconfirmed (no PROPOSED, UNASSIGNED or BLOCKED row; `activation-check` is ready).

**Validation (12 sessions):**
- **Completion:** at least 11 of 12 reach an estimate without assistance.
- **Not a quotation:** at least 10 of 12 understand it is not a final quotation (Q2 = 2).
- **Allowance:** at least 9 of 12 understand the allowance (Q4 = 2).
- **Materials:** median material-trust rating of at least 4 out of 5 (Q5).
- **Warranty:** at least 8 of 12 distinguish the manufacturer warranty from Veda Spaces service support (Q6 = 2).
- **Conversion:** at least 5 of the 9 existing-customer and new-prospect participants would request a detailed quotation (Q10 rating 7 or more, or yes at the debrief).
- **Findings:** no open Critical finding; no unresolved High finding.

**Also reported, though not part of the gate:**
- Q1, Q3, Q7 and Q8 scores;
- median time to the first estimate;
- mobile usability and accessibility barriers;
- Q9 suggestions.

## 11. Synthesis and reporting

**After each round, within two working days:**
1. Merge the observation CSVs.
2. Group the confusion points into issues in the issue log, and count distinct participants.
3. Apply §9 to rank them and decide which justify a change.
4. Report:
   - the scores per measure against §10;
   - the ranked issues, with verbatim quotes;
   - the recommended changes, each citing its participants;
   - the watch-list items;
   - the release recommendation.

**After round 3:** the final report goes to the owner with the release recommendation.

## 12. Release recommendation (today)

**Not ready.** Neither protected staging activation nor public release is ready.

**Protected staging activation** needs every §10 condition. None of the validation conditions can be met yet,
because no session has run. Several governance conditions are also open: the sales decisions, the named operations
owners, the confirmed promises and the owner's approval of the ESSENTIAL-1.1 digest.

**Public release** also needs the public-intake conditions, which are unchanged:
- the ADR-011 intake hostname;
- production estimator flag approval;
- Premium rates;
- sizes other than 3 BHK;
- material warranty durations reconciled;
- your explicit decision.

**Recommended now:**
1. Run round 1 (3 friends and family) on the verified session stack.
2. In parallel, take the sales and operations decision sheets to their owners.
3. Round 2 follows the round 1 review. Round 3 waits for the approved promises.
