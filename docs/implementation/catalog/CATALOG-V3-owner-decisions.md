# Catalog V3: owner decisions (proposed defaults, not approved)

These are **proposals** for the owner's acceptance. None is approved, and nothing in the code treats any of them as
approved. Each one names what the code does today until the owner decides.

| # | Decision | Proposed default | Until decided, the code does |
|---|---|---|---|
| 1 | Source storage | A private, versioned S3 bucket, encrypted with KMS, with no public ACL ([design](CATALOG-V3-media-infrastructure.md)) | Stores locally (development and tests only). Staging and production refuse the catalog without the bucket |
| 2 | Delivery | Content-hash URLs through an approved CDN or media hostname | Public media is off (`VEDA_CATALOG_MEDIA_DELIVERY_ENABLED=false`); production refuses it |
| 3 | Malware scanner | ClamAV first, failing closed, with reviewed size and resource limits | Media stays PENDING outside local and test, and no release with media validates |
| 4 | Image processing | Pillow with a hard pixel limit of 24,000,000 pixels and 8,000 per side; an async worker deferred until scale needs it | Enforces that limit synchronously in the upload request |
| 5 | Video | Approved external embeds only (youtube-nocookie.com, player.vimeo.com) | Refuses video uploads |
| 6 | 3D | Gallery only until the vertical slice is validated with people | Customers see no 3D (`VEDA_CATALOG_3D_ENABLED=false`); glTF and USDZ are refused, and a GLB is only stored after sanitisation |
| 7 | XLSX import | Deferred; keep the validated CSV and JSON import | CSV and JSON only |
| 8 | Media manifest | Manual for the representative slice | No manifest import |
| 9 | Noncurrent-version window in the bucket | 30 days | n/a until the bucket exists |
| 10 | Media hostname and the V3 page's CSP entry | For example `media.vedaspaces.com` in `img-src` on `/estimate-v3` only | The site-wide policy is unchanged; only the local test server allows API images on the V3 page |
| 11 | Veneer pricing | A separately approved engine input and rule, or stay consultation-only | Veneer is consultation-only and never priced |
| 12 | Soft-close TV storage | Explicit price rule, confirmed room applicability, a named promise owner and quotation mapping | Blocked from every release (its matrix row `spec.soft_close` is BLOCKED, owner UNASSIGNED) |
| 13 | Typed per-kind admin forms | Required before operational adoption | Records are edited as JSON documents that the server validates (engineering and review use only) |
| 14 | Imagery identity | Real project photography with rights, or commissioned references | Generated placeholders labelled "Illustrative example" |

**Owner acceptance:** not recorded. This file is not an approval record.
