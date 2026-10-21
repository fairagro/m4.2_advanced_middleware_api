# Design

## Context

See proposal.md for why the harvest catalog-event list needs a bound. ARC metadata already drops the oldest events in
`add_event` and on ARC save once `len(events) > max_event_log_size`, keeping the tail. Harvest updates append in
`_apply_harvest_updates` and save the full list. `update_harvest` refetches and reapplies the same payload on revision
conflict, so the trim has to live in that apply step.

## Goals / Non-Goals

**Goals:**

- One config field, default 100, read through the existing document-store config.
- After an append, the saved list is the newest `max_catalog_event_log_size` events, order preserved.

**Non-Goals:**

- Skipping a redundant `CATALOG_PUSH_SUCCESS`.
- Capping harvest `errors`.
- Trimming on a harvest update that does not append.
- Changing `max_event_log_size` or the ARC event log.

## Decisions

1. **New field `max_catalog_event_log_size` on `CouchDBConfig`, default 100, minimum 1.** Catalog finalize and the ARC
   event log grow for different reasons, so one shared ceiling would force a single knob for both. A minimum of 1 keeps
   the event just appended. A hardcoded 100 would match today's ARC default but would not give operators the knob the
   issue asks for.
2. **Trim only inside the append branch of `_apply_harvest_updates`.** After the new event is concatenated, replace the
   list with its tail when it is longer than the configured maximum. That is the same tail-keep as the ARC log, and a
   status-only update does not touch the list. Trimming on every harvest save would shrink an already long document
   sooner, and it would violate the requirement that a non-append update leaves the list unchanged.
3. **Keep recording every finalize outcome.** `ArcManager` still appends one success or failure per attempt that records
   today. The ring buffer is what stops the document from growing. Suppressing a repeated success would change the
   harvest-manager recording rules, which this change does not.

## Risks / Trade-offs

- [A harvest that already has more than the maximum keeps the extra events until the next append.] → Accepted. The
  requirement only bounds the list when an event is appended. The next finalize drops the oldest.
- [Raising or lowering the knob does not rewrite stored documents by itself.] → The new ceiling applies on the next
  append. Rollback is to stop trimming; events already dropped are not restored.
- [A later document-store engine still has to append through this update path.] → The trim sits next to the append, not
  in a CouchDB query.
