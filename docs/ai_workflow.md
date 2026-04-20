# AI Agent Workflow

This document describes how AI coding agents (GitHub Copilot, Claude Code, etc.)
are integrated into this project and how the supporting artifacts are structured.

---

## Overview

The workflow is built on three open standards:

| Standard | Purpose | URL |
| -------- | ------- | --- |
| **agents.md** | Central entry point — gives agents project context at startup | <https://agents.md/> |
| **Specifica** | Spec-driven development — machine- and human-readable feature specs | <https://specifica.org> |
| **Agent Skills** | On-demand procedural knowledge — loaded by agents when relevant | <https://agentskills.io/> |

---

## VS Code Integration

GitHub Copilot in VS Code natively supports the artifacts described in this
document. Use **Chat: Open Customizations** (Command Palette `Ctrl+Shift+P`)
to explore and edit all active customization files in one place.

| Artifact | VS Code mechanism |
| -------- | ----------------- |
| `AGENTS.md` | Loaded automatically as an *instructions file* by GitHub Copilot. Shown in **Chat: Open Customizations** under "Instructions". |
| `.agents/skills/*/SKILL.md` | Skill files are listed in **Chat: Open Customizations** under "Skills". The agent sees the frontmatter `description` at startup and loads the full file on demand. |
| `.github/agents/*.agent.md` | Custom agents are listed in the agent picker dropdown. Select an agent to activate its persona, tool set, and instructions. |
| `spec/**/*.md` | Not loaded automatically — agents follow links from `AGENTS.md` and read spec files with file-read tools as needed. |

To verify which files are active, open the Copilot Chat panel, click the
settings icon, and select **Open Customizations**. All discovered instructions
and skill files are listed there.

---

## Custom Agents: `.github/agents/`

