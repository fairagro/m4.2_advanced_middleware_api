# harvest-report Specification

## Purpose

Provide a shared, format-neutral harvest-run report that client tools initialise at the start of a harvest, update
through counting methods on repository scope handles while the run progresses, and render via a pluggable serializer
(JSON-LD shipped first) to a document string. Counting is owned by the report; callers signal events and MUST NOT
maintain parallel counters for the same statistics. Multiple repository scopes MAY be open concurrently; each has its
own handle and counters. How callers write or log that string (e.g. stdout) is outside this library.

The wire shape follows the Middleware Harvester baseline (`schema:Action` with `schema:result` of repository
`EntryPoint`s). The vocabulary IRI is versioned under the repository namespace tree.

## Requirements

### Requirement: Mutable run initialisation

The shared library SHALL provide a mutable harvest-run report that is created at the start of a harvest run and records
an authoritative start time at creation (or an explicit start operation that MUST be invoked before counting).

#### Scenario: Report exists before first count

- **GIVEN** a harvest run is about to begin
- **WHEN** the caller creates (or starts) the harvest-run report
- **THEN** a mutable report instance is available for counting methods
- **AND** a start timestamp is recorded for later duration and wire emission

### Requirement: Finish run

The report SHALL support finishing the harvest run, recording an end time used for overall duration on the wire
(`schema:endTime` / duration derived from start and end).

#### Scenario: Finish after counting

- **GIVEN** a started harvest-run report with zero or more counted events
- **WHEN** the caller finishes the run
- **THEN** an end timestamp is recorded
- **AND** serializers MAY read a stable snapshot of all counted statistics

### Requirement: Repository scope

The report SHALL support opening a repository scope identified by an RDI string and closing that scope so per-repository
duration can be recorded. Opening a scope SHALL yield a distinct scope handle. A run MAY contain one or more repository
scopes. Multiple scopes MAY be open at the same time (e.g. parallel RDI harvest tasks). Repository-specific counting
methods SHALL apply to an explicit scope handle — there is no single implicit “current” open scope on the run.

#### Scenario: Open and close a repository

- **GIVEN** a started harvest-run report
- **WHEN** the caller opens a repository scope with an RDI identifier and later closes that scope handle
- **THEN** that RDI appears as a repository entry in the report
- **AND** that entry has a recorded duration for the open interval

#### Scenario: Concurrent scopes for parallel RDIs

- **GIVEN** a started harvest-run report
- **WHEN** the caller opens two repository scopes for different RDIs without closing either
- **THEN** both scopes remain independently countable
- **AND** counting on one handle MUST NOT change the other handle’s totals

#### Scenario: Single-RDI tools use one scope

- **GIVEN** a tool that harvests exactly one RDI (e.g. SQL-to-ARC)
- **WHEN** it opens one repository scope for that RDI for the whole run
- **THEN** the emitted report contains exactly one repository entry for that RDI

### Requirement: Set expected dataset count

The report SHALL allow setting an expected dataset count on a given open repository scope handle. Expected count MAY
remain unset when the source cannot provide a total. When unset, JSON-LD MUST omit `fairagro:expectedDatasets`.

#### Scenario: Expected count known

- **GIVEN** an open repository scope handle
- **WHEN** the caller sets an expected dataset count of N on that handle
- **THEN** serializers that emit `fairagro:expectedDatasets` include N for that repository

#### Scenario: Expected count unknown

- **GIVEN** an open repository scope handle where expected count was never set
- **WHEN** JSON-LD is produced
- **THEN** `fairagro:expectedDatasets` is omitted for that repository

### Requirement: Set harvest identifier

The report SHALL allow setting a harvest identifier on a given open repository scope handle. The identifier MAY be
unset; when unset, JSON-LD uses JSON `null` for `fairagro:harvestId`.

#### Scenario: Harvest id assigned mid-run

- **GIVEN** an open repository scope handle
- **WHEN** the caller sets a harvest identifier string on that handle
- **THEN** JSON-LD includes that string as `fairagro:harvestId` for the entry

### Requirement: Record harvested dataset

The report SHALL provide a counting method on a repository scope handle that records one successfully harvested (or
equivalently found-and-accepted) dataset, incrementing that scope’s harvested count by one. Callers MUST use this method
instead of maintaining their own harvested counter for the report.

#### Scenario: Successful ARC accepted

- **GIVEN** an open repository scope handle with harvested count H
- **WHEN** the caller records a harvested dataset on that handle
- **THEN** the harvested count becomes H + 1

### Requirement: Record failed dataset

