# Design

## Context

See `proposal.md` — Why. ARCtrl serializes Study table parameters as `PropertyValue` nodes with
`additionalType: ParameterValue`, typically linked from `LabProcess.parameterValue` under a Study’s `about` chain.
Catalog materialize already forbids **emitting** LabProcess / PropertyValue subgraphs into the dump; it does not today
**read** them for derived root fields. CouchDB / Git ARC bodies stay untouched on finalize (materialize is
catalog-only).

## Goals / Non-Goals

**Goals:**

- Derive one root `spatialCoverage` Place/GeoShape from existing Study `Bounding Box` ParameterValues.
- Keep ARC bytes unchanged; only the published `{rdi}.json` Dataset gains the field.

**Non-Goals:**

- Writing Investigation Comments or otherwise enriching the ARC for export.
- Extending `_DATASET_PART_FIELDS` with `spatialCoverage` (#684).
- Full GIS / non-WGS84 CRS handling beyond documented parse + axis-aligned union.

## Decisions

1. **Read-only ParameterValue scan, not Comment transport** — Matches “do not alter the original ARC” and reuses what
   INSPIRE already writes. Alternatives rejected: Investigation Comment (would require harvester ARC writes); lifting
   boxes only if already on root Dataset (usually absent).

2. **Scope of discovery** — Collect ParameterValues whose `name` casefolds to `bounding box`, reachable from root
   `hasPart` Study Datasets via `about` → `LabProcess` → `parameterValue` (and accept inline PropertyValue objects). If
   a Study has no `about` chain but the graph still holds ParameterValues only used by that Study’s processes, prefer
   the Study-scoped walk; document fallback: ignore orphan ParameterValues not reachable from those Studies so unrelated
   tables cannot pollute the union.

3. **Parse then union** — Parse each `value` (string) into south/west/north/east floats. Accept common separators
   (spaces/commas). Prefer schema.org box order (south west north east). Also accept INSPIRE-style west,south,east,north
   when four numbers are present and a simple heuristic or explicit documented order from the harvester string is needed
   — **implementation MUST pick one documented primary order and one compatibility parse**, covered by unit tests with
   fixtures mirroring INSPIRE mapper output. Invalid / empty values are skipped (warn once per ARC id when cheap).

4. **Union = axis-aligned envelope** — `south=min(souths)`, `west=min(wests)`, `north=max(norths)`, `east=max(easts)` in
   the parsed lat/lon space. Emit schema.org `box` as four space-separated numbers: `south west north east`.

5. **Preserve existing root `spatialCoverage`** — Same rule as Landing Page/`url`: never overwrite.

6. **Spec nuance vs “do not materialize PropertyValue”** — Finalize MAY **read** ParameterValue nodes to compute a
   derived root field; it MUST NOT copy those nodes (or LabProcess) into the published Dataset / `hasPart` trees.

## Risks / Trade-offs

- **[Risk]** Ambiguous box string order → wrong envelope → Mitigation: golden tests against known INSPIRE mapper
  strings; document accepted formats in tasks/tests.
- **[Risk]** Studies with disjoint regions → one fat envelope → Mitigation: accepted product lock-in; #684 for per-Study
  later.
- **[Risk]** Graph walk misses boxes if mapper shape differs → Mitigation: tests with Process/`about` fixtures; warn
  when zero boxes found but ParameterValue name matches exist outside walk (optional debug).

## Migration Plan

- Deploy worker with new materialize logic; no ARC migration.
- Records without parseable Study boxes remain without `spatialCoverage`.
- Rollback: revert materialize; dumps lose derived field only.

## Open Questions

- None blocking propose; exact INSPIRE mapper string samples should be copied into unit fixtures during apply (from
  harvester fixtures or a minimal synthetic graph matching production shape).
