# Tasks

## 1. Payload + dispatch

- [ ] 1.1 Change `ArcSyncTask.arc` to a JSON string type; update builders at Celery dispatch to serialize once
- [ ] 1.2 Update `sync_to_gitlab` / worker path to use the string with `ARC.from_rocrate_json_string` (no dict
      `json.dumps`)

## 2. Specs & tests

- [ ] 2.1 Keep OpenSpec delta aligned; note hard-cut deploy/drain in design (already in change design)
- [ ] 2.2 Update unit tests for task payload and sync path (string in, no double dumps)
- [ ] 2.3 Run focused pytest + ruff on touched files
