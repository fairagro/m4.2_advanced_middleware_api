# Harvest Report

## Purpose

Provide a shared, format-neutral harvest-run report that client tools initialise
at the start of a harvest, update through counting methods on repository scope
handles while the run progresses, and render via a pluggable serializer
(JSON-LD shipped first) to a document string. Counting is owned by the report;
callers signal events and MUST NOT maintain parallel counters for the same
statistics. Multiple repository scopes MAY be open concurrently; each has its
own handle and counters. How callers write or log that string (e.g. stdout) is
outside this library.

The wire shape follows the Middleware Harvester baseline (`schema:Action` with
`schema:result` of repository `EntryPoint`s). The vocabulary IRI is versioned
under the repository namespace tree.

## ADDED Requirements

### Requirement: Mutable run initialisation

The shared library SHALL provide a mutable harvest-run report that is created
at the start of a harvest run and records an authoritative start time at
creation (or an explicit start operation that MUST be invoked before counting).

#### Scenario: Report exists before first count

- **GIVEN** a harvest run is about to begin
- **WHEN** the caller creates (or starts) the harvest-run report
- **THEN** a mutable report instance is available for counting methods
- **AND** a start timestamp is recorded for later duration and wire emission

### Requirement: Finish run

The report SHALL support finishing the harvest run, recording an end time used
for overall duration on the wire (`schema:endTime` / duration derived from
start and end).

#### Scenario: Finish after counting

- **GIVEN** a started harvest-run report with zero or more counted events
- **WHEN** the caller finishes the run
- **THEN** an end timestamp is recorded
- **AND** serializers MAY read a stable snapshot of all counted statistics

### Requirement: Repository scope

The report SHALL support opening a repository scope identified by an RDI
string and closing that scope so per-repository duration can be recorded.
Opening a scope SHALL yield a distinct scope handle. A run MAY contain one
or more repository scopes. Multiple scopes MAY be open at the same time
(e.g. parallel RDI harvest tasks). Repository-specific counting methods
SHALL apply to an explicit scope handle — there is no single implicit
“current” open scope on the run.

#### Scenario: Open and close a repository

- **GIVEN** a started harvest-run report
- **WHEN** the caller opens a repository scope with an RDI identifier and later
  closes that scope handle
- **THEN** that RDI appears as a repository entry in the report
- **AND** that entry has a recorded duration for the open interval

#### Scenario: Concurrent scopes for parallel RDIs

- **GIVEN** a started harvest-run report
- **WHEN** the caller opens two repository scopes for different RDIs without
  closing either
- **THEN** both scopes remain independently countable
- **AND** counting on one handle MUST NOT change the other handle’s totals

#### Scenario: Single-RDI tools use one scope

- **GIVEN** a tool that harvests exactly one RDI (e.g. SQL-to-ARC)
- **WHEN** it opens one repository scope for that RDI for the whole run
- **THEN** the emitted report contains exactly one repository entry for that RDI

### Requirement: Set expected dataset count

The report SHALL allow setting an expected dataset count on a given open
repository scope handle. Expected count MAY remain unset when the source
cannot provide a total. When unset, JSON-LD MUST omit
`fairagro:expectedDatasets`.

#### Scenario: Expected count known

- **GIVEN** an open repository scope handle
- **WHEN** the caller sets an expected dataset count of N on that handle
- **THEN** serializers that emit `fairagro:expectedDatasets` include N for that
  repository

#### Scenario: Expected count unknown

- **GIVEN** an open repository scope handle where expected count was never set
- **WHEN** JSON-LD is produced
- **THEN** `fairagro:expectedDatasets` is omitted for that repository

### Requirement: Set harvest identifier

The report SHALL allow setting a harvest identifier on a given open
repository scope handle. The identifier MAY be unset; when unset, JSON-LD
uses JSON `null` for `fairagro:harvestId`.

#### Scenario: Harvest id assigned mid-run

- **GIVEN** an open repository scope handle
- **WHEN** the caller sets a harvest identifier string on that handle
- **THEN** JSON-LD includes that string as `fairagro:harvestId` for the entry

### Requirement: Record harvested dataset

The report SHALL provide a counting method on a repository scope handle that
records one successfully harvested (or equivalently found-and-accepted)
dataset, incrementing that scope’s harvested count by one. Callers MUST use
this method instead of maintaining their own harvested counter for the report.

#### Scenario: Successful ARC accepted

- **GIVEN** an open repository scope handle with harvested count H
- **WHEN** the caller records a harvested dataset on that handle
- **THEN** the harvested count becomes H + 1

### Requirement: Record failed dataset

The report SHALL provide a counting method on a repository scope handle that
records one failed dataset: increment that scope’s failed count by one and
append a failed record carrying a human-readable message and optional record
identifier and optional URL. Callers MUST use this method instead of
maintaining parallel failure counters or failure lists for the report.

#### Scenario: Failure with record id and URL

- **GIVEN** an open repository scope handle
- **WHEN** the caller records a failure with message M, record id R, and URL U
- **THEN** the failed count increases by one
- **AND** the failure list includes an entry with M, R, and U

#### Scenario: Failure with message only

- **GIVEN** an open repository scope handle
- **WHEN** the caller records a failure with only a message
- **THEN** the failed count increases by one
- **AND** the failure entry omits unset optional fields on the wire as
  specified for failed records

### Requirement: Record skipped dataset

The report SHALL provide a counting method on a repository scope handle that
records one intentionally skipped dataset, incrementing that scope’s skipped
count by one. Skipped count defaults to zero and is always present on the wire
(`fairagro:skippedDatasets`), including when zero.

#### Scenario: Intentional skip

