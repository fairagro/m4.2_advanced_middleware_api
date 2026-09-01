## Context

See `proposal.md` for why dummy `http://example.org/base/` URLs appear after
pyld expand/compact. Worker finalize already compacts each Dataset with a
vendored schema.org processing context and then **overwrites** `@context` with
the public emit array (`https://schema.org` + ARC/Bioschemas map). Compact
currently does not set `@base`; pyld therefore uses `DEFAULT_BASE_IRI`.

## Goals / Non-Goals

**Goals:**

- Relativize IDs that pyld absolutized against the dummy base, using JSON-LD
  compact `@base` (option B1).
- Keep public `@context` unchanged (no `@base` published).
- Keep expand/compact and existing schema.org term compact.

**Non-Goals:**

- Per-Dataset landing-page or DOI `@base` (real absolute Dataset IRIs).
- Option B2 (`@base` in the public catalog `@context`).
- Turning off normalize or stripping `example.org` with ad-hoc string replace
  instead of compact `@base`.
- Harvester/ARCtrl exporters.

## Decisions

### 1. Internal compact `@base` equals pyld `DEFAULT_BASE_IRI`

**Choice:** Pass `@base: "http://example.org/base/"` only on the **processing**
compact context (or compact options), the same IRI pyld uses when none is set.
After compact, continue to set the public `@context` to the emit array without
`@base`.

**Why:** Compact with that `@base` re-relativizes IRIs that were expanded
against the same base (ARCtrl `./`, `#…`, `assays/…/`). Using a different dummy
base would leave `example.org/base/` in the output or produce wrong relatives.

**Alternatives considered:**

- **B2 — emit `@base` in public `@context`:** consumers would see dummy base
  semantics; rejected.
- **String-replace `http://example.org/base/`:** brittle (miss nested fields,
  query strings, encoding); rejected as primary mechanism.
- **Skip expand/compact:** loses schema.org compact; rejected.

### 2. Apply `@base` only for compact, not for public emit

**Choice:** Processing context may include `@base`; `result["@context"]` after
compact is always the existing emit context builder (no `@base`).

**Why:** Catalog records are independent Datasets, not one graph. Publishing
`@base` would imply a shared document base that does not exist.

### 3. Already-absolute IRIs are left absolute

**Choice:** Only IRIs under the dummy base are re-relativized (JSON-LD compact
does this when `@base` matches). Real `https://` DOI/landing URLs stay absolute.

**Why:** Matches ARCtrl mix of relative crate paths and real absolute links
(`license` URLs, ORCID, etc.).

## Risks / Trade-offs

- **[Risk] pyld changes `DEFAULT_BASE_IRI`** → Mitigation: pin the dummy base
  as a named constant equal to today’s pyld default; tests fail if compact
  leaves `example.org/base/` in output.
- **[Risk] Compact `@base` plus emit-context overwrite still leaves absolute
  dummy URLs in some term forms (`id` vs `@id`)** → Mitigation: unit test
  ARCtrl-shaped nested nodes (`creator`, `hasPart`, `comment`, `citation`,
  `license`).
- **[Trade-off] Catalog `@id` remains non-globally-unique (`./` per Dataset)** →
  Accepted; identity is `identifier`. Same as source ARCs.

## Migration Plan

- Deploy with API/worker that compacts catalogs; next harvest `COMPLETED`
  finalize rewrites `{rdi}.json`. No CouchDB migration.
- Rollback: revert compact `@base`; catalogs may again contain dummy URLs until
  the next finalize.

## Open Questions

None. Dummy base IRI is pyld’s current default; no product landing-page base.
