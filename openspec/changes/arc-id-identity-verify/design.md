# Design

## Context

See `proposal.md` for motivation (#101 Option 1). Today `store_arc` loads `arc_{calculate_arc_id(identifier, rdi)}` and,
if present, merges metadata / overwrites `arc_content` without comparing stored identity to the incoming pair.
`calculate_arc_id` only applies `.strip()` to both inputs (`utils.py`). Documents store top-level `rdi` and identifier
inside `arc_content` (RO-Crate root). Harvest-local content conflicts already raise `DuplicateArcError` →
`DuplicateArcInHarvestError` → HTTP `409`; standalone has no analogous identity gate.

Unicode NFC canonicalize-before-hash is out of scope (#537).

## Goals / Non-Goals

**Goals:**

- Fail closed on `arc_id` key collision when strip-normalized identity differs.
- Keep successful matching-identity paths (create, content update, harvest duplicate-content) unchanged.
- Map identity mismatch to HTTP `409` for both upload surfaces.

**Non-Goals:**

- Changing the `arc_id` formula (NFC, scheme version, migration) — #537.
- Changing `content_hash` / RO-Crate canonicalization.
- Using GitLab project metadata as the primary collision check.
- Replaying or repairing historically overwritten documents.

## Decisions

### 1. Compare strip-normalized stored vs incoming `(identifier, rdi)`

- **Choice:** Extract stored identifier from existing `arc_content` (same RO-Crate root rules as ingest) and compare
  `stored.strip()` / `incoming.strip()` for both identifier and `rdi` against the document's top-level `rdi`.
- **Why:** Matches the lock-in and current `calculate_arc_id` contract without renaming keys.
- **Alternatives:** Compare only `rdi` (misses identifier collisions); compare raw bytes without strip (false positives
  vs hash input); NFC now (#537) — deferred breaking change.

### 2. Raise a dedicated conflict, not `DuplicateArcError`

- **Choice:** New document-store / business-logic conflict type for identity mismatch (e.g. subclass of
  `ConflictError`), distinct from harvest content-duplicate `DuplicateArcError` / `DuplicateArcInHarvestError`.
- **Why:** Harvest callers already map content duplicates to `409` with harvest-specific messaging; identity mismatch
  can happen standalone or mid-harvest and needs a clear operator-facing detail.
- **Alternatives:** Reuse `DuplicateArcError` for both (ambiguous); map to `500` (hides client-correctable conflict).

### 3. HTTP `409 Conflict` for both standalone and harvest

- **Choice:** Map identity mismatch to `409` on `POST /v3/arcs` and `POST /v3/harvests/{id}/arcs`.
- **Why:** Semantic conflict with an existing resource key; harvest already uses `409` for related conflicts; clients
  should not retry as if the write succeeded.
- **Alternatives:** `422` (validation — wrong: payload is structurally fine); `500` (server fault — wrong for known
  collision).

### 4. Check before merge / save; no body write on failure

- **Choice:** Perform the identity check as soon as an existing document is loaded (before metadata merge and
  `save_document`). On conflict retries, re-validate against the fresh document the same way harvest identity validators
  do for content duplicates if a concurrent writer could race.
- **Why:** Spec requires no overwrite; TOCTOU-safe save path already exists for harvest duplicates.

### 5. True crypto collision ≡ identity mismatch

- **Choice:** No separate detection path; differing strip-normalized pairs at the same `arc_id` is the observable
  signal.
- **Why:** Matches lock-in; probability of true SHA-256 collision is irrelevant to the control.

## Risks / Trade-offs

- **[Risk] Malformed legacy docs without extractable identifier** → Mitigation: treat missing/unparseable stored
  identifier as identity failure (fail closed) or log + conflict; prefer fail closed so overwrite cannot proceed.
- **[Risk] Clients confuse identity `409` with harvest content `409`** → Mitigation: distinct exception type and error
  detail text; OpenAPI/docs note both map to `409`.
- **[Risk] Whitespace-only differences already collapse via strip** → Accepted; intentional parity with
  `calculate_arc_id`.
- **[Risk] NFC/NFD still produce different `arc_id`s** → Accepted for this MVP; tracked in #537.

## Migration Plan

- Deploy as a pure behavior change: no CouchDB schema bump, no `arc_id` rewrite.
- Rollback: revert the gate; previously refused writes may succeed again (integrity risk returns).
- No backfill required for Option 1.

## Open Questions

_(none — HTTP status and strip-only compare locked in.)_