The report SHALL provide a counting method on a repository scope handle that records one failed dataset: increment that
scope’s failed count by one and append a harvest issue of kind `dataset` carrying a human-readable message and optional
record identifier and optional URL. Callers MUST use this method instead of maintaining parallel failure counters or
failure lists for the report.

#### Scenario: Failure with record id and URL

- **GIVEN** an open repository scope handle
- **WHEN** the caller records a dataset failure with message M, record id R, and URL U
- **THEN** the failed count increases by one
- **AND** the failure list includes an entry with kind `dataset`, M, R, and U

#### Scenario: Failure with message only

- **GIVEN** an open repository scope handle
- **WHEN** the caller records a dataset failure with only a message
- **THEN** the failed count increases by one
- **AND** the failure entry has kind `dataset` and omits unset optional fields on the wire as specified for failures

### Requirement: Record repository-level issue

The report SHALL provide a method on a repository scope handle that appends a harvest issue of kind `repository` with a
human-readable message and optional URL, without incrementing the failed dataset count. Callers MUST use this method for
RDI-global or discovery failures that are not attributable to a single dataset.

#### Scenario: Sitemap discovery failure

- **GIVEN** an open repository scope handle with failed dataset count F
- **WHEN** the caller records a repository-level issue with message M and URL U
- **THEN** the failed dataset count remains F
- **AND** the failure list includes an entry with kind `repository`, M, and U

### Requirement: Harvest issue construction constraints

Constructing a harvest issue SHALL normalize `kind` to `dataset` or `repository` and SHALL reject a `record_id` when
`kind` is `repository` (record identifiers apply only to dataset-scoped issues).

#### Scenario: Repository issue with record id rejected

- **GIVEN** a caller constructs a harvest issue with kind `repository` and a non-null record id
- **WHEN** construction is attempted
- **THEN** construction fails with an error

### Requirement: Record skipped dataset

The report SHALL provide a counting method on a repository scope handle that records one intentionally skipped dataset,
incrementing that scope’s skipped count by one. Skipped count defaults to zero and is always present on the wire
(`fairagro:skippedDatasets`), including when zero.

#### Scenario: Intentional skip

- **GIVEN** an open repository scope handle with skipped count S
- **WHEN** the caller records a skipped dataset on that handle
- **THEN** the skipped count becomes S + 1

#### Scenario: No skips during run

- **GIVEN** an open repository scope handle where skip was never recorded
- **WHEN** JSON-LD is produced
- **THEN** `fairagro:skippedDatasets` is present with value 0

### Requirement: Record warned dataset

The report SHALL provide a counting method on a repository scope handle that records one dataset-scoped warning:
increment that scope’s warned-dataset count by one and append a harvest issue of kind `dataset` with a human-readable
message and optional record identifier and URL. The method MUST NOT increment harvested, failed, or skipped counts.
Callers MUST use this method instead of parallel warning counters or lists for the report.

#### Scenario: Warning with record id and URL

- **GIVEN** an open repository scope handle with warned-dataset count W, harvested count H, failed count F, and skipped
  count S
- **WHEN** the caller records a dataset warning with message M, record id R, and URL U
- **THEN** the warned-dataset count becomes W + 1
- **AND** the warnings list includes an entry with kind `dataset`, M, R, and U
- **AND** harvested, failed, and skipped counts remain H, F, and S

#### Scenario: Warning with message only

- **GIVEN** an open repository scope handle
- **WHEN** the caller records a dataset warning with only a message
- **THEN** the warned-dataset count increases by one
- **AND** the warning entry has kind `dataset` and omits unset optional fields on the wire as specified for failures

#### Scenario: Harvested with warning still counts as harvested

- **GIVEN** an open repository scope handle with harvested count H and warned-dataset count W
- **WHEN** the caller records one harvested dataset and one dataset warning for the same logical record
- **THEN** harvested becomes H + 1 and warned-dataset becomes W + 1
- **AND** failed and skipped counts are unchanged

#### Scenario: Warning alone does not imply harvested

- **GIVEN** an open repository scope handle where only a dataset warning was recorded
- **WHEN** serializers read harvested and warned counts
- **THEN** warned-dataset count is at least 1
- **AND** harvested count is unchanged by the warning recording itself

### Requirement: Warned dataset count on the wire

Warned-dataset count SHALL default to zero and MUST always be present on the wire (`fairagro:warnedDatasets`), including
when zero.

#### Scenario: No warnings during run

- **GIVEN** an open repository scope handle where warning was never recorded
- **WHEN** JSON-LD is produced
- **THEN** `fairagro:warnedDatasets` is present with value 0
- **AND** `fairagro:warnings` is omitted

### Requirement: Record studies and assays

