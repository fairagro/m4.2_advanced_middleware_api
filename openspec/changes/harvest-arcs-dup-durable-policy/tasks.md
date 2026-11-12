# Tasks

## 1. Spec framing

- [ ] 1.1 Sync main `openspec/specs/harvest-client/spec.md` from this change’s delta (or apply the MODIFIED requirement
      text in place during apply) and verify `openspec validate harvest-arcs-dup-durable-policy --strict` (or
      project-equivalent validate) succeeds
- [ ] 1.2 Confirm the duplicate-identifier and collect-errors requirements no longer mention temporary shim / #566 —
      verify with `rg -n 'shim|#566' openspec/specs/harvest-client/` returning no hits

## 2. Client wording

- [ ] 2.1 Replace “Compatibility shim” / “until #566” comments and Field descriptions in
      `middleware/api_client/src/middleware/api_client/api_client.py` and `models.py` with durable-policy wording;
      verify `rg -n 'shim|#566' middleware/api_client/src/` returns no hits
- [ ] 2.2 Update the AGENTS.md harvest-client blurb (drop “temporary client shim until #566”); verify the same `rg`
      against `AGENTS.md`
- [ ] 2.3 Run `uv run pytest middleware/api_client/tests/unit/test_harvest_arcs.py -q` and confirm skip + `DUPLICATE`
      tests still pass (no behaviour change)

## Workflow follow-up

- Archive this change after the draft PR lands (`/opsx-archive` / issue-fixer last `go`)
