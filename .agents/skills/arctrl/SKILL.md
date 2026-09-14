---
name: arctrl
description: >
  Reference for using the arctrl Python library (v3.2+) to build ARC (Annotated
  Research Context) objects and serialize them to RO-Crate JSON-LD. Use when
  working with ArcInvestigation, ArcStudy, ArcAssay, ArcTable, CompositeHeader,
  CompositeCell, OntologyAnnotation, OntologySourceReference, Person, or
  Publication objects, or when calling ToROCrateJsonString / WriteAsync,
  GetWriteContracts, GetAdditionalPayload, or supplementary ARC files.
compatibility: Python 3.12+, arctrl >= 3.2.1 (Fable-transpiled F# library)
---

# ARCtrl — Usage Reference

ARCtrl is a Fable-transpiled F# library — the Python surface is idiomatic but some internals are Fable runtime types.

**Casing rule (arctrl 3.2+):** constructor / factory kwargs are usually `snake_case` (`first_name=…`, `name=…`);
**instance properties** on ARC / Person / Investigation stay mostly **PascalCase** (`FirstName`, `Identifier`,
`Contacts`). Exception: each entry in `ArcTable.Columns` exposes **lowercase** `header` and `cells` (not `Header` /
`Cells`).

---

## Package & Imports

arctrl ships no `py.typed` marker. Fleet typing uses **shared incomplete stubs** under
[`stubs/arctrl/`](../../../stubs/arctrl/) and [`stubs/fable_library/`](../../../stubs/fable_library/) (synced from
Devinfra — see [`stubs/README.md`](../../../stubs/README.md)).

- Put `stubs` on **`MYPYPATH`** in hooks/CI (e.g. `MYPYPATH=stubs:…`).
- Basedpyright / Pylance: synced `pyrightconfig.json` already sets `stubPath: "stubs"`.
- Do **not** add `[mypy-arctrl*]` / fable overrides to synced `mypy.ini`, and do **not** keep
  `# type: ignore[import-untyped]` on arctrl / fable_library imports once stubs are synced.
- Other one-off untyped libs (few call sites) may still use a per-import ignore; do not invent stub packages for those.

```python
from fable_library.async_ import start_as_task
from arctrl.py.Core.Table.composite_cell import Data
```

---

```python
from arctrl import (
    ARC,
    ArcAssay,
    ArcInvestigation,
    ArcStudy,
    ArcTable,
    CompositeCell,
    CompositeHeader,
    IOType,
    OntologyAnnotation,
    Person,
    Publication,
)

# Not re-exported from top-level arctrl (3.2+):
from arctrl.py.Core.ontology_source_reference import OntologySourceReference

# Async helpers live in the standalone fable_library package (not under arctrl.py):
from fable_library.async_ import start_as_task
```

---

## Core Objects

### OntologyAnnotation

```python
# Empty / unknown
oa = OntologyAnnotation()

# With values — constructor kwargs are snake_case; read-back uses .Name:
oa = OntologyAnnotation(
    name="soil texture",  # human-readable term
    tan="http://purl.obolibrary.org/obo/ENVO_00002001",  # TermAccessionNumber (URI)
    tsr="ENVO",  # TermSourceREF: short name of the ontology source
)
assert oa.Name == "soil texture"
# tsr is a back-reference to an OntologySourceReference registered on the
# investigation (by its .Name). If no OntologySourceReference is registered,
# tsr can be left empty or omitted.
```

### OntologySourceReference

Registered on `ArcInvestigation.OntologySourceReferences`. Describes an ontology source and holds its version.

```python
from arctrl.py.Core.ontology_source_reference import OntologySourceReference

osr = OntologySourceReference(
    name="ENVO",  # short name — must match OntologyAnnotation tsr kwarg
    description="Environment Ontology",
    file="http://purl.obolibrary.org/obo/envo.owl",
    version="2024-01-01",  # ontology version / access date
)
# or: OntologySourceReference.create(name=..., file=..., version=..., description=...)
investigation.OntologySourceReferences.append(osr)
assert osr.Name == "ENVO"
```

**Relationship:** the `tsr=` constructor argument is a string key that references `OntologySourceReference.Name`. ARCtrl
does not enforce referential integrity at runtime, but the RO-Crate serialization will include both objects.

### ArcInvestigation

```python
inv = ArcInvestigation.create(
    identifier="inv001",  # required, must be non-empty
    title="My Investigation",
    description="...",
    submission_date="2024-01-15",  # ISO string or None
    public_release_date="2025-01-01",
)
```

### ArcStudy

```python
study = ArcStudy.create(
    identifier="study001",
    title="My Study",
    description="...",
    submission_date=None,
    public_release_date=None,
)
```

### ArcAssay

```python
assay = ArcAssay.create(
    identifier="assay001",
    measurement_type=OntologyAnnotation("soil metagenome", "http://...", ""),
    technology_type=OntologyAnnotation("nucleotide sequencing", "http://...", ""),
    technology_platform=OntologyAnnotation("Illumina", None, None),
    # technology_platform=None is fine if unknown
)
```

### Person

Constructor kwargs are `snake_case`; properties are PascalCase:

```python
person = Person(
    last_name="Doe",
    first_name="John",
    mid_initials="A",
    email="j.doe@example.com",
    phone="+49 123 456789",
    fax=None,
    address="Somewhere",
    affiliation="UFZ",
    roles=[OntologyAnnotation("author", "http://...", "")],
)
# Read-back:
assert person.FirstName == "John"
assert person.LastName == "Doe"
person.Roles.append(OntologyAnnotation(name="author"))
person.Comments.append(...)  # if needed
```

Do **not** pass `FirstName=` / `LastName=` to the constructor — those kwargs are rejected
(`unexpected keyword argument`).

### Publication

```python
pub = Publication(
    doi="10.1234/example",
    pub_med_id="12345678",
    authors="Doe J, Smith A",
    title="Paper title",
    status=OntologyAnnotation("published", "http://...", ""),
)
# Properties: pub.DOI, pub.Title, pub.Authors, …
```

### Comment

```python
from arctrl import Comment

c = Comment.create("Keywords", "alpha, beta")
assert c.Name == "Keywords"
assert c.Value == "alpha, beta"  # not .Text / .text
```

---

## Building an ARC

```python
# 1. Wrap investigation
arc = ARC.from_arc_investigation(inv)

# 2. Add studies (registers them in the investigation)
arc.AddRegisteredStudy(study)

# 3. Add assays
arc.AddAssay(assay)

# 4. Link assay → study
study.RegisterAssay(assay.Identifier)  # pass the string identifier

# 5. Attach contacts
arc.Contacts.append(person)  # investigation-level
study.Contacts.append(person)  # study-level
assay.Performers.append(person)  # assay-level

# 6. Attach publications
arc.Publications.append(pub)  # investigation-level
study.Publications.append(pub)  # study-level

# 7. Serialize to RO-Crate JSON-LD string
json_str: str = arc.ToROCrateJsonString()
```

---

## ArcTable (Annotation Tables)

```python
# Create table
table = ArcTable.init("my-table-name")

# Build headers
header_input = CompositeHeader.input(IOType.of_string("Source Name"))
header_output = CompositeHeader.output(IOType.of_string("Sample Name"))
header_char = CompositeHeader.characteristic(OntologyAnnotation("pH", "", ""))
header_factor = CompositeHeader.factor(OntologyAnnotation("temperature", "", ""))
header_param = CompositeHeader.parameter(OntologyAnnotation("extraction", "", ""))
header_comp = CompositeHeader.component(OntologyAnnotation("reagent", "", ""))
header_cmt = CompositeHeader.comment("My comment label")
header_perf = CompositeHeader.performer  # property, not callable
header_date = CompositeHeader.date  # property, not callable
# Fallback for unknown/simple header names:
header_any = CompositeHeader.OfHeaderString("SomeColumnName")

# IOType canonical strings recognised by IOType.of_string() (maps to named tags 0-3):
# "Source Name" / "Source"  → tag 0 (Source)
# "Sample Name" / "Sample"  → tag 1 (Sample)
# "Data" / "RawDataFile" / "Raw Data File" / "DerivedDataFile" /
# "Derived Data File" / "ImageFile" / "Image File"  → tag 2 (Data)
# "Material"                → tag 3 (Material)
# Any other string          → tag 4 (FreeType — avoid for strict ISA compliance;
#                             valid for domain-specific types, e.g. IOType.of_string("URI")
#                             for URL output columns — produces @type "URI" in RO-Crate)
# NOTE: IOType.data() must NOT be used with free_text cells — WriteAsync raises
#       "Not a Data Cell." at serialisation time. Use IOType.of_string("URI") instead.

# Build cells
cell_text = CompositeCell.free_text("some value")
cell_term = CompositeCell.term(OntologyAnnotation("sandy loam", "http://...", ""))
cell_unitized = CompositeCell.unitized("6.8", OntologyAnnotation("pH", "http://...", ""))
cell_empty = CompositeCell.free_text("")

# Add column (header + matching cell list)
table.AddColumn(header_char, [cell_term, cell_term, cell_empty])

# Check whether a header expects a term cell
if header.IsTermColumn:
    cell = CompositeCell.term(OntologyAnnotation(str(value), "", ""))
else:
    cell = CompositeCell.free_text(str(value))

# Attach table to study or assay
study.AddTable(table)
assay.AddTable(table)

# Read columns back (arctrl 3.2+): use Columns with lowercase header/cells
for col in table.Columns:
    header = col.header  # NOT col.Header
    cells = col.cells  # NOT col.Cells
    if header.IsTermColumn:
        term_name = cells[0].AsTerm.Name
    else:
        text = cells[0].AsFreeText

# table.Headers still exists (PascalCase list of CompositeHeader), but
# cell values live on Columns[i].cells.
```

---

## Reading Back / Deserializing

```python
# From RO-Crate JSON-LD string
arc = ARC.from_rocrate_json_string(json_str)

# Async write to directory (creates ISA file structure on disk)
await start_as_task(arc.WriteAsync("/path/to/output/dir"))
```

---

## WriteContracts vs RO-Crate Serialization (two separate pipelines)

ARCtrl maintains **two independent paths** from an `ARC` object:

```text
ARC object
  ├─► GetWriteContracts() ──► full_fill_contract_batch_async() ──► files on disk
  └─► ToROCrateJsonString() ──► ROCrate_encoder(arc, license, fs) ──► JSON-LD @graph
```

**WriteContracts do not affect `ToROCrateJsonString()`.** Manually created contracts appended to a contract list change
neither the in-memory ARC state nor the serialized RO-Crate JSON.

`GetWriteContracts()` generates contracts only for the ISA scaffold: investigation/study/assay xlsx files, datamaps,
license, and `.gitkeep` placeholders. It does **not** include supplementary files added via `AddFile()`.

To write supplementary file **content** to disk without ARCtrl changes, create a contract manually and fulfill it (after
or alongside ISA contracts):

```python
from arctrl.py.Contract.contract import Contract, DTO, DTOType
from arctrl.py.ContractIO.contract_io import full_fill_contract_batch_async
from fable_library.async_ import run_synchronously

arc_dir = "/path/to/output/dir"
manual = Contract.create_create(
    "iso19115.xml",
    DTOType(10),  # PlainText
    DTO(1, "<xml>...</xml>"),
)
contracts = list(arc.GetWriteContracts()) + [manual]
run_synchronously(full_fill_contract_batch_async(False, arc_dir, contracts))
```

`full_fill_contract_batch_async` signature (arctrl 3.1+): `(force_overwrite: bool, base_path: str, contracts)`.

`WriteAsync()` / `TryWriteAsync()` call `GetWriteContracts()` internally — they write only the ISA scaffold, not
`AddFile()` supplementary paths.

---

## Supplementary Files (`AddFile`, `GetAdditionalPayload`)

Register a path in the ARC filesystem tree (metadata only — no content API on `AddFile` itself):

```python
arc.FileSystem = arc.FileSystem.AddFile("iso19115.xml")
```

| Mechanism                           | Supplementary `AddFile()` path  |
| ----------------------------------- | ------------------------------- |
| `FileSystem.Tree` / `ToFilePaths()` | ✓ path listed                   |
| `GetAdditionalPayload()`            | ✓ path listed                   |
| `GetWriteContracts()`               | ✗ not included                  |
| `WriteAsync()`                      | ✗ file not written              |
| `ToROCrateJsonString()` `@graph`    | ✗ no `File` entity (arctrl 3.1) |
| ISA xlsx files (`isa.*.xlsx`)       | ✗ unchanged                     |

`GetAdditionalPayload()` returns a `FileSystemTree` of paths present in `FileSystem` but **not** part of the registered
ISA payload (`GetRegisteredPayload()`). It lists paths only — not file bytes.

`UpdateFileSystem()` rebuilds the ISA folder tree and unions it with the existing `FileSystem`; it does not create write
contracts for supplementary files.

**Implication for upload pipelines:** `ToROCrateJsonString()` alone cannot transport supplementary file content to a
remote API. Pass file bytes in a separate payload and write them on the server after `WriteAsync()`, or embed content in
ISA-modeled fields (see below).

To reference a file in RO-Crate **metadata** (still without content), an ISA table `Output [URI]` column can produce a
`URI=filename` node in `@graph` — distinct from `@type: File` and still without embedded bytes.

---

## In-memory vs on-disk vs RO-Crate

| Action                           | ISA xlsx on disk | Supplementary file on disk     | In `@graph` after `ToROCrateJsonString()` |
| -------------------------------- | ---------------- | ------------------------------ | ----------------------------------------- |
| `AddFile()` only                 | unchanged        | not written                    | not present                               |
| `AddFile()` + manual `Contract`  | unchanged        | written                        | not present                               |
| `Comment.create(name, text)`     | unchanged        | not written                    | `text` property present                   |
| `SetLicenseFulltext(text, path)` | unchanged        | written (via license contract) | `CreativeWork` with `text`                |

`from_rocrate_json_string()` roundtrip: manually injected `@type: File` nodes may restore a path in `FileSystem` /
`GetAdditionalPayload()`, but custom properties (e.g. embedded `text`) are **not** retained in the ARC object and
disappear on re-serialization. Do not patch RO-Crate JSON to carry file bytes and expect `from_rocrate_json_string()` to
preserve them.

`License` is the only built-in ARC field that feeds **both** `GetWriteContracts()` and `ROCrate_encoder` — usable for
text payload but semantically wrong for arbitrary supplementary files (serializes as `CreativeWork`, not `File`).

---

## Identifiers

- `assay.Identifier` — string property, read-only after creation
- `study.Identifier`
- `arc.Identifier`

---

## Known Pitfalls

**`start_as_task` / `run_synchronously` import path (3.2+)** — use `from fable_library.async_ import …`. The old path
`arctrl.py.fable_modules.fable_library.async_` no longer exists.

**`OntologySourceReference` is not on `from arctrl import …`** — import from `arctrl.py.Core.ontology_source_reference`.

**Ctor kwargs ≠ property names** — `Person(first_name=…)` then `person.FirstName`; never `Person(FirstName=…)`.

**`ArcTable` column fields are lowercase** — `col.header` / `col.cells`. `col.Header` / `col.Cells` raise
`AttributeError` on 3.2+. `table.Headers` and `table.Columns` remain PascalCase.

**`start_as_task` / `fable_library` typing** — covered by shared `stubs/fable_library/` (no per-import ignore once
`MYPYPATH` / `stubPath` include `stubs`).

**`CompositeHeader.performer` and `.date` are properties, not constructors** — call them without `()`:

```python
header = CompositeHeader.performer  # CORRECT
header = CompositeHeader.performer()  # TypeError
```

**`OntologyAnnotation()` without args is valid** — use for empty/unknown terms instead of `None` to avoid null-ref
errors in the F# layer.

**ARC objects carry .NET interop state** — do not pickle or transfer across multiprocessing boundaries. Serialize to
JSON string first.

**`ToROCrateJsonString()` + `gc.collect()`** — after serializing in a worker process, explicitly `del arc` and call
`gc.collect()` to release .NET bridge memory promptly.

**`ArcAssay.create(technology_platform=None)`** — `None` is safe. An empty `OntologyAnnotation()` is also accepted.

**`AddFile()` is not enough for harvest/upload** — registers a path in `FileSystem` and `GetAdditionalPayload()` only.
For disk output, add a manual `Contract.create_create()` or write the file directly. For API upload, send bytes in a
separate `files` payload; do not rely on RO-Crate JSON roundtrip.

**Do not assert supplementary files via `GetWriteContracts()`** — use `FileSystem.Tree.ToFilePaths()` and/or
`GetAdditionalPayload().ToFilePaths()` for path registration; use manual contracts or direct I/O for content.

---

## RO-Crate JSON-LD Output Shape

```json
{
  "@context": { "...": "..." },
  "@graph": [
    { "@id": "inv001", "@type": "Dataset", "identifier": "inv001" },
    { "@id": "study001", "@type": "Dataset" },
    { "@id": "assay001", "@type": "Dataset" },
    { "@id": "#Doe_John", "@type": "Person", "familyName": "Doe" }
  ]
}
```

Test assertion pattern:

```python
import json
graph = json.loads(arc.ToROCrateJsonString()).get("@graph", [])
inv_node = next(item for item in graph if item.get("identifier") == "inv001")
person = next(item for item in graph if item.get("familyName") == "Doe")
```
