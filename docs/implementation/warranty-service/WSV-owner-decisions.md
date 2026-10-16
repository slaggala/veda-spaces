# Warranty and after-sales service: owner decisions (WSV-D01)

A register separate from PLB-OD-01…13, CPP-D01…06, PCM-D01/D02 and PEX-D01/D02 (none of which this workstream changes).
The record is `api/veda/modules/warranty/fixtures/warranty-policy.json`. While a slot is null the code fails closed for
what it governs; everything else works.

| Slot | Exact question | Affected behaviour | Safe default while undecided | Impact while undecided |
|---|---|---|---|---|
| WSV-D01 | Which structured warranty coverage terms apply, and to which accepted quotations? Per coverage class: a label, the customer description, exclusions, the duration in months and the start trigger (HANDOVER); the policy version and text digest they come from (for example the published Warranty, Service & Customer Care Policy); and the quotation `terms_version` values whose accepted documents carry them. A class may be marked as conflicting with a quotation's statements. | Coverage status (ACTIVE, EXPIRED, NOT_STARTED); COVERED and OUTSIDE_WARRANTY_PERIOD decisions based on a class | Every entitlement shows "Not recorded in your portal" and the customer reads "as stated in your accepted quotation and the Policy"; no period is computed; a coverage decision cites a statement of the accepted quotation and records why the request is within (or outside) its period | Staff decide coverage with an explicit, recorded basis; nothing is shown as active or expired |

Not an owner slot: **chargeable post-handover service** needs a commercial agreement mechanism the repository does not
have (Project Commercials is bound to the accepted lineage; quotation variations exist only while a project is
active). It is a missing integration, so it fails closed: a request decided as chargeable waits in
AWAITING_COMMERCIAL_AGREEMENT and can only be withdrawn or closed CHARGEABLE_NOT_AGREED; no visit or resolution is
possible and no charge is invented.

Not decided here either: retention periods (nothing is purged; erasure redacts), and how manufacturer warranty cards
reach the portal (they are handed over physically).

A decision is recorded by a reviewed change to the record; it applies only to quotations carrying a listed
`terms_version`, so it never rewrites an earlier promise. A record marked SYNTHETIC is refused outside tests.