Custom agents (see [Custom agents in VS Code](https://code.visualstudio.com/docs/copilot/customization/custom-agents))
combine a fixed persona, a curated tool set, and pre-loaded instructions into a
single, selectable configuration. Unlike skills — which are loaded on demand by
any agent — a custom agent *is* the active agent for the whole conversation.

### `spec-to-code` — Spec-driven implementation

[`.github/agents/spec-to-code.agent.md`](../.github/agents/spec-to-code.agent.md)

This agent's job is to translate Specifica spec changes into matching source
code. Switch to it whenever a `spec.md` or `design.md` was updated and the code
needs to catch up.

**How to use it:**

1. Open Copilot Chat and select **spec-to-code** from the agent dropdown
   (or type `@spec-to-code`).
2. Tell it what changed:

   > The `arc-manager/spec.md` now requires that ARCs without a valid RDI
   > are rejected with a 422 response. Please implement this.

3. The agent reads the spec, finds the affected code and its tests, applies
   the change, runs `ruff format` and `pytest`, and reports which requirements
   were implemented.

**Tool set:** file read/write, codebase search, terminal (for formatter and
tests), Problems tab — no browser, no git push.

**When to use it vs plain Agent mode:**

| Situation | Use |
| --------- | --- |
| Spec changed, code needs to follow | `spec-to-code` |
| Exploratory coding, no spec context needed | default Agent mode |
| Writing a new spec from scratch | default Agent mode + `create-specifica-feature` skill |

---

## Entry Point: `AGENTS.md`

[`AGENTS.md`](../AGENTS.md) at the repository root is the single entry point
for all AI agents. It is automatically loaded by compatible agents (GitHub
Copilot, Claude Code, and others) at the start of every session.

It contains only what every agent needs for every task:

- Tech stack and key versions
- Project structure (with links to `spec/` and component specs)
- Essential commands (`uv`, `ruff`, `pytest`)
- Architecture & Design section — two-level spec index
- Code quality standards and file modification workflow

**Principle:** `AGENTS.md` links to specs instead of duplicating their content.
It stays short and current.

---

## Spec-Driven Development: `spec/` and `middleware/*/spec/`

Specs follow the [Specifica](https://specifica.org) convention: each feature
lives in its own folder with a `spec.md` (what it does) and optionally a
`design.md` (key decisions and rationale).

### Two-Level Layout

```text
spec/                          ← Project-level (cross-cutting concerns)
└── principles.md              # Foundation contract, project values

middleware/
└── api/
    └── spec/                  ← Component-level (api internals)
        ├── arc-manager/       # Two-phase ARC ingest: CouchDB + async GitLab sync
        ├── arc-store/         # ArcStore interface + GitRepo implementation
        ├── document-store/    # CouchDB persistence layer
        └── harvest-manager/    # Harvest run lifecycle and ownership
```

**Project-level specs** cover concerns that cut across components or that don't
belong to any single component (deployment, shared patterns, principles).

**Component-level specs** live next to the code they describe
(`middleware/<component>/spec/`). Each future component gets its own `spec/`
folder. This makes specs portable and keeps context close to the code.

### spec.md vs design.md

- **`spec.md`** — requirements: what the feature must do, acceptance criteria,
  interface contracts. Written before implementation.
- **`design.md`** — decisions: *why* it was built this way, key trade-offs,
  alternatives rejected. Written alongside or after implementation.

---

## Agent Skills: `.agents/skills/`

Skills follow the [Agent Skills](https://agentskills.io/) open standard. Each
skill is a folder containing a `SKILL.md` file with YAML frontmatter and
Markdown instructions.

```text
.agents/
└── skills/
    ├── arctrl/
    │   └── SKILL.md                  # How to use the arctrl Python library
    ├── config-wrapper/
    │   └── SKILL.md                  # How to use ConfigWrapper / ConfigBase
    └── create-specifica-feature/
        └── SKILL.md                  # How to create a new Specifica feature folder
```

Skills are **project-neutral** — they document a library or pattern in general
terms. Project-specific usage (concrete prefixes, mock paths, accepted
trade-offs) lives in the corresponding feature spec, not in the skill.

### How Agents Use Skills

1. **Discovery**: At startup, agents see only the `name` and `description` from
   each skill's frontmatter — just enough to know when a skill might apply.
2. **Activation**: When a task matches a skill's description, the agent loads
   the full `SKILL.md` into context.
3. **Execution**: The agent follows the instructions, optionally loading
   referenced files or scripts.

Skills are activated on demand, keeping the agent's context window lean.

---

## Workflow in Practice

When an agent starts a task it:

1. Loads `AGENTS.md` → gets project context, commands, and spec links.
2. If the task touches a feature → reads the relevant `spec.md` / `design.md`.
3. If the task requires library knowledge → loads the matching skill.
4. After editing → runs `uv run ruff format middleware/` and `uv run pytest`,
   checks the VS Code **Problems** tab for Pylance / Mypy / Ruff diagnostics.

### Example: Modifying the ARC Ingestion Flow

1. `AGENTS.md` links to `middleware/api/spec/arc-manager/`.
2. Agent reads `arc-manager/spec.md` → learns requirements (identifier required,
   CouchDB first, enqueue Celery task only on change).
3. Agent reads `arc-manager/design.md` → understands key decisions (two-phase
   ingest, mode enforcement via dispatcher, idempotency via content hash).
4. Agent edits `arc_manager.py`, formats, runs tests.

### Example: Adding a New Config Field

1. `AGENTS.md` links to `spec/principles.md`.
2. Agent loads the `config-wrapper` skill → learns the exact Pydantic pattern
   and how to write the test.
3. Agent edits `config.py`, formats, and runs the tests.

---

## Adding New Skills or Specs

### New Skill with VS Code and Copilot Chat

VS Code has built-in support for creating and managing skills (see [Use Agent
Skills in VS Code](https://code.visualstudio.com/docs/copilot/customization/agent-skills)).

#### Option A — AI-generated skill (recommended)

Type `/create-skill` in the Copilot Chat input and describe what you need:

> `/create-skill` a skill for the `aiocouch` library covering async document
> CRUD, Mango queries, and conflict handling

Copilot asks clarifying questions and writes the complete
`.agents/skills/aiocouch/SKILL.md` with valid frontmatter and instructions.

#### Option B — Manual creation via the Skills menu

Type `/skills` in the Chat input to open the **Configure Skills** menu directly.
Select **New Skill (Workspace)**, choose a location, and enter a name.
VS Code creates the folder and an empty `SKILL.md` scaffold to fill in.

Rules that apply regardless of creation method:

- `name` must match the folder name; lowercase letters and hyphens only.
- `description` must say both *what* the skill does and *when to use it*.
- Keep the skill **project-neutral** — no FAIRagro-specific paths or prefixes.
  Project-specific constraints belong in the corresponding feature spec.
- Reference the skill from the relevant feature spec so agents know to load it.

### New Feature Spec with `create-specifica-feature`

The `create-specifica-feature` skill guides Copilot through the full process.

**Example prompt** (Copilot Chat, Agent mode):

> Use the `create-specifica-feature` skill to create a new component-level
> spec for an "api-rate-limiting" feature in `middleware/api`. The feature
> limits the number of ARC submissions per client per minute.

Copilot will:

1. Load the `create-specifica-feature` skill.
2. Choose the right location: `middleware/api/spec/api-rate-limiting/`
   (component-level — affects only the api component).
3. Create `spec.md` with a one-sentence purpose, `## Requirements` as
   `- [ ]` checkboxes, and `## Edge Cases` as scenario → outcome pairs.
4. Create `design.md` with a `## Key Decisions` section, each decision
   preceded by a `—` reasoning clause.
5. Add a link to `AGENTS.md` under **Architecture & Design**.

For detailed formatting rules, see
[`.agents/skills/create-specifica-feature/SKILL.md`](../.agents/skills/create-specifica-feature/SKILL.md).
