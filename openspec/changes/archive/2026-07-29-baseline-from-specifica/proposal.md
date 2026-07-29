# Proposal: Baseline seed from Specifica

## Why

The project migrates from Specifica (`spec/` and `middleware/*/spec/`) to
OpenSpec. Existing feature specs already describe implemented behaviour and
must become the initial source of truth under `openspec/specs/`.

## What Changes

- Curated rewrite of all Specifica feature `spec.md` files into OpenSpec
  requirement/scenario form under `openspec/specs/<domain>/`.

- Companion `design.md` files moved alongside capabilities where they existed.
- Project principles relocated to `openspec/principles.md`.
- Specifica directories removed after the seed; AGENTS.md and AI workflow docs
  point at OpenSpec.

## Scope

- **In scope:** documentation and agent-workflow artifacts only.
- **Out of scope:** middleware application code, CI workflow YAML behaviour
  (documented by `ci-cd/` but not changed by this seed).

## Non-goals

- No code behaviour changes.
- No delta merge via `/opsx:archive` — this archive folder is provenance only.
