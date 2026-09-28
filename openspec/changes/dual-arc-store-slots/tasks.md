## 1. Config models and validation

- [ ] 1.1 Add required `arc_store` + optional `consolidated_store` models (catalog settings; type optional/implied;
      per-slot `git:` with shared `GitCliSettings`) and verify Pydantic accepts valid dual-slot YAML fixtures
- [ ] 1.2 Restrict `arc_store.type` to `git_repo` | deprecated `gitlab_api`; reject `consolidated_git` under `arc_store`
      — verify validation unit tests fail closed
- [ ] 1.3 Remove top-level `git_repo` / `gitlab_api` / `consolidated_git` from API and worker configs; delete or gut
      `legacy_config.py` / legacy resolution branch — verify obsolete keys raise clear errors
- [ ] 1.4 Update `BusinessLogicFactoryConfig` / protocols to expose both slots (no legacy fields) — verify typecheck on
      factory config surface

## 2. Factory and ArcManager wiring

- [ ] 2.1 Change factory to construct `(arc_store, consolidated_store | None)` and pass both into `BusinessLogic` /
      `ArcManager` — verify construction tests for with/without consol.
- [ ] 2.2 Route `sync_to_gitlab` / `GIT_PUSH_*` only to `arc_store`; route `finalize` / `CATALOG_PUSH_*` only to
      `consolidated_store` when present — verify unit tests assert the other store is not called
- [ ] 2.3 Remove `supports_standalone_upload` gate from `create_or_update_arc`; always schedule per-ARC sync — verify
      standalone upload tests pass with consol. configured
- [ ] 2.4 Enqueue finalize on harvest `COMPLETED` only when `consolidated_store` is set — verify no enqueue when absent;
      enqueue when present (including unchanged harvest / re-COMPLETE)
- [ ] 2.5 Drop or stop using `publishes_per_arc_git` as sync/event gate where the slot already implies the role — verify
      event tests still pass
- [ ] 2.6 Shutdown both stores when present — verify shutdown called on consol. executor path

## 3. Health

- [ ] 3.1 Extend global health to check `arc_store` and, when configured, `consolidated_store` as separate keys under
      existing git-backend health enablement — verify map keys and `all()` aggregation (consol. false → ERROR)

## 4. Helm and operator docs

- [ ] 4.1 Update Helm values comments / examples to dual-slot canonical form; remove legacy top-level guidance — verify
      values render / chart docs read correctly
- [ ] 4.2 Update `config-secret` (and related templates) so obsolete top-level keys are not required or silently
      preferred — verify template logic against dual-slot fixture
- [ ] 4.3 Add migration notes (NOTES or chart README) for consol.-only and top-level key deploys — verify text mentions
      required `arc_store` + optional `consolidated_store`

## 5. OpenAPI / Swagger copy

- [ ] 5.1 Update Pydantic model descriptions for standalone ARC create so OpenAPI states per-ARC-only publish (no
      consolidated catalog) — verify generated schema/description text

## 6. Tests and quality

- [ ] 6.1 Update/remove tests that assumed exactly one backend, consol.-only standalone reject, and legacy top-level
      resolution — verify focused `uv run pytest` on affected packages
- [ ] 6.2 Run format/lint on touched Python (`ruff`) and Prettier on changed Markdown — verify clean
- [ ] 6.3 `openspec validate dual-arc-store-slots` (or project equivalent) stays green after artifact edits — verify
      validate succeeds
