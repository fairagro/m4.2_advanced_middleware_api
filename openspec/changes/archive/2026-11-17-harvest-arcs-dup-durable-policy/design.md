# Design

## Context

See `proposal.md` — Why. Runtime already implements intra-batch duplicate skip + client/server error merge
(`ApiClient._submit_arcs_parallel` / `harvest_arcs`). Main-spec and code comments still describe a temporary shim toward
#566. #565 closed will-not-do for turning identical-content retries into server `duplicate` rows; those retries remain
HTTP `200`.

## Goals / Non-Goals

**Goals:**

- Align `harvest-client` requirements and client docstrings with durable policy
- Preserve existing tests and merge semantics

**Non-Goals:**

- Changing skip rules, HTTP mapping, or server harvest `errors` persistence
- Implementing #566 (removal) or reopening #565
- Server-side detection of “would-have-been” in-batch duplicates that the client never POSTs

## Decisions

1. **Wording-only apply** — Edit delta + comments/AGENTS; no control-flow changes in `api_client`.
   - Alternative: remove skip now — rejected by #650 / #566 supersession.
2. **Keep client merge** — Server never sees skipped duplicate POSTs; merge remains the only way those `DUPLICATE` rows
   appear on `HarvestResult.errors`.
3. **Delta vs skip_specs** — Requirement text changes (temporary → durable), so a real `harvest-client` delta is
   required; do not set `skip_specs: true`.

## Risks / Trade-offs

- [Docs drift vs archived #240 design] → Archive stays historical; main + this change are SoT going forward.
- [Operators expecting server-only error lists] → Document that client-only skips still merge into the result.
