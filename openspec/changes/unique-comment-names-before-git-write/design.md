# Design

## Context

Git sync parses the stored RO-Crate with arctrl and calls `ARC.Write` in `GitRepo._create_or_update`. ARCtrl 3.2.x
rejects duplicate Comment names on one holder (clear error after #641). Ingest already does structural `parse_rocrate`
and Investigation RDI Comment upsert before CouchDB; hash canonicalisation is separate and does not collapse Comment
names. Product rule: pre-store work stays limited to hash stability plus the existing RDI enrich; Comment uniqueness is
a Write-time concern (#562 lock-ins: last-wins + warn, Git path only, all holders, no `dateModified` special-case).

## Goals / Non-Goals

**Goals:**

- Make Git materialisation succeed when a holder has duplicate Comment names
- Last-wins merge with an explicit warning log
- Cover Investigation, Study, Assay, Person, Publication
- Preserve same-name Comments across different holders (e.g. Investigation + Study `RDI`)

**Non-Goals:**

- Changing CouchDB body, HTTP status, or `content_hash` for duplicate Comments
- Harvester-style `; ` join (API is last-wins; producers may still join themselves)
- Rejecting duplicates with `422` at ingest
- Special-casing `dateModified` or waiting on further ARCtrl releases to drop the uniqueness contract
- Reworking Investigation RDI upsert (#258)

## Decisions

1. **Where:** Helper invoked in the Git create/update path immediately before `arc.Write(...)`, operating on the
   in-memory arctrl `ARC` (and nested Study/Assay/Person/Publication Comment lists). Not in
   `ArcManager.create_or_update_arc`.
2. **Policy:** For each holder, walk Comments in order; for a repeated `Name`, keep the later Comment and drop earlier
   ones; log a warning once per collapsed name (include holder kind + identity/identifier when cheap).
3. **Empty/None names:** Treat missing/blank names conservatively — only collapse when names are equal non-empty strings
   (match ISA keying); do not invent names.
4. **Stored vs written:** Document-store ARC may still contain duplicate Comment nodes; Git tree reflects post-merge
   ARC. Accept Store≠Git for this field class under the hash-stability ingest rule.
5. **Tests:** Unit-test the helper (collapse + cross-holder keep) and a GitRepo/Write integration-style unit that
   previously would fail `Write` without the helper.

## Risks / Trade-offs

- **Drift:** Operators reading CouchDB RO-Crate may still see duplicates while Git/ISA does not — mitigated by warning
  logs and docs in the change/spec.
- **Last-wins vs harvester `; `:** Values may differ between products for the same multi-valued source — accepted
  lock-in.
- **Shared Comment `@id` across holders:** Collapse is per holder list in the arctrl model after parse; shared graph
  nodes are already handled carefully by RDI enrich — avoid deleting graph nodes globally; only rewrite each holder’s
  Comment collection.
