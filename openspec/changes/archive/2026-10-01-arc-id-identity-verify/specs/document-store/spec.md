# Document Store — Delta

## ADDED Requirements

### Requirement: Verify ARC identity before update

When an ARC document already exists at `arc_{arc_id}` (where `arc_id` is derived with `calculate_arc_id` from the
incoming identifier and `rdi`), the store MUST compare the stored identity to the incoming pair under the same
normalization used by `calculate_arc_id`: whitespace `.strip()` on both identifier and `rdi` only (no Unicode NFC or
other canonicalize-before-hash). Stored identifier MUST be taken from the existing document's RO-Crate content; stored
`rdi` MUST be the document's top-level `rdi` field. If either stripped value differs, the store MUST raise an identity
conflict error, MUST NOT write the document body or metadata update for that attempt, and MUST treat a true
cryptographic hash collision the same as an identity mismatch. Matching identity SHALL continue existing content-hash
and harvest-local duplicate rules unchanged.

#### Scenario: Refuse overwrite on identity mismatch

- **GIVEN** a document at `arc_{arc_id}` whose stripped stored identifier or `rdi` differs from the incoming pair
- **WHEN** `store_arc` is called with an incoming identifier and `rdi` that hash to that same `arc_id`
- **THEN** an identity conflict error is raised
- **AND** the existing document body and metadata remain unchanged

#### Scenario: Matching identity updates normally

- **GIVEN** an existing document whose stripped identifier and `rdi` match the incoming pair
- **WHEN** `store_arc` is called again
- **THEN** no identity conflict is raised
- **AND** content-hash and harvest-local duplicate behavior apply as today
