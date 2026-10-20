# Spec Delta

## MODIFIED Requirements

### Requirement: Dispatch background sync after every successful persist

The system SHALL schedule background Git sync after every successful document persist for an ingested ARC (whether new
or unchanged). The ingest path MUST NOT skip enqueue solely because document storage reports no content change. During a
full sync it MUST delegate Git persistence to `arc-store/`, which derives human-readable Git metadata from the parsed
arctrl ARC. ARC payloads sent to Celery MUST be JSON strings containing RO-Crate JSON text, not arctrl `ARC` objects and
not Python dictionaries; the worker MUST revalidate the queued JSON (via `parse_rocrate` on the parsed object graph as
required today) and parse it with `ARC.from_rocrate_json_string` using that same string (no intermediate `json.dumps` of
a dict payload) before syncing. The worker MUST decide whether to perform a full Git sync or skip write/push using
content-change information and DataHub project existence (see added worker requirement).

#### Scenario: Avoid redundant sync

- **GIVEN** an identical ARC re-submission
- **WHEN** document storage reports no content change
- **THEN** a background sync task is still scheduled
- **AND** the ingest path does not call GitLab to check project existence
- **AND** the worker MAY skip scaffold write and git push when DataHub already has the project (see worker requirement)

#### Scenario: Celery payload is a JSON string

- **GIVEN** an ARC that schedules background sync
- **WHEN** the sync task is enqueued
- **THEN** the ARC field on the task payload is a JSON string suitable for `ARC.from_rocrate_json_string`

#### Scenario: New or changed content schedules sync

- **GIVEN** a new or changed ARC
- **WHEN** document storage completes successfully
- **THEN** a background sync task is scheduled

## ADDED Requirements

### Requirement: Worker skips full Git sync when unchanged and present on DataHub

When the worker handles per-ARC Git sync for content that is not new and not changed, it MUST probe whether the DataHub
GitLab project for that `arc_id` already exists using the GitLab HTTP API (not git CLI). If the project exists and is
usable (not pending deletion), the worker MUST NOT write an ARC scaffold or run git commit/push for that attempt. If the
project is missing or not usable, the worker MUST perform a full Git sync via the per-ARC store. When content is new or
changed, the worker MUST perform a full Git sync (the exists probe MUST NOT be used to skip that work).

#### Scenario: Unchanged and project exists

- **GIVEN** a sync task for unchanged content and a usable GitLab project for the ARC id
- **WHEN** the worker runs
- **THEN** no ARC scaffold write and no git push are performed for that attempt
- **AND** the outcome is logged as skipped because DataHub already has the project

#### Scenario: Unchanged and project missing

- **GIVEN** a sync task for unchanged content and no usable GitLab project for the ARC id
- **WHEN** the worker runs
- **THEN** a full per-ARC Git sync runs

#### Scenario: Changed content always full sync

- **GIVEN** a sync task for new or changed content
- **WHEN** the worker runs
- **THEN** a full per-ARC Git sync runs
