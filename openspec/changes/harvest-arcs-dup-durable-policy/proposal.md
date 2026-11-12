# Proposal

## Why

`ApiClient.harvest_arcs()` already skips later ARCs that reuse an identifier inside one batch and merges those
client-collected `DUPLICATE` errors into `HarvestResult.errors`. That behaviour was framed as a temporary compatibility
shim pending #566. Product lock-in keeps the skip (#565 closed will-not-do for reclassifying identical-content retries;
removing the skip would drop same-content in-batch duplicates from the error list). Specs, docstrings, and AGENTS.md
still point at shim removal — wording must match the durable client policy.

## What Changes

- Treat intra-batch duplicate-identifier detection / skip / client `DUPLICATE` recording as durable `harvest-client`
  policy (not “temporary until #566”)
- Keep merge of client-collected item errors with server-persisted harvest `errors` as durable client behaviour for
  modes the server never sees (skipped duplicate POSTs)
- Replace “Compatibility shim (#566)” / “until shim removal” comments in `api_client` / models and the AGENTS.md
  harvest-client blurb
- **No** runtime behaviour change; existing unit tests for skip + `DUPLICATE` stay

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `harvest-client`: Rephrase duplicate-identifier and client/server error-merge requirements so they describe durable
  client policy instead of a temporary shim pending server coverage / #566

## Impact

- `openspec/specs/harvest-client/` (via this change’s delta, then archive sync)
- `middleware/api_client/src/middleware/api_client/api_client.py`, `models.py` (comments/docstrings only)
- `AGENTS.md` harvest-client blurb
- Related history: #240 (persist server errors), #565 (retry-200 kept), #566 (shim removal superseded by #650)
