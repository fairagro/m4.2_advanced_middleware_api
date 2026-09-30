## 1. Chart values and template

- [x] 1.1 Add `api.httpRoute` block to chart `values.yaml` (`enabled: false`, empty `parentRefs` / `hostnames`; comment
      example for ListenerSet `fairagro-https` without activating it)
- [x] 1.2 Add `templates/httproute.yaml` gated on `api.httpRoute.enabled`, `gateway.networking.k8s.io/v1` `HTTPRoute`,
      pass-through `parentRefs` / `hostnames`, default path to chart Service + `api.service.port`
- [x] 1.3 Confirm Ingress template and `api.ingress` remain unchanged and independently flaggable; do not add a
      public-hostname `Certificate` template

## 2. Docs and NOTES

- [x] 2.1 Update `docs/helmchart_related.md` for dual-path (Ingress mTLS vs Gateway HTTPRoute), ListenerSet namespace
      allowlist, and platform mTLS follow-up boundary
- [x] 2.2 Extend `templates/NOTES.txt` when HTTPRoute is enabled (Gateway attachment + namespace allowlist)

## 3. Render verification

- [x] 3.1 Add `helmchart/test_deploy/values-httproute.yaml` (or equivalent) with sample `parentRefs` / hostnames; keep
      `test_deploy/values.yaml` Ingress-oriented for minikube
- [x] 3.2 Run `helm template` with HTTPRoute values and verify `HTTPRoute` present; run with defaults and verify no
      `HTTPRoute`; optionally both flags on

## 4. Spec mapping

- [x] 4.1 Add Spec-to-Code Mapping row for `helm-httproute` in `AGENTS.md` (chart paths)
