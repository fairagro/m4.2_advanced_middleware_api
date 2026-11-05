# Proposal

## Why

ISA-XLSX / ARCtrl `ARC.Write` rejects two Comments with the same name on one holder. Clients (and some crates) still
submit duplicates; Git sync then fails even though CouchDB accepted the body. The API needs a last-wins merge with a log
warning immediately before Write, without changing the CouchDB/hash ingest path.

## What Changes

- Before `ARC.Write` in the Git sync path, ensure each Comment holder has unique Comment names (last-wins; warn on
  collapse)
- Cover Investigation, Study, Assay, Person, and Publication holders
- Keep same-name Comments on **different** holders allowed
- Do **not** merge or reject duplicates at HTTP ingest / CouchDB persist / `content_hash` time
- No special-case for `dateModified` (generic last-wins covers residual duplicates)
- Investigation RDI Comment upsert (#258) unchanged

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `arc-store`: Require unique Comment names per holder immediately before Git materialization (`ARC.Write`), with
  last-wins merge and a warning log when duplicates are collapsed

## Impact

- Code: `middleware/api` GitRepo create/update path (and a small helper used there); unit tests around Comment
  collapse + Write success; cross-holder RDI regression
- Specs: `openspec/specs/arc-store/`
- Non-impact: document store / content hash / HTTP upload contracts; harvester may keep its own `; ` join (API last-wins
  is independent)
- Issue: #562
