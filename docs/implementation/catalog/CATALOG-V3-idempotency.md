# Catalog V3: idempotency of public estimates

Status: implemented and tested; V3 is OFF everywhere (no environment serves it to customers).

The scope of this document is `POST /api/v1/public/catalog/estimates`. It is implemented in:

- `api/veda/modules/catalog/routes.py` (`_idempotency_key`, `_estimate_prepare`)
- `api/veda/modules/catalog/configure.py` (`key_digest`, `replay`, `create_public`)
- migration `0104_catalog_idempotency`

The tests are in `api/tests/integration/test_catalog_idempotency.py`.

| Property | Rule |
|---|---|
| Required | Every V3 estimate request carries an `Idempotency-Key`. Without one the request is `422` with the field error `Idempotency-Key / REQUIRED`. The V3 page always sends one. |
| Key format | 32–64 characters `[A-Za-z0-9_-]`. The page uses `v3-` followed by 128 bits from `crypto.getRandomValues`. Shorter or other keys are `422 INVALID`. |
| Key scope | One key per request. The page keeps the key only while the same choices are retried after a lost response (`status 0` or `5xx`). Any answered failure (`409`, `422`, `429`) makes the page drop it. |
| Anonymity | The key identifies a request, not a person. Nothing personal is derived from it or stored with it. |
| Storage (privacy) | The server never stores the key. It stores `SHA-256("veda.catalog.idempotency/1" ‖ X-Veda-Client ‖ key)`. A database reader therefore cannot replay a request, and the digest says nothing about the browser. |
| Cross-customer isolation | The digest is scoped to the browser's `X-Veda-Client` token (random per browser session). A second browser presenting the same key gets its own estimate, never the first browser's, and still needs its own anti-bot token. |
| Retry | A repeat of the same key and the same choices within the expiry returns the original `201` response unchanged, with `Idempotent-Replayed: true`. The repeat is answered before the anti-bot check, because the first token was single-use. |
| Expiration | 24 hours from the first request (`IDEMPOTENCY_TTL`). After that a repeat is `409 IDEMPOTENCY_KEY_EXPIRED` and the page starts again with a new key. |
| Conflict | The same key with different choices is `409 IDEMPOTENCY_KEY_REUSED`. Nothing new is created. |
| Concurrency | Two requests with the same key that both pass the replay check race on the unique partial index `ux_catalog_configuration__idempotency_key`. One wins; the other is `409 IDEMPOTENCY_CONFLICT`, and its estimate is rolled back with its transaction. A request that arrives while the first is still in flight (snapshot stored, estimate not yet linked) is `409 IDEMPOTENCY_CONFLICT`. |
| Retention | The digest lives on the configuration snapshot and follows its retention. The snapshot is soft-deleted when its estimate is purged (`configure.purge`). A soft-deleted snapshot no longer reserves its key. |
| Response recovery | The replayed response is rebuilt from the stored estimate through the same strict public DTO and canonical checks as the first response. If the stored text no longer passes them, the replay is `503 ESTIMATOR_UNAVAILABLE`, not served. |

Customer messages on the V3 page:

| Status | Message |
|---|---|
| 409 | "This request conflicts with an earlier submission. Please refresh and try again." |
| 422 | "Please review the highlighted information." |
| 429 | "Too many attempts. Please wait before trying again." |
