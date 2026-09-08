# Adopt Devinfra Wave A — Design

## Context

See `proposal.md` for motivation (#366, Devinfra Wave A). This repo already has
local copies of much of the AI review stack; content hashes diverge from
Devinfra `main`. `scripts/ai` / `m42-ai`, `openspec/principles.global.md`, and
`docs/surface-quality-bar.global.md` are missing. Token helpers exist but are
older than Devinfra’s b64-only, Dev-Container-only store. Product domain specs
under `openspec/specs/` are unchanged (`skip_specs: true`).

Explore decisions (process A→B→C then sync; A + thin Auth-B; P3; F1 fleet
pilot) are on
[issue #366](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/366).
**2026-09-08 refresh:** Devinfra [#32](https://github.com/fairagro/m4.2_middleware_devinfra/issues/32)
and [#35](https://github.com/fairagro/m4.2_middleware_devinfra/issues/35) are
closed; issue body now requires syncing the surface-bar global map and shared
arctrl skill. Former “O1 in principles / provisional until #32” is superseded
by the official overlay file.

## Goals / Non-Goals

**Goals:**

- Synced Wave A paths match Devinfra at a pinned SHA (no intentional local drift).
- Agents run `/review-fixer` (and create/issue-fixer) via `m42-ai` with
  `scripts/bin/gh` auth matching skill docs.
- Surface-bar **rules** stay in synced policy; **default path map** in synced
  `.global.md`; **product path rows** only in local `docs/surface-quality-bar.md`.
- Local principles remain the product contract (stack, modules, scaling) while
  shared foundation lives only in `principles.global.md`.
- Pilot pattern reusable by sibling repos on the same SHA.

**Non-Goals:**

- Designing Devinfra sync automation or Wave B/C surfaces.
- Changing product API/runtime behaviour or domain OpenSpec requirements.
- Keeping a parallel Finder-examples section in `principles.md` once the
  surface-bar overlay exists.

## Decisions

### D1: Verbatim sync from pinned Devinfra SHA

Copy listed paths from `fairagro/m4.2_middleware_devinfra` at one commit SHA
recorded in the adopt PR. Do not hand-edit synced files after copy.

**Reason:** Single source of truth; avoids triple drift across the fleet.
**Alternatives:** Wait for #13 sync PRs (still optional); cherry-pick with local
edits (creates permanent forks).

### D2: A + thin Auth-B in one PR

Include `scripts/bin/gh`, `scripts/dev-tokens.sh`, `scripts/set-dev-tokens.sh`
with Wave A; exclude `scripts/bin/git` and the rest of Wave B.

**Reason:** Shared skills document these wrappers; older local copies diverge
(b64 encoding, DC-only store, gh resolution). Thin slice keeps the PR
reviewable without pulling quality/Dev Container.
**Alternatives:** A-only (skills/docs mismatch on auth); full Wave B in same PR
(too large).

### D3: `m42-ai` via `--project scripts/ai`

Do not add `scripts/ai` to the product root uv workspace in this change.

**Reason:** Devinfra `main` documents `uv run --project scripts/ai m42-ai …`;
product root already workspaces `middleware/*`. Devinfra root workspace wiring
is that repo’s layout, not a product template.
**Alternatives:** Add workspace member now (optional later convenience).

### D4: P3 local principles overlay

Add `openspec/principles.global.md` verbatim. Rewrite local `principles.md` to
extend `.global` (read-first; do not weaken Type Safety / Supported
environment), drop duplicated shared sections, keep and modernize
product-only sections (Technology Stack, Module Dependency Rules, Scaling, …).

**Reason:** Agents and Copilot must load shared rules from `.global` while
retaining this repo’s stack/module contract.
**Alternatives:** Mechanical delete-only split (P1/P2) — weaker alignment;
leave fat local file (contradicts / weakens `.global`).

### D5: Surface-bar split (replaces former O1-in-principles)

Sync `docs/surface-quality-bar.global.md` verbatim. Create local
`docs/surface-quality-bar.md` with product-only path rows / typical entries
(e.g. `/v3/…`, Celery tasks, CouchDB documents, `dev_environment/config.yaml`
as clarifications under Product/domain). Do not edit synced policy or `.global`
solely to add a path row. Do **not** put a provisional-#32 Finder section in
`principles.md`.

**Reason:** #32 landed; issue #366 and Devinfra policy point at this overlay
contract. Keeps product Finder/surface context without forking synced files.
**Alternatives:** Former O1 in principles (superseded); skip local overlay if
global `middleware/*/src/` row alone is enough (rejected — product wants
explicit typical entries).

### D6: Remove `scan-secrets`; sync shared `arctrl`

Delete `.agents/skills/scan-secrets/` and update AGENTS / lint excludes to the
shared vendor set `{gh,docker,hadolint,uv}`. Replace
`.agents/skills/arctrl/` with Devinfra’s first-party skill (synced, not a
vendor `gh skill` pin).

**Reason:** Matches #366 allowlist after #35; avoids local vendor exceptions and
arctrl drift.
**Alternatives:** Keep local arctrl / scan-secrets (rejected).

### D7: `skip_specs: true`

No delta under `openspec/changes/.../specs/`. Shared agent behaviour remains
specified in Devinfra; product domain specs unchanged.

**Reason:** Avoid inventing requirements solely for validation; this change is
tooling/docs adoption.
**Alternatives:** Import Devinfra capability specs into this repo (out of scope
for Wave A pilot).

## Risks / Trade-offs

- **[Risk] Legacy `tokens.env` non-b64 lines break after Auth-B** → Mitigation:
  document one-time `source ./scripts/set-dev-tokens.sh` in PR / smoke notes.
- **[Risk] P3 principles rewrite grows the PR** → Mitigation: keep product
  sections purposeful; no unrelated AGENTS essay; separate commits if helpful.
- **[Risk] Replacing local arctrl drops product-only notes** → Mitigation: diff
  local vs Devinfra skill before overwrite; move any unique product tips into
  AGENTS or a short local doc if still needed (prefer shared skill as SoT).
- **[Risk] Later #13 sync overlaps manual A** → Mitigation: pin SHA; synced path
  list matches #366 / Devinfra; do not hand-edit synced paths after merge.
- **[Risk] Sibling repos lag (F1)** → Mitigation: updated decision matrix on
  #366/#93/#167; copy same SHA after pilot.

## Migration Plan

1. Pin Devinfra SHA; copy allowlisted Wave A paths (incl. surface-bar `.global`
   and `arctrl`) + thin Auth-B.
2. Add local `docs/surface-quality-bar.md`; apply P3 on principles; update
   AGENTS; remove scan-secrets; minimal lint excludes.
3. Verify `uv run --project scripts/ai m42-ai --help` / `auth-status`.
4. Smoke `/review-fixer` on one PR; brief create/issue-fixer entry checks.
5. Merge pilot; siblings reuse matrix + SHA (out of this change).

Rollback: revert the adopt PR (synced paths return to prior forks; re-prompt
tokens if store format changed).
