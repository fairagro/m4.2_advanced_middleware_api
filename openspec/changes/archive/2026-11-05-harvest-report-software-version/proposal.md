# Proposal

## Why

Batch clients (Harvester, SQL-to-ARC) need the PEP 440 tool/image version on every harvest run — in the shared report
model and on the JSON-LD wire — so ops can correlate reports with releases. Today `HarvestReport` has no version field
and the JSON-LD `schema:Action` omits tool identity. Product-local serializer subclasses diverge; the durable contract
belongs in `middleware.shared.report` (#598; consumers #508 / #287).

## What Changes

- Add optional `software_version: str | None` on `HarvestReport` (caller-set; omit on wire when unset).
- Add a small shared helper `read_distribution_version(distribution_name) -> str | None` wrapping `importlib.metadata`
  (`PackageNotFoundError` → `None`).
- Emit nested `schema:instrument` → `schema:SoftwareApplication` with `schema:softwareVersion` from
  `JsonLdReportSerializer` when a version is set (additive schema.org; no harvest-report vocab major bump).
- Spec delta under `harvest-report`: model + JSON-LD requirements; production callers SHOULD set the version
  (fail-closed enforcement stays in product issues).

Non-goals: wiring Harvester / SQL-to-ARC (follow-up issues); requiring version in shared `finish()`/`render` (local
builds without a stamp remain valid); new `fairagro:` vocabulary terms; HTTP `/v3/version` (#588).

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `harvest-report`: optional software version on the run report; JSON-LD `schema:instrument` emission; distribution
  version helper for callers.

## Impact

- Code: `middleware/shared/.../report/model.py`, `formats/jsonld.py`, new small helper module, unit tests.
- Specs: `openspec/specs/harvest-report/`.
- Consumers: Harvester #508, SQL-to-ARC #287 after shared publish.
