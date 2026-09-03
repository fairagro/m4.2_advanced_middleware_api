# AI Agent Workflow

This document describes how AI coding agents (GitHub Copilot, Cursor, Claude
Code, etc.) are integrated into this project and how the supporting artifacts
are structured.

---

## Overview

The workflow is built on these open standards and tools:

| Standard / tool | Purpose | URL |
| --------------- | ------- | --- |
| **agents.md** | Central entry point — project context at startup | <https://agents.md/> |
| **OpenSpec** | Spec-driven development — living specs + change proposals | <https://openspec.dev/> |
| **Agent Skills** | On-demand procedural knowledge | <https://agentskills.io/> |

---

## VS Code / Cursor Integration

| Artifact | Mechanism |
| -------- | --------- |
| `AGENTS.md` | Loaded as an instructions file. |
| `.agents/skills/*/SKILL.md` | Project skills (arctrl, config-wrapper, review-fixer, gh, scan-secrets); loaded on demand. |
| `.cursor/skills/openspec-*/` | OpenSpec skills for Cursor (`openspec update`). |
| `.github/skills/openspec-*/` | OpenSpec skills for GitHub Copilot. |
| `.cursor/commands/opsx-*.md` / `.github/prompts/opsx-*.prompt.md` | OpenSpec slash commands (`/opsx-propose`, …). |
| `.cursor/commands/review-fixer.md` / `.github/prompts/review-fixer.prompt.md` | Triage Copilot/Bugbot PR comments. |
| `.github/copilot-instructions.md` / `.cursor/BUGBOT.md` | Entry points → `docs/ai_review_policy.md`. |
| `docs/ai_review_policy.md` | Finder + fixer policy (single source). |
| `openspec/specs/**/*.md` | Not auto-loaded — agents follow links from `AGENTS.md`. |

Restart the IDE after `openspec init` / `openspec update` so new commands appear.

### Why multiple `skills/` directories?

OpenSpec installs **tool-native** skill paths so each assistant discovers them
without extra config ([supported tools](https://github.com/Fission-AI/OpenSpec/blob/main/docs/supported-tools.md)):

- Cursor → `.cursor/skills/openspec-*/`
- GitHub Copilot → `.github/skills/openspec-*/`
- Project library skills (not OpenSpec) → `.agents/skills/`

Do **not** merge the generated OpenSpec skills into `.agents/skills/` —
`openspec update` would rewrite the tool paths and discovery would break.
Keep both: project skills in `.agents/skills/`, OpenSpec-generated skills in
the tool directories.

---

## OpenSpec Loop

```text
/opsx-explore  →  /opsx-propose  →  /opsx-apply  →  /opsx-archive
   (optional)         plan              code           merge specs
```

| Path | Role |
| ---- | ---- |
| `openspec/specs/<domain>/` | Source of truth for **current** behaviour (`spec.md`, optional companion `design.md`) |
| `openspec/changes/<name>/` | Active proposal: `proposal.md`, delta `specs/`, `design.md`, `tasks.md` |
| `openspec/principles.md` | Foundation contract (not a capability domain) |
| `openspec/config.yaml` | Project context, artifact rules, apply/archive guidance |

Validate with:

```bash
openspec validate --specs --strict
openspec list
```

Project conventions (domain naming, Spec-to-Code Mapping, uv/ruff/pytest) live
in `openspec/config.yaml` and `AGENTS.md` — use the official `/opsx-*` commands.

---

## Entry Point: `AGENTS.md`

[`AGENTS.md`](../AGENTS.md) is the single entry point for agents. It links to
`openspec/principles.md` and capability specs instead of duplicating them.

---

## Spec Layout

```text
openspec/
├── principles.md
├── config.yaml
├── specs/
│   ├── arc-manager/
│   ├── arc-store/
│   ├── document-store/
│   ├── harvest-manager/
│   ├── arc-upload/
│   ├── harvest-arc-upload/
│   ├── admission-control/
│   ├── harvest-client/
│   └── ci-cd/
└── changes/
    └── archive/
```

Domains are flat under `openspec/specs/` (kebab-case). Spec-to-code mapping
lives in `AGENTS.md`.

### spec.md vs design.md

- **`spec.md`** — Purpose + Requirements (`SHALL`/`MUST`) + Scenarios
  (GIVEN/WHEN/THEN).
- **`design.md`** — Key Decisions (current state + reasoning). Companion files
  under `openspec/specs/<domain>/` hold stable architecture; change folders hold
  delta design.

---

## Agent Skills

```text
.agents/skills/          # Project skills (arctrl, config-wrapper, review-fixer,
                         # plus vendor gh + scan-secrets via `gh skill install`)
.cursor/skills/          # OpenSpec → Cursor (do not hand-edit; openspec update)
.github/skills/          # OpenSpec → Copilot (do not hand-edit; openspec update)
```

Vendor skills (`gh`, `scan-secrets`) are installed at **project** scope into
`.agents/skills/` (shared by Cursor and Copilot). Refresh with
`gh skill update`. Do not hand-edit them. CLI auth still uses the TTY prompt
and `/commandhistory/tokens.env` — not `gh auth login` / `ggshield auth login`
into ephemeral `~/.config` inside the Dev Container.

### AI pull-request reviews

Copilot and Bugbot are **finders** (high recall). `/review-fixer` is the
**fixer** (policy). Re-reviews stay enabled so late risk findings are not
dropped; nits are capped by the nit-budget in
[`docs/ai_review_policy.md`](ai_review_policy.md). Merge when risk threads
are gone, not when AI comments are zero.

```text
Finder comments on the PR
        ↓
/review-fixer  →  fix | dismiss | one follow-up issue
        ↓
push, allow another finder pass (risk channel only must be clean)
```

---

## Workflow in Practice

1. Load `AGENTS.md` → stack, commands, spec links.
2. Read `openspec/principles.md` and the relevant `openspec/specs/<domain>/`.
3. For new behaviour: `/opsx-propose` → review → `/opsx-apply` → `/opsx-archive`.
4. After editing code: `uv run ruff format middleware/` and focused
   `uv run pytest`.
5. After Copilot/Bugbot comments: `/review-fixer` (do not implement every nit).

### Example: Modifying ARC ingestion

1. `AGENTS.md` → `openspec/specs/arc-manager/`.
2. Read `spec.md` / `design.md`.
3. Propose a change or update the main spec, then implement via `/opsx-apply`.
4. Edit `arc_manager.py`, format, test.

### Example: Adding a Config field

1. Read `openspec/principles.md` (ConfigWrapper rules).
2. Load the `config-wrapper` skill.
3. Edit `config.py`, format, test.

---

## Adding New Skills or Specs

### New Skill

Use `/create-skill` in Copilot Chat or create `.agents/skills/<name>/SKILL.md`
manually. Keep skills project-neutral where possible; project constraints belong
in OpenSpec specs or `openspec/config.yaml`.

### New capability / behaviour change

> `/opsx-propose add-api-rate-limiting`

After archive, add the domain to the Spec-to-Code Mapping in `AGENTS.md` if it
is new.
