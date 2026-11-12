## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Callers do not own parallel counters

Client code that uses the shared report for operator statistics SHALL treat the report (via its scope handles) as the
sole owner of harvested, failed, skipped, warned, expected (when set), study, and assay counts for that run. Parallel
counters for those same fields are out of scope for correct use of the library.

#### Scenario: Event-driven updates only

- **GIVEN** a harvest client using the shared report
- **WHEN** datasets are harvested, fail, are skipped, or are warned
- **THEN** the client updates those totals only through the report’s counting methods on the appropriate scope handle

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
