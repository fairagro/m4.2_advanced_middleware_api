# Design

## Context

See `proposal.md` — Why. Existing `HarvestReport` / `RepositoryScope` already owns harvested, failed (+ `failures`
list), skipped, and optional composition counts; JSON-LD maps failures via `_failure_node`. Warnings should reuse that
pattern rather than invent a second issue type.

## Goals / Non-Goals

**Goals:**

- One API path to record a dataset-scoped warning (count + issue list).
- Additive JSON-LD v2 terms so existing consumers keep parsing.
- Clear separation: warned datasets MAY also be counted as harvested; never auto-count as failed/skipped.

**Non-Goals:**

- Harvester / sql-to-arc call-site changes (linked follow-ups).
- Repository-level warnings (no `record_repository_warning` in MVP — mirror dataset-scoped failures first; repo-level
  issues stay on the failures list via `record_repository_issue`).
- Bumping vocabulary to v3.
- Changing log/ARC-comment behaviour in consumers.

## Decisions

1. **Reuse `HarvestIssue` for warning entries** Same fields (`message`, `kind`, optional `record_id` / `url`). MVP
   recording method always uses `kind=dataset` (like `record_failed`). Alternatives considered: separate
   `HarvestWarning` dataclass — rejected (duplication); allow repository-kind warnings in MVP — deferred (no caller need
   yet).

2. **Separate list and count from failures** `warnings: tuple[HarvestIssue, ...]` and `warned_datasets: int` on the
   snapshot; mutable list + counter on the scope. Wire: `fairagro:warnedDatasets` always (including 0, same as skipped);
   `fairagro:warnings` only when non-empty (same omission pattern as `fairagro:failures`). Alternatives: fold warnings
   into `failures` with a new kind — rejected (would inflate failure semantics / operator filters).

3. **Caller still records harvested separately** `record_warning` does not call `record_harvested`. Consumers that
   harvested with a non-fatal problem call both. Alternatives: auto-increment harvested on warning — rejected
   (warning-only repo issues must not invent harvests; and some tools may warn before deciding harvest success).

4. **Stay on vocabulary v2** New terms are additive. Update `ns/harvest-report/v2/README.md` (and context if terms are
   listed there).

## Risks / Trade-offs

- [Operators confuse warnings with failures] → Spec + wire field names keep lists separate; docs state non-inflation.
- [Consumers forget to call `record_harvested`] → Follow-up acceptance criteria in harvester/sql-to-arc; shared library
  does not couple the two.
- [Large warning lists in big runs] → Same unbounded-list trade-off as failures today; no new cap in MVP.

## Migration Plan

1. Land shared library + tests + ns docs; release middleware shared package.
2. Harvester #637 / sql-to-arc #339 bump dependency and call `record_warning`.
3. No rollback beyond reverting the shared release; additive wire fields are forward-compatible for old readers that
   ignore unknown keys.
