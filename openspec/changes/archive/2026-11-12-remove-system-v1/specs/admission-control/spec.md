# Spec Delta

## MODIFIED Requirements

### Requirement: Exempt probes and cover all other routes

The limiter SHALL exempt liveness, readiness, health, and version probe paths (`/v3/liveness`, `/v3/readiness`,
`/v3/health`, `/v3/version`, and legacy `/v2/health` where still registered), which MUST neither consume a slot nor
receive a limiter-generated `503`. Exemption MUST apply to both `GET` and `HEAD` on those paths. It MUST apply to every
other HTTP method and API version, including ARC upload POSTs. Paths under `/v1/` are not exempt (no `/v1` system routes
remain registered).

#### Scenario: Serve a probe at capacity

- **GIVEN** the process is at capacity
- **WHEN** a request targets an exempt probe path
- **THEN** it is handled normally without consuming a slot

#### Scenario: Serve version at capacity

- **GIVEN** the process is at capacity
- **WHEN** a client sends `GET` or `HEAD` `/v3/version`
- **THEN** the request is handled normally without consuming a slot

#### Scenario: Limit ARC upload traffic

- **GIVEN** the process is at capacity
- **WHEN** an ARC upload POST arrives
- **THEN** it receives the admission `503`

#### Scenario: Do not exempt removed v1 health

- **GIVEN** the process is at capacity
- **WHEN** a client sends `GET` or `HEAD` `/v1/health`
- **THEN** the request is subject to admission control (no probe exemption for `/v1`)
