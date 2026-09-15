## Purpose

Defines how the product Helm chart optionally exposes the API via a Gateway API
`HTTPRoute` attached to a platform-owned parent (for example a shared `ListenerSet`),
while Ingress remains independently available during the mTLS transition.

## ADDED Requirements

### Requirement: Optional HTTPRoute rendering

The chart SHALL render a Gateway API `HTTPRoute` only when the HTTPRoute feature is
explicitly enabled in values. When disabled, the chart MUST NOT emit an `HTTPRoute`
resource.

#### Scenario: Disabled by default

- **GIVEN** chart default values with HTTPRoute disabled
- **WHEN** the chart is rendered
- **THEN** no `HTTPRoute` manifest is produced

#### Scenario: Enabled with required fields

- **GIVEN** HTTPRoute is enabled with at least one parent reference, hostname, and a
  backend Service port
- **WHEN** the chart is rendered
- **THEN** an `HTTPRoute` is produced that references those parents and hostnames and
  routes HTTP traffic to the chart’s API Service on the configured port

### Requirement: Cluster-agnostic parentRefs and hostnames

Chart default values MUST NOT hardcode cluster inventory names (for example elise, fizz,
draven, or gangplank). Deploy overlays SHALL supply `parentRefs` and `hostnames`
appropriate to the target cluster. Default chart values MAY document an example shape
suitable for a shared `ListenerSet` named `fairagro-https` in namespace
`kube-gateway-api` without making that configuration active by default.

#### Scenario: Overlay supplies parentRefs

- **GIVEN** an overlay that sets `parentRefs` to a platform `ListenerSet` and sets
  hostnames for the API
- **WHEN** the chart is rendered with that overlay
- **THEN** the `HTTPRoute` `parentRefs` and `hostnames` match the overlay values

### Requirement: Dual-path with Ingress

Enabling HTTPRoute MUST NOT require disabling Ingress. Ingress and HTTPRoute SHALL be
independently feature-flagged. This change MUST NOT remove the existing Ingress template.

#### Scenario: Both paths enabled

- **GIVEN** Ingress and HTTPRoute are both enabled in values
- **WHEN** the chart is rendered
- **THEN** both an Ingress and an `HTTPRoute` manifest are produced

#### Scenario: Ingress-only remains valid

- **GIVEN** Ingress is enabled and HTTPRoute is disabled
- **WHEN** the chart is rendered
- **THEN** only Ingress exposure is produced (no `HTTPRoute`)

### Requirement: No chart-owned public hostname certificate

The chart MUST NOT create a `Certificate` (or equivalent chart-owned TLS issuer resource)
for the platform public hostname pattern served by the shared ListenerSet (for example
`*.fairagro.net`). Server TLS for that path remains platform-owned.

#### Scenario: HTTPRoute without Certificate

- **GIVEN** HTTPRoute is enabled for a public hostname
- **WHEN** the chart is rendered
- **THEN** no chart-owned `Certificate` for that public hostname is produced

### Requirement: Document dual-path and deploy constraints

Operator-facing documentation (Helm chart NOTES and helmchart docs) SHALL describe:

1. Dual-path exposure: Ingress may provide client mTLS today; HTTPRoute attaches to
   platform Gateway TLS.
2. That client mTLS cutover to Gateway Fabric is a platform follow-up, not chart-local.
3. That the Helm release namespace MUST be allowed by the target ListenerSet allowlist
   (currently `fairagro-advanced-middleware` on platform inventories).

#### Scenario: NOTES mention dual-path when HTTPRoute is enabled

- **GIVEN** HTTPRoute is enabled
- **WHEN** Helm NOTES are rendered
- **THEN** the notes mention Gateway attachment and the ListenerSet namespace constraint

### Requirement: Renderability without a live Gateway

The repository SHALL provide a values or template-check path that exercises HTTPRoute
rendering without requiring a live Gateway API installation in the local minikube
smoke path. Local minikube install values MAY remain Ingress-only.

#### Scenario: Template smoke for HTTPRoute

- **GIVEN** values that enable HTTPRoute with sample `parentRefs` and hostnames
- **WHEN** `helm template` (or equivalent chart test) is run
- **THEN** a well-formed `HTTPRoute` appears in the output and Ingress-oriented
  `test_deploy` values remain usable for minikube without a Gateway
