## Context

See `proposal.md`. Markers `system_external` / `system_local` are already registered in `pyproject.toml` and applied on
current tests under those directories. Devinfra #120 will exclude both on pre-push.

## Goals / Non-Goals

**Goals:** Directory-level marker enforcement; product docs for intentional runs; ready signal on Devinfra #120.

**Non-Goals:** Forking synced `.pre-commit-config.yaml`; re-homing `integration/` tests; changing CI workflows in this
slice.

## Decisions

### D1: `pytestmark` in package confests

Add to `middleware/api/tests/system_external/conftest.py` and `middleware/api/tests/system_local/conftest.py`:

```python
pytestmark = pytest.mark.system_external  # or system_local
```

Keep existing per-test marks (harmless duplication). **Reason:** New files in the folder cannot forget the marker.

### D2: Docs in product-owned paths

Document in `docs/python_related.md` (and a short AGENTS testing bullet if useful). Do **not** edit synced
`docs/quality.md`.

### D3: Ready comment on Devinfra #120

After implement, comment that this product’s markers/docs are aligned for the pre-push filter.

## Risks / Trade-offs

| Risk                                        | Mitigation                                                                           |
| ------------------------------------------- | ------------------------------------------------------------------------------------ |
| Session fixtures still import on collection | Marker filter deselects tests; verify with `pytest --collect-only -m 'not system_…'` |
| Double marks                                | Benign                                                                               |
