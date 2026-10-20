## ADDED Requirements

### Requirement: Single-flight critical section for consolidated finalize per RDI

When the consolidated Git backend runs `finalize` for an RDI, the rebuild-through-push **critical section** for that RDI
MUST be single-flight across concurrent callers: at most one such critical section may execute at a time per RDI.
Ephemeral per-call clones and byte-stable catalog rules from **Publish a byte-stable consolidated RDI catalog file on
finalize** remain in force. Overlapping callers MUST wait (bounded) or otherwise serialize rather than racing solely on
Git non-fast-forward. Last-successful-push semantics for conflicts with **external** writers are unchanged.

#### Scenario: Concurrent finalize for one RDI does not parallelize push work

- **GIVEN** two concurrent consolidated `finalize` invocations for the same RDI
- **WHEN** both enter rebuild/push
- **THEN** their critical sections for that RDI do not run in parallel