- **GIVEN** an open repository scope handle with skipped count S
- **WHEN** the caller records a skipped dataset on that handle
- **THEN** the skipped count becomes S + 1

#### Scenario: No skips during run

- **GIVEN** an open repository scope handle where skip was never recorded
- **WHEN** JSON-LD is produced
- **THEN** `fairagro:skippedDatasets` is present with value 0

### Requirement: Record studies and assays

The report SHALL provide counting methods on a repository scope handle that
add a non-negative number of studies and of assays (default addend one when
the caller records a single unit). These totals are optional on the wire:
when both remain zero, `fairagro:totalStudies` and `fairagro:totalAssays` MAY
be omitted; when either is non-zero, both SHOULD be emitted.

#### Scenario: SQL batch contributes studies and assays

- **GIVEN** an open repository scope handle
- **WHEN** the caller adds S studies and A assays on that handle
- **THEN** the repository study total increases by S and assay total by A

### Requirement: Callers do not own parallel counters

Client code that uses the shared report for operator statistics SHALL treat
the report (via its scope handles) as the sole owner of harvested, failed,
skipped, expected (when set), study, and assay counts for that run. Parallel
counters for those same fields are out of scope for correct use of the
library.

#### Scenario: Event-driven updates only

- **GIVEN** a started harvest-run report with an open repository scope handle
- **WHEN** a harvest event occurs (success, failure, or skip)
- **THEN** the caller invokes the corresponding counting method on that handle
- **AND** does not independently increment a separate variable that is later
  copied into the report for that same statistic

### Requirement: Concurrent updates within a process

When multiple concurrent tasks in the same process update the same open
repository scope handle, counting methods SHALL preserve correct totals (no
lost updates under concurrent asyncio tasks sharing one handle). Updates to
different open handles on the same run MUST remain isolated from each other.

#### Scenario: Parallel workers record successes and failures

- **GIVEN** one open repository scope handle shared by concurrent tasks
- **WHEN** those tasks interleave harvested and failed recordings
- **THEN** final harvested and failed totals equal the number of respective
  recording calls

#### Scenario: Parallel RDIs do not cross-count

- **GIVEN** two open repository scope handles on the same run
- **WHEN** concurrent tasks record harvested datasets only on the first handle
- **THEN** the second handle’s harvested count remains unchanged

### Requirement: Format-neutral readable statistics

After or during a run, serializers SHALL be able to read repository
statistics without depending on a particular wire format: RDI, harvest id
(nullable), duration, expected (optional), harvested, failed, skipped, optional
study/assay totals, and the list of failed records (message; optional id and
URL).

#### Scenario: Serializer reads counted state

- **GIVEN** a repository scope with counted events
- **WHEN** a serializer reads that scope
- **THEN** it obtains those statistics without importing format-specific types
  from the counting API

### Requirement: Pluggable serializers

The shared library SHALL expose a common serializer contract that turns a
finished harvest-run report (or equivalent readable statistics) into one
document string. Multiple serializer implementations MAY exist behind that
contract. Callers select which serializer to use when rendering. This change
SHALL ship a JSON-LD implementation of that contract. Additional formats are
optional and out of scope unless separately specified. Emitting the string
(stdout, files, logs) is the caller’s responsibility — the library SHALL NOT
require a shared stdout emit helper.

#### Scenario: JSON-LD is one serializer among a common contract

- **GIVEN** a finished harvest-run report
- **WHEN** the caller renders it with the JSON-LD serializer
- **THEN** the result is a document string conforming to the JSON-LD
  requirements below
- **AND** the counting API does not hard-wire rendering to JSON-LD alone

### Requirement: JSON-LD harvest Action shape

JSON-LD serialization SHALL emit a `schema:Action` whose `schema:result` is an
array of `schema:EntryPoint` objects (one per repository), using a `@context`
that maps `schema` to `https://schema.org/` and `fairagro` to the versioned
harvest-report vocabulary IRI.

#### Scenario: Multi-repository Action

- **GIVEN** a finished run with two repository scopes
- **WHEN** JSON-LD is produced
- **THEN** `@type` is `schema:Action`
- **AND** `schema:result` is a JSON array of length 2
- **AND** each element has `@type` `schema:EntryPoint`

### Requirement: EntryPoint property mapping

Each `schema:EntryPoint` in JSON-LD SHALL include: `@id` equal to the RDI
identifier; `schema:duration` as ISO 8601 duration for that scope;
`fairagro:harvestId` as string or JSON `null`; `fairagro:harvestedDatasets` and
`fairagro:failedDatasets` as integers; `fairagro:skippedDatasets` as integer
(including 0); `fairagro:expectedDatasets` only when set; optional
`fairagro:totalStudies` / `fairagro:totalAssays` per the studies/assays rule;
and `fairagro:failedRecords` as an array of failed-record objects.

#### Scenario: Complete entry with expected and failures

- **GIVEN** a repository scope with expected set, non-zero harvested/failed,
  skipped zero, and at least one failed record with message and record id
- **WHEN** JSON-LD is produced for that entry
- **THEN** the mapped properties above are present with those values
- **AND** `fairagro:expectedDatasets` is present
- **AND** `fairagro:skippedDatasets` is 0

### Requirement: Versioned vocabulary IRI

The JSON-LD `@context` entry for `fairagro` SHALL use
`https://fairagro.github.io/m4.2_advanced_middleware_api/ns/harvest-report/v1/`
(trailing slash). Bumps that break term compatibility use a new version
segment; documentation lives under `ns/harvest-report/v1/` and is published
via GitHub Pages from tags without publishing unrelated `docs/` trees.
