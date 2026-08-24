# Harvest Manager — Delta

## ADDED Requirements

### Requirement: Finalize ArcStore catalog on harvest completion

When a harvest transitions to `COMPLETED`, the system SHALL request ArcStore
`finalize` for that harvest’s RDI (via an asynchronous worker task). Harvest
status transition to `COMPLETED` MUST NOT wait for the Git push to finish. The
system MUST record distinct harvest/catalog events for catalog publish success
and failure so operators can distinguish “harvest complete” from “RDI catalog
flushed”.

#### Scenario: Complete harvest enqueues catalog finalize

- **GIVEN** a running harvest for RDI `edal` with the consolidated backend
  configured
- **WHEN** the harvest is completed
- **THEN** the harvest status becomes `COMPLETED` and a finalize task for
  `edal` is enqueued

#### Scenario: Finalize no-op on per-ARC backends

- **GIVEN** `git_repo` is configured
- **WHEN** a harvest completes
- **THEN** finalize is still invoked and succeeds as a no-op without failing
  the harvest transition

#### Scenario: Catalog push failure is observable

- **GIVEN** finalize fails after harvest `COMPLETED`
- **WHEN** the worker records the outcome
- **THEN** a catalog-failure event is stored and the harvest remains
  `COMPLETED` (retry of finalize is allowed without re-opening the harvest)
