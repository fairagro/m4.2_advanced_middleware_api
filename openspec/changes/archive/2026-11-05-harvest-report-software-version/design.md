# Design

## Context

See `proposal.md`. `HarvestReport` is a mutable accumulator; `JsonLdReportSerializer` emits a `schema:Action` with
repository `EntryPoint`s under vocabulary v2. Lock-in: nested `schema:instrument` (A); optional in shared / product
fail-closed (H); mini helper with explicit distribution name (M).

## Goals / Non-Goals

**Goals:**

- Caller-visible optional `software_version` on the report.
- Additive JSON-LD instrument node when set.
- Reusable `read_distribution_version(name) -> str | None` without product package defaults.

**Non-Goals:**

- Enforcing version in `finish()` / `render`.
- Consumer product wiring; fairagro vocab new terms; HTTP API version (#588).

## Decisions

1. **Field name `software_version`** — Matches schema.org `softwareVersion` semantics and Jorge’s #508 proposal.
   Alternative `tool_version` — rejected as less aligned with the wire term.

2. **Ctor kwarg + mutable attribute** — `HarvestReport(..., software_version: str | None = None)` and allow assignment
   before finish. Reason: set-at-start pattern; tests can omit. No separate setter required unless clarity needs it.

3. **Omit vs empty string** — Treat only non-`None` non-empty strings as “set”; empty string SHOULD be normalized to
   unset or rejected with `ValueError` at set time (prefer reject empty to avoid silent omit bugs).

4. **Helper module** — e.g. `middleware.shared.report.distribution_version.read_distribution_version`. Uses
   `importlib.metadata.version`; `PackageNotFoundError` → `None`. No pyproject filesystem fallback (products own release
   stamps; local missing metadata is intentional under H).

5. **JSON-LD shape** — When set:

   ```json
   "schema:instrument": {
     "@type": "schema:SoftwareApplication",
     "schema:softwareVersion": "<pep440>"
   }
   ```

   No `name` required in MVP. Reason: schema.org-correct nesting; additive; no v3 vocab path.

6. **Spec SHOULD for production** — Document in harvest-report requirements; enforcement in Harvester/SQL-to-ARC issues.

## Risks / Trade-offs

- **[Risk] Products forget to set version in release images** → Mitigate in #508/#287 with fail-closed start checks.
- **[Trade-off] No shared pyproject fallback** → Local editable installs may get `None` from the helper; acceptable
  under H; callers may still pass an explicit env stamp.

## Migration Plan

- Publish shared with additive API; existing callers unchanged.
- Consumers adopt helper + set field; remove any product-local instrument subclass after that.
