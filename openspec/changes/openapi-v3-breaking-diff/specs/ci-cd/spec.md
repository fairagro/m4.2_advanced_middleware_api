# Spec Delta

## ADDED Requirements

### Requirement: Compare generated HTTP /v3 OpenAPI tip versus main

The product code-quality gate (CI on code pull requests, and the documented local quality entrypoint) MUST compare the
HTTP `/v3` OpenAPI contract on the change tip against the same contract on `main`. The compared surface MUST come from
the production API application’s generated OpenAPI document and MUST include only paths under `/v3`.

#### Scenario: Non-/v3 OpenAPI changes do not fail this gate

- **GIVEN** a pull request that only changes OpenAPI paths outside `/v3` (for example `/v2`) vs `main`
- **AND** the `/v3` filtered contract is unchanged or non-breaking
- **WHEN** code quality runs the HTTP `/v3` OpenAPI check
- **THEN** the check passes

### Requirement: Fail undeclared /v3 OpenAPI breaking changes only

The `/v3` OpenAPI gate MUST fail only when the comparison reports one or more **breaking** changes and no commit in
`main..HEAD` declares breaking via Conventional Commits (`type!:` subject or a `BREAKING CHANGE:` footer). Non-breaking
`/v3` changes, or breaking changes declared on the branch, MUST pass. Public Python library surface and CouchDB
document-shape diffs are out of scope for this requirement.

#### Scenario: Undeclared /v3 OpenAPI breaking change fails

- **GIVEN** a pull request that removes or incompatibly changes a `/v3` path, method, required field, or response schema
  vs `main` in the generated OpenAPI document
- **AND** no commit on the branch uses a breaking Conventional Commit marker
- **WHEN** code quality runs the HTTP `/v3` OpenAPI check
- **THEN** the check fails

#### Scenario: Declared /v3 OpenAPI breaking change passes the gate

- **GIVEN** a pull request that introduces a breaking `/v3` OpenAPI change vs `main`
- **AND** at least one commit on the branch declares breaking via `type!:` or `BREAKING CHANGE:`
- **WHEN** code quality runs the HTTP `/v3` OpenAPI check
- **THEN** the OpenAPI check passes (other quality gates may still fail independently)

#### Scenario: Additive non-breaking /v3 OpenAPI change passes

- **GIVEN** a pull request that only adds non-breaking `/v3` OpenAPI surface (for example a new path or optional field)
  vs `main`
- **WHEN** code quality runs the HTTP `/v3` OpenAPI check
- **THEN** the check passes
