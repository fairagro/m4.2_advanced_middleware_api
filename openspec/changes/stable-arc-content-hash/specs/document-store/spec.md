# Document Store — Delta

## ADDED Requirements

### Requirement: Detect content change via arc-content-hash

When deciding whether stored ARC content changed, the document store SHALL
compare `content_hash` values computed under the `arc-content-hash` capability.
It MUST NOT treat raw JSON serialization differences that that capability
canonicalizes away as a content change.

#### Scenario: Re-submit after order-only RO-Crate noise

- **GIVEN** an ARC document already stored with a content hash
- **WHEN** the same logical ARC is stored again with only order or serialization
  differences covered by `arc-content-hash`
- **THEN** the content-changed flag is false and no body write occurs
