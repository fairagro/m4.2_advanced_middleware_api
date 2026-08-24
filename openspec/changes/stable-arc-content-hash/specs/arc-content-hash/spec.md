# ARC Content Hash

## Purpose

Define how the Middleware API canonicalizes ARC RO-Crate JSON before computing
`content_hash`, so logically identical crates from any producer yield a stable
hash while real semantic edits still change it.

## ADDED Requirements

### Requirement: Compute content hash from canonicalized RO-Crate

The system SHALL compute an ARC `content_hash` as the SHA-256 hex digest of the
canonicalized RO-Crate JSON document (UTF-8), with object keys sorted during
serialization. Callers that decide whether ARC content changed MUST compare
hashes produced by this contract.

#### Scenario: Identical logical content hashes equal

- **GIVEN** two RO-Crate JSON documents that differ only by order and
  serialization noise covered by this capability
- **WHEN** each document’s content hash is computed
- **THEN** both hashes are identical

#### Scenario: Semantic edit changes hash

- **GIVEN** two RO-Crate JSON documents that differ by a non-volatile semantic
  field value (for example a different description text or a different keyword
  set)
- **WHEN** each document’s content hash is computed
- **THEN** the hashes differ

### Requirement: Exclude volatile timestamps from the hash input

Before hashing, the system SHALL remove these properties recursively wherever
they appear: `dateCreated`, `datePublished`, `sdDatePublished`, `dateModified`.
No other fields SHALL be stripped as “volatile” under this capability.

#### Scenario: Timestamp-only refresh

- **GIVEN** two crates that differ only in one or more of the listed timestamp
  fields
- **WHEN** content hashes are computed
- **THEN** the hashes are identical

### Requirement: Stabilize @graph entry order

Within the hash input, the system SHALL order `@graph` entries deterministically
by string `@id` ascending, with a deterministic tie-breaker when `@id` is
missing or duplicated, so `@graph` permutation alone does not change the hash.

#### Scenario: Permuted @graph

- **GIVEN** two crates with the same nodes and the same non-order fields
- **WHEN** only the order of `@graph` entries differs
- **THEN** the content hashes are identical

### Requirement: Treat allowlisted @id reference lists as unordered

For the properties `hasPart`, `creator`, `author`, `contributor`, and
`comment`, when the property value is a list and every element is an object
with a string `@id`, the system SHALL sort that list deterministically by
`@id` (with a deterministic tie-breaker) in the hash input. Lists that contain
any non-`@id` element MUST remain order-sensitive. Properties not on this
allowlist MUST remain order-sensitive.

#### Scenario: Permuted creator references

- **GIVEN** two crates whose `creator` lists contain the same set of
  `{ "@id": … }` references in different order
- **WHEN** content hashes are computed
- **THEN** the hashes are identical

#### Scenario: Non-allowlisted list stays order-sensitive

- **GIVEN** two crates that differ only in the order of a non-allowlisted
  reference list of `{ "@id": … }` objects
- **WHEN** content hashes are computed
- **THEN** the hashes differ

#### Scenario: Mixed literal list stays order-sensitive

- **GIVEN** an allowlisted property whose list includes a string literal or an
  object without a string `@id`
- **WHEN** two crates differ only in that list’s order
- **THEN** the content hashes differ

### Requirement: Canonicalize Keywords comment text as an unordered multiset

In the hash input, for every `@graph` node that is a Comment (or equivalent
comment node) whose `name` is `Keywords`, the system SHALL treat the keyword
payload text as an unordered multiset of tokens: split on commas, strip
surrounding whitespace per token, drop empty tokens, sort tokens with
Unicode casefold ordering, and rejoin with `", "`. If that canonical join
differs from the original text, the hash input MUST use the canonical text
and MUST rewrite any `@id` values and `@id` references in the document that
encoded the pre-canonical join so identity tracks the multiset, not join
order.

#### Scenario: Keywords token order only

- **GIVEN** two crates whose Keywords comment texts contain the same tokens in
  different join order (and any `@id`s derived only from that join)
- **WHEN** content hashes are computed
- **THEN** the hashes are identical

#### Scenario: Keywords set change

- **GIVEN** two crates whose Keywords comments differ by at least one token
  membership (add, remove, or replace)
- **WHEN** content hashes are computed
- **THEN** the hashes differ

### Requirement: Canonicalize keyword-like string arrays as unordered multisets

When a property value is a JSON array of strings used as keywords (including
Schema.org-style `keywords` arrays), the system SHALL sort those strings with
Unicode casefold ordering in the hash input so array permutation alone does
not change the hash. Arrays that mix strings with non-strings MUST remain
order-sensitive.

#### Scenario: Permuted keywords array

- **GIVEN** two crates that differ only in the order of a homogeneous string
  `keywords` array with the same elements
- **WHEN** content hashes are computed
- **THEN** the hashes are identical

### Requirement: Do not apply language preference or blank-node stripping

The hash canonicalization MUST NOT choose among language-tagged literals, MUST
NOT drop empty descriptions in favour of another language, and MUST NOT strip
or rewrite comment bodies or identifiers solely because they look like RDF
blank-node labels. Those behaviours remain producer / harvester
responsibilities.

#### Scenario: Description text change remains a hash change

- **GIVEN** two crates that differ only in description string content (for
  example German vs English text)
- **WHEN** content hashes are computed
- **THEN** the hashes differ

#### Scenario: Blank-node-looking comment text remains a hash change

- **GIVEN** two crates that differ only in opaque comment text that resembles
  an RDF blank-node label
- **WHEN** content hashes are computed
- **THEN** the hashes differ
