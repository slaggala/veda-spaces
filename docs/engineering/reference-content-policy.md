# Reference content and test fixtures

External or reference documents, such as another company's quotation used as a completeness benchmark, may inform
requirements and coverage analysis. Nothing literal or derived from them may be committed: no value, no wording, no
paraphrase of their policy, and no hash or fingerprint of any of it. In particular never:

- personal information (names, addresses, phone numbers, e-mail addresses);
- bank details or payment identifiers (account numbers, bank codes, UPI handles, card numbers, QR payloads);
- tax or company identifiers (GST, PAN, CIN-style values);
- contact details of any person or company;
- customer data;
- competitor commercial values (rates, prices, payment terms, warranty periods, statistics);
- proprietary wording (slogans, claims, legal text, warranty or payment wording, distinctive phrases);
- hashes, fingerprints or other signatures computed from any of the above.

**Negative and security tests use synthetic fixtures only.** A test that proves "bank-account-like content is refused"
uses an obviously synthetic value, never a value taken from a document. Synthetic forms the fixture guard always
accepts: numbers with two or fewer distinct digits (all zeros, all nines), `+00` phone numbers, branch codes starting
`ZZZZ0`, identifiers containing `ZZZ`, payment handles starting `synthetic` or `test`, and reserved e-mail domains
(`example.com`, `example.net`, `example.org`, `*.example`, `*.test`, `*.invalid`, `*.localhost`) or Veda Spaces' own.

## Controls

1. **Structural fixture guard** (`api/tests/support/reference_guard.py`, `api/tests/unit/test_reference_content_guard.py`):
   bank-account-like numbers in a banking context, bank branch codes, tax and company identifiers, payment handles,
   mobile numbers and e-mail addresses are recognised by their shape. A real-looking value in test or fixture sources
   fails unless it is in a synthetic form. Values that `main` already held before the guard are tolerated by a
   **counts-only** ratchet (`api/tests/support/fixture_rules_baseline.json`: category, file and count, never a value);
   a new one, or a higher count, fails. The guard stores nothing derived from any document.
2. **This policy and code review** for what structure cannot see: names, addresses, commercial values, and copied or
   paraphrased wording and policy.
3. **Customer-copy governance** (`api/veda/modules/mtq_commercial/customer_pack.py`): customer-facing text refuses
   money, durations, contact data outside contact fields, links, bank details and unsupported claims.

**If literal or derived reference content is found in a branch,** replace it with synthetic values and rewrite the
branch history before merge so it never becomes reachable from `main`; then re-check every rewritten commit.
