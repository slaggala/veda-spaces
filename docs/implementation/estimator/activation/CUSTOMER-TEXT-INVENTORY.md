# Estimator V2: customer-visible text inventory (M3)

Every piece of text a customer can see in Estimator V2, where it comes from, how it is registered in the reviewed
customer-promise matrix, and what stops unregistered text from reaching the page.

**Rule:** V2 shows only text that the reviewed matrix registers. Unregistered runtime text is suppressed. An
unregistered sentence in the page code fails the tests. A changed customer copy refuses the staging V2 build until
the owner approves its digest.

| Source | Examples | Registered in the matrix as | Control that blocks unregistered text |
|---|---|---|---|
| Customer copy, `promise` (`app/e2e/site-release/assets/estimate-v2-copy.js`) | Package text and components, allowance text, notes and examples, warranty and service sentences, trust markers, next steps, callback and confirmation messages, "Room amounts … include installation", typical-size summaries, room inclusions, fallbacks, GST line, estimate basis | One row per group (`package_text`, `package_components`, `allowance_*`, `manufacturer_warranty`, `service_support`, `callback`, `rooms_note`, `assumptions_summary`, `room_inclusions`, `fallbacks`, `gst_line`, `basis` and others) | Tests in both languages require every `promise` entry to be in the matrix, and every page row of the matrix to be on the page (`test_promise_matrix.py`, `staging-build.test.mjs`). `checkV2Approval` refuses `STAGING_ESTIMATOR_UX=v2` unless the approved `customer_copy_sha256` and `warranty_copy_sha256` match this file |
| Customer copy, `ui` | Headings, buttons, labels, field hints, error messages | Not promises (instructions and labels) | The page code holds no multi-word literal outside the copy file (staging-build test, L3), so a sentence cannot be added to the code without going through the copy file |
| Page markup (`estimate.html`) | Consent line | `consent` | The page-row check (both languages) |
| Specification snapshot | Category labels, summaries, requirements, grades, thicknesses, finishes, brand examples, equivalent rule, final selection, warranty summary, room-line phrases | One row per category, plus `spec.package` (statements must equal the specification's, exactly) | `promise_matrix.validate` on the snapshot document; V2 shows no material text unless `v2_copy.approved` is true and `room_promises` is set |
| Engine: disclaimer | "This is a preliminary budgetary estimate …" | `engine_disclaimer` (also the copy fallback) | `registered_text`: an unregistered disclaimer is dropped and V2 shows the approved copy fallback |
| Engine: assumption text | "Kitchen – Modular kitchen: counter length assumed 12 ft (typical for 3 bhk)." | `engine_assumptions`: two templates (with and without a unit) | `registered_text` matches each line against the templates; non-matching lines are suppressed |
| Rate card: exclusions | "Civil, plumbing-line and structural changes", … | `card_exclusions` | `registered_text` keeps only registered exclusions; if none remain, V2 shows "Your detailed quotation lists what is and is not included." |
| Rate card: client scope | Sink, tiles, granite, taps | `card_client_scope` | As above |
| Engine: package description and note, allowance description, warranty items and note, title, subject-to list | "Includes the site preparation …", "Kitchen tandems: up to 3 years …" | Not shown in V2 (V1 shows them, unchanged) | A staging-build test refuses any V2 code that reads these fields |
| Engine: room names | "Kitchen", "Master bedroom" | Labels (copy `ui.rooms`) | V2 uses the copy's room names |

**Runtime check (API):**
- `public_view` adds `v2_copy`, computed by `_registered_copy` → `promise_matrix.registered_text`, against the packaged matrix of the estimate's own specification snapshot.
- Without a packaged matrix that validates against the snapshot, `v2_copy` is `{"approved": false}`. V2 then shows no runtime text and no material promise, only approved fallbacks.

**Tests:**
- unit: `test_unregistered_runtime_text_is_suppressed`;
- integration: `test_only_registered_runtime_text_reaches_v2`, `test_without_a_registered_matrix_v2_gets_no_runtime_text`;
- e2e: "unregistered API text never reaches V2", where the raw response is tampered with in flight, and "without registered text V2 shows only approved fallbacks and no material promise".
