# Design

## Context

See proposal.md for why this lands before the PostgreSQL document-store cutover. Today `_finalize` keeps the full
Dataset list, calls `serialize_catalog_file` (another full buffer), then `_publish_catalog_bytes` clones and compares
those bytes. `catalog_list_page_size` already pages CouchDB reads (default 500).

## Goals / Non-Goals

**Goals:**

- Drop the Dataset list before the ephemeral Git clone starts.
- Keep catalog file bytes identical to today's serializer.
- Leave the page-size knob as the operator control for the CouchDB read window.

**Non-Goals:**

- A new CouchDB or PostgreSQL pager.
- Changing the default page size.
- Sort-key canonical-JSON micro-optimization.
- Shallow or sparse clone work (#346; shallow clone is already required).
- Document-store engine changes (#590).

## Decisions

1. **Serialize to a file, then publish from that path.** Write the existing canonical bytes to a temporary file, record
   `dataset_count` and the skip list, drop the Dataset list, then clone and copy the file into the working tree. Git
   publish no longer takes a `bytes` object that lives for the whole clone.
   - Alternative: `del datasets` while still passing `catalog_bytes` into publish. That frees the list but keeps a
     second full copy of the catalog in RAM next to the clone. The file path removes that copy.
   - Alternative: stream JSON incrementally while reading CouchDB. That needs a stable order before the full set is
     known (identifier sort, duplicate tie-break), so the Dataset list still exists until serialization finishes.
     Streaming the Git side is the part that can start after that list is dropped.

2. **Byte compare stays on the serialized file.** Unchanged-catalog skip reads the clone target and the serialized file.
   It MUST NOT rebuild the Dataset list to decide whether to push.

3. **Page size stays a config field.** `catalog_list_page_size` remains operator-settable through the existing config
   wrapper. Document in the field description that a lower value shrinks the CouchDB page of full ARC bodies. Default
   stays 500.

4. **Cleanup.** The serialized file is removed in the same `finally` path as the ephemeral clone, including when Git
   raises.

## Risks / Trade-offs

- [Risk] Peak moves from RAM to a temp file the size of the catalog plus the shallow clone. → Acceptable; the Dataset
  object graph is the larger resident set. The file lives under the existing cache directory and is deleted with the
  clone.
- [Risk] A crash between serialize and `finally` leaves an extra cache file. → Use the existing ephemeral cache naming
  and stale-cache reclaim patterns so leftovers are eligible for age-based cleanup.
- [Risk] Tests that mock `serialize_catalog_file` return bytes. → Update them to the path-based publish seam without
  changing expected catalog bytes.

## Migration Plan

No data migration and no config default change. Rollback is reverting the finalize publish path; already published
catalogs stay valid because bytes do not change.
