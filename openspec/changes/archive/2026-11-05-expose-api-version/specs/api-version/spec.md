# Spec Delta

## Purpose

Expose the installed middleware-api PEP 440 package version over a dedicated probe-style HTTP path and as an additive
field on the global health response, so operators and clients can read the build identity without scraping OpenAPI.

## ADDED Requirements

### Requirement: Expose package version on GET and HEAD /v3/version

The API SHALL provide `GET /v3/version` and `HEAD /v3/version` that return the PEP 440 version string of the installed
`api` distribution (same source used for the OpenAPI `info.version`). A successful `GET` MUST use status `200` and a
JSON body with a single required field `version` (string). A successful `HEAD` MUST use the same status and response
headers as the corresponding `GET` and MUST NOT include a response body. The handlers MUST NOT perform dependency health
checks. The paths MUST NOT require a client certificate even when write APIs require one.

#### Scenario: GET returns installed version

- **GIVEN** the API process can answer HTTP requests
- **WHEN** a client sends `GET /v3/version` with an acceptable `Accept` header for JSON
- **THEN** the response is `200` with body `{"version": "<pep440>"}` matching the installed `api` package version

#### Scenario: HEAD mirrors GET without a body

- **GIVEN** the API process can answer HTTP requests
- **WHEN** a client sends `HEAD /v3/version`
- **THEN** the response is `200` with no body and headers consistent with a successful `GET` for the same path

#### Scenario: No client certificate required

- **GIVEN** client certificates are required for write APIs
- **WHEN** a client calls `GET /v3/version` without a client certificate
- **THEN** the request is not rejected for missing client authentication

### Requirement: Include version on /v3/health responses

The `/v3/health` JSON response SHALL include a `version` string field with the same PEP 440 value as `/v3/version`. The
field MUST be present for both healthy (`200`) and unhealthy (`503`) responses. Existing `status` and `services`
semantics and status-code rules MUST remain unchanged. Liveness and readiness responses MUST NOT gain a `version` field
as part of this capability.

#### Scenario: Healthy health includes version

- **GIVEN** global health checks all pass
- **WHEN** a client sends `GET /v3/health`
- **THEN** the response is `200` and the JSON includes `version` equal to the `/v3/version` value

#### Scenario: Unhealthy health still includes version

- **GIVEN** at least one global health check fails
- **WHEN** a client sends `GET /v3/health`
- **THEN** the response is `503` and the JSON still includes `version` equal to the `/v3/version` value

#### Scenario: HEAD health retains version semantics without a body

- **GIVEN** the health endpoint is registered for `GET`
- **WHEN** a client sends `HEAD /v3/health`
- **THEN** the response uses the same status the corresponding `GET` would return and has no body
