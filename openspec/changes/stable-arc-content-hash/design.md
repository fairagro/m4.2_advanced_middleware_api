# Stable ARC Content Hash — Design

## Context

See `proposal.md` for motivation. Hashing lives in
`middleware/api/.../document_store/content_hash.py` and already strips volatile
timestamps, sorts `@graph` by `@id`, and sorts allowlisted `{ "@id" }` reference
lists (`hasPart`, `creator`, `author`, `contributor`, `comment`). Document store
and arc-manager compare that hash for idempotency / GitLab sync gating.

OpenAgrar still churns hashes when keyword join order (and derived Comment /
ParameterValue `@id`s) changes. Person-list order is largely covered; remaining
`#Author_*` churn from comma-splitting names is a harvester mapping issue once
contacts use `"F. Last"` form—API hardening stays limited to order/multiset
rules.

Architectural preference: canonicalize in the API immediately before hash
(Prio 1). Shared `api_client` extraction is a later follow-up (Prio 2).

## Goals / Non-Goals

**Goals:**

- Spec-backfill the existing hash contract under `arc-content-hash`.
- Extend hash-input canonicalization for Keywords comment multisets and
  keyword string arrays, including `@id`/reference rewrite when identity is
  join-derived.
- Keep reference-list allowlist behaviour; add tests that lock the contract.
- Wire `document-store` content-changed detection to this capability in the
  specs (implementation already calls the same helper).

**Non-Goals:**

- en/de/untagged description preference in the hash layer.
- Blank-node comment / identifier hacks in the hash layer.
- Harvester or mapper edits in this repo.
- Moving canonicalize into `middleware/shared` or `api_client` in this change.
- Changing GitLab path or push-gate logic beyond equality of `content_hash`.

## Decisions

### Decision: New capability `arc-content-hash` (not only a document-store delta)

**Choice:** Dedicated capability for the hash contract; `document-store` gains
one ADDED requirement that content-changed uses it.

**Why:** Past stabilization never landed in OpenSpec; the rules are reusable
beyond CouchDB (workers, future api_client prediction). Stuffing them only into
document-store obscures the contract.

**Alternatives:** Modify document-store only — rejected (harder to share / find).

### Decision: Canonicalize on a hash-only copy; do not rewrite stored CouchDB bodies

**Choice:** `canonicalize_rocrate_for_hash` mutates a deep-normalized copy used
solely as hash input. Persisted ARC JSON stays as uploaded.

**Why:** Avoids surprising body rewrites, revision noise, and harvester/API
divergence on stored shape. Change detection only needs hash equality.

**Alternatives:** Persist canonical form — rejected for this change (larger
migration / diff surface).

### Decision: Keywords Comment rule — comma-split, casefold sort, `", "` join + @id rewrite

**Choice:** For `@graph` nodes with `name == "Keywords"` (string), canonicalize
`text` / primary textual value fields used as the keyword payload by splitting
on `,`, stripping tokens, dropping empties, sorting with `casefold`, rejoining
with `", "`. If the joined string changes, replace occurrences of the old
string inside `@id` values across the document and update `{ "@id": … }`
references accordingly (same old→new map).

**Why:** Matches OpenAgrar / Schema.org→ARC noise (Investigation Comment
“Keywords” and derived `#…Keywords…` ids) without domain-specific keyword
ontologies. Casefold avoids trivial case churn while preserving multiset
cardinality (duplicates kept).

**Alternatives considered:**

- Sort only without rewriting `@id`s — rejected; derived ids would still churn.
- Normalize all Comment nodes — rejected; too broad.
- Ignore Keywords comments entirely — rejected; real keyword set changes must
  still change the hash.

### Decision: Also sort homogeneous `keywords` string arrays

**Choice:** When property key is `keywords` and value is a list of only
strings, sort by `casefold` in the hash input.

**Why:** Common Schema.org shape; same multiset intent as Keywords comments.

**Alternatives:** Only Comments — rejected; arrays appear in crates too.

### Decision: Do not invent Author comma-name parsing in the API

**Choice:** Rely on existing allowlisted `author` / `creator` / `contributor`
`{ "@id" }` list sorting and `@graph` order. Do not attempt to reparsing
`"Last, F."` author strings in the hash layer.

**Why:** Comma-inside-name vs list-separator is ambiguous; harvester already
moves to `"F. Last"`. Spec scenarios cover person-list order; keyword rules
cover the remaining API-suitable OpenAgrar family.

**Alternatives:** Heuristic author-string split — rejected as unsafe semantic
guessing.

### Decision: Explicit non-normalization of language and blank nodes

**Choice:** Spec requirements forbid language preference and blank-node
stripping in this layer.

**Why:** Prevents “helpful” hash hacks that hide real mapper bugs and conflict
with harvester ownership.

### Decision: Follow-up shared module deferred

**Choice:** Keep implementation in `middleware/api/.../content_hash.py` for
this change. Optional later: one shared `canonicalize_*` used by api_client.

**Why:** Prio 1 is API correctness; duplication risk accepted until a second
consumer needs the exact function.

## Risks / Trade-offs

- **[Risk] Keywords `@id` rewrite misses a derived field shape** → Mitigation:
  unit tests with Comment text + mirrored `@id` substrings; extend with
  OpenAgrar fixtures if harvester team supplies them.
- **[Risk] Comma split wrong for keywords containing commas** → Mitigation:
  accept RO-Crate/Schema.org common join; document rule in spec; real set
  changes still differ.
- **[Risk] Hash changes for existing stored ARCs after deploy** (one-time
  re-hash on next upload) → Mitigation: expected; identical logical re-upload
  stabilizes afterward; no CouchDB migration required because bodies are not
  rewritten.
- **[Trade-off] Casefold sort may equate keywords that differ only by case** →
  Acceptable for change-detection; producers that need case-significant
  keywords as distinct semantics are rare in this pipeline.

## Migration Plan

1. Land spec + implementation + unit tests.
2. Deploy API; no CouchDB schema migration.
3. On next harvest, previously noisy OpenAgrar ARCs should stop flipping hash
   for keyword/contact/@graph order alone.
4. Harvester may later drop redundant mapper-only ORDER sorts after soak;
   language / blank-node rules stay in harvester.
5. Rollback: revert `content_hash` module; hashes return to prior (noisier)
   behaviour.

## Open Questions

- Whether to treat `name: "keywords"` case-insensitively — default for
  implement: exact `Keywords` as in ARC Comment name; revisit if fixtures show
  variance.
- Exact textual property on Comment nodes (`text` vs `value` vs both) —
  implement against observed arctrl RO-Crate shape and lock in tests.
