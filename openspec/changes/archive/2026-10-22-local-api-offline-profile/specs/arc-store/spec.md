# Spec Delta

## ADDED Requirements

### Requirement: Filesystem ARC persistence for local offline stand-in

The local offline stand-in MUST persist ARCs under a configured local output root using arctrl write semantics and MUST
NOT require a Git remote or DataHUB. Path segments derived from ARC identifiers MUST stay contained under the output
root (unsafe or empty identifiers MUST fall back to a generated safe id). Catalog finalize for this persistence path MAY
be a successful no-op in this change.

#### Scenario: Create or update writes an ARC tree under the output root

- **GIVEN** filesystem persistence with a configured output root
- **WHEN** an ARC create-or-update succeeds
- **THEN** an ARC directory tree for that ARC exists under the output root

#### Scenario: Unsafe identifier does not escape the output root

- **GIVEN** filesystem persistence with a configured output root
- **WHEN** create-or-update is called with an identifier that would escape that root
- **THEN** the writer uses a generated safe id under the output root
- **OR** rejects the write without writing outside the output root

#### Scenario: No Git remote required

- **GIVEN** filesystem persistence for the local offline stand-in
- **WHEN** health or create-or-update runs
- **THEN** no Git remote or DataHUB connectivity is required