The report SHALL provide counting methods on a repository scope handle that add a non-negative number of studies and of
assays (default addend one when the caller records a single unit). These totals are optional on the wire: when both
remain zero, `fairagro:totalStudies` and `fairagro:totalAssays` MAY be omitted; when either is non-zero, both SHOULD be
emitted.

#### Scenario: SQL batch contributes studies and assays

- **GIVEN** an open repository scope handle
- **WHEN** the caller adds S studies and A assays on that handle
- **THEN** the repository study total increases by S and assay total by A

### Requirement: Callers do not own parallel counters

Client code that uses the shared report for operator statistics SHALL treat the report (via its scope handles) as the
sole owner of harvested, failed, skipped, warned, expected (when set), study, and assay counts for that run. Parallel
counters for those same fields are out of scope for correct use of the library.

#### Scenario: Event-driven updates only

- **GIVEN** a harvest client using the shared report
- **WHEN** datasets are harvested, fail, are skipped, or are warned
- **THEN** the client updates those totals only through the report’s counting methods on the appropriate scope handle

### Requirement: Concurrent updates within a process

When multiple concurrent tasks in the same process update the same open repository scope handle, counting methods SHALL
preserve correct totals (no lost updates under concurrent asyncio tasks sharing one handle). Updates to different open
handles on the same run MUST remain isolated from each other.

#### Scenario: Parallel workers record successes and failures

- **GIVEN** one open repository scope handle shared by concurrent tasks
- **WHEN** those tasks interleave harvested and failed recordings
- **THEN** final harvested and failed totals equal the number of respective recording calls

#### Scenario: Parallel RDIs do not cross-count

- **GIVEN** two open repository scope handles on the same run
- **WHEN** concurrent tasks record harvested datasets only on the first handle
- **THEN** the second handle’s harvested count remains unchanged

### Requirement: Format-neutral readable statistics

After or during a run, serializers SHALL be able to read repository statistics without depending on a particular wire
format: RDI, harvest id (nullable), duration, expected (optional), harvested, failed, skipped, optional study/assay
totals, and the list of harvest issues (kind; message; optional id and URL).

#### Scenario: Serializer reads counted state

- **GIVEN** a repository scope with counted events
- **WHEN** a serializer reads that scope
- **THEN** it obtains those statistics without importing format-specific types from the counting API

### Requirement: Pluggable serializers

The shared library SHALL expose a common serializer contract that turns a finished harvest-run report (or equivalent
readable statistics) into one document string. Multiple serializer implementations MAY exist behind that contract.
Callers select which serializer to use when rendering. This change SHALL ship a JSON-LD implementation of that contract.
Additional formats are optional and out of scope unless separately specified. Emitting the string (stdout, files, logs)
is the caller’s responsibility — the library SHALL NOT require a shared stdout emit helper.

#### Scenario: JSON-LD is one serializer among a common contract

- **GIVEN** a finished harvest-run report
- **WHEN** the caller renders it with the JSON-LD serializer
- **THEN** the result is a document string conforming to the JSON-LD requirements below
- **AND** the counting API does not hard-wire rendering to JSON-LD alone

### Requirement: JSON-LD harvest Action shape

JSON-LD serialization SHALL emit a `schema:Action` whose `schema:result` is an array of `schema:EntryPoint` objects (one
per repository), using a `@context` that maps `schema` to `https://schema.org/` and `fairagro` to the versioned
harvest-report vocabulary IRI.

#### Scenario: Multi-repository Action

- **GIVEN** a finished run with two repository scopes
- **WHEN** JSON-LD is produced
- **THEN** `@type` is `schema:Action`
- **AND** `schema:result` is a JSON array of length 2
- **AND** each element has `@type` `schema:EntryPoint`

### Requirement: EntryPoint property mapping

Each `schema:EntryPoint` in JSON-LD SHALL include: `@id` equal to the RDI identifier; `schema:duration` as ISO 8601
duration for that scope; `fairagro:harvestId` as string or JSON `null`; `fairagro:harvestedDatasets` and
`fairagro:failedDatasets` as integers; `fairagro:skippedDatasets` as integer (including 0); `fairagro:warnedDatasets` as
integer (including 0); `fairagro:expectedDatasets` only when set; optional `fairagro:totalStudies` /
`fairagro:totalAssays` per the studies/assays rule; `fairagro:failures` as an array of issue objects (each with
`fairagro:kind` of `dataset` or `repository`, `fairagro:message`, and optional `fairagro:recordId` / `fairagro:url`)
when non-empty; and `fairagro:warnings` as an array of issue objects with the same per-issue shape as failures when
non-empty.

