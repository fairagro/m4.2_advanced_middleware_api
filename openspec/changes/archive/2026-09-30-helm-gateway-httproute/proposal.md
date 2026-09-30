## Why

Platform clusters (especially draven) expose TLS via Gateway API + NGINX Gateway Fabric and a shared `ListenerSet`
(`fairagro-https`), while this chart still only offers classic `networking.k8s.io` Ingress. Deploy overlays need an
optional, cluster-agnostic `HTTPRoute` without inventing a second public certificate or dropping Ingress during the mTLS
transition ([#411](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/411)).

## What Changes

- Add an optional Helm `HTTPRoute` template driven by `api.httpRoute.*` values (`enabled`, `parentRefs`, `hostnames`,
  backend Service/port).
- Keep existing Ingress templates feature-flagged and independently usable (dual-path; no forced removal).
- Do **not** add a chart-owned `Certificate` / ClusterIssuer for `*.fairagro.net` (platform ListenerSet owns server
  TLS).
- Document dual-path (Ingress mTLS today; HTTPRoute attaches to platform Gateway), ListenerSet namespace allowlist
  constraint, and that client mTLS cutover is a **platform** follow-up (out of scope here).
- Exercise HTTPRoute rendering via `helm template` / test values without requiring a real Gateway in minikube
  `test_deploy` (Ingress remains the local smoke path).

## Capabilities

### New Capabilities

- `helm-httproute`: Optional Gateway API `HTTPRoute` rendering from the product Helm chart — cluster-agnostic
  `parentRefs` / hostnames, dual-path with Ingress, no chart-owned public hostname certificate.

### Modified Capabilities

_None — no existing `openspec/specs/` domain covers Helm exposure today._

## Impact

- Chart: `helmchart/fairagro-advanced-middleware-api-chart/` (`values.yaml`, new `templates/httproute.yaml`,
  `NOTES.txt`).
- Docs: `docs/helmchart_related.md` (and NOTES).
- Deploy overlays (outside this repo) supply host / `parentRefs`; release namespace must match ListenerSet allowlist
  (`fairagro-advanced-middleware` on current inventories).
- No FastAPI / middleware application behaviour change; no Gateway CRD install in the chart.
- Platform NGF optional client TLS / App-CA remains a separate misc issue.
