# Shared Harvest Report — Tasks

## 1. Module skeleton

- [x] 1.1 Create `middleware/shared/src/middleware/shared/report/` package
      (`__init__.py` exports for public API)
- [x] 1.2 Add format-neutral model types: `FailedRecord`, `RepositoryReport`
      (incl. optional study/assay counts), `HarvestReport` (start/end,
      repository list, duration helper)

## 2. Serialization

- [x] 2.1 Add serializer Protocol/ABC under `report/formats/`
- [x] 2.2 Implement JSON-LD serializer (harvester-compatible `@context`,
      Action/EntryPoint, fairagro metrics, omit rules, ISO timestamps/durations,
      optional totalStudies/totalAssays)
- [x] 2.3 Add stdout emit helper that catches serialization/print errors, logs a
      warning, and does not raise

## 3. Tests and docs

- [x] 3.1 Unit tests for model construction and omit/optional field behavior
- [x] 3.2 Unit tests for JSON-LD wire shape (context, types, metrics, failures,
      empty result list)
- [x] 3.3 Unit test that emit helper does not raise on serialization failure
- [x] 3.4 Update `AGENTS.md` Spec-to-Code mapping for `harvest-report`
- [x] 3.5 Run `uv run pytest middleware/shared/tests/` and
      `uv run ruff format/check` on touched code

## 4. Versioned vocabulary and tag-gated publish

- [x] 4.1 Add `ns/harvest-report/v1/context.jsonld` defining all emitted
      `fairagro:` terms (`@id` under the versioned Pages IRI, `@type` where
      applicable)
- [x] 4.2 Add `ns/harvest-report/v1/README.md` (term descriptions, canonical
      IRI, tag/publish notes) and optional `index.html` for browser resolution
- [x] 4.3 Point `JsonLdReportSerializer` `fairagro` prefix at
      `https://fairagro.github.io/m4.2_advanced_middleware_api/ns/harvest-report/v1/#`
- [x] 4.4 Add GitHub Actions workflow: on tags `ns/harvest-report/v*`, publish
      only `ns/` to GitHub Pages (Actions source—not branch `/docs`)
- [x] 4.5 Update unit tests for the versioned namespace IRI
- [x] 4.6 Run `uv run pytest middleware/shared/tests/` and ruff on touched code
