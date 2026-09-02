# ARC Store — Delta

## ADDED Requirements

### Requirement: Expose catalog finalize skip outcomes to callers

When the consolidated catalog backend completes a successful `finalize` for an
RDI (including when the remote catalog bytes are unchanged and no Git push
occurs), the operation MUST return enough outcome information for orchestrators
to report how many Datasets were published and which ARCs were skipped under
interim partial-push rules. The outcome MUST include whether a push occurred,
the count of Datasets included in the built catalog, and for each skipped ARC
its `arc_id` and a human-readable reason. Per-ARC Git backends that treat
`finalize` as a no-op MUST return an outcome with no skips and no push.
Failure paths that raise a permanent store error (including all-ARC extract or
normalize failure that refuses an empty wipe) remain exceptions and MUST NOT
pretend success with an empty skip list.

#### Scenario: Successful partial finalize reports skips

- **GIVEN** a consolidated finalize that includes at least one Dataset and skips
  at least one ARC for extract or JSON-LD failure
- **WHEN** finalize completes without raising
- **THEN** the outcome indicates the included Dataset count and lists each
  skipped `arc_id` with a reason
- **AND** the push flag reflects whether remote bytes were updated

#### Scenario: Per-ARC backend finalize outcome is empty

- **GIVEN** a per-ARC Git backend
- **WHEN** finalize runs for an RDI
- **THEN** the outcome reports no push and no skipped ARCs
