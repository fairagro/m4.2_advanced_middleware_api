# Spec Delta

## ADDED Requirements

### Requirement: Release in-memory catalog datasets before Git publish

When the consolidated backend has fully serialized an RDI catalog for finalize, it MUST release the in-memory collection
of included Dataset records before it starts the ephemeral Git clone and push for that attempt. The catalog bytes
written to Git MUST be the deterministic bytes required by **Publish a byte-stable consolidated RDI catalog file on
finalize**. Partial-push skip rules, the empty-catalog wipe refusal, and the finalize outcome (push flag, Dataset count,
skip list) MUST stay the same. Deciding that the remote catalog is unchanged MUST NOT require rebuilding that Dataset
collection.

#### Scenario: Datasets are released before clone

- **GIVEN** a consolidated finalize that serializes one or more included Datasets
- **WHEN** the ephemeral Git clone for that attempt starts
- **THEN** the in-memory Dataset collection built for that serialization is no longer retained
- **AND** the catalog file bytes match a rebuild from the same included ARC contents

#### Scenario: Unchanged catalog still skips push

- **GIVEN** a serialized catalog whose bytes already match the remote catalog file
- **WHEN** finalize compares the remote file to that serialization
- **THEN** no commit or push is performed
- **AND** the comparison does not rebuild the Dataset collection

#### Scenario: All ARC failures still refuse an empty wipe

- **GIVEN** an RDI with one or more ARC documents that all fail extract or normalize
- **WHEN** finalize runs
- **THEN** a permanent store error is raised
- **AND** no catalog push occurs
