# Estimator V2: moderated homeowner validation plan

**Goal:** before any public release, find out whether homeowners understand the estimate, trust it and act on it. We
learn by watching people use it and asking them to explain it back, not by asking whether they like it.

**Rules for this workstream:**
- **Do not:** change estimator code, change pricing, enable public intake or activate anything on staging.
- **Recommend a change only when several homeowners show the same confusion** (§9).

**Companion files:**
- [observation sheet](OBSERVATION-SHEET.md), one per session;
- [observations-template.csv](observations-template.csv), one row per observation, for synthesis;
- [issues-log-template.csv](issues-log-template.csv), the ranked issue log.

---

## 1. What we are validating

| Question | Measure (§6) |
|---|---|
| Can they understand the estimate? | M1: what the number is, what it includes, that it is not a quotation |
| Do they understand the range? | M2: why it is a range and what narrows it |
| Do they trust the materials? | M3: what their kitchen is made of, the equivalent rule, a trust rating |
| Do they understand the allowance? | M4: included, a planning amount, not charged automatically |
| Do they understand exclusions? | M5: what is not included, what they supply, GST |
| Do they understand the warranty? | M6: manufacturer protection against Veda Spaces service support |
| Would they request a quotation? | M7: the next step they choose, its likelihood, what stops them |

## 2. What participants see

