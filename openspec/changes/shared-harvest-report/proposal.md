# Shared Harvest Report — Proposal

## Why

Harvester and SQL-to-ARC both emit end-of-run reports as JSON-LD on stdout for
operators, but their shapes diverge (namespaces, nesting, failure detail). A
shared library in `middleware/shared` establishes one compatible
`HarvestReport` contract—based on the newer harvester report—so client tools
can depend on `fairagro-middleware-shared` and produce the same operator-facing
summary. Work is scoped to this repository only; consumer migrations happen
separately.

## What Changes

- Add a new **harvest-report** capability: domain model (`HarvestReport`,
  `RepositoryReport`, `FailedRecord`), pluggable serialization (JSON-LD first),
  and a stdout emit helper that never fails the process.
- Place the library under `middleware/shared` (package
  `fairagro-middleware-shared`); no separate package for now.
- Wire contract follows the harvester JSON-LD shape (`schema:Action` +
  `schema:result` of `EntryPoint`s, `https://schema.org/`, `fairagro:` metrics
  and failed records). Optional per-repository study/assay counts MAY be
  included when cheap.
- Own the `fairagro:` harvest-report vocabulary under `ns/harvest-report/v1/`
  (not under `docs/`), with a **versioned** GitHub Pages namespace IRI and a
  JSON-LD context document. Publish **only** `ns/` via GitHub Actions on
  vocabulary tags—independent of general documentation.
- Update Spec-to-Code mapping in `AGENTS.md` for the new domain.
- **Non-goals:** changing `middleware/api` or `api_client` behavior; migrating
  `m4.2_middleware_harvester` or `m4.2_sql_to_arc`; additional formats beyond
  JSON-LD in this change; machine-facing schema versioning / parse APIs;
  instrument / PROV / actionStatus from the older sql_to_arc report; a custom
  apex domain (e.g. `fairagro.net`) for the namespace; publishing the whole
  `docs/` tree via Pages.

## Capabilities

### New Capabilities

- `harvest-report`: Format-neutral harvest run report model and serializers
  (JSON-LD primary) for compatible operator-facing stdout summaries.

### Modified Capabilities

- (none)

## Impact

- **Code:** new module tree under
  `middleware/shared/src/middleware/shared/` (e.g. `report/`) plus unit tests
  under `middleware/shared/tests/`.
- **Vocab:** `ns/harvest-report/v1/` (context + human README); GitHub Actions
  workflow publishes only `ns/` to Pages on matching tags.
- **Package:** `fairagro-middleware-shared` gains a public report API;
  published consumers can adopt it in later, separate changes.
- **Specs:** new `openspec/specs/harvest-report/` after archive.
- **Docs:** `AGENTS.md` Spec-to-Code mapping entry.
- **Out of scope repos:**
  [m4.2_middleware_harvester](https://github.com/fairagro/m4.2_middleware_harvester),
  [m4.2_sql_to_arc](https://github.com/fairagro/m4.2_sql_to_arc) — not modified
  here.
