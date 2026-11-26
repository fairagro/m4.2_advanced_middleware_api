# Spec Delta

## ADDED Requirements

### Requirement: Optional SnippetsFilter for Gateway client TLS

The chart SHALL render an NGINX Gateway Fabric `SnippetsFilter` in the release namespace only when HTTPRoute is enabled
and Gateway client TLS is explicitly enabled in values. When client TLS is disabled, the chart MUST NOT emit that
`SnippetsFilter`.

#### Scenario: Client TLS disabled by default

- **GIVEN** chart default values with HTTPRoute and Gateway client TLS disabled
- **WHEN** the chart is rendered
- **THEN** no `SnippetsFilter` for client TLS is produced

#### Scenario: Client TLS enabled with HTTPRoute

- **GIVEN** HTTPRoute is enabled and Gateway client TLS is enabled
- **WHEN** the chart is rendered
- **THEN** a `SnippetsFilter` is produced in the release namespace that configures optional client certificate
  verification against the configured CA file path and passes verify status and certificate material to the upstream
  using header names compatible with the Middleware API (`ssl-client-cert` and `ssl-client-verify`, or documented
  equivalents the API already accepts)

### Requirement: HTTPRoute ExtensionRef to client-TLS SnippetsFilter

When Gateway client TLS is enabled together with HTTPRoute, the rendered `HTTPRoute` SHALL include an `ExtensionRef`
filter referencing that chart-owned `SnippetsFilter` on the routing rule that forwards to the API Service.

#### Scenario: ExtensionRef present when client TLS enabled

- **GIVEN** HTTPRoute and Gateway client TLS are both enabled
- **WHEN** the chart is rendered
- **THEN** the `HTTPRoute` rule that targets the API Service references the chart `SnippetsFilter` via `ExtensionRef`

#### Scenario: No ExtensionRef when client TLS disabled

- **GIVEN** HTTPRoute is enabled and Gateway client TLS is disabled
- **WHEN** the chart is rendered
- **THEN** the `HTTPRoute` does not require a client-TLS `SnippetsFilter` ExtensionRef

### Requirement: Cluster-agnostic client CA path

Gateway client TLS values MUST NOT hardcode cluster inventory names. The chart SHALL derive the default CA file path as
`/etc/nginx/client-cas/<project>/ca.crt` from a configurable project identifier (default suitable for the Fairagro
Middleware Argo CD project), and SHALL allow an explicit CA path override in values.

#### Scenario: Default project path

- **GIVEN** Gateway client TLS is enabled without a CA path override
- **WHEN** the chart is rendered
- **THEN** the `SnippetsFilter` references `/etc/nginx/client-cas/<configured-project>/ca.crt`

#### Scenario: Explicit caPath override

- **GIVEN** Gateway client TLS is enabled with an explicit CA path in values
- **WHEN** the chart is rendered
- **THEN** the `SnippetsFilter` uses that path instead of the project-derived default

## MODIFIED Requirements

### Requirement: Document dual-path and deploy constraints

Operator-facing documentation (Helm chart NOTES and charts operator docs (`docs/helmchart_related.md`)) SHALL describe:

1. Dual-path exposure: Ingress and HTTPRoute remain independently feature-flagged.
2. When Gateway client TLS is enabled, optional client certificate verification and upstream cert headers are provided
   by the chart `SnippetsFilter` on the HTTPRoute (platform must mount the project CA and enable snippets on the Gateway
   dataplane).
3. Ingress may still provide nginx client mTLS for local smoke or transition; Fairagro Ingress-off cutover is a separate
   follow-up.
4. That the Helm release namespace MUST be allowed by the target ListenerSet allowlist (currently
   `fairagro-advanced-middleware` on platform inventories).

#### Scenario: NOTES mention dual-path when HTTPRoute is enabled

- **GIVEN** HTTPRoute is enabled
- **WHEN** Helm NOTES are rendered
- **THEN** the notes mention Gateway attachment and the ListenerSet namespace constraint

#### Scenario: NOTES mention Gateway client TLS when enabled

- **GIVEN** HTTPRoute and Gateway client TLS are enabled
- **WHEN** Helm NOTES are rendered
- **THEN** the notes also mention optional client TLS via the chart SnippetsFilter

### Requirement: Renderability without a live Gateway

The repository SHALL provide a values or template-check path that exercises HTTPRoute rendering (and, when covered by
that overlay, Gateway client TLS `SnippetsFilter` rendering) without requiring a live Gateway API installation in the
local minikube smoke path. Local minikube install values MAY remain Ingress-only.

#### Scenario: Template smoke for HTTPRoute

- **GIVEN** values that enable HTTPRoute with sample `parentRefs` and hostnames
- **WHEN** `helm template` (or equivalent chart test) is run
- **THEN** a well-formed `HTTPRoute` appears in the output and Ingress-oriented `test_deploy` values remain usable for
  minikube without a Gateway

#### Scenario: Template smoke for HTTPRoute with client TLS

- **GIVEN** values that enable HTTPRoute and Gateway client TLS with a sample project or CA path
- **WHEN** `helm template` (or equivalent chart test) is run
- **THEN** a well-formed `HTTPRoute` with SnippetsFilter ExtensionRef and a `SnippetsFilter` manifest appear in the
  output
