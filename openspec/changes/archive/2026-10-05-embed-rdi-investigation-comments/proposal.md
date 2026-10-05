# Proposal

## Why

Source RDI context lives only outside the ARC today (request/harvest `rdi`, CouchDB envelope, Celery task, ArcStore
topics). After Git sync or clone, the ARC no longer records which RDI it belongs to. Issue #258 asks for a portable,
ISA-aligned mirror inside the ARC that survives `ARC.from_rocrate_json_string` → `arc.Write()`, without treating ARC
content as the security boundary.

## What Changes

- Embed authorized source RDI on the Investigation via standardized ISA Comments (`RDI`, `RDI Description`, `RDI URL`)
  during ingest (standalone and harvest paths).
- Extend deployment config so each known RDI can carry description and canonical URL (identifier list remains the auth
  allowlist surface; string-only entries stay valid with empty description/URL).
- Validate client-supplied `Comment[RDI]` against the authorized request/harvest RDI; conflict → `422`. Description and
  URL are always written from the deployment registry (overwrite).
- Enrich **before** `content_hash` / document store so identical re-submits stay idempotent after injection.
- Unit tests for enrichment, conflict, harvest path, and idempotent re-submit.
- **Not BREAKING** for wire APIs: `rdi` on `CreateArcRequest` / harvest document remains required for authorization.
- **Not** removing the `rdi` argument from ArcStore / Celery in this change (Issue Phase 3 deferred).

## Capabilities

### New Capabilities

- _(none)_

### Modified Capabilities

- `arc-manager`: After structural RO-Crate validation and before document persist, inject/update Investigation RDI
  Comments from the authorized RDI + registry; reject conflicting `Comment[RDI]`; ensure enriched body is what is hashed
  and queued for Git sync.
- `arc-upload`: Document that conflicting client `Comment[RDI]` maps to HTTP `422` via the shared pipeline mapping
  (behavior owned by `arc-manager/`).
- `harvest-arc-upload`: Same `422` conflict behavior when harvest RDI disagrees with ARC `Comment[RDI]`.

## Impact

- **Code:** `ArcManager.create_or_update_arc` enrichment helper; API (+ worker) `Config` RDI registry shape;
  `dependencies.get_known_rdis` still exposes identifier strings; focused unit tests.
- **Specs:** `openspec/specs/arc-manager/`, `arc-upload/`, `harvest-arc-upload/`.
- **Ops:** Deployments that want non-empty Description/URL Comments must supply them in config; identifiers alone still
  work (empty comment values).
- **Out of scope:** AnnotationTable / Study-Assay process modelling; RO-Crate `Organization` as sole carrier;
  proprietary sidecars; removing envelope/`rdi` auth; ArcStore `rdi` parameter removal (Phase 3); api_client README
  Phase 4 beyond a brief note if touched.
