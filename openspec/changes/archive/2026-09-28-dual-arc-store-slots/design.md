## Context

See `proposal.md` for motivation. Today `create_arc_store` resolves exactly one backend; `ArcManager` / health hold a
single `_store` and use flags (`supports_standalone_upload`, `publishes_per_arc_git`) to gate behaviour. Consolidated
catalog and per-ARC Git already do real work on different operations and write different CouchDB surfaces.

Lock-ins live on GitHub #517 comments (newer than the original issue body).

## Goals / Non-Goals

**Goals:**

- Wire required `arc_store` + optional `consolidated_store` end-to-end (config → factory → ArcManager → health → Helm)
- Role-based calls only; drop obsolete flags used as behavioural switches
- Hard-cut migration off top-level keys and off `arc_store.type: consolidated_git`

**Non-Goals:**

- Failure-policy framework / peer array of equal stores
- Split ABC into `ConsolidatedArcStore` (#518)
- Record `*_FAILED` after Celery transient exhaustion (#519)
- Remove `GitlabApi` backend (#182)
- Cross-store ordering barrier before finalize

## Decisions

### 1. Two typed config slots (not an array)

**Choice:** Required `arc_store` (nested `git_repo` | deprecated `gitlab_api` selects the backend — no `type` field) +
optional `consolidated_store` (catalog settings under `consolidated_git`; slot name selects the role).

**Why:** Roles already differ (sync vs finalize, ARC events vs harvest catalog events). An array implies equal peers and
a success policy we do not need. Nesting the backend settings key under the slot reuses the historical “type at the
config key” idea without a redundant `type:` discriminator.

**Alternatives:** Homogeneous `arc_stores[]` + policy (rejected); primary/secondary named pair without shared settings
type (rejected — use two slots + shared `GitCliSettings` type).

### 2. ArcManager holds two references; call by role

**Choice:** `arc_store` for `create_or_update` / `GIT_PUSH_*`; `consolidated_store` for `finalize` / `CATALOG_PUSH_*`
only when non-`None`. Do not enqueue finalize when consol. absent. Do not call consol. on the sync path (even if ABC
still has no-op `create_or_update`).

**Why:** Matches lock-in; avoids fake fan-out and flag gymnastics until #518.

### 3. Drop standalone gate

**Choice:** Always accept standalone uploads; sync via `arc_store` only; skip catalog. Remove
`supports_standalone_upload` checks and the arc-upload “reject when consolidated” requirement. Document on
Pydantic/OpenAPI.

**Why:** With required per-ARC `arc_store`, consol.-only deploys are gone; catalog still needs harvest finalize.

### 4. Health: two keys, same aggregation

**Choice:** When git-backend global checks are enabled and consol. is configured, include both `git_backend` and
`consolidated_store_backend` (exact key name flexible). No separate disable flag. `/v3/health` stays ERROR if any
included check is false.

### 5. Ordering

**Choice:** Keep enqueue timing (sync on ingest, finalize on `COMPLETED`). Document no cross-store ordering guarantee;
catalog reads CouchDB.

### 6. Keep one ABC for this change

**Choice:** Both slots may be `ArcStore` implementations; consol. instance simply is not invoked for sync. Port split
deferred to #518.

### 7. Helm in this change

**Choice:** Update chart values comments, config-secret unset logic, and migration notes so canonical dual-slot config
is the only supported form (no top-level store keys).

## Risks / Trade-offs

- **[Risk] Catalog-only deploys break** → Mitigation: migration note; operators must add `arc_store` (GitRepo) even if
  they mainly care about catalog.
- **[Risk] Standalone never updates catalog** → Mitigation: explicit Spec + Swagger text; harvest path remains the
  catalog path.
- **[Risk] #334 / #517 overlap on legacy removal** → Mitigation: implement legacy drop here; close or shrink #334 after
  merge.
- **[Trade-off] Keep-one-ABC** leaves no-op methods on consol. until #518 → Acceptable; ArcManager must not call them on
  the wrong slot.

## Migration Plan

1. Deploy configs: move top-level / `type: consolidated_git` into dual slots; add required `arc_store` where missing.
2. Roll API/worker with new validation (reject old keys).
3. Rollback: previous chart/config only if images rolled back together (breaking config).

## Open Questions

None for this change — lock-ins on #517 cover config, wiring, health, standalone, ordering, Helm, and out-of-scope
splits (#518/#519/#182).
