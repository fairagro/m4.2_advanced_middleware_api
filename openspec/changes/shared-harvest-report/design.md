# Shared Harvest Report — Design

## Context

See `proposal.md` for motivation. Client tools
([m4.2_middleware_harvester](https://github.com/fairagro/m4.2_middleware_harvester),
[m4.2_sql_to_arc](https://github.com/fairagro/m4.2_sql_to_arc)) already accumulate
statistics during the run (`_ArcStreamState`, `ProcessingStats`) and only then
build a report snapshot. The shared library owns that accumulation: callers
create a report at harvest start, invoke counting methods on events, finish the
run, and serialize. Wire shape remains the harvester JSON-LD baseline.

## Goals / Non-Goals

**Goals:**

- Mutable harvest-run report with counting methods as the sole owner of
  harvested / failed / skipped / expected / study / assay statistics
- API surface covering both consumers’ event kinds (including study/assay
  totals for SQL-to-ARC)
- Safe concurrent updates from asyncio tasks sharing one repository scope
- Format-neutral readable statistics for serializers; JSON-LD first
- Versioned in-repo vocabulary under `ns/`, published independently of `docs/`

**Non-Goals:**

- Migrating harvester or sql_to_arc code in this change
- Extra formats beyond JSON-LD
- A shared stdout / emit helper (callers print or log the serializer string)
- Parse / round-trip / schema-version APIs for machines
- Porting sql_to_arc-only PROV / instrument / actionStatus terms
- API or api_client behavioral changes
- Custom apex-domain hosting for the vocabulary
- Publishing the entire `docs/` tree via GitHub Pages
- Making callers pass pre-aggregated integer totals into a frozen-only constructor
  as the primary API

## Decisions

1. **Package placement: `middleware.shared.report` inside shared**
   — Both client repos depend (or will depend) on `fairagro-middleware-shared`;
   a nested module avoids a new PyPI artifact until extraction is justified.
   Living under `api_client` is rejected: reports are not HTTP-client concerns
   and shared must not reverse-depend on api.

2. **Primary API: mutable accumulator, not end-of-run snapshot construction**
   — Harvester and SQL-to-ARC already treat stats as event-driven counters.
   Owning increments in the report removes duplicated counter state and keeps
   omit/null rules consistent. A frozen snapshot MAY exist for serializers after
   finish, but callers MUST NOT be required to assemble counts themselves.

3. **Lifecycle: start run → open scope handle(s) → count on handles → close →
   finish run → serialize**
   — Matches “initialise at harvest start” and multi-RDI harvester tasks.
   Opening a scope returns an explicit handle; counting methods live on that
   handle. Multiple handles MAY be open concurrently so parallel RDI tasks do
   not share a single implicit “current” scope. Single-RDI tools open one
   handle for the whole run. Duration is derived from open/close (per
   repository) and start/finish (overall Action times).

4. **Counting method surface (domain events on a scope handle)**
   — Methods cover the union of consumer needs observed in the two repos:
   - set expected dataset count (optional; harvester pre-fetch)
   - set harvest id (nullable until assigned)
   - record harvested dataset (definitive success / sql_to_arc found)
   - record failed dataset (message; optional record id; optional URL)
   - record skipped dataset (harvester `SkippedRecord`; always-on wire field)
   - add studies / add assays (sql_to_arc batch totals)
   Callers signal these events on the correct handle; the run aggregates
   scopes for serialization. No “reclassify harvested → failed” API: consumers
   MUST count harvested only after definitive success (e.g. after
   `harvest_arcs` / upload result), so duplicate or submission failures are
   recorded as failures only, never as a correction of a prior success count.

5. **Names: `HarvestReport` (run), repository scope / handle, `FailedRecord`**
   — Align with harvester/operator vocabulary. Exact type and method names live
   in code; requirements speak in domain events. A thin frozen view for
   serializers is an implementation detail as long as counting remains the
   public write path.

6. **Concurrency: same-handle asyncio safety; multi-handle isolation**
   — SQL-to-ARC mutates one stats object from concurrent tasks. Counting on
   one handle MUST preserve totals under interleaved calls. Different open
   handles on the same run MUST not cross-count (harvester parallel RDIs).
   Multi-process merge remains out of scope unless a later need appears.

7. **Pluggable serializers behind a common contract; JSON-LD shipped first**
   — Counting stays format-neutral. Rendering goes through a shared serializer
   interface (Strategy) that returns a document string. JSON-LD is the only
   format required in this change. Further formats are additive
   implementations, not changes to the accumulator API. Writing the string
   (stdout, files, logs) stays in the calling tool.

8. **JSON-LD wire shape = harvester baseline**
   — Newer multi-RDI shape, richer failures, `https://schema.org/`, documented
   omit semantics. SQL-to-ARC maps to one `EntryPoint` in `result[]`. Compact
   unprefixed keys and PROV-only terms are rejected for the shared wire format.

9. **Optional study/assay totals on repository entries**
   — Preserves SQL-to-ARC operator value without overloading `schema:result`.
   Omit both when zero; when either is non-zero, emit both.

10. **No dependency on api / api_client**
    — Shared module boundary in `openspec/principles.md` /
    `openspec/config.yaml`.

11. **Versioned namespace IRI; vocab under `ns/` (not `docs/`)**
    — Canonical IRI:
      `https://fairagro.github.io/m4.2_advanced_middleware_api/ns/harvest-report/v1/#`
    — Source: `ns/harvest-report/v1/{context.jsonld,README.md,index.html}`.
    — Serializer embeds compact `@context` with that IRI; body keys stay
      prefixed. Unversioned or `docs/`-hosted IRIs are rejected.

12. **Publish only `ns/` via GitHub Actions on vocabulary tags**
    — Tag pattern `ns/harvest-report/v*`; incompatible breaks use `v2/` path.
    — Branch Pages sources cannot publish a subdirectory alone; Actions can.

13. **Hash fragment on the versioned path (`…/v1#term`)**
    — One context document covers all terms under that major version.

## Risks / Trade-offs

- **[Risk] Consumer drift until harvester/sql_to_arc migrate** → Mitigation:
  document the contract in the delta (then main) harvest-report spec; migrations
  stay out of scope here.
- **[Risk] Existing snapshot-oriented shared code must be reshaped** → Mitigation:
  treat tasks section 5 as the redesign implementation; keep wire tests green.
- **[Risk] Operators comparing old sql_to_arc logs to new shape** → Mitigation:
  accept a one-time break on consumer migration.
- **[Trade-off] Broader counting API than either consumer alone** → One library
  for both is preferable to two partial APIs.
- **[Risk] Lock contention under heavy asyncio fan-out** → Mitigation: short
  critical sections around integer/list updates only; revisit if profiling shows
  hotspots.
- **[Risk] Pages / Actions misconfigured → dead IRI** → Mitigation: tag +
  workflow docs; embedded `@context` still expands by IRI string offline.
- **[Trade-off] Major version in path vs full semver in path** → Major (`v1`)
  keeps the serializer IRI stable across compatible patches.

## Migration Plan

1. Align OpenSpec artifacts with the accumulator/counting design (this update).
2. Reshape `middleware.shared.report` to the counting API; keep JSON-LD wire
   tests and vocab/Pages artifacts.
3. Publish shared package via normal release process when ready.
4. Separate consumer-repo migrations (out of scope): replace `_ArcStreamState` /
   `ProcessingStats` report fields with shared counting methods.

## Open Questions

- None that block redesign of the shared library. Exact public method names are
  an implementation choice within the domain events above.
  Multi-process merge is deferred until a consumer needs it.
