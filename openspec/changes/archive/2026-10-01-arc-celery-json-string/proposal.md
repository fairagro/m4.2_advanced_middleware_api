# Proposal

## Why

Celery sync tasks currently carry the ARC as a Python `dict`. Celery’s JSON serializer round-trips that dict, and the
worker still calls `json.dumps` before `ARC.from_rocrate_json_string` — two serialization steps. Issue #201 asks to pass
a JSON string at dispatch so the worker can feed arctrl directly. The API client already uses the string pattern on the
HTTP wire.

## What Changes

- **BREAKING** for in-flight Celery messages and rolling API/worker skew: `ArcSyncTask.arc` becomes a JSON **string**
  (hard cut — Option A). Operators must drain the queue or deploy API+worker together with no leftover dict payloads.
- Serialize once on the API side at dispatch; remove the worker-path `json.dumps` before `from_rocrate_json_string`.
- Update `arc-manager` spec + design (KD7): cross-process payloads are JSON strings, not dictionaries (still not pickle
  / not `ARC` objects).

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `arc-manager`: Celery ARC payload MUST be a JSON string; worker MUST accept that string for arctrl parse (no
  intermediate `json.dumps` of a dict payload).

## Impact

- **Code:** `task_payloads.ArcSyncTask`, `arc_manager` dispatch + `sync_to_gitlab`, worker tests.
- **Ops:** Coordinated deploy / queue drain required for the hard cut.
- **Out of scope:** Dual-accept `dict | str` (Option B); changing HTTP upload wire format; catalog finalize payloads.
