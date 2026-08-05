# Harvest report vocabulary (v1)

Canonical namespace IRI:

`https://fairagro.github.io/m4.2_advanced_middleware_api/ns/harvest-report/v1/#`

Machine-readable JSON-LD context: [context.jsonld](./context.jsonld)

This vocabulary defines FAIRagro-specific terms used in the shared harvest-run
report (`middleware.shared.report`). Schema.org terms (`Action`, `EntryPoint`,
`startTime`, …) are not redefined here.

## Terms

| Term | Meaning |
| ---- | ------- |
| `harvestDurationSeconds` | Wall-clock duration of the entire harvest run, in seconds |
| `harvestId` | Harvest id returned by the Middleware harvest API (`null` if none) |
| `expectedDatasets` | Expected dataset count for a repository, when known |
| `harvestedDatasets` | Datasets successfully harvested and forwarded to the API |
| `failedDatasets` | Datasets that failed during harvest or upload |
| `skippedDatasets` | Datasets intentionally skipped |
| `failures` | Ordered list of harvest issues (dataset or repository) |
| `kind` | Issue kind: `dataset` or `repository` |
| `message` | Human-readable failure message on an issue |
| `recordId` | Optional source record identifier (dataset issues) |
| `url` | Optional URL related to the issue |
| `totalStudies` | Optional count of studies produced for a repository |
| `totalAssays` | Optional count of assays produced for a repository |

## Versioning

- Path `v1` is the vocabulary **major** version used by the serializer.
- Incompatible changes require a new major path (`v2/`) and a new IRI.
- Compatible additions may update files under `v1/` and be published with a new
  patch/minor tag.

## Publishing

Do **not** enable GitHub Pages from branch `/docs`. Vocabulary publication is
tag-gated:

1. Tag: `ns/harvest-report/v<major>.<minor>.<patch>` (example:
   `ns/harvest-report/v1.0.0`)
2. Workflow [publish-ns-pages.yml](../../../.github/workflows/publish-ns-pages.yml)
   deploys **only** the `ns/` tree to GitHub Pages (Actions source).
3. Repo setting: Pages → Source = **GitHub Actions** (once).

General documentation under `docs/` is not published by this workflow.
