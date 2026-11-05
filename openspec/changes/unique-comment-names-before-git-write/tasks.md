# Tasks

## 1. Helper and Git path

- [ ] 1.1 Add a last-wins Comment-name collapse helper for ARC holders (Investigation/root, Study, Assay, Person,
      Publication) with warning logs on collapse
- [ ] 1.2 Invoke the helper in the GitRepo create/update path immediately before `ARC.Write`
- [ ] 1.3 Verify unit tests: duplicate name on one holder collapses; Investigation+Study same name kept; Person and
      Publication covered; `ARC.Write` succeeds after collapse

## 2. Spec-facing checks

- [ ] 2.1 Confirm ingest / document store / content_hash paths are unchanged (no merge at persist)
- [ ] 2.2 Confirm Investigation RDI enrich behaviour from #258 still passes existing tests
