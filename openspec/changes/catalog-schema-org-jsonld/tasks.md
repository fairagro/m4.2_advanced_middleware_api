# Catalog schema.org JSON-LD — Tasks

## 1. Vendored schema.org context

- [x] 1.1 Vendor a schema.org release context file under
      `arc_store/jsonld_contexts/` (e.g. `schemaorg-30.0-context.jsonld`)
- [x] 1.2 Load the vendored document offline (cached per process); no HTTP
      fetch and no config option for the schema.org version
- [x] 1.3 Ensure wheel packaging includes `jsonld_contexts/`

## 2. JSON-LD dependency and RO-Crate expand support

- [x] 2.1 Add JSON-LD library dependency (`pyld`) to the api package
- [x] 2.2 Vendor RO-Crate 1.1/1.2 context JSON for offline expand; document
      loader fail-closed for unknown remote contexts
- [x] 2.3 Define pinned ARC/Bioschemas extension term map used in the compact
      target

## 3. Worker finalize normalize path

- [x] 3.1 Compact with vendored schema.org + ARC/Bioschemas map; emit
      `@context` as `https://schema.org` + that extension map
- [x] 3.2 On consolidated **worker finalize** only: expand then compact each
      Dataset; do not compact on API ingest
- [x] 3.3 Concurrent Dataset normalize with safe sharing of read-only contexts;
      preserve `@id` sort at serialize time
- [x] 3.4 Expand/compact failure: no silent RO-Crate passthrough; classify
      permanent vs retryable where applicable

## 4. Tests

- [x] 4.1 Unit tests: worker finalize compact → emitted schema.org IRI +
      extensions; ingest path leaves `@context` unchanged
- [x] 4.2 Unit tests: vendored schema.org loads offline; byte-stable double
      compact with fixed ARC body
- [x] 4.3 Integration/unit consolidated finalize: catalog uses normalized
      `@context` (not source RO-Crate passthrough)
