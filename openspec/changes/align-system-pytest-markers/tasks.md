## 1. Marker hardening

- [ ] 1.1 Add `pytestmark = pytest.mark.system_external` to `middleware/api/tests/system_external/conftest.py`
- [ ] 1.2 Add `pytestmark = pytest.mark.system_local` to `middleware/api/tests/system_local/conftest.py` (create thin conftest if missing)
- [ ] 1.3 Verify collect counts: `system_external` / `system_local` match suite; `-m "not system_external and not system_local"` deselects them

## 2. Docs

- [ ] 2.1 Document intentional `uv run pytest -m system_external` / `system_local` (and pre-push exclude intent) in `docs/python_related.md`

## 3. Ready signal

- [ ] 3.1 Comment on Devinfra #120 that this product is ready for the pre-push marker filter
