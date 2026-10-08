# Design

## Context

See proposal.md — Why. Clients need DataHUB-equivalent `arc-export` without the Middleware runtime. Existing
`middleware/tools/rocrate2arc.py` shows the ARCtrl write adapter but is not published. `fairagro-middleware-shared`
intentionally omits `arctrl`; `api_client` is HTTP-only.

## Goals / Non-Goals

**Goals:** Published library + CLI; DataHUB-equivalent defaults; structured results; mockable Docker for unit tests.

**Non-Goals:** Running against live Middleware; shipping RDI fixtures here; changing DataHUB CI; digest-pinning as the
only default (override is enough for MVP).

## Decisions

### D1: Separate package `fairagro-middleware-arc-validation`

New workspace member at `middleware/arc_validation/` with hatch-vcs, same tag scheme as shared/api_client.

**Reason:** Needs `arctrl` + Docker CLI; must be installable from PyPI without this monorepo checkout.

### D2: Pipeline stages

1. `write_arc_scaffold(rocrate, out_dir) -> Path` — `ARC.from_rocrate_json_string` + `Write` (same idea as
   `rocrate2arc.py` / API worker path).
2. `run_arc_export(arc_dir, *, image, formats) -> ArcExportResult` — `docker run --rm -v … -w /arc <image> arc-export`
   (or image entrypoint) with DataHUB-equivalent `-f` flags under the mounted ARC root.
3. `validate_rocrate(...)` — temp dir → write → export → cleanup.

**Reason:** Separates ARCtrl failures from Docker/export failures; clients can call stages independently.

### D3: Image and formats

Default image `ghcr.io/nfdi4plants/arc-export:main`. Override via `image=` kwarg and/or env `FAIRAGRO_ARC_EXPORT_IMAGE`
(exact env name documented in README). Default formats: `rocrate-metadata-lfs`, `isa-json`, `summary-markdown`.

**Reason:** Match DataHUB CI; digest tags for reproducibility without forcing digests on every call.

### D4: Cause excerpt

Extract a short `cause_excerpt` preferring lines around `Internal Error:` / classified failure hints (reuse ideas from
`scripts/list_failed_arc_json_jobs.py`, not a hard import of that script into the published package).

**Reason:** Client CI logs stay readable.

### D5: Testing

Unit tests mock `subprocess`/`docker` invocation. Optional `@pytest.mark.requires_docker` integration test skipped by
default in commit-stage CI.

**Reason:** Keep pre-commit/CI deterministic; live Docker is opt-in.

### D6: ci-cd PyPI third package

Extend OpenSpec `ci-cd` and the release publish list so wheels for shared, api-client, **and** arc-validation publish
when credentials exist.

**Reason:** Acceptance criterion — clients install from PyPI.

## Risks / Trade-offs

- [`:main` drifts] → Document digest override; optional follow-up to pin default digest.
- [Docker permission / DinD in client CI] → Consumer responsibility; README documents socket requirement.
- [ARCtrl Write crash before export] → Surface as failed `ArcExportResult` (non-zero / ok=False) with excerpt from
  exception text, not only Docker stderr.

## Migration Plan

Additive package. No existing callers. Rollback = stop publishing / clients stay on previous pins.
