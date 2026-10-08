# fairagro-middleware-arc-validation

Run the same ARC validation check DataHUB CI uses (`ghcr.io/nfdi4plants/arc-export`) against client-produced RO-Crate
JSON-LD — without Middleware API, Celery, CouchDB, or GitLab.

## Install

```bash
pip install fairagro-middleware-arc-validation
# or
uv add fairagro-middleware-arc-validation
```

Requires Docker on the host (or CI runner) with permission to pull/run the `arc-export` image.

## Python API

```python
from pathlib import Path
from middleware.arc_validation import validate_rocrate

result = validate_rocrate(Path("fixture.rocrate.json").read_text(encoding="utf-8"))
assert result.ok, result.cause_excerpt
```

Lower-level helpers:

| Symbol                                           | Role                                                   |
| ------------------------------------------------ | ------------------------------------------------------ |
| `write_arc_scaffold(rocrate, out_dir)`           | ARCtrl load + `Write`                                  |
| `run_arc_export(arc_dir, *, image=…, formats=…)` | `docker run … arc-export`                              |
| `validate_rocrate(rocrate, *, image=…)`          | temp dir → write → export → cleanup                    |
| `ArcExportResult`                                | `ok`, `exit_code`, `stdout`, `stderr`, `cause_excerpt` |

## CLI

```bash
fairagro-arc-validate path/to/rocrate.json
# exit 0 = pass; non-zero = fail; short cause on stderr
```

## Image and formats

| Setting | Default                                                |
| ------- | ------------------------------------------------------ |
| Image   | `ghcr.io/nfdi4plants/arc-export:main`                  |
| Formats | `rocrate-metadata-lfs`, `isa-json`, `summary-markdown` |

Override the image for reproducibility (digest tags recommended in CI):

```bash
export FAIRAGRO_ARC_EXPORT_IMAGE='ghcr.io/nfdi4plants/arc-export@sha256:…'
fairagro-arc-validate path/to/rocrate.json
```

Or pass `image=` to `validate_rocrate` / `run_arc_export`. Explicit `image=` wins over the environment variable.

## Pytest tip

```python
from middleware.arc_validation import validate_rocrate


def test_fixture_passes_arc_export(rocrate_json: str) -> None:
    assert validate_rocrate(rocrate_json).ok
```

Live Docker smoke tests are marked `@pytest.mark.requires_docker` and skip unless `FAIRAGRO_ARC_VALIDATE_LIVE=1` (so
default CI / pre-push stay deterministic).
