# Proposal

## Why

Harvested ARCs store organisational creators as Investigation Comments named `Creator Organization` (and
`Creator Organization URL`) because ARC Persons require a given name and ARCtrl drops RO-Crate `Organization` creators
on read. Catalog materialization today only inlines Person `creator` references, so Search Hub dumps omit those orgs
(e.g. Thünen Atlas: many records have only an organisational creator). Exporting them as schema.org `Organization`
creators restores author visibility without changing the harvester Comment contract.

## What Changes

- During worker catalog materialize, map Comment nodes named `Creator Organization` into schema.org `Organization`
  objects on Dataset `creator`, **alongside** any Person creators (lock-in from #586 explore).
- When `Creator Organization URL` is present, set `Organization.url` by parallel pairing with org names.
- Support both one Comment per org and a single Comment whose `text` joins several orgs with `; ` (harvester /
  historical shapes).
- Do **not** leave these Comments as opaque Dataset `comment` entries once mapped (same pattern as Keywords / Language).
- No **BREAKING** HTTP API change; catalog JSON shape gains Organization entries in `creator` where Comments existed.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `arc-store`: Extend catalog materialize LDComment → schema.org mapping to cover organisational creators from
  `Creator Organization` / `Creator Organization URL` Comments.

## Impact

- Code: `middleware/api/src/middleware/api/arc_store/consolidated_git/catalog_materialize.py` (+ unit tests in
  `test_catalog_materialize.py`; finalize integration coverage if needed).
- Spec: `openspec/specs/arc-store/`.
- Consumers: Search Hub / basic-layout dump ingest (`.creator` including Organizations).
- Related: #586; sibling Comment-materialize work #663 (keywords), #617 (Landing Page); harvester
  `person_contacts.add_creator_organization` / #411 / #429. Out of scope: ARCtrl Organization support, DataPLANT Person
  rules, renaming harvester Comments.
