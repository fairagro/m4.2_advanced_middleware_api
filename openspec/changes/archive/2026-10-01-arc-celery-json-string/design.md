# Design

## Context

Issue [#201](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/201): pass ARC as a JSON string on the
API→Celery boundary. Lock-in: **hard cut (Option A)** — no dual-accept of dict payloads; coordinated deploy / queue
drain. OpenSpec updates to `arc-manager` (spec + design KD7).

## Goals / Non-Goals

**Goals:**

- `ArcSyncTask.arc` is a JSON string produced once at dispatch.
- Worker/`sync_to_gitlab` calls `ARC.from_rocrate_json_string` on that string without `json.dumps` of a dict.
- Specs/design match (string payloads; still no pickle / no `ARC` across process boundary).

**Non-Goals:**

- Dual-accept `dict | str` on the worker.
- Changing HTTP ARC upload request/response shapes.
- Celery serializer changes beyond payload field type.

## Decisions

1. **Hard cut to `str`** — `ArcSyncTask.arc: str` (validated as JSON text of a RO-Crate). Reason: simplest end state;
   operators accept short drain/coordinated deploy.

2. **Serialize at API dispatch** — After CouchDB store, `json.dumps(arc_content)` (or equivalent stable dump) once when
   building `ArcSyncTask`. Document store continues to use dict/`RoCratePayload` in-process. Reason: one explicit
   serialization at the process boundary.

3. **Worker path** — `sync_to_gitlab` accepts `str` (or parses task field as str); optional
   `parse_rocrate(json.loads(...))` if revalidation still required by spec, then
   `ARC.from_rocrate_json_string(arc_json)` without a second dumps. Reason: keep wire revalidation if still mandated;
   remove redundant dumps.

4. **Update KD7** — Design text: cross process as **JSON strings**, not dictionaries; arctrl still not pickle-safe.

5. **Deploy note** — Document in design/migration: empty `sync_arc_to_gitlab` queue (or stop workers) before rolling the
   new API+worker images together.

## Risks / Trade-offs

| Risk                                                    | Mitigation                                          |
| ------------------------------------------------------- | --------------------------------------------------- |
| In-flight dict tasks fail after cut                     | Drain queue / coordinated deploy (accepted under A) |
| Float/key-order drift from Celery nested dict serialize | Eliminated for ARC body (opaque string)             |

## Migration Plan

1. Drain or pause Celery consumers for `sync_arc_to_gitlab`.
2. Deploy API + worker with string payloads together.
3. Resume consumers.

## Open Questions

_(none)_
