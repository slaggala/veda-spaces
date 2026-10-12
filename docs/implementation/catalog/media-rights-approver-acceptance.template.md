# Media-rights approver: written acceptance (template; owner decision AD-4)

**Status: TEMPLATE. No approver is named; nothing is accepted.** This file is not an approval record and enables
nothing. The owner names the primary and backup approver in
[CATALOG-V3-activation-owner-decisions.md](CATALOG-V3-activation-owner-decisions.md) (AD-4) and records the primary
in `infra/config/staging-platform.json` → `media_rights.approver` through a reviewed pull request. Each approver signs a
copy of this note; the owner keeps the signed copies outside Git (for example under `~/veda-private/approvals/`) and
the SHA-256 of the primary approver's signed note becomes the activation record's `media_rights_approver` evidence
(`reference`: where the note is kept; `sha256`: the file digest).

Every `[TO FILL]` is filled by a person. A note that still contains `TO FILL` is not an acceptance.

---

## Acceptance of the media-rights approver role (Veda Spaces, catalog V3, protected staging)

| Field | Value |
|---|---|
| Approver | [TO FILL: name and role] |
| Role | [TO FILL: primary / backup] |
| Named by the owner on | [TO FILL: date, UTC] |
| Scope | Catalog V3 media on protected staging only (`https://api-staging.vedaspaces.com` behind Cloudflare Access). No production scope exists; a production role needs a separate decision and a separate note. |

### Responsibilities accepted

1. Verify ownership or licence of every media object before it is approved for publication.
2. Verify consent, and its reference, where media shows a client's premises or requires client permission.
3. Verify attribution where a licence requires it.
4. Verify the usage scope recorded for the media (products, rooms, styles) against what the licence or consent allows.
5. Verify the effective, expiry and review dates of each media-rights record.
6. Approve withdrawal of media when rights, consent, privacy or security require it, and expect withdrawal to take
   effect at once (delivery answers 404 from the next request).
7. Approve publication eligibility of catalog records that carry media (the record's `reviewed_by`), under the
   four-eyes rule the application enforces.

### Independence accepted

The approver will not approve media they uploaded, a claim or record they authored, or evidence they produced where
four eyes apply, and is not the author of the activation record. The application refuses an approver who is the
editor, submitter or release author of the same record or release; independence from the activation-record author is a
rule the owner enforces by this note.

### Limits acknowledged

- The approver's name is read by the application from `VEDA_CATALOG_MEDIA_RIGHTS_APPROVER` and shown in audit
  output; no credentials and no personal address are stored in the repository.
- The approver does not activate V3, enable media delivery or change infrastructure; those remain the owner's
  decisions through reviewed pull requests and the approval record.
- A backup approver acts only when the primary is unavailable and under the same rules.

| Signature | |
|---|---|
| Signed by | [TO FILL] |
| Date (UTC) | [TO FILL] |
| Method | [TO FILL: handwritten and scanned / `ssh-keygen -Y sign` over this file / other] |
| Owner acknowledgement | [TO FILL: owner name, date] |

SHA-256 of the signed file (recorded by the owner, never of this template): `[TO FILL]`
