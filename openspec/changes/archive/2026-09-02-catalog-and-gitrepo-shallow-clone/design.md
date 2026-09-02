# Catalog and GitRepo shallow clone — Design

## Context

See `proposal.md` and [#346](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/346).
`GitContext.__enter__` calls `Repo.clone_from(url, path, branch=…)` with no
`depth`. Consolidated catalog finalize and `GitRepo` create-or-update / get both
use that path into ephemeral workdirs. Neither path needs commit history beyond
the tip.

## Goals / Non-Goals

**Goals:**

- Always pass `depth=1` on fresh clones in `GitContext`.
- Cover ConsolidatedGit and `GitRepo` without per-backend forks or YAML.
- Preserve soft-404 → init, sync-existing-repo, and push error behaviour.

**Non-Goals:**

- Sparse-checkout.
- ConfigWrapper / YAML `clone_depth`.
- Changing fetch/`reset --hard` semantics for rare pre-existing `.git` dirs
  beyond what Git already does on shallow repos.
- #349 in-memory catalog peak.

## Decisions

### 1. Hardcode depth in shared `GitContext` clone

**Choice:** Add `depth=1` to the `Repo.clone_from` call in `GitContext.__enter__`
when creating a new clone (no `.git` yet). Do not add fields to
`GitContextConfig` or `GitCliSettings`.

**Why:** Both backends share this entry point; tip-only usage makes depth always
correct; user chose no config when applying to both backends.

**Alternatives:**

- Catalog-only override via `GitContextConfig.clone_depth` — rejected (user wants
  both backends, no YAML).
- YAML `clone_depth` on `GitCliSettings` — rejected for this change.

### 2. Leave `_sync_existing_repo` unchanged

**Choice:** Existing-dir path (`fetch` + `reset --hard`) stays as-is. Ephemeral
`mkdtemp` workdirs mean this path is rare; shallow fresh clones are the hot path.

**Why:** Avoid expanding scope into deepen/unshallow logic.

### 3. Tests assert clone kwargs and tip behaviour

**Choice:** Unit-test that `clone_from` receives `depth=1` (mock). Keep or extend
integration-style bare-remote tests so publish/sync still work.

**Why:** Depth is an implementation contract of the clone; tip publish is the
observable guarantee.

## Risks / Trade-offs

- **[Risk] Future need for full history in workers** → Mitigation: reopen with
  config or unshallow; current code never reads history.
- **[Risk] Exotic remotes rejecting shallow clones** → Mitigation: same soft/
  transient error paths; unlikely for GitLab/file remotes we use.
- **[Trade-off] Working-tree size for catalog (all `{rdi}.json`)** → unchanged;
  sparse is a follow-up.

## Migration Plan

- Deploy only; no remote migration. Rollback = revert the `depth=1` commit.

## Open Questions

None.
