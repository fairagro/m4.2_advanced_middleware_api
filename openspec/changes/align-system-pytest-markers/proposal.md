## Why

Devinfra [#120](https://github.com/fairagro/m4.2_middleware_devinfra/issues/120) will filter
pre-push pytest with `-m "not system_external and not system_local"`. This product must guarantee
heavy suites stay under those markers (and document how to run them intentionally) so the synced
hook stays fast without forking `.pre-commit-config.yaml`
([#416](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/416)).

## What Changes

- Harden directory-level marking: `pytestmark` in `system_external` / `system_local` confests so
  new tests cannot omit the marker by accident (per-test marks already present on current cases).
- Document intentional `system_*` runs in product docs (`docs/python_related.md` and/or AGENTS
  testing notes) — not synced `docs/quality.md`.
- Comment on Devinfra #120 that this product is ready for the pre-push filter.

## Capabilities

### New Capabilities

_None — `skip_specs: true` (test-marker / DX tooling; no domain requirement change)._

### Modified Capabilities

_None._

## Impact

- Pre-push after Devinfra #120 lands excludes Testcontainers / GitLab system suites by marker.
- CI and manual `uv run pytest -m system_external` / `system_local` unchanged in intent.
- No `.pre-commit-config.yaml` product fork.
