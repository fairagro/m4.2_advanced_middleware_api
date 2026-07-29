# Shared Harvest Report — Design

## Context

See `proposal.md` for motivation. Today `fairagro-middleware-shared` exposes
config, tracing, and API models; it has no harvest-run report types. External
clients duplicate incompatible JSON-LD emitters. This design ports the
harvester report shape into shared as a reusable library with pluggable
formats. Consumers outside this repo adopt it in separate work.

## Goals / Non-Goals

**Goals:**

- Format-neutral domain model matching the harvester report baseline
- JSON-LD serializer as the first format, operator-readable (`indent=2`)
- Extension point for future formats without changing the model
- Optional study/assay fields on repository entries (omit when unset)
- Unit-tested public API under `middleware/shared`
- Versioned in-repo vocabulary under `ns/`, published independently of `docs/`

**Non-Goals:**

- Migrating harvester or sql_to_arc code in this change
- Extra formats beyond JSON-LD
- Parse / round-trip / schema-version APIs for machines
- Porting sql_to_arc-only PROV / instrument / actionStatus terms
- API or api_client behavioral changes
- Custom apex-domain hosting for the vocabulary (e.g. `fairagro.net`)
- Compact unprefixed body keys (sql_to_arc style); keep prefixed wire keys
- Publishing the entire `docs/` tree (or repo root) via GitHub Pages

## Decisions

1. **Package placement: `middleware.shared.report` inside shared**
   - Reason: both client repos already (or will) depend on
     `fairagro-middleware-shared`; a nested module avoids a new PyPI artifact
     until extraction is justified.
   - Alternatives considered: separate workspace package now — deferred;
     living under `api_client` — rejected because shared must not reverse-depend
     and reports are not HTTP-client concerns.

2. **Domain names: `HarvestReport`, `RepositoryReport`, `FailedRecord`**
   - Reason: both tools call the harvest API; harvester naming is the preferred
     baseline and is already familiar to operators.
   - Alternatives considered: `RunReport` / generic naming — rejected after
     product preference for harvest terminology.

3. **Dataclasses for the model; Protocol/ABC for serializers**
   - Reason: harvester already uses dataclasses successfully; serializers are
     a small Strategy surface (`render(report) -> str`). Avoid coupling the
     model to JSON-LD methods as the only path (keep `to_jsonld` optional
     convenience if useful, but format selection goes through the serializer
     API).
   - Alternatives considered: Pydantic-only like sql_to_arc `ProcessingStats` —
     unnecessary for an in-memory builder used at process end.

4. **JSON-LD wire shape = harvester baseline**
   - Reason: newer, multi-RDI, richer failures, `https://schema.org/`, documented
     omit semantics. sql_to_arc maps later to one `EntryPoint` in `result[]`.
   - Alternatives considered: unify on sql_to_arc flat `prov:Activity` —
     rejected (weaker failure detail, broken study/assay mapping to
     `schema:result`, wrong schema.org scheme).

5. **Optional `total_studies` / `total_assays` → `fairagro:totalStudies` /
   `fairagro:totalAssays`**
   - Reason: cheap optional ints preserve sql_to_arc value without overloading
     `schema:result`. Omit when unset.
   - Alternatives considered: drop entirely — acceptable fallback if unexpected
     complexity appears; keep in model because cost is low.

6. **Stdout emit helper with silent failure**
   - Reason: matches harvester contract; report must not change process exit
     behavior for operators.
   - Alternatives considered: raise to caller — rejected for this audience.

7. **No dependency on api / api_client**
   - Reason: shared module boundary in `openspec/principles.md` /
     `openspec/config.yaml`.

8. **Versioned namespace IRI; vocab under `ns/` (not `docs/`)**
   - Canonical namespace IRI (vocabulary major `v1`):
     `https://fairagro.github.io/m4.2_advanced_middleware_api/ns/harvest-report/v1/#`
   - Source of truth in git:
     `ns/harvest-report/v1/context.jsonld`,
     `ns/harvest-report/v1/README.md`,
     optional `ns/harvest-report/v1/index.html` for browser resolution of the
     hash-namespace base URL.
   - Serializer embeds compact `@context` with `fairagro` pointing at that
     versioned IRI; body keys stay prefixed.
   - Reason: unversioned IRIs cannot safely evolve; `docs/` must not be
     wholesale-published just to host a vocab; namespace releases must be
     controllable via tags independent of documentation.
   - Alternatives considered:
     - Unversioned `…/harvest-report#` — rejected (no safe evolution).
     - Pages from branch `/docs` — rejected (exposes all docs; not tag-gated).
     - `raw.githubusercontent.com/.../main/...` — rejected (branch-volatile).
     - Dead `fairagro.net/ns/` — rejected (404).
     - sql_to_arc compact keys / overloaded `schema:` — rejected.

9. **Publish only `ns/` via GitHub Actions on vocabulary tags**
   - Tag pattern: `ns/harvest-report/v<major>.<minor>.<patch>` (e.g.
     `ns/harvest-report/v1.0.0`).
   - Workflow uploads **only** the `ns/` tree (or the tagged vocab folder) to
     GitHub Pages—never `docs/` or application sources.
   - Incompatible vocabulary changes MUST add a new major path
     (`ns/harvest-report/v2/`) and a new serializer IRI; published `v1`
     semantics MUST stay backward-compatible (additive terms only).
   - Reason: GitHub’s branch Pages sources (`/` or `/docs`) cannot publish a
     subdirectory alone; Actions artifact deploy can.
   - Alternatives considered: separate vocab mini-repo — deferred until
     multiple products share the namespace.

10. **Hash fragment on the versioned path (`…/v1#term`)**
    - Reason: one context document covers all terms under that major version.
    - Alternatives considered: slash per-term paths — unnecessary at this size.

## Risks / Trade-offs

- **[Risk] Consumer drift until harvester/sql_to_arc migrate** → Mitigation:
  document the wire contract in `openspec/specs/harvest-report/`; publish via
  existing shared release; migrations are out of scope here.
- **[Risk] Operators comparing old sql_to_arc logs to new shape** → Mitigation:
  accept a one-time break on consumer migration; new shape is intentional.
- **[Trade-off] Optional study/assay in core model** → Slightly broader API than
  harvester today; keeps one shared type instead of extension hooks.
- **[Risk] Pages / Actions misconfigured → dead IRI** → Mitigation: document
  tag + workflow; keep embedded `@context` so offline logs still expand terms
  by IRI string even if HTTP fetch fails.
- **[Risk] Repo rename breaks github.io URLs** → Mitigation: treat published
  IRIs as permanent; redirects or a later successor IRI if the org/repo moves.
- **[Trade-off] Major version in path vs full semver in path** → Major (`v1`)
  keeps the serializer IRI stable across compatible patches; patch tags redeploy
  the same `v1/` tree with additive fixes only.

## Migration Plan

1. Land library + tests + Spec-to-Code mapping in this repo.
2. Add `ns/harvest-report/v1/` vocab files; point serializer at the versioned
   IRI.
3. Add GitHub Actions workflow to publish only `ns/` on
   `ns/harvest-report/v*` tags; enable Pages via Actions (not branch `/docs`).
4. Cut first vocab tag (e.g. `ns/harvest-report/v1.0.0`) when ready to resolve
   the HTTP namespace.
5. Publish shared package via normal release process.
6. Separate consumer-repo migrations (out of scope).

## Open Questions

- None that block implementation. First vocab tag timing is operational.
