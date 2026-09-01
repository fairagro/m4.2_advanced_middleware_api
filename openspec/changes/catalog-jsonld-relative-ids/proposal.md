# Catalog JSON-LD relative IDs — Proposal

## Why

Worker catalog finalize JSON-LD-expands and compacts Dataset records. pyld then
absolutizes ARCtrl-relative `@id` values (`./`, `#Person_…`, `assays/…/`) against
its default base `http://example.org/base/` because no compact `@base` is set.
Those dummy URLs leak into `{rdi}.json`. The catalog is a bag of independent
Datasets (identity is `identifier`, not `@id`); relative IDs including root `./`
are the intended published form.

## What Changes

- After expand/compact on worker finalize, restore relative IDs by compacting
  with an **internal** dummy `@base` matching pyld’s default
  (`http://example.org/base/`).
- Published Dataset fields (`@id`/`id`, `license`, nested `creator.@id`,
  `hasPart.@id`, `comment.@id`, `citation.@id`, …) MUST NOT contain
  `http://example.org/base/`.
- Public `@context` stays `["https://schema.org", <ARC/Bioschemas map>]` —
  **no** `@base` in the emitted context (option B1, not B2).
- Expand/compact and schema.org normalization remain; ingest is unchanged.
- Tests cover ARCtrl-shaped relative IDs round-tripping to relative form.

Non-goals: real landing-page/DOI bases; publishing `@base`; skipping normalize;
naive string-strip without compact `@base`; Harvester/ARCtrl changes.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `arc-store`: Worker catalog Dataset compact MUST re-relativize IDs against an
  internal dummy `@base` and MUST NOT emit that base (or `@base`) in catalog JSON.

## Impact

- Code: `middleware/api/src/middleware/api/arc_store/consolidated_git/catalog_jsonld.py`
  (compact/normalize/context builders).
- Tests: `middleware/api/tests/unit/test_catalog_jsonld.py` and related finalize tests.
- Specs: `openspec/specs/arc-store/` (delta; related prior change
  `catalog-schema-org-jsonld`).
- No HTTP contract, config, or pyld version change required.
