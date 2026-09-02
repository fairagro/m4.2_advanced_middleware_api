# Standalone ARC Upload — Delta

## ADDED Requirements

### Requirement: Reject standalone upload when consolidated Git store is configured

When the deployment’s ArcStore backend is the consolidated Git catalog store,
standalone ARC create endpoints (`POST /v1/arcs`, `POST /v2/arcs`, and
`POST /v3/arcs`) SHALL reject the request with HTTP `400` (or another documented
4xx) before staging content in CouchDB or scheduling Git sync. Harvest-scoped
ARC submission (`POST /v3/harvests/{harvest_id}/arcs`) remains the supported
ingestion path for that backend.

#### Scenario: Standalone ARC rejected under consolidated store

- **GIVEN** `consolidated_git` is the configured ArcStore backend
- **WHEN** a client calls `POST /v1/arcs`, `POST /v2/arcs`, or `POST /v3/arcs`
- **THEN** the API returns HTTP `400` and does not stage or publish catalog
  content for that request
