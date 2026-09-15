## Context

See `proposal.md` for motivation ([#411](https://github.com/fairagro/m4.2_advanced_middleware_api/issues/411)).

Today the chart exposes the API via optional `networking.k8s.io/v1` Ingress
(`templates/ingress.yaml`, `api.ingress.*`), including nginx mTLS annotations when
`mtlsEnabled`. App TLS material for Ingress lives under `api.tls.*` / Secret templates.
There is no Gateway API resource. Platform clusters already terminate `*.fairagro.net`
on a shared `ListenerSet` (`fairagro-https` in `kube-gateway-api`); app releases attach
with an `HTTPRoute` whose namespace is on the ListenerSet allowlist.

## Goals / Non-Goals

**Goals:**

- Add optional, cluster-agnostic `HTTPRoute` values + template.
- Keep Ingress independently usable (dual-path).
- Document operator constraints and the platform mTLS follow-up boundary.
- Provide a render-only verification path for HTTPRoute.

**Non-Goals:**

- Installing Gateway / NGF CRDs or Controllers in the chart.
- Chart-owned `Certificate` / ClusterIssuer for public `*.fairagro.net`.
- Client mTLS on Gateway Fabric (platform / misc follow-up).
- Changing FastAPI auth or app TLS verification behaviour.
- Hardcoding inventory hostnames or cluster names in chart defaults.

## Decisions

### D1: Values key `api.httpRoute`

Mirror `api.ingress` under `api.httpRoute` with at least:

| Key | Default | Role |
| --- | ------- | ---- |
| `enabled` | `false` | Feature flag |
| `parentRefs` | `[]` | Full parentRef objects as YAML (ListenerSet or Gateway) |
| `hostnames` | `[]` | HTTPRoute hostnames |
| (rules) | single default path `/` → chart Service + `api.service.port` | Keep MVP minimal; optional future `rules` override only if needed |

**Reason:** Same nesting as Ingress; overlays own parentRef details.

**Alternatives:** Nested `api.gateway.httpRoute` — extra indirection without benefit for one resource kind.

### D2: API versions

- `HTTPRoute`: `gateway.networking.k8s.io/v1`
- `parentRefs` may reference `gateway.networking.x-k8s.io` / `ListenerSet` (experimental
  group used by current platform inventories). Chart passes through whatever the overlay
  sets; it does not validate CRD presence at render time.

**Reason:** Matches platform attachment pattern; chart stays agnostic to parent kind.

### D3: No Certificate template for public hostname

Do not add cert-manager resources for ListenerSet hostnames. Existing `api.tls` /
Ingress TLS Secrets remain for the Ingress path only.

**Reason:** Avoid duplicate cert ownership and conflict with platform wildcard cert.

### D4: Minikube / test_deploy stays Ingress-only

Add something like `helmchart/test_deploy/values-httproute-render.yaml` (or a short
documented `helm template -f …` snippet) for CI/local render checks. Do not require
Gateway in `test_deploy/values.yaml`.

**Reason:** Minikube addon path is still Ingress; Gateway smoke is cluster-specific.

### D5: Documentation surfaces

Update `docs/helmchart_related.md` and `templates/NOTES.txt` when `api.httpRoute.enabled`
(and briefly in the docs body always). Point to platform mTLS follow-up without requiring
a live misc issue URL if still unset.

**Reason:** Acceptance criteria call out NOTES + helmchart docs.

### D6: Spec-to-code mapping

After archive, add `openspec/specs/helm-httproute/` → chart paths in `AGENTS.md`.

## Risks / Trade-offs

| Risk | Mitigation |
| ---- | ---------- |
| Overlay forgets namespace allowlist → Route not accepted | Document in NOTES/docs; fail is platform-visible, not chart crash |
| Dual-path double exposure of same host | Overlays choose flags; document transition intent |
| Experimental `ListenerSet` API group changes | parentRefs are overlay-owned; chart only templates YAML |
| `helm template` without CRDs still succeeds | Expected; apply-time validation is cluster’s job |

## Migration Plan

1. Land chart defaults with `api.httpRoute.enabled: false` (no behaviour change).
2. Deploy overlays enable HTTPRoute + supply `parentRefs` / hostnames; keep Ingress for
   mTLS until platform cutover.
3. Later (out of scope): disable Ingress when Gateway client TLS is ready.
4. Rollback: set `api.httpRoute.enabled: false` and redeploy; Ingress path unchanged.
