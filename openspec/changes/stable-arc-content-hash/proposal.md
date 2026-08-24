# Stable ARC Content Hash — Proposal

## Why

OpenAgrar (and other RDIs) re-upload logically identical ARCs whose RO-Crate JSON
differs only by serialization / join order. That churns `content_hash`, triggers
false “content changed” updates, and wastes GitLab sync work. Order and
serialization canonicalization belongs in this API immediately before the hash
is computed so every producer (all mappers, older harvester versions) gets a
stable hash without inventing per-mapper workarounds.

Past API hash hardening (volatile timestamps, `@graph` sort, order-insensitive
`hasPart` / `creator` / `author` / `contributor` / `comment` reference lists)
shipped without an OpenSpec contract. That gap must be closed now while extending
the rules for keyword-join and related order noise.

## What Changes

- Introduce capability `arc-content-hash`: the authoritative contract for how
  ARC RO-Crate JSON is canonicalized into `content_hash` / `arc_hash`.
- **Backfill** requirements for already-shipped behaviour:
  - strip volatile timestamps (`dateCreated`, `datePublished`, `sdDatePublished`,
    `dateModified`);
  - stable `@graph` ordering by `@id` (with deterministic tie-breakers);
  - order-insensitive allowlisted `@id` reference lists (`hasPart`, `creator`,
    `author`, `contributor`, `comment`) under the existing safe heuristic.
- **Extend** canonicalization for order/serialization noise only:
  - keyword-like multi-value text and Comment nodes named `"Keywords"` so
    equivalent keyword multisets (casefold-sorted tokens) hash identically,
    including derived strings / `@id`s whose identity is solely join-order;
  - harden person-related / `#Author_*`-style nodes so array-order flips alone
    do not change the hash (extend existing order-insensitive logic as needed).
- Add regression tests for keyword token order, creator/author order, `@graph`
  order → same hash; real description text change or real keyword **set** change
  → different hash.
- Clarify in `document-store` that content-changed detection uses this contract.
- **Non-goals:** language preference (en/de) in the hash layer; stripping
  blank-node-looking comment bodies; inventing Investigation identifiers;
  harvester mapper changes in this repo; GitLab path rules beyond hash equality;
  extracting shared code into `api_client` (optional follow-up, Prio 2).

## Capabilities

### New Capabilities

- `arc-content-hash`: Canonicalization contract for ARC RO-Crate `content_hash`
  (volatile-field strip, graph/reference-list ordering, keyword multiset
  normalization, person/Author order hardening). Documents existing behaviour
  and the OpenAgrar-driven extensions.

### Modified Capabilities

- `document-store`: Content-changed detection MUST use the `arc-content-hash`
  contract (not raw JSON dumps or legacy full-document hashes).

## Impact

- **Code:** `middleware/api/src/middleware/api/document_store/content_hash.py`
  and `middleware/api/tests/unit/test_content_hash.py` (primary). Callers that
  already use `calculate_arc_content_hash` inherit behaviour; no HTTP API shape
  change.
- **Specs:** new `openspec/specs/arc-content-hash/` after archive; delta under
  this change; small `document-store` delta; update Spec-to-Code mapping in
  `AGENTS.md` on apply/archive.
- **Coordination:** Harvester
  `openspec/changes/deterministic-schema-org-mapping` may keep temporary
  mapper-side sorts; API must still cover older / other producers. Language
  preference and blank-node rules stay in the harvester.
- **Out of scope:** `middleware/api_client` shared canonicalize (follow-up);
  harvester repo edits.
