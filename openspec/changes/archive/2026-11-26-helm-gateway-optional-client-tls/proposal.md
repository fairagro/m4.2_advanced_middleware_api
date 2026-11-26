# Proposal

## Why

[#411](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/411) added an optional chart `HTTPRoute`, but
Fairagro production still needs **ingress-nginx** for optional client TLS and upstream cert headers (`ssl-client-cert` /
`ssl-client-verify`) that the API uses for path-local auth. Platform misc#562 provisions project client CAs on
`gateway-external` for SnippetsFilter-based optional client TLS; the **SnippetsFilter belongs in this chart**. Issue
[#738](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/738) slice **A1** wires that contract without
forcing Ingress off (harder cutover is [#741](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/741)).

## What Changes

- Chart can render an NGINX Gateway Fabric `SnippetsFilter` (app namespace) for **optional** client cert verify against
  the platform-mounted project CA path, and pass cert material upstream in API-compatible headers
- `HTTPRoute` can attach that filter via `ExtensionRef` when client TLS is enabled in values
- Values stay cluster-agnostic: default `project` → CA path `/etc/nginx/client-cas/<project>/ca.crt` (optional `caPath`
  override); no elise/draven hardcoding
- Operator docs / NOTES / `helm-httproute` spec: Gateway can own optional client TLS; Ingress remains independently
  available (dual-path); Ingress-off Fairagro cutover deferred to #741
- `charts/test_deploy` render overlay exercises HTTPRoute + SnippetsFilter without a live Gateway
- **Non-goals (A1):** disable Ingress by default; DNS cutover; remove Ingress templates; app header adapter; live
  cluster deploy commits

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `helm-httproute`: optional Gateway client TLS via chart-owned `SnippetsFilter` + `HTTPRoute` ExtensionRef; docs no
  longer claim client mTLS cutover is only a platform follow-up

## Impact

- Chart: `charts/fairagro-advanced-middleware-api-chart/` (`values.yaml`, `httproute.yaml`, new snippetsfilter template,
  `NOTES.txt`)
- Docs: `docs/helmchart_related.md`, `openspec/specs/helm-httproute/`
- Render smoke: `charts/test_deploy/values-httproute.yaml`
- Depends on platform misc#562 (CA mount + `snippets.enable` on the target cluster) at **deploy** time; chart changes
  remain mergeable without that merge
- No Middleware Python/API changes expected if headers match existing readers
- Follow-up: #741 (A2 Ingress-off / Fairagro cutover)
