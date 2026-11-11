# Design

## Context

See proposal.md — Why. Catalog finalize already returns `CatalogFinalizeResult.pushed` and builds distinct message
strings for publish vs unchanged; only the harvest event **type** always stays `CATALOG_PUSH_SUCCESS`.

## Goals / Non-Goals

**Goals:**

- Map `pushed=False` → `CATALOG_PUSH_SKIPPED`, `pushed=True` → `CATALOG_PUSH_SUCCESS`
- Reuse existing message helper text for both types
- Keep partial-ARC skip summaries on whichever type is chosen

**Non-Goals:**

- Exposing `catalog_events` on HTTP `HarvestResponse`
- Changing when finalize pushes (byte-stable comparison unchanged)
- New event type for partial ARC omission alone

## Decisions

1. **Enum member name `CATALOG_PUSH_SKIPPED`** — Matches per-ARC `GIT_PUSH_SKIPPED` wording; prefer over
   `CATALOG_UNCHANGED` so operators filter one “skipped push” vocabulary.
2. **Branch only on `outcome.pushed`** — Do not invent a second signal; `CatalogFinalizeResult` already owns the push
   boolean. Alternatives: message-text heuristics (rejected — fragile).
3. **Shared message builder** — Rename/clarify `_catalog_push_success_message` to a neutral helper (e.g.
   `_catalog_push_event_message`) used for SUCCESS and SKIPPED; behaviour of the string stays the same.

## Risks / Trade-offs

- **[Risk] Strict readers of harvest docs reject unknown enum** → Mitigation: additive member; events are not on the
  public harvest HTTP response today; document in changelog if external tooling scrapes CouchDB.
- **[Risk] Dashboards keyed only on SUCCESS under-count no-ops** → Mitigation: intentional; filters should include
  SKIPPED or treat SUCCESS as “pushed only”.

## Migration Plan

- Deploy API/worker with the new enum; existing CouchDB events remain valid.
- No backfill of historical SUCCESS-for-no-op rows.
