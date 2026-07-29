# Harvest Report

## Purpose

Provides a shared, format-neutral harvest-run report model and serializers so
middleware clients can emit compatible operator-facing summaries (JSON-LD first)
after talking to the harvest API.

## ADDED Requirements

### Requirement: Capture harvest-run timing and per-repository results

A harvest run report MUST record overall start and end times (UTC) and an
ordered list of per-repository result entries. Each repository entry MUST
include the RDI identifier, optional harvest id, wall-clock duration in
seconds, optional expected / harvested / failed dataset counts, a skipped
dataset count, and an ordered list of failed-record entries.

#### Scenario: Build a run report with one repository

- **GIVEN** a harvest run with known start and end times and one repository
  result
- **WHEN** a harvest run report is built from those inputs
- **THEN** the report exposes the run timing and exactly one repository entry
  with the supplied RDI, counts, and failure list

#### Scenario: Build a run report with no repositories

- **GIVEN** a harvest run with start and end times and an empty repository list
- **WHEN** a harvest run report is built
- **THEN** the report exposes the run timing and an empty repository list

### Requirement: Capture failed-record detail

Each failed-record entry MUST include a human-readable message and MAY include
an optional record id and optional URL.

#### Scenario: Failed record with optional identifiers

- **GIVEN** a failure message, a record id, and a URL
- **WHEN** a failed-record entry is created
- **THEN** the entry exposes the message, record id, and URL

#### Scenario: Failed record with message only

- **GIVEN** only a failure message
- **WHEN** a failed-record entry is created
- **THEN** the entry exposes the message and omits record id and URL as unset

### Requirement: Optional study and assay counts on repository entries

A repository entry MAY include optional total study and total assay counts.
Unset optional counts MUST NOT be treated as zero.

#### Scenario: Repository entry with study and assay counts

- **GIVEN** a repository entry that includes study and assay totals
- **WHEN** the entry is inspected
- **THEN** those totals are available to serializers

#### Scenario: Repository entry without study and assay counts

- **GIVEN** a repository entry without study or assay totals
- **WHEN** the entry is inspected
- **THEN** those totals are unset rather than zero

### Requirement: Serialize reports through a pluggable format

The library MUST separate the format-neutral report model from serialization.
Callers MUST be able to render a report using a selected format. The library
MUST provide a JSON-LD format. Additional formats MAY be added later without
changing the report model contract.

#### Scenario: Render with the JSON-LD format

- **GIVEN** a populated harvest run report
- **WHEN** the report is rendered with the JSON-LD format
- **THEN** the library returns a JSON-LD document string for that report

#### Scenario: Model remains format-neutral

- **GIVEN** a harvest run report built without choosing a format
- **WHEN** the report is inspected
- **THEN** the report holds domain fields only and does not embed a serialized
  document

### Requirement: JSON-LD vocabulary and document types

The JSON-LD format MUST use `https://schema.org/` as the primary vocabulary and
MUST declare the `fairagro:` prefix as the versioned harvest-report namespace
IRI
`https://fairagro.github.io/m4.2_advanced_middleware_api/ns/harvest-report/v1/#`.
The top-level document MUST be typed as `schema:Action`. Each repository result
MUST be typed as `schema:EntryPoint` and appear under `schema:result`.

#### Scenario: Top-level Action with EntryPoint results

- **GIVEN** a harvest run report with one or more repository entries
- **WHEN** the report is rendered as JSON-LD
- **THEN** the document uses the required `@context`, `@type` `schema:Action`,
  and a `schema:result` array of `schema:EntryPoint` objects

#### Scenario: fairagro prefix expands to the versioned GitHub Pages namespace

- **GIVEN** a harvest run report rendered as JSON-LD
- **WHEN** the document `@context` is inspected
- **THEN** the `fairagro` prefix equals
  `https://fairagro.github.io/m4.2_advanced_middleware_api/ns/harvest-report/v1/#`

### Requirement: Own a versioned harvest-report vocabulary in this repository

This repository MUST be the source of truth for harvest-report `fairagro:`
terms. Vocabulary major version `v1` MUST live under `ns/harvest-report/v1/`
(not under `docs/`) and MUST include a machine-readable JSON-LD context
document and a short human-readable description of each term. The context
document MUST define `@id` (and `@type` where applicable) for every `fairagro:`
property emitted by the JSON-LD serializer. Incompatible vocabulary changes
MUST introduce a new major path (for example `ns/harvest-report/v2/`) rather
than silently changing published `v1` term semantics.

#### Scenario: Context document defines emitted fairagro terms

