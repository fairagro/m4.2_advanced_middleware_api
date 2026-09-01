# Catalog Dataset Materialize — Design

## Context

See proposal.md — Why. Today finalize runs:

`extract_catalog_dataset` → `normalize_catalog_datasets` → `serialize_catalog_file`.

Only the root RO-Crate `Dataset` node is extracted; referenced `@graph` entities
(Person, Comment, Study, Assay, `#LICENSE`) are left as `@id` pointers.
`catalog-schema-org-jsonld` added worker-side expand/compact and vendored
schema.org context; `catalog-jsonld-relative-ids` added internal compact base
(B1) so relative path IDs survive without `example.org` in output. Neither
step resolves references.

## Goals / Non-Goals

**Goals:**

- Self-contained schema.org `Dataset` entries in `{rdi}.json` with maximal
  useful fields (Person, license, Study/Assay hierarchy, citation).
- Materialize **before** expand/compact so pyld validates the enriched shape.
- First-class schema.org types where possible; `Comment` only as fallback for
  unmappable LDComment metadata.
- Best-effort on missing refs (omit + warn); align with partial-push finalize.
- Preserve catalog array shape and existing normalize/serialize contracts.

**Non-Goals:**

- Harvester, ARCtrl, or CouchDB ARC body changes.
- Full RO-Crate `@graph` copy or ISA/LabProcess reconstruction.
- Materializing nested `comment` / `creativeWorkStatus` on `ScholarlyArticle`.
- Following `about` → LabProcess, Sample, PropertyValue chains.
- API-ingest materialization or new config options.

## Decisions

### Decision: Materialize-before-normalize (explicit walk)

**Choice:** New step `materialize_catalog_dataset(record, arc_content)` between
extract and normalize. Build `@graph` index keyed by `@id`; walk selected
properties on the root Dataset (and one level of nested Study `hasPart`);
copy whitelisted fields into inline objects.

**Why:** Full control over depth, types, and field whitelist. Subgraph
expand/compact (alternative B) produces unpredictable `@graph` compact shapes;
post-compact enrichment (alternative C) fights pyld output.

**Alternatives:** Mini-`@graph` document for pyld only (rejected—hard to extract
single Dataset); post-compact patch (rejected—duplicate logic).

### Decision: Property and type whitelist

**Choice:** Materialize only:

| Source property | Target | Max depth |
|-----------------|--------|-----------|
| `creator`, `author`, `contributor` | inline `Person` | 1 hop from root or Study |
| `comment` (root) | map to `keywords` / `inLanguage` or inline `Comment` | 1 hop |
| `license` | URL string, text string, or omit `#LICENSE` | 1 hop (`#LICENSE` node) |
| `citation` | inline `ScholarlyArticle` / `CreativeWork` fields | 1 hop, no nested comment |
| `hasPart` | inline `Dataset` (Study/Assay via `additionalType`) | 2 hops (root→Study→Assay) |

**Person fields:** `givenName`, `familyName`, `name`, `email`, `sameAs`,
`affiliation` (inline name if DefinedTerm ref).

**Dataset fields (hasPart):** `@type`, `additionalType`, `identifier`, `name`,
`description`, `datePublished`, `dateModified`, plus Person props on Study.

**Why:** Matches BonaRes/OpenAgrar Investigation→Study→Assay without pulling
lab metadata graphs.

### Decision: LDComment → schema.org mapping

**Choice:** When `Comment.name` matches known keys (case-insensitive), set
schema.org property instead of `comment`:

- `Keywords` → `keywords` (split `text` on comma if needed)
- `Language` → `inLanguage`

Otherwise inline `Comment` with `name` and `text` (strip fragment `@id`).

**Why:** User preference for first-class schema.org types over Comment nodes.

**Alternatives:** Always inline Comment (rejected—noisy for harvest metadata).

### Decision: `#LICENSE` resolution

**Choice:** If `license` is `{"@id": "#LICENSE"}`:

1. `#LICENSE` node has `url` → `license` = URL string
2. else node has `text` → `license` = text string
3. else root already has string `license` → keep
4. else omit `license` + warning

**Why:** Matches ARCtrl pattern in production ARCs (`edaphobase.json`).

### Decision: Strip fragment `@id` on inlined nodes

**Choice:** Remove `@id` / `id` on materialized Person and Comment objects.
Keep relative path `@id` on `hasPart` Study/Assay children.

**Why:** Catalog consumers need data fields, not ARCtrl fragment conventions.
Supersedes prior “keep `#Person_…` relative” interpretation for inlined nodes
only (see MODIFIED spec).

### Decision: Missing references — omit and warn

**Choice:** If `@graph` lacks a referenced `@id`, drop that property value or
list item; log warning with arc id and missing `@id`. Do not fail finalize.

**Why:** Consistent with `normalize_catalog_datasets_best_effort` partial push.

**Alternatives:** Fail-closed (rejected—blocks whole RDI); keep dangling ref
(rejected—defeats purpose).

### Decision: Wire point

**Choice:** Call materialize inside `_collect_catalog_datasets` immediately
after successful `extract_catalog_dataset`, before normalize. Implementation
lives in `catalog_serialize.py` (or sibling module imported there).

**Why:** Keeps finalize orchestration in `store.py` thin; unit-testable without
Git/CouchDB.

### Decision: `additionalType` on Study/Assay

**Choice:** Preserve `additionalType` strings (`Investigation`, `Study`, `Assay`)
on materialized `Dataset` nodes; `@type` remains `Dataset`.

**Why:** Standard schema.org property; distinguishes ISA levels without
Bioschemas-only types.

## Risks / Trade-offs

- **[Risk] Larger catalog entries** → Limit to 2-hop `hasPart`; no LabProcess
  follow; monitor size in production.
- **[Risk] LDComment name variants** → Start with Keywords/Language; extend map
  in follow-up if harvest patterns need it.
- **[Risk] Breaking catalog bytes** → Expected on next finalize (documented).
- **[Trade-off] Anonymous inline Person** → Loses link to RO-Crate `@id`; OK
  for catalog use case.
- **[Trade-off] Citation without nested comment** → Publication status notes
  dropped; acceptable for catalog discovery.

## Migration Plan

1. Implement materialize + tests; deploy workers.
2. Next finalize per RDI rewrites `{rdi}.json`.
3. Rollback: revert code; subsequent finalize restores prior extract-only
   behaviour for newly rebuilt catalogs.

## Open Questions

- Exact LDComment `name` strings beyond Keywords/Language (collect from
  production exports when available; safe to extend mapping later).
