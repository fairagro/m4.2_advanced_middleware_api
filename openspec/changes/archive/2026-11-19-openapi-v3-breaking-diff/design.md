# Design

## Context

See `proposal.md` for motivation. Sibling gate #570 (`scripts/check_api_surface.py` + `docs/api-surface-check.md`)
already encodes Conventional Commit escape (**B2**) and a Feature PR job. Production FastAPI mounts `/v2` and `/v3` in
one OpenAPI document (`middleware.api.api.fastapi_app.Api`); unit tests already construct `Api` with dummy config
without live CouchDB/Celery. Lock-in: **A1** (generate at check time), **B2** (commit escape), **C2** (`/v3` filter),
**D1** (`oasdiff`).

## Goals / Non-Goals

**Goals:**

- Reliable tip-vs-`main` breaking detection for the public HTTP `/v3` contract
- Same declare-to-pass semantics as the griffe gate so agents/release bump stay coherent
- Product-local scripts + CI job; docs that mark failures toolchain-owned

**Non-Goals:**

- Committed `openapi.json` artifact or hand-maintained spec
- Guarding `/v2` or offline-profile OpenAPI
- CouchDB document schemas (#652)
- Moving the gate into a Devinfra fleet fragment
- Changing runtime API behaviour or OpenAPI content itself

## Decisions

1. **SoT = live generate (A1), not a git-tracked JSON** Export via constructing the production `Api` (or equivalent)
   with a minimal in-memory `Config` (same shape as the pytest dummy path), call `app.openapi()`, write temp JSON. For
   `main`, use a second git worktree (or checkout) at the base ref and run the same exporter. _Alternatives:_ committed
   artifact (**A2**) — simpler diff but stale risk + sync CI; rejected for MVP.

2. **Filter to `/v3` before diff (C2)** After generate, drop `paths` keys that do not start with `/v3` (and prune
   unreferenced `components` if cheap; if not, leave components — oasdiff breaking mode still keys off path ops).
   _Alternatives:_ full-app diff (**C1**) — noise from legacy `/v2`; bare `api_v3` mount only (**C3**) — misses
   production-only `/v3` routes.

3. **Tool = oasdiff breaking mode (D1)** Pin a known oasdiff version (container image or released binary fetched in
   CI/script). Invoke breaking-only; treat exit “breaking found” as gate failure subject to commit-marker override.
   _Alternatives:_ other OpenAPI diff CLIs — less aligned with the issue wording.

4. **Commit-marker reuse (B2)** Share the same Conventional Commit detection rules as `check_api_surface.py` (subject
   `type!:` / `type(scope)!:` or `BREAKING CHANGE:` footer on `main..HEAD`). Prefer a small shared helper module under
   `scripts/` over copy-paste if both gates call it; otherwise duplicate minimally and note a follow-up.

5. **CI placement** New job (or step) on `feature-pull-request.yml` next to `api-surface`, base `origin/main`, local
   entry `./scripts/check-openapi-v3.sh`. Document in `docs/openapi-v3-check.md`; cross-link from
   `docs/api-surface-check.md` and the product surface-quality bar. Do not edit synced `docs/quality.md`.

6. **App boot without secrets** Exporter MUST NOT require `MIDDLEWARE_API_CONFIG` on disk: inject
   `Config.from_data({...})` the same way tests avoid production secrets. Do not run lifespan / connect to CouchDB or
   RabbitMQ; OpenAPI is derived from route registration at construction time.

## Risks / Trade-offs

- **[Risk] App construction pulls heavy imports or fails without full env** → Mitigation: dedicated export entry that
  patches/injects config before `Api` init; keep deps to what unit tests already import; fail the gate with a clear
  “could not generate OpenAPI” error (not a silent pass).
- **[Risk] oasdiff false positives (enum widen, description-only noise)** → Mitigation: use breaking-only flags; tune
  ignore rules only if proven noisy in CI; document known benign cases.
- **[Risk] Worktree/base checkout cost in CI** → Mitigation: shallow worktree at `origin/main`; mirror griffe base
  resolution (`origin/main` then `main`).
- **[Trade-off] `/v2` unguarded** → Accepted; out of #651 done-when.
- **[Trade-off] Supply-chain pin for oasdiff binary/image** → Accept; document version in script or workflow env.

## Migration Plan

- Land scripts + docs + CI on the issue branch; no runtime deploy change.
- First red CI on undeclared `/v3` breaks teaches the escape hatch (same as griffe).
- Rollback: remove the CI job / script; no data migration.

## Open Questions

- None that block specs/tasks; exact oasdiff pin and whether to extract a shared commit-marker helper can be decided
  during apply.