**The build:**
- Estimator V2 as merged on `main` (after #60), with ESSENTIAL-1.1 and the real draft-4 rate card.
- 3 BHK apartments, Essential only. Premium shows "Pricing coming soon"; Luxury leads to a consultation.

**Where it runs:** a local **session stack** on the moderator's laptop (§5), never staging and never the public site.
- Staging keeps `STAGING_ESTIMATOR_UX=v1` and ESSENTIAL-1.1 stays inactive there, as the pre-activation guards require.
- The session stack is local, so nothing reaches staging, production or the lead workflow. Enquiries land in a throwaway local database.

**Material promises are still awaiting sales and operations confirmation.** Every participant is told the page is a
prototype being tested, and that no figure, brand or timing on it is an offer (§4). Sessions with **new prospects**
start only after sales has recorded its decisions on the
[sales decision package](../ESSENTIAL-1.1-SALES-DECISIONS.md), because prospects may act on what they see.

## 3. Participants and rounds

**Target:** 12 sessions in three rounds. Five to six sessions per round find most repeated problems; three rounds
let us check whether a change actually helped.

| Round | Who | Sessions | Purpose | Starts when |
|---|---|---|---|---|
| 1. Pilot | Friends and family who own, or are buying, a flat | 3 | Shake out the script and setup; first comprehension signal | Now |
| 2 | Existing Veda Spaces customers (another flat, a relative's flat, or recalling their own decision) | 4 | Compare V2 with a real quotation experience | After round 1 synthesis |
| 3 | New prospects (current enquiries not yet quoted, or referrals) | 5 | Real purchase intent: trust and conversion | After the sales decisions are recorded, and after any change that round 2 justified (§9) |

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

**One-time setup** (repository root; the card stays outside the repository):

```bash
export PY=api/.venv/bin/python CARD=~/veda-private/estimator-2026-10/rate-cards/rate-card-essential-2026-10-draft-4.json
(cd api && PYTHON=.venv/bin/python tools/e2e_reset.sh)            # fresh throwaway local database
est() { (cd api && VEDA_ENV=local VEDA_DATABASE_URL=sqlite:///var/e2e.db .venv/bin/python -m veda.cli estimator "$@"); }
est load-card "$CARD" && est activate-card --version ESS-2026-10-PRIVATE-DRAFT-4 --approval "Local homeowner validation"
est load-spec docs/implementation/estimator/specifications/essential-specification-v1.1.json
est activate-spec --spec ESSENTIAL-1.1 --approval "Local homeowner validation"
```

**Before each session day**, start the API and the site in two terminals, exactly as `app/e2e/run-all.sh` does:
- the API on port 5000 with `VEDA_ESTIMATOR_ENABLED=true`;
- `node app/e2e/static-server.mjs app/e2e/site-release 8000 http://localhost:5000`.

Then open **`http://localhost:8000/estimate?ux=v2`** in a new private window.

**Pre-session checklist:**
- [ ] A new private (incognito) window for every participant, so no earlier answers are carried over.
- [ ] Phone participants: Chrome device toolbar at 360 × 800, or the participant uses the laptop at that size.
- [ ] The "Verify you are human" box ticks itself (Cloudflare's test key). If it does not, check the internet connection.
- [ ] Recording on (with consent); observation sheet ready with the participant code, segment, device and scenario.
- [ ] The moderator has the scenario card printed, and does **not** show the plan or the answers.

**Remote sessions:** share the moderator's screen and give the participant remote control (for example Zoom remote
control), so that they do the clicking. "Tell me where to click" sessions are a fallback and are marked as such.

## 6. Measures and scoring

Each measure is asked as a **teach-back**: the participant explains in their own words. Score immediately on the
sheet:
- **2:** correct without help.
- **1:** correct only after finding it on the page again, or partly correct.
- **0:** wrong, or a misconception. Write the misconception down verbatim.

| ID | Ask (after the related task) | A 2 sounds like | Misconceptions to listen for |
|---|---|---|---|
| M1 | "In your own words, what is this number? What does it include?" | A preliminary planning range, not a final quotation. It includes the rooms, the Site Execution & Handover Package and the Design Personalisation Allowance. GST is extra | "That's the price I'll pay"; "the package is an extra charge"; "GST is included" |
| M2 | "Why is it a range? What would make it narrower?" | Typical sizes until measured, design choices, site conditions. Measurements or the site visit narrow it | "They'll charge the top"; "the range is a discount"; "it can never change" |
| M3 | "What would your kitchen actually be made of? What happens if that brand isn't available?" Then: "How much do you trust that?" (1–5) | Branded plywood, laminate, soft-close kitchen hardware. An approved equivalent of the same grade, confirmed in the quotation | "I'm guaranteed Sylvan Blu"; "they can swap in anything"; "every room has soft-close" |
| M4 | "What is the Design Personalisation Allowance? Will you pay the top amount?" | Included in the range; planning money for common additions; not charged automatically; the quotation replaces it with what they approve | "It's an extra fee on top"; "I'll be charged the maximum"; "it's a hidden margin" |
| M5 | "Name something that isn't included. Who supplies the sink?" | For example civil or plumbing changes, appliances, loose furniture. The sink, tiles, granite and taps come from them. GST is extra | "Everything is included"; "they supply the granite" |
| M6 | "If a drawer hinge breaks 18 months after handover, what happens?" | Hardware is covered by the manufacturer's warranty for that product, on its terms. Veda Spaces service support is one year from handover, under the policy | "Veda Spaces guarantees everything for 10 years"; "after a year there's nothing"; "plywood is 30 years" |
| M7 | "What would you do next?" Then: "How likely are you to request a detailed quotation, 0–10?" and "What, if anything, stops you?" | A clear next step (narrow, quotation or designer) and an honest reason | Distrust ("this is a sales trick"); confusion about the next step |

**Also recorded for every task:**
- **Outcome:** unaided, assisted, or failed.
- **Time**, from task start to answer.
- **Single Ease Question:** "How easy was that?" (1–7).
- **Behaviour:** did they open "View inclusions & materials", "View technical assumptions", "What it covers" (package), or the warranty policy link? Where did they scroll back to?

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
| T1 | "Using this page, get a budget for the home on your card." | (Do not help unless stuck for 2 minutes; mark "assisted".) |
| T2 | "Look at what you got. Tell me what you see." | M1, then M2 |
| T3 | "Your card says what matters most to you. Find out what you'd get for that." | M3 (kitchen, or the room on the card) |
| T4 | "Is there anything in this estimate you'd worry about paying extra for?" | M4, then: "Is the Site Execution & Handover Package an extra charge?" |
| T5 | "What isn't covered?" | M5 |
| T6 | "Your card has a warranty question. Find the answer." | M6 |
| T7 | "If you wanted a more accurate number, what would you do? Go ahead." (Use the measurements on the card, if any.) | "What changed? What didn't?" |
| T8 | "What would you do now, if this were real?" Let them choose and follow it to the form; stop before they send real details. | M7 |

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

1. "In one sentence, what is this estimate?" (a second M1 reading)
2. "What, if anything, did you find confusing or untrustworthy?"
3. "Compared with how you'd get a quotation today, is this better, worse or about the same? Why?"
4. "If you could change one thing on this page, what would it be?"
5. Trust overall: "How much would you trust this estimate when planning your budget?" (1–5)
6. Debrief: "Just to be clear, nothing you saw is an offer. If you'd like a real quotation, I can pass your details to
   our team after today. Would you like that?" (Record yes or no; this is the real conversion signal.)

## 8. Ten homeowner scenarios

Each card is read to the participant and handed over. Every scenario is a **3 BHK apartment**, the only size V2
prices today. Spread the scenarios across segments, with scenarios 1 to 3 used twice.

| # | Scenario card (read aloud) | What it exercises |
|---|---|---|
| 1 | **New flat, first home.** "You've just received the keys to a new 3 BHK. You want the whole home done, but money is tight, and you need a number to tell your family." | First estimate; reading the range; package and allowance as included (M1, M2, M4) |
| 2 | **Comparing a cheaper quote.** "Another company quoted ₹2 lakh less than you expected for the same flat. You want to know whether this estimate is fair to compare with it." | "How to compare this estimate", "Not included", "Included in your estimated range" (M1, M5) |
| 3 | **Lived-in renovation.** "You've lived in your 3 BHK for eight years. You only want to redo the kitchen and the master bedroom." | Turning rooms off; room subtotals; package scope (M1, M2) |
| 4 | **Has measurements.** "Your builder's plan says the kitchen counter is 14 ft and the master wardrobe 7 ft. You want the tightest number you can get before calling anyone." | "Personalise and narrow my estimate"; what changes and what doesn't, including the allowance (M2, M4) |
| 5 | **Worried about materials.** "A neighbour's kitchen swelled with water within two years. You want to know exactly what your kitchen and bathroom vanity would be made of." | Room promise, "View inclusions & materials", the equivalent rule, final selection (M3) |
| 6 | **Burned before on service.** "A previous contractor disappeared after handover. If a hinge breaks after 18 months, you want to know who fixes it." | Warranty split and the policy link (M6) |
| 7 | **Design-forward.** "You want feature walls, a veneer arch, profile lighting and a partition. You care about looks more than the lowest price." | Extras, the decorative final-selection statement, allowance examples (M3, M4) |
| 8 | **Ceiling and painting only.** "Your carpentry is already done. You only need the false ceiling, lights and painting." | Ceiling-only scope; the package lists only what applies; optional items in the build-up (M1, M5) |
| 9 | **Wants the best.** "You'd like premium finishes and wonder what a luxury fit-out would cost." | Premium "Pricing coming soon", the Luxury consultation, staying with Essential (M7, trust) |
| 10 | **Buying from abroad.** "You live overseas, your parents will live in the flat, and you want a designer to call you on WhatsApp to explain options." | "Talk to a designer", "What happens next?", the reference, the callback promise (M7) |

## 9. Confusion points, severity and the change rule

**Capture every confusion point** on the observation sheet:
- where (screen and section);
- what the participant did or said, verbatim;
- what they expected;
- the misconception, if any;
- a proposed severity.

The note-taker logs it; the moderator never corrects it during the session.

**Severity:**

| Severity | Definition | Examples |
|---|---|---|
| **Critical** | A misunderstanding that could cost the customer money, break a promise or create a false expectation of price, scope, brand or warranty; or the participant cannot get an estimate at all | Believes the range is a fixed price; believes the maximum allowance will be charged; believes a named brand is guaranteed; believes Veda Spaces gives a multi-year warranty on materials; believes the package is an extra charge |
| **High** | Cannot explain a core idea (range, package, allowance, exclusions, warranty), or abandons, or states distrust that would stop them requesting a quotation | Cannot say why it is a range; "this looks like a sales trick" |
| **Medium** | Gets there only after hesitation, re-reading or a probe; finds information only by searching | Scrolls up and down to find what the package covers |
| **Low** | Wording or visual preference, with no effect on understanding or the decision | "I'd prefer lakh instead of full rupees" |

**Ranking and the change rule:** group the confusion points into issues (the same underlying confusion, wherever it
appears), then count distinct participants per issue. **Recommend a change only when multiple homeowners show the same
confusion:**

| Severity | Change recommended when |
|---|---|
| Critical | 2 or more participants (any segment) |
| High | 2 or more participants |
| Medium | 3 or more participants |
| Low | Never on its own. Bundle it with a change already justified for the same screen |

**Below the threshold:**
- **A single Critical or High occurrence** changes nothing. It is put on a **watch list**, and the next round adds a probe for it.
- **A single Critical occurrence in round 3** is reported to the owner immediately.

**Changes:**
- Changes are proposed after a round's synthesis, never during sessions, and go through the normal review.
- Wording changes to promises also update the promise matrix and, where needed, a new specification version.
- Pricing never changes as a result of this study.

## 10. Success criteria (release gate)

These are measured over all 12 sessions. For criteria on how many people "get it", scores are taken at first
reading, before the wrap-up.

| Area | Criterion |
|---|---|
| Getting an estimate | ≥ 11 of 12 get a first estimate unaided; median time ≤ 3 minutes; no one is asked for contact details or measurements first |
| M1 Estimate | ≥ 10 of 12 score 2, and **no participant ends the session believing the range is a fixed price** |
| M2 Range | ≥ 9 of 12 score ≥ 1; ≥ 7 of 12 score 2 |
| M3 Materials | ≥ 9 of 12 score ≥ 1; median materials trust ≥ 4 of 5; no participant believes a named brand is guaranteed |
| M4 Allowance | ≥ 9 of 12 score 2; at most 1 believes the maximum is charged automatically (2 or more is a Critical issue and fails) |
| Package | ≥ 10 of 12 say the Site Execution & Handover Package is included, not extra |
| M5 Exclusions | ≥ 9 of 12 name at least one exclusion and that GST is extra |
| M6 Warranty | ≥ 8 of 12 separate the manufacturer's warranty from Veda Spaces service support; no one believes Veda Spaces warrants materials for multiple years |
| M7 Conversion | Among customers and prospects (9): ≥ 5 rate a quotation request 7 or above, or ask to be contacted at the debrief; no trust objection raised by 2 or more |
| Ease | Median Single Ease Question ≥ 5 of 7 for T1, T2 and T8 |
| Accessibility | At least 2 phone-sized sessions with no blocking layout problem |
| Issues | **No open Critical issue; no High issue shared by 2 or more participants left without an accepted change** |

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

**Not ready for public release.** Release needs all of the following, and none is met yet:
1. **Validation:** the three rounds above are run and the §10 criteria are met, with every change justified under §9
   made and re-tested in a later round.
2. **Pre-activation conditions** (PR #60 package):
   - the sales decisions recorded;
   - the operations sign-off complete;
   - every matrix row confirmed with a named owner;
   - the ESSENTIAL-1.1 digest approved;
   - `activation-check` ready.

   Then protected staging activation, with V1 kept available.
3. **Public-intake conditions (unchanged):**
   - the ADR-011 intake hostname built and reviewed;
   - production estimator flag approval;
   - Premium rates;
   - sizes other than 3 BHK;
   - material warranty durations reconciled;
   - your explicit decision.

**Recommended now:** start round 1 (pilot, 3 friends and family) on the local session stack this week. In parallel,
sales works through its decision package, so that round 3 with real prospects can follow round 2 without delay.
