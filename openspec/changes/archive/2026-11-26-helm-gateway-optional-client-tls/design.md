# Design

## Context

See `proposal.md` for motivation. Chart already renders optional `HTTPRoute` (#411) and optional Ingress with nginx mTLS
annotations. Platform misc#562 mounts project CA PEMs on `gateway-external` at `/etc/nginx/client-cas/<project>/ca.crt`
and enables NGF snippets on elise. Spike preference: SnippetsFilter with `http.server` optional+CA (host-scoped on NGF
2.9). Middleware reads `ssl-client-cert` / `ssl-client-verify` (and `X-SSL-*`) and `unquote`s the PEM.

## Goals / Non-Goals

**Goals:**

- Values-driven chart `SnippetsFilter` + HTTPRoute `ExtensionRef` for optional Gateway client TLS
- API-compatible upstream headers without Python changes
- Cluster-agnostic defaults (`project` → CA path; optional `caPath`)
- Spec/docs/render smoke aligned with A1

**Non-Goals:**

- Ingress-off Fairagro overlay / DNS cutover (#741)
- Platform CA provisioning or `snippets.enable` (misc#562)
- Removing Ingress templates
- App-level TLS termination

## Decisions

1. **SnippetsFilter in app chart, not inventory** Matches platform ownership: HTTPRoute-adjacent resources stay in the
   release namespace; inventories must not host app SnippetsFilters. _Alt:_ SnippetsPolicy on Gateway — rejected
   (gateway-wide blast radius).

2. **Values shape** under `api.httpRoute.clientTls`:
   - `enabled` (default `false`)
   - `project` (default `fairagro-m42`)
   - `caPath` (optional override; else `/etc/nginx/client-cas/{{ project }}/ca.crt`)
   - `verifyDepth` (default `1`, maps to `ssl_verify_depth`) _Alt:_ only free-form `caPath` — less ergonomic vs platform
     project key convention.

3. **Snippet contexts**
   - `http.server`: `ssl_client_certificate`, `ssl_verify_client optional`, `ssl_verify_depth`
   - `http.server.location`: `proxy_set_header ssl-client-cert $ssl_client_escaped_cert;`,
     `proxy_set_header ssl-client-verify $ssl_client_verify;` Matches nginx directive contexts and existing API
     `unquote` behavior.

4. **Gate SnippetsFilter on HTTPRoute + clientTls** Do not emit a dangling filter when HTTPRoute is off. ExtensionRef
   only when both enabled.

5. **Keep Ingress dual-path** Independently flagged; A1 does not change Ingress defaults. Deprecation / Ingress-off →
   #741.

6. **Render smoke** Extend `charts/test_deploy/values-httproute.yaml` (or sibling overlay) to enable `clientTls` so
   `helm template` covers both resources without a live Gateway.

## Risks / Trade-offs

- **[Risk]** Invalid snippet blocks nginx reload for the dataplane → Mitigation: keep snippet minimal; validate with
  `helm template` + elise smoke before Fairagro cutover (#741).
- **[Risk]** `http.server` snippets can affect more than one route on some NGF versions → Mitigation: spike showed
  host-scope on elise 2.9; document caveat; do not use SnippetsPolicy.
- **[Risk]** Cluster without `snippets.enable` or CA mount → filter Accepted=False / TLS fails → Mitigation: docs state
  platform prerequisites; chart remains off by default.
- **[Trade-off]** NGF-specific CRD (`gateway.nginx.org`) couples chart to Fabric — accepted; Fairagro path already
  assumes NGF ListenerSets.

## Migration Plan

1. Merge A1 chart+spec (filters off by default).
2. On a snippets-enabled cluster with CA mount: overlay enables `httpRoute` + `clientTls`; verify headers with/without
   client cert (operator checklist; full Ingress-off in #741).
3. Rollback: disable `clientTls` / HTTPRoute in values; re-enable Ingress mTLS if needed.

## Open Questions

- None for A1 task breakdown; header naming confirmed against current API readers.
