# Catalog schema.org JSON-LD — Tasks

## 1. HTTP client and schema.org pin

- [ ] 1.1 Fetch the pinned schema.org context with `httpx.AsyncClient`
      (explicit timeouts)
- [ ] 1.2 Add a Pydantic/ConfigWrapper field for the schema.org context version
      pin on consolidated catalog settings (description + default, e.g. `30.0`;
      env override); derive the immutable fetch URL from that version
- [ ] 1.3 Implement process-local single-flight load of the pinned schema.org
      context (one fetch per worker process; safe under concurrent first use)

## 2. JSON-LD dependency and RO-Crate expand support

- [ ] 2.1 Add `pyld` to the `api` package via `uv` and lockfile
- [ ] 2.2 Vendor RO-Crate 1.1/1.2 context JSON for offline expand; document
      loader fails closed on unknown remote context URLs

## 3. Worker finalize normalize path

- [ ] 3.1 Define compact target = loaded schema.org context + pinned
      ARC/Bioschemas extension map (observed Lab/Sample set)
- [ ] 3.2 On consolidated **worker finalize** only: expand then compact each
      Dataset; do not compact on API ingest
- [ ] 3.3 Run Dataset normalize with bounded concurrency; shared context
      read-only; stable `@id` ordering after normalize
- [ ] 3.4 Expand/compact or context-load failure: no silent RO-Crate
      passthrough (transient vs permanent per fetch/JSON-LD error class)

## 4. Tests and verification

- [ ] 4.1 Unit tests: worker finalize compact → schema.org-oriented context;
      ingest path leaves `@context` unchanged
- [ ] 4.2 Unit tests: unknown IRI remains absolute; single-flight load under
      concurrent first use (one fetch); byte-stable double compact with fixed
      pin
- [ ] 4.3 Update catalog serialize / consolidated finalize tests that asserted
      passthrough `@context`
- [ ] 4.4 Run focused `uv run pytest` for catalog / consolidated git / worker
      finalize coverage
