# Design

## Context

See `proposal.md` — Why. Dual-slot config and call sites already route sync vs finalize by role. Both backends still
subclass one `ArcStore` ABC with shared OTEL/error wrappers; catalog stubs CRUD and per-ARC inherits default `finalize`.
Explore lock-in for #615: **option C** (small shared lifecycle base + two role ABCs).

## Goals / Non-Goals

**Goals:**

- Make illegal cross-role calls a type error at `ArcManager` / factory / health wiring.
- Keep one place for tracer init, `check_health` error wrap, and default `shutdown`.
- Drop stubs/no-ops that only existed for the single ABC.
- Spec contract matches typed ports (no “call finalize on GitRepo”).

**Non-Goals:**

- Protocols-only ports (option B).
- Peer store arrays / cross-store failure policy.
- Renaming `git_repo/` or `consolidated_git/` packages.
- Changing finalize catalog semantics, locks, or JSON-LD materialization.
- Offline filesystem stand-in unless it currently subclasses product `ArcStore` (it does not for this ABC).

## Decisions

### 1. Shared lifecycle base + two role ABCs (option C)

- **`_ArcStoreBase`** (name may be public `ArcStoreBase` if exports need it): owns tracer, `check_health` /
  `_check_health`, default `shutdown`, shared error helpers. **No** `create_or_update` / `finalize`.
- **`ArcStore(_ArcStoreBase)`**: per-ARC public wrappers + abstract `_create_or_update` / `_get` / `_delete` /
  `_exists`. No `finalize`.
- **`ConsolidatedArcStore(_ArcStoreBase)`**: public `finalize` wrapper + abstract `_finalize`. No per-ARC CRUD.
- **`GitRepo(ArcStore)`**, **`ConsolidatedGitArcStore(ConsolidatedArcStore)`**.
- Shared errors (`ArcStoreError`, …) and `CatalogFinalizeResult` stay module-level (not on a role ABC).
- `arc_id` static helper stays on `ArcStore` (per-ARC identity) or moves to a free function already used via
  `calculate_arc_id` — prefer keep `ArcStore.arc_id` as thin alias for call-site stability.

**Alternatives:** A (two ABCs, duplicate wrappers) — more copy-paste. B (Protocols) — fights existing wrapper ABC
pattern in this package.

### 2. Typing at dual slots only (MVP)

- `create_arc_stores` → `(ArcStore, ConsolidatedArcStore | None)`.
- `ArcManager.__init__(store: ArcStore, consolidated_store: ConsolidatedArcStore | None = None)`.
- Health keys unchanged (`git_backend`, `consolidated_store`); values call `.check_health()` on the typed instances.
- No runtime `isinstance` branching for roles beyond what already exists for optional consolidated slot.

### 3. Remove cross-role surface

- Delete `ConsolidatedGitArcStore` CRUD stubs (`_create_or_update` / `_get` / `_delete` / `_exists`).
- Remove `ArcStore._finalize` / `finalize` default and public wrapper from the per-ARC ABC (move finalize wrappers onto
  `ConsolidatedArcStore` only).
- Tests that asserted per-ARC default finalize no-op are replaced with: `ArcStore` has no `finalize`; consolidated port
  requires `_finalize`; factory/wiring types accept matching ports.

### 4. Spec edits

- **REMOVED** “Support optional finalize on ArcStore”.
- **MODIFIED** role-based ops + finalize outcome requirements to name the two ports and drop per-ARC finalize scenarios.
- **ADDED** explicit port/lifecycle typing requirement.
- Purpose in main `openspec/specs/arc-store/spec.md` updated to mention both ports (Purpose is not delta-mergeable).

## Risks / Trade-offs

- **[Risk]** Call sites or tests still call `store.finalize` on a mock `ArcStore` → Mitigation: grep + fix in apply;
  focused unit tests.
- **[Risk]** Export/`__all__` churn for new type name → Mitigation: export `ConsolidatedArcStore` (+ base if public)
  from `middleware.api.arc_store`.
- **[Trade-off]** Extra type name in docs vs A’s two flat ABCs — accepted for shared lifecycle.

## Migration Plan

- Pure typing/refactor; no config or wire-format change. Deploy as normal API/worker image bump.
- Rollback: revert the PR; dual-slot runtime behavior unchanged in intent.

## Open Questions

_None — explore locked option C; GitlabApi already absent._