- **GIVEN** the vocabulary files under `ns/harvest-report/v1/`
- **WHEN** the JSON-LD context document is read
- **THEN** it maps each emitted fairagro term
  (`harvestDurationSeconds`, `harvestId`, `expectedDatasets`,
  `harvestedDatasets`, `failedDatasets`, `skippedDatasets`, `failedRecords`,
  `message`, `recordId`, `url`, `totalStudies`, `totalAssays`) to an `@id`
  under the versioned harvest-report namespace IRI

#### Scenario: Human-readable term list exists

- **GIVEN** the vocabulary files under `ns/harvest-report/v1/`
- **WHEN** an operator opens the vocabulary README
- **THEN** each fairagro term used by the report has a brief plain-language
  description

### Requirement: Publish only the namespace tree via tag-gated Pages

Vocabulary publication MUST use GitHub Actions to deploy GitHub Pages content
drawn only from `ns/` (or the tagged vocabulary subtree). Publication MUST be
triggered by vocabulary tags matching `ns/harvest-report/v*`. The publication
process MUST NOT publish the general `docs/` tree as the Pages site root or
sole source.

#### Scenario: Vocabulary tag publishes ns content only

- **GIVEN** a git tag `ns/harvest-report/v1.0.0` and vocabulary files under
  `ns/harvest-report/v1/`
- **WHEN** the vocabulary publish workflow runs successfully
- **THEN** GitHub Pages serves the `v1` vocabulary artifacts under
  `/ns/harvest-report/v1/` and does not require publishing `docs/` for that
  purpose

### Requirement: JSON-LD timing and duration fields

The JSON-LD format MUST emit `schema:startTime` and `schema:endTime` on the
top-level action as ISO 8601 UTC timestamps ending in `Z`. It MUST emit
`fairagro:harvestDurationSeconds` as the overall duration in seconds. Each
repository entry MUST emit `schema:duration` as an ISO 8601 duration string
derived from that entry's duration in seconds.

#### Scenario: Emit ISO timestamps and durations

- **GIVEN** a harvest run report with known start time, end time, and repository
  durations
- **WHEN** the report is rendered as JSON-LD
- **THEN** start and end times end with `Z`, overall duration seconds are
  present, and each repository entry includes an ISO 8601 `schema:duration`

### Requirement: JSON-LD fairagro metrics and failed records

For each repository entry, the JSON-LD format MUST emit `fairagro:harvestId`
(including when null), `fairagro:skippedDatasets`, and when set
`fairagro:expectedDatasets`, `fairagro:harvestedDatasets`, and
`fairagro:failedDatasets`. When failed records exist, it MUST emit
`fairagro:failedRecords` as objects with `fairagro:message` and optional
`fairagro:recordId` / `fairagro:url`. When study or assay totals are set, it
MUST emit `fairagro:totalStudies` and/or `fairagro:totalAssays`.

#### Scenario: Emit metrics and failed records

- **GIVEN** a repository entry with harvest id, counts, and failed records that
  include message, record id, and URL
- **WHEN** the report is rendered as JSON-LD
- **THEN** the EntryPoint includes the fairagro metric properties and a
  `fairagro:failedRecords` array with the nested message, recordId, and url
  fields

#### Scenario: Emit optional study and assay totals

- **GIVEN** a repository entry with study and assay totals set
- **WHEN** the report is rendered as JSON-LD
- **THEN** the EntryPoint includes `fairagro:totalStudies` and
  `fairagro:totalAssays`

### Requirement: Omit unset optional JSON-LD keys

The JSON-LD format MUST omit keys for unset optional counts
(`fairagro:expectedDatasets`, `fairagro:harvestedDatasets`,
`fairagro:failedDatasets`, `fairagro:totalStudies`, `fairagro:totalAssays`)
rather than emitting JSON `null`. It MUST omit `fairagro:failedRecords` when
the failure list is empty. Nested failed-record objects MUST omit unset
`fairagro:recordId` and `fairagro:url`.

#### Scenario: Omit unavailable expected datasets

- **GIVEN** a repository entry whose expected dataset count is unset
- **WHEN** the report is rendered as JSON-LD
- **THEN** the EntryPoint does not include the `fairagro:expectedDatasets` key

#### Scenario: Omit empty failed records

- **GIVEN** a repository entry with an empty failed-record list
- **WHEN** the report is rendered as JSON-LD
- **THEN** the EntryPoint does not include the `fairagro:failedRecords` key

### Requirement: Print the report to stdout without failing the process

The library MUST provide a way to serialize a report and print it to stdout
(not stderr and not only the logging subsystem). Serialization or print
failures MUST be caught: the library MUST log a warning and MUST NOT raise to
the caller.

#### Scenario: Successful stdout print

- **GIVEN** a valid harvest run report
- **WHEN** the report is printed
- **THEN** a JSON-LD document is written to stdout

#### Scenario: Serialization failure does not raise

- **GIVEN** a report that cannot be serialized
- **WHEN** print is attempted
- **THEN** a warning is logged and no exception propagates to the caller
