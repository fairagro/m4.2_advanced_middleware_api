# Spec Delta

## Purpose

Shared library and CLI that turn client RO-Crate JSON-LD into an ARC scaffold via ARCtrl and run DataHUB-equivalent
`arc-export` in Docker, returning a structured pass/fail result without Middleware API, Celery, CouchDB, or GitLab.

## ADDED Requirements

### Requirement: Write an ARC scaffold from RO-Crate

The library MUST accept RO-Crate JSON-LD (string or UTF-8 file contents), load it with ARCtrl, write an ARC directory
tree to a caller-supplied or temporary output path, and return that path. Write failures MUST be reported as a failed
validation result (or raised only from the low-level write helper when used directly — `validate_rocrate` MUST catch and
map them into `ArcExportResult` with `ok=False`).

#### Scenario: Successful scaffold write

- **GIVEN** valid RO-Crate JSON-LD with a root dataset identifier
- **WHEN** `write_arc_scaffold` runs against an empty output directory
- **THEN** the directory contains an ARC written by ARCtrl
- **AND** the returned path is that directory

### Requirement: Run arc-export in Docker

The library MUST invoke Docker to run the configured `arc-export` image against a written ARC directory, mounting that
directory into the container and requesting the configured export formats. The default image MUST be
`ghcr.io/nfdi4plants/arc-export:main` unless overridden. The default formats MUST include `rocrate-metadata-lfs`,
`isa-json`, and `summary-markdown`.

#### Scenario: Successful export

- **GIVEN** a written ARC directory and a Docker invocation that exits 0
- **WHEN** `run_arc_export` completes
- **THEN** the result has `ok=True` and `exit_code=0`

#### Scenario: Failed export

- **GIVEN** a written ARC directory and a Docker invocation that exits non-zero
- **WHEN** `run_arc_export` completes
- **THEN** the result has `ok=False` and the non-zero `exit_code`
- **AND** stdout/stderr from the container are retained on the result

### Requirement: Validate RO-Crate end-to-end

`validate_rocrate` MUST write a scaffold into a temporary directory, run `arc-export`, clean up the temporary directory,
and return the `ArcExportResult`. It MUST NOT require a running Middleware API or GitLab.

#### Scenario: End-to-end pass

- **GIVEN** RO-Crate that writes and exports successfully under the default image/formats
- **WHEN** `validate_rocrate` is called
- **THEN** `ok` is True

#### Scenario: End-to-end fail with cause excerpt

- **GIVEN** an export that fails with an `Internal Error:` (or similar) line in the logs
- **WHEN** `validate_rocrate` returns
- **THEN** `ok` is False
- **AND** `cause_excerpt` contains a short readable excerpt of the failure

### Requirement: Allow image override for reproducibility

Callers MUST be able to override the container image via an explicit argument and via a documented environment variable,
so CI can pin a digest without code changes.

#### Scenario: Digest override via environment

- **GIVEN** the documented image override environment variable is set to a digest-tagged image reference
- **WHEN** `validate_rocrate` / `run_arc_export` runs without an explicit `image=` argument
- **THEN** Docker is invoked with that image reference

### Requirement: Provide a CLI entry point

The package MUST expose a console script that accepts a path to a RO-Crate JSON file, runs `validate_rocrate`, exits 0
on success, and exits non-zero on failure while printing a short cause on stderr.

#### Scenario: CLI failure exit code

- **GIVEN** a RO-Crate file that fails `arc-export`
- **WHEN** the CLI is invoked with that path
- **THEN** the process exit code is non-zero
- **AND** stderr includes a short cause excerpt
