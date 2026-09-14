# Shared type stubs (arctrl / fable_library)

Keep third-party silence **out of** synced `mypy.ini` (Devinfra sync overwrites it).

Incomplete stubs here use `__getattr__ -> Any` so imports resolve without listing every symbol. Products MUST append
`stubs` to `MYPYPATH` in hooks/CI; basedpyright uses `stubPath: "stubs"` in synced
[`pyrightconfig.json`](../pyrightconfig.json) ([#64](https://github.com/fairagro/m4.2_middleware_devinfra/issues/64)).

## What belongs where

| Stub / silence                         | Where                                                                                            | Why                                 |
| -------------------------------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------- |
| `arctrl/`, `fable_library/`            | This tree → product sync ([#67](https://github.com/fairagro/m4.2_middleware_devinfra/issues/67)) | Shared across middleware products   |
| `owslib/`, `rdflib/`                   | Product-local only                                                                               | Many import sites / multi-module    |
| One-off libs (`lxml`, `defusedxml`, …) | `# type: ignore[import-untyped]` on the import                                                   | Few call sites — stubs not worth it |

Do **not** use `# type: ignore[import-untyped]` for packages covered by the shared stubs above after sync. Do **not**
patch per-module `[mypy-…]` overrides into synced `mypy.ini`.
