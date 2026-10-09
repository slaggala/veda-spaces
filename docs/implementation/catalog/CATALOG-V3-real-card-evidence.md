# Catalog V3: owner-run real-card evidence procedure

This procedure checks V2/V3 equivalence on the owner's private rate card and produces a hashed record of the result.

**Status: procedure ready, not yet run on the real card.** No real-card artifact exists. Until the owner runs this
procedure and gives the reviewer the artifact, nobody may say the real-card equivalence was verified, independently or
otherwise.

## Rules

- The private card never enters Git, CI, a pull request, a log, a chat or an artifact. It is read in place from
  `~/veda-private/`.
- The tool refuses a card inside the repository and a card whose canonical fingerprint is not the expected one.
- No rate or amount is printed. Test output is discarded, and the real-card tests assert equality without printing an
  amount.
- The tests run on both engines, SQLite and PostgreSQL.

## Run (owner, on their own machine)

```sh
cd api
.venv/bin/python tools/catalog_real_card_evidence.py \
  --card ~/veda-private/<path>/<card>.json \
  --expected-sha256 <the card's known canonical fingerprint> \
  --operator "<the owner's role or name>"
```

The tool:

1. Checks the card's location and canonical fingerprint (SHA-256 of the JSON with sorted keys and no whitespace).
2. Runs `tests/integration/test_catalog_real_card.py` once per engine, with `VEDA_PRIVATE_CARD`,
   `VEDA_PRIVATE_CARD_SHA256` and `VEDA_TEST_ENGINES` set and all output discarded.
3. Writes `~/veda-private/evidence/real-card-evidence-<timestamp>.json` with file mode `0600`.

## The artifact

The artifact contains exactly these fields, and nothing else:

| Field | Meaning |
|---|---|
| `card_fingerprint_sha256` | The canonical SHA-256 of the card. It does not reveal the card's content. |
| `commit_sha` | The commit tested. It carries a `-dirty` suffix if tracked files were modified. |
| `engines` | `sqlite`, `postgresql`. |
| `scenarios` | Each test ID with its engine and outcome (`passed`, `failed`, `error` or `skipped`). |
| `equality` | `PASS` only when every scenario passed on every engine. Otherwise `FAIL`. |
| `timestamp` | UTC, to the second. |
| `operator` | As entered by the operator. |
| `artifact_sha256` | The SHA-256 of the canonical JSON of the fields above. This is the integrity hash. |

The artifact holds no rate, amount or card content. It is therefore also the sanitised copy for the reviewer.

## Handover

The owner keeps the original in the private evidence location and gives the reviewer a copy. The reviewer checks it:

```sh
.venv/bin/python tools/catalog_real_card_evidence.py --verify real-card-evidence-<timestamp>.json
```

The check confirms the artifact has only the allowed fields and an intact hash. It is a hash, not a signature: it
proves the artifact was not altered after it was written, not who wrote it. If a signed record is wanted, the owner
can sign the file with their own key, for example `ssh-keygen -Y sign`. No signing key is provided or assumed here.

The tool's own tests (`tests/unit/test_catalog_real_card_evidence.py`) run only on the synthetic card.
