## ADDED Requirements

### Requirement: Single-flight overlapping catalog finalize for the same RDI

When multiple catalog finalize worker tasks for the **same RDI** overlap (concurrent harvest completes, re-complete
re-enqueue, or retries), the system MUST ensure that at most one finalize **critical section** (document-store catalog
rebuild through Git commit/push attempt) runs at a time for that RDI. Additional tasks for that RDI MUST wait for the
active critical section (bounded) and then either run against current document-store state or observe an unchanged
catalog and skip commit/push. The system MUST NOT drop the enqueue-on-`COMPLETED` / re-complete re-enqueue behaviour
from **Finalize ArcStore catalog on harvest completion**. Failing to acquire the single-flight lock within the bound
MUST be treated as a retryable (transient) finalize failure rather than a permanent catalog failure.

#### Scenario: Overlapping finalize tasks serialize per RDI

- **GIVEN** `consolidated_store` is configured and two finalize tasks for RDI `edal` are active concurrently
- **WHEN** both attempt the rebuild/push critical section
- **THEN** the critical sections do not run in parallel for `edal`
- **AND** both complete without relying solely on Git non-fast-forward races between each other

#### Scenario: Lock wait timeout is transient

- **GIVEN** a finalize task cannot enter the per-RDI critical section before the wait bound elapses
- **WHEN** finalize aborts for that reason
- **THEN** the failure is retryable (Celery may retry)
- **AND** the harvest remains `COMPLETED` (no forced harvest status change)
