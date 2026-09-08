# Surface quality bar — path map (product overlay)

Product-local **path→surface** map for Finder/Fixer triage. Use **this table
first** when a path matches; otherwise fall back to
[`docs/surface-quality-bar.global.md`](surface-quality-bar.global.md). Rules
(how the bar affects step 5 / nits / dismiss) stay in
[`docs/ai_review_policy.md`](ai_review_policy.md).

Do not hand-edit the synced `.global.md`. Sync of `.global.md` must not
overwrite this file.

## Model (this repo)

Quality is driven by **who can hurt whom**, not by “is it under `middleware/`”.

1. **User-facing contracts** — anything an operator or client library user
   supplies or relies on as the product boundary: HTTP API, config file /
   config model, public PyPI client API, user-invoked CLIs. Highest bar:
   wrong or hostile input must fail safely with **clear errors**; no silent
   corruption; authz / ownership / idempotency hold.
2. **Supporting domain + third-party I/O** — code only reached through (1),
   including CouchDB, Git/GitLab, RabbitMQ/Celery. It must **not undermine**
   user-facing robustness (propagate or map errors; keep contracts). Toward
   third parties, apply **similar care** as user-facing (retries/idempotency,
   explicit failure, no clobber on races) on realistic paths. Everything else
   on this surface: **documented happy path only** — exotic edges → dismiss.
3. **Global rows** (scripts, agent plumbing, docs, vendor skills) — unchanged;
   see `.global.md`.

## Path map

| Surface | Typical paths | Bar (what must work) | Default for exotic edge cases |
| ------- | ------------- | -------------------- | ----------------------------- |
| **User-facing contracts** | `middleware/api/.../api/v3/` (e.g. arcs, harvests, system); request/response models on those routes; operator config (`Config` / `ConfigWrapper`, `dev_environment/config.yaml` and env overrides); public `middleware/api_client` API (`ApiClient`, `Config`, exported models); product CLIs operators run by design | **Full boundary:** valid and invalid / partial input; meaningful error responses or exit codes; no silent data loss; security and ownership; tests for failure modes callers hit | **Fix** when correct and in this PR |
| **Supporting domain + third-party I/O** | `business_logic/`, `document_store/`, `arc_store/`, Celery workers/tasks, `middleware/shared` used by the API or client, other `middleware/*/src/` not in the row above | **Uphold** user-facing contracts (errors, idempotency, types). **Third-party care** on CouchDB / Git / GitLab / RabbitMQ realistic paths (same seriousness as user-facing for integrity and failure signaling). **Otherwise** only the documented happy path | **Dismiss** exotic edges that do not threaten a user-facing contract or third-party integrity (practicality Low / None). Still **fix** when a default caller or DB/Git path is wrong |

When a file sits under both ideas, pick the **stricter** surface (usually
user-facing if it shapes HTTP/config/client errors).

## Out of scope here

Agent CLI (`scripts/ai/`), synced Devinfra scripts, vendor skills, and pure
docs/OpenSpec cadence stay on the **global** rows — do not restate them unless
this product needs a different bar for a path the global table mis-classifies.
