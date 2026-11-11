# Proposal

## Why

Search Hub needs a resolvable dataset landing page (`url`) on basic-layout catalog records (#552). Harvesters already
write it into the ARC as the Investigation Comment `Landing Page`, but catalog materialize leaves it as an opaque
`comment` entry, so dumps never expose `url`.

## What Changes

- During worker catalog materialize, map Comment `Landing Page` (case-insensitive) to Dataset `url` when `url` is
  absent.
- Store the value as `{"@id": "<text>"}` so JSON-LD compact keeps the `url` term (not `schema:url`).
- **Consume** the Comment (do not retain it as an opaque Dataset `comment`), same pattern as Keywords / Language /
  Creator Organization.
- Do not overwrite an existing Dataset `url`.
- No invented `url` when the Comment is missing.
- Update OpenSpec `arc-store` materialize contract; unit tests on the materialize (+ compact) path.

**Non-goals:** harvester mapper changes; mutating CouchDB / per-ARC Git ARC bodies; changing `@id` or DOI fields;
PhenoRoam dump verification as a merge gate (manual optional).

## Capabilities

### New Capabilities

_None — extends existing catalog materialize under `arc-store`._

### Modified Capabilities

- `arc-store`: Require Landing Page Comment → Dataset `url` on materialize (consume Comment; preserve existing `url`;
  `@id` IRI shape for compact).

## Impact

- Code: `middleware/api/src/middleware/api/arc_store/consolidated_git/catalog_materialize.py`; unit tests in
  `test_catalog_materialize.py` (and compact survival as needed).
- Specs: `openspec/specs/arc-store/`.
- Issue: #617 (settles #552 “where does the landing page live” for the Comment path). Harvester follow-up remains
  external (#534).
