# Tasks

## 1. Model and helper

- [x] 1.1 Add optional `software_version` on `HarvestReport` (ctor + readable attribute; reject empty string); verify
      existing report unit tests still pass without setting it
- [x] 1.2 Add `read_distribution_version(distribution_name: str) -> str | None` and export from `report` package; verify
      unit tests for installed vs missing distribution names

## 2. JSON-LD and spec-facing tests

- [x] 2.1 Emit `schema:instrument` / `SoftwareApplication` / `softwareVersion` when version is set; omit when unset;
      verify JSON-LD unit tests for both cases
- [x] 2.2 Confirm no harvest-report v2 vocabulary file changes are required (schema.org only); verify README still
      accurate (optional one-line note that tool version uses schema.org `instrument`)

## 3. Package surface

- [x] 3.1 Export new helper (and document in package `__all__` if used); verify imports from `middleware.shared.report`
      work in unit tests
