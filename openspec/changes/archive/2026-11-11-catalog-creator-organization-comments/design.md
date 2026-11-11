# Design

## Context

See proposal.md — Why. Catalog materialize already walks Dataset `comment` references, maps Keywords / Language via
`_LDComment_NAME_MAP`, and inlines Person `creator` refs via `_materialize_person_value`. Organisational creators never
become Person nodes in the RO-Crate; they only exist as Comments.

## Goals / Non-Goals

**Goals:**

- Append schema.org `Organization` creators from `Creator Organization` (+ optional URL) Comments.
- Keep Person creators; merge into one `creator` value (list when multiple).
- Consume mapped Comments so they do not clutter Dataset `comment`.

**Non-Goals:**

- Changing harvester Comment naming / uniqueness (#562 last-wins stays as-is).
- Materializing other role Comments (`Publisher`, `Owner`, …) — not in #586 done-when.
- DefinedTerm keywords (#663) or Landing Page (#617).
- Fixing ARCtrl Organization round-trip.

## Decisions

1. **Alongside Persons (lock-in)** — Always append Organizations to whatever Person creators already materialized.
   Alternative (orgs only when no Person) rejected: mixed datasets would still hide orgs from Search Hub.

2. **Collect-then-append after Person materialize** — Run Creator-Organization extraction while processing Comments
   (same pass as Keywords), buffer `Organization` objects, then merge into `record["creator"]` after
   `_replace_or_delete(..., _PERSON_PROPERTIES, ...)` (or at end of `materialize_catalog_dataset`). Ordering: existing
   Persons first, then Organizations in Comment encounter order. Alternative (inject during Person pass) rejected —
   Comments are not on the Person property.

3. **Flatten names/URLs with `; ` split** — Trim, drop empties; pair by index. Handles issue’s merged Comment shape and
   single-org Comments. Multiple Comment nodes with the same name (pre–unique-name collapse) are concatenated in list
   order before pairing. Alternative (require 1:1 Comment nodes only) rejected — issue documents `; ` joins; API
   last-wins uniqueness can leave a single merged Comment.

4. **Do not use `_LDComment_NAME_MAP` string property redirect** — Keywords/Language write scalar/array properties;
   creators need structured objects and merge with Persons. Dedicated handler for these two Comment names.

5. **Organization shape** — `{"@type": "Organization", "name": ...}` plus optional `url`. Strip fragment ids. No
   `identifier` / `sameAs` in this slice unless already present as URL text.

## Risks / Trade-offs

- **[Risk] Name↔URL mis-pairing when counts differ** → Document index pairing; orphan URLs ignored; missing URL → name
  only (spec scenarios).
- **[Risk] Org names containing `; `** → Accept harvester join convention; no quote escaping in this slice.
- **[Trade-off] Opaque `comment` loss for these names** → Same as Keywords; Search Hub wants `creator`, not Comments.

## Migration Plan

- Deploy with worker finalize; next catalog rebuild / finalize picks up Organizations. No CouchDB migration. Rollback =
  revert materialize change (dumps lose org creators again).

## Open Questions

- None for this slice (alongside Persons locked). Other role Comments deferred.
