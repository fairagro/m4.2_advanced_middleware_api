# Spec Delta

## ADDED Requirements

### Requirement: Enforce public Python API surface sync with Conventional Commits

The product code-quality gate (CI on code pull requests, and the documented local quality entrypoint) MUST compare an
allowlisted public Python API surface on the change tip against the same surface on `main` using a static API inspector
(griffe or equivalent). The allowlist MUST include the published `api_client` package surface and the selected `shared`
public modules agreed for this product (`report`, `security`, and `ConfigWrapper` / config-wrapper contract). When the
comparison reports one or more **breaking** changes and no commit in `main..HEAD` declares a breaking change via
Conventional Commits (`type!:` subject or a `BREAKING CHANGE:` footer), the gate MUST fail. When the tip introduces only
non-breaking surface changes, or breaking changes are declared on the branch, the gate MUST pass. HTTP OpenAPI and
CouchDB document-shape diffs are out of scope for this requirement.

#### Scenario: Undeclared breaking change fails

- **GIVEN** a pull request that removes or incompatibly changes an allowlisted public Python symbol vs `main`
- **AND** no commit on the branch uses a breaking Conventional Commit marker
- **WHEN** code quality runs the API surface check
- **THEN** the check fails

#### Scenario: Declared breaking change passes the surface gate

- **GIVEN** a pull request that introduces a breaking change on the allowlisted surface vs `main`
- **AND** at least one commit on the branch declares breaking via `type!:` or `BREAKING CHANGE:`
- **WHEN** code quality runs the API surface check
- **THEN** the surface check passes (other quality gates may still fail independently)

#### Scenario: Additive non-breaking change passes

- **GIVEN** a pull request that only adds optional public API without breaking existing symbols vs `main`
- **WHEN** code quality runs the API surface check
- **THEN** the check passes
