# Design

## Context

See proposal.md — Why. Ingest today validates with `RoCratePayload` only (no arctrl on the HTTP path), stores the dict
in CouchDB, and queues the same JSON string for the worker, which parses with arctrl and `Write()`s the ISA scaffold.
RO-Crate `Organization` nodes do not survive that round-trip; Investigation `Comment` nodes do (`name` + `text`, linked
from root `./` via `comment`).

Lock-in: Comments MVP (not AnnotationTable). Auth remains request/harvest `rdi` + cert allowlist.

## Goals / Non-Goals

**Goals:**

- Enrich the stored/queued RO-Crate with the three Investigation Comments before hash/persist.
- Keep structural validation free of arctrl on the ingest path.
- Config carries optional description/URL per known RDI without breaking string-only `known_rdis` YAML.
- Map `Comment[RDI]` conflicts to HTTP `422` via the existing semantic-error path.

**Non-Goals:**

- Removing `rdi` from Celery / ArcStore / GitLab metadata builders (Issue Phase 3).
- Harvester-side pre-fill (Phase 4).
- Changing `content_hash` volatility rules (Comments are semantic; included in the hash by design).

## Decisions

1. **Enrich on the RO-Crate JSON graph, not via arctrl on ingest** — After `parse_rocrate`, mutate `@graph`: upsert
   three `@type: Comment` nodes with `name` / `text`, ensure root `./` `comment` links them, remove superseded Comment
   nodes with the same `name`. Reason: `arc-manager` forbids arctrl on the ingest path; worker arctrl still materializes
   Comments into `isa.investigation.xlsx` on sync. Alternative considered: `ARC.from_rocrate_json_string` +
   `ToROCrateJsonString` on ingest — rejected (would change the “no arctrl on ingest” contract and add CPU/latency).

2. **Stable Comment `@id`s by name** — Use fixed ids `#Comment_RDI`, `#Comment_RDI_Description`, `#Comment_RDI_URL` (not
   arctrl’s value-embedding `#LDComment_…` pattern). Reason: overwriting description/URL must not orphan old nodes or
   churn `@id`s; hash stability for identical logical RDI metadata. On upsert, drop any other Comment node with the same
   `name` and rewrite root `comment` refs.

3. **Conflict only on `Comment[RDI]` identity** — Non-empty trimmed `text` that differs from authorized `rdi` → reject
   (`InvalidJsonSemanticError` or a thin subclass that still maps to `422`). `RDI Description` / `RDI URL` always
   overwritten from registry. Reason: registry is SoT for human-readable fields; only the identifier can assert a
   different affiliation. Alternative: require all three to match — rejected as brittle when ops update descriptions.

4. **Config: backward-compatible RDI entries** — Model each known RDI as `{id, description?, url?}` while still
   accepting bare strings in YAML (`"edal"` ≡ `{id: edal, description: "", url: ""}`). Expose identifier list via a
   helper used by auth (`get_known_rdis`) and GitLab topic validation. Apply the same shape on API and worker Config.
   Reason: existing deployments keep working; description/URL become opt-in for richer Comments.

5. **Enrichment order in `create_or_update_arc`** — `parse_rocrate` → enrich/validate Comments → `model_dump` / persist
   → dispatch. Reason: hash and CouchDB body must reflect Comments so bare re-submits converge after injection.

6. **Defer ArcStore `rdi` decoupling** — Git metadata and topics continue to use the task/envelope `rdi`. Reason:
   smallest MVP; Phase 3 can read Comments later with parameter fallback.

## Risks / Trade-offs

| Risk                                                                  | Mitigation                                                                                                                         |
| --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Hand-built Comment JSON diverges from arctrl encoding                 | Mirror verified `name`/`text`/`@type`/`comment` link shape; unit-test round-trip through `ARC.from_rocrate_json_string` → Comments |
| Clients send Comments under Investigation entity `@id` not root `./`  | Prefer Comments linked from root; also accept/scan `@graph` Comment nodes by `name` for conflict detection; write only on root     |
| Empty description/URL look “missing” in ISA                           | Document that empty strings are valid when registry omits them                                                                     |
| Enrichment changes hashes for previously stored ARCs without Comments | Expected once; next harvest/update rewrites body and re-syncs — not a silent auth change                                           |

## Migration Plan

1. Deploy config accepting string or object `known_rdis` entries; optionally fill description/URL.
2. Ship enrichment; first update of each ARC rewrites body with Comments and schedules sync when content changes.
3. Rollback: revert release; Comments already written remain harmless portable metadata.

## Open Questions

_(none — Phase 3/4 deferred by proposal)_
