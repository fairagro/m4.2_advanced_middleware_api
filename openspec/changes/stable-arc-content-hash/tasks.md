# Stable ARC Content Hash — Tasks

## 1. Align code with backfilled contract

- [ ] 1.1 Inventory `content_hash.py` against `specs/arc-content-hash/spec.md`
      (volatile strip, `@graph` sort, allowlisted `@id` lists) and fix any
      drift; keep hash-only copy (do not rewrite stored CouchDB bodies)
- [ ] 1.2 Confirm document-store / arc-manager paths already call
      `calculate_arc_content_hash` for content-changed; adjust only if a
      legacy full-JSON hash path remains
- [ ] 1.3 Add Spec-to-Code mapping for `arc-content-hash` →
      `middleware/api/.../document_store/content_hash.py` in `AGENTS.md`

## 2. Keywords and keyword-array canonicalization

- [ ] 2.1 Implement Keywords Comment multiset canonicalization (comma-split,
      strip, drop empties, `casefold` sort, join with `", "`) on textual
      fields used by arctrl Comments (`text` and/or `value` as observed)
- [ ] 2.2 When the canonical join differs, rewrite matching `@id` substrings
      and `{ "@id": … }` references across the hash-input document
- [ ] 2.3 Sort homogeneous string `keywords` arrays by `casefold` in the hash
      input; leave mixed-type arrays order-sensitive
- [ ] 2.4 Do not add language preference or blank-node comment stripping

## 3. Regression tests

- [ ] 3.1 Add tests: Keywords comment token-order permutation (+ derived
      `@id`s) → same hash; keyword **set** change → different hash
- [ ] 3.2 Add/keep tests: `keywords` string-array permutation → same hash;
      creator/author/`@graph` order → same hash (existing coverage OK if
      still green)
- [ ] 3.3 Add/keep negative tests: description text change and
      blank-node-looking comment text → different hash; non-allowlisted /
      mixed lists stay order-sensitive

## 4. Verification

- [ ] 4.1 Run `uv run pytest middleware/api/tests/unit/test_content_hash.py -v --tb=short`
- [ ] 4.2 Run `uv run pytest middleware/api/tests/unit/ -v --tb=short`
- [ ] 4.3 Run ruff check + format check on
      `content_hash.py` and `test_content_hash.py` (workspace-root
      `pyproject.toml` via `uv run`)
