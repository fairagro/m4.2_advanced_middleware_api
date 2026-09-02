# Catalog finalize skip observability — Design

## Context

See `proposal.md`. Consolidated finalize already collects `(arc_id, reason)`
skips internally (`_collect_catalog_datasets`) but `ArcStore.finalize` /
`_finalize` only return `bool` (pushed). `ArcManager.finalize_catalog` therefore
cannot put skip detail into `HarvestCatalogEvent.message`.

## Goals / Non-Goals

**Goals:**

- Typed finalize outcome available to `ArcManager`.
- Harvest-visible skip summary on `CATALOG_PUSH_SUCCESS` when skips > 0.
- Default no-op backends unchanged for operators (empty skips).

**Non-Goals:**

- Structured CouchDB fields on `HarvestCatalogEvent` beyond `message`.
- New `CatalogPushEventType` or `ArcEventType`.
- Passing `harvest_id` into the store for per-ARC events.
- Last-good merge.

## Decisions

### 1. Result object instead of bool

**Choice:** Introduce a small immutable result (e.g. dataclass) with at least
`pushed: bool`, `dataset_count: int`, `skipped: Sequence[tuple[str, str]]`
(arc_id, reason). Change `ArcStore.finalize` / `_finalize` to return it.
Default `_finalize` returns `pushed=False`, empty skips, `dataset_count=0`.
Consolidated `_finalize` fills from the existing collect/publish path.
Keep a `bool`-compatible story only via the `pushed` field — do not keep a
parallel bool API.

**Why:** Callers need more than push/no-push; a single return type avoids
side channels. Reasons stay available for logs and optional message truncation
policy.

**Alternatives:**

- Enrich message only inside the store by writing harvest events — rejected
  (store should not own harvest documents; no `harvest_id` today).
- New event type `CATALOG_PUSH_PARTIAL` — rejected for interim (proposal).

### 2. Enrich SUCCESS message in ArcManager

**Choice:** When `harvest_id` is set and `skipped` is non-empty, append a
compact clause to the existing success string, e.g. counts plus up to N
`arc_id`s (constant such as 20), with an “+K more” suffix if truncated.
Full reasons remain in worker logs (already emitted). No schema change to
`HarvestCatalogEvent`.

**Why:** Meets harvest-visible AC with minimal wire/schema churn; `message` is
already the operator-facing field.

**Alternatives:**

- Persist structured `skipped` JSON on the event — deferred (larger CouchDB /
  API surface).
- Per-ARC `add_event` — deferred to lifecycle / #340.

### 3. Compatibility for callers of finalize

**Choice:** Update all in-repo callers (`ArcManager`, tests, any Celery path)
to the result type in the same change. No public HTTP contract exposes the
bool today.

**Why:** Internal port only; one-shot migration is cheaper than a deprecation
shim.

## Risks / Trade-offs

- **[Risk] Long skip lists bloat CouchDB messages** → Mitigation: hard cap on
  IDs in the message; counts always present.
- **[Risk] Operators miss that SUCCESS can mean “partial catalog”** → Mitigation:
  explicit skip clause in the message; docs/issue note that datasets may still
  disappear until last-good (#356 target).
- **[Trade-off] Reasons not in harvest event** → Acceptable for interim; logs
  retain detail.

## Migration Plan

- Deploy worker + API image together (same package). Rollback = revert; old
  messages simply lack skip clauses.
- No CouchDB migration.

## Open Questions

None for implementation. ID list cap can be a named constant without a YAML
knob.