#### Scenario: Complete entry with expected and failures

- **GIVEN** a repository scope with expected set, non-zero harvested/failed, skipped zero, warned zero, and at least one
  dataset failure with message and record id
- **WHEN** JSON-LD is produced for that entry
- **THEN** the mapped properties above are present with those values
- **AND** `fairagro:expectedDatasets` is present
- **AND** `fairagro:skippedDatasets` is 0
- **AND** `fairagro:warnedDatasets` is 0
- **AND** `fairagro:failures` entries include `fairagro:kind`
- **AND** `fairagro:warnings` is omitted

#### Scenario: Repository issue does not inflate failedDatasets

- **GIVEN** a repository scope with only a repository-level issue recorded
- **WHEN** JSON-LD is produced for that entry
- **THEN** `fairagro:failedDatasets` is 0
- **AND** `fairagro:failures` contains one entry with `fairagro:kind` `repository`

#### Scenario: Warnings list and count on EntryPoint

- **GIVEN** a repository scope with one dataset warning (message and record id) and zero failures
- **WHEN** JSON-LD is produced for that entry
- **THEN** `fairagro:warnedDatasets` is 1
- **AND** `fairagro:warnings` contains one entry with `fairagro:kind` `dataset`, the message, and `fairagro:recordId`
- **AND** `fairagro:failedDatasets` is 0
- **AND** `fairagro:failures` is omitted

### Requirement: Versioned vocabulary IRI

The JSON-LD `@context` entry for `fairagro` SHALL use
`https://fairagro.github.io/m4.2_advanced_middleware_api/ns/harvest-report/v2/#` (hash fragment on the versioned path).
Bumps that break term compatibility use a new version segment; documentation lives under `ns/harvest-report/v2/` and is
published via GitHub Pages from tags without publishing unrelated `docs/` trees. The v1 vocabulary under
`ns/harvest-report/v1/` remains frozen (`failedRecords`) and MUST NOT be altered by this rename.

#### Scenario: Context uses v2 vocabulary IRI

- **GIVEN** a harvest report serialized as JSON-LD
- **WHEN** the `@context` maps the `fairagro` prefix
- **THEN** the IRI is `https://fairagro.github.io/m4.2_advanced_middleware_api/ns/harvest-report/v2/#`
- **AND** the frozen v1 vocabulary under `ns/harvest-report/v1/` is unchanged

### Requirement: Optional software version on the harvest-run report

The harvest-run report SHALL allow the caller to set an optional PEP 440 software version string (tool or image stamp)
on the mutable report. When unset (`None`), serializers MUST omit tool-version wire fields. Shared library finish and
render paths MUST NOT fail solely because the version is unset. Production harvest tools SHOULD set the version for
every productive run; fail-closed enforcement of that policy is outside this shared library.

#### Scenario: Version set by caller

- **GIVEN** a harvest-run report
- **WHEN** the caller sets a non-empty software version string
- **THEN** serializers that emit tool identity can read that string from the report

#### Scenario: Version unset remains valid

- **GIVEN** a harvest-run report with no software version set
- **WHEN** the caller finishes the run and renders JSON-LD
- **THEN** rendering succeeds
- **AND** the document does not include `schema:instrument`

### Requirement: Read installed distribution version for callers

The shared library SHALL provide a helper that accepts a Python distribution name and returns its installed PEP 440
version string, or `None` when the distribution metadata is not available. The helper MUST NOT hard-code a product
package name.

#### Scenario: Installed distribution

- **GIVEN** a distribution name that is installed in the environment
- **WHEN** the helper is invoked with that name
- **THEN** it returns a non-empty version string

#### Scenario: Missing distribution

- **GIVEN** a distribution name that is not installed
- **WHEN** the helper is invoked with that name
- **THEN** it returns `None`

### Requirement: JSON-LD emits schema:instrument when version is set

When the finished report has a software version set, JSON-LD serialization SHALL include `schema:instrument` as an
object with `@type` `schema:SoftwareApplication` and `schema:softwareVersion` equal to that string. When unset,
`schema:instrument` MUST be omitted. This MUST NOT require a new harvest-report vocabulary major version (schema.org
terms only).

#### Scenario: Instrument present with version

- **GIVEN** a finished report with software version `1.2.3`
- **WHEN** JSON-LD is produced
- **THEN** `schema:instrument` has `@type` `schema:SoftwareApplication`
- **AND** `schema:softwareVersion` is `1.2.3`

#### Scenario: Instrument omitted without version

- **GIVEN** a finished report with software version unset
- **WHEN** JSON-LD is produced
- **THEN** the document has no `schema:instrument` property
