# Arc Manager Delta

## MODIFIED Requirements

### Requirement: Dispatch sync only for new or changed content

The system SHALL schedule background Git sync if and only if the ARC is new or changed. During sync it MUST delegate Git
persistence to `arc-store/`, which derives human-readable Git metadata from the parsed arctrl ARC. ARC payloads sent to
Celery MUST be JSON strings containing RO-Crate JSON text, not arctrl `ARC` objects and not Python dictionaries; the
worker MUST revalidate the queued JSON (via `parse_rocrate` on the parsed object graph as required today) and parse it
with `ARC.from_rocrate_json_string` using that same string (no intermediate `json.dumps` of a dict payload) before
syncing.

#### Scenario: Avoid redundant sync

- **GIVEN** an identical ARC re-submission
- **WHEN** document storage reports no content change
- **THEN** no second background sync is scheduled

#### Scenario: Celery payload is a JSON string

- **GIVEN** a new or changed ARC that schedules background sync
- **WHEN** the sync task is enqueued
- **THEN** the ARC field on the task payload is a JSON string suitable for `ARC.from_rocrate_json_string`
