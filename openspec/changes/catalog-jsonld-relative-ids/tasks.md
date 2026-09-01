# Catalog JSON-LD relative IDs — Tasks

## 1. Compact processing @base

- [x] 1.1 Add a named constant for the internal compact `@base` equal to pyld
      `DEFAULT_BASE_IRI` (`http://example.org/base/`) in
      `catalog_jsonld.py`.
- [x] 1.2 Pass that `@base` only on the processing compact context (or compact
      options) used by Dataset expand/compact; do not add it to the public emit
      `@context` builder.
- [x] 1.3 After compact, keep assigning the existing public `@context`
      (`https://schema.org` + ARC/Bioschemas map) with no `@base`.

## 2. Tests

- [x] 2.1 Add unit tests with an ARCtrl-shaped Dataset (`@id` `./`, `#Person_…`,
      `#LICENSE`, `assays/…/`, nested creator/hasPart/comment/citation) that
      after normalize has relative IDs and no `http://example.org/base/` in
      identifier-bearing fields.
- [x] 2.2 Assert public `@context` has no `@base` and no `example.org`.
- [x] 2.3 Assert `identifier` and schema.org short names are preserved; an
      already-absolute HTTP(S) IRI (not the dummy base) stays absolute.
- [x] 2.4 Adjust existing `test_catalog_jsonld.py` / finalize tests that currently
      expect dummy-base absolute URLs.

## 3. Verify

- [x] 3.1 Run `uv run pytest middleware/api/tests/unit/test_catalog_jsonld.py`
      and related consolidated-git finalize tests.
