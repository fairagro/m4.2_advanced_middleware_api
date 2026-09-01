# Catalog Dataset Materialize — Tasks

## 1. Materialize core

- [x] 1.1 Add `@graph` index builder keyed by `@id` from `RoCrateContent`
- [x] 1.2 Implement `materialize_catalog_dataset(record, arc_content)` with
      property/type whitelist and 2-hop `hasPart` depth
- [x] 1.3 Implement Person materialization for `creator`, `author`, and
      `contributor` (strip fragment `@id`, copy whitelisted fields)
- [x] 1.4 Implement `#LICENSE` resolution (url → string, else text → string)
- [x] 1.5 Implement LDComment mapping (`Keywords` → `keywords`,
      `Language` → `inLanguage`; else inline `Comment`)
- [x] 1.6 Implement `citation` materialization (ScholarlyArticle/CreativeWork
      fields only; no nested comment chain)
- [x] 1.7 Implement `hasPart` Study/Assay nested Dataset materialization with
      `additionalType` preserved
- [x] 1.8 Omit missing `@id` targets with warning; do not abort finalize

## 2. Finalize integration

- [x] 2.1 Call `materialize_catalog_dataset` in `_collect_catalog_datasets`
      after extract, before normalize
- [x] 2.2 Ensure materialize runs only on worker finalize path (not API ingest)

## 3. Unit tests

- [x] 3.1 Add synthetic fixture: root with dangling Person/Comment refs + graph
      nodes (production dangling-ref pattern)
- [x] 3.2 Test Person inline (`givenName`/`familyName`, no `#Person_…` `@id`)
- [x] 3.3 Test `#LICENSE` → text (`edaphobase.json` pattern) and url case
- [x] 3.4 Test LDComment Keywords/Language mapping and Comment fallback
- [x] 3.5 Test `hasPart` Study→Assay two-hop (`sample.json` pattern)
- [x] 3.6 Test citation inline without nested Comment (`sample.json` `#test`)
- [x] 3.7 Test missing ref omitted + materialize continues
- [x] 3.8 Update `test_catalog_jsonld.py` expectations: materialized input
      before compact (no dangling `#Person_…` in published creator)
- [x] 3.9 Test materialize + normalize round-trip: schema.org `@context`, no
      `example.org` in fields (B1 still holds)

## 4. Integration and quality

- [x] 4.1 Extend consolidated finalize integration test to assert materialized
      fields in pushed `{rdi}.json`
- [x] 4.2 Run `uv run pytest` on affected tests; `./scripts/quality-check.sh`
      on touched paths
