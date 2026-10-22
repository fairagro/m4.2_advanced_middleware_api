# Spec Delta

## ADDED Requirements

### Requirement: Bound graceful Git executor shutdown

When a Git-backed store shuts down while Git work is in flight, it MUST wait up to a finite bound for that work to
finish, including removal of the ephemeral working directory for that attempt. Work that has not started MUST NOT start.
When the bound expires, shutdown MUST return even if work is still running. Shutdown MUST NOT wait without a bound.
Directories left behind stay subject to **Reclaim stale ephemeral Git cache directories**.

#### Scenario: In-flight work finishes within the bound

- **GIVEN** a Git-backed store with one in-flight operation that removes its ephemeral working directory when it
  finishes
- **WHEN** the store shuts down and that operation finishes before the bound
- **THEN** shutdown waits until the operation has finished
- **AND** the ephemeral working directory for that operation is gone

#### Scenario: Shutdown returns when the bound expires

- **GIVEN** a Git-backed store with one in-flight operation that does not finish
- **WHEN** the store shuts down and the bound expires
- **THEN** shutdown returns
- **AND** it does not wait further for that operation

#### Scenario: Work that has not started does not start

- **GIVEN** a Git-backed store with one operation that has not started
- **WHEN** the store shuts down
- **THEN** that operation does not run

### Requirement: Log a failed ephemeral workdir delete

When a Git-backed store fails to remove an ephemeral working directory, it MUST log a warning that identifies that
directory. The failure MUST NOT by itself fail the Git operation that already finished, and it MUST NOT by itself fail
store shutdown.

#### Scenario: Delete failure after a finished publish is a warning

- **GIVEN** a catalog or per-ARC Git operation that has already finished its Git work
- **WHEN** removing its ephemeral working directory fails
- **THEN** a warning is logged that identifies the directory
- **AND** the Git operation's outcome is unchanged

#### Scenario: Delete failure does not fail shutdown

- **GIVEN** a store shutdown that is waiting for in-flight Git work
- **WHEN** that work fails to remove its ephemeral working directory
- **THEN** a warning is logged
- **AND** shutdown still completes
