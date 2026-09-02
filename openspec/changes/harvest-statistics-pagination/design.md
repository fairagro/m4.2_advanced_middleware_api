# Harvest statistics pagination — Design

## Context

See `proposal.md` and [#345](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/345). Today
`CouchDB.get_harvest_statistics` calls `find_projected` once; `CouchDBClient.find_projected` defaults `limit` to
`default_query_limit` (100) and logs when a page is full. No second page is fetched.

Harvest finalization (`HarvestManager.transition_harvest`) persists whatever statistics the document store
returns. Downstream catalog finalize logic (consolidated Git) may use `arcs_new + arcs_updated` to decide whether
a catalog rebuild is needed; truncated stats can suppress finalize incorrectly.

## Goals / Non-Goals

**Goals:**

- Scan all ARC rows for `metadata.last_harvest_id == harvest_id` when computing statistics.
- Keep projection minimal (`metadata.first_harvest_id`, `metadata.last_changed_harvest_id`) to limit payload size
  per page.
- Reuse existing classification logic in `get_harvest_statistics`.

**Non-Goals:**

- New CouchDB indexes solely for this change (existing selector is sufficient).
- Changing `default_query_limit` globally.
- Rewriting harvest HTTP contracts.

## Decisions

### 1. Page loop on `find_projected` with `skip` until short page

**Choice:** In `get_harvest_statistics`, loop:

```text
skip = 0
repeat:
  page = find_projected(selector, fields, limit=page_size, skip=skip)
  aggregate page into stats
  if len(page) < page_size: break
  skip += page_size
```

Use `page_size = self._config.default_query_limit` (or client default) for consistency with other store queries.

**Why:** Works on `main` without requiring bookmark support. `find_projected` already accepts `skip`/`limit`.
Issue #345 accepts skip paging when bookmark is unavailable.

**Alternatives:**

- **Bookmark paging on `_find`:** Preferred when `find_page` / bookmark exists (see #343 on consolidated branch).
  Adopt on branches that already ship bookmark helpers; same outer aggregation loop.
- **Raise when page is full:** Fails closed but breaks large harvests — rejected.

### 2. Keep per-page truncation warning in the client

**Choice:** Leave `find_projected`'s "exactly limit documents" warning; callers that paginate consume subsequent
pages. Optionally downgrade to debug for interior pages if log noise becomes an issue — not required initially.

### 3. No change to statistics schema

**Choice:** Same `HarvestStatistics` fields and classification rules; only completeness fixes.

## Risks / Trade-offs

- **[Risk] Skip paging cost on very large harvests** → Mitigation: projected fields only; page size configurable
  via `default_query_limit`; bookmark path available on branches with #343.
- **[Risk] Concurrent ARC writes during finalize** → Accepted; same race as today (stats are point-in-time at
  finalize).

## Migration Plan

- Deploy API/worker with paginated statistics; no CouchDB migration.
- Large harvests finalized after deploy get correct stats on next completion.

## Open Questions

None for `main`. If this branch merges into `feature/consolidated_arc_store`, prefer wiring
`find_projected` through the existing bookmark helper when present.
