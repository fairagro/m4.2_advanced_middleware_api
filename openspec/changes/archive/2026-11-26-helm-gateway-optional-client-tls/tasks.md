# Tasks

## 1. Chart values and SnippetsFilter

- [x] 1.1 Add `api.httpRoute.clientTls` to chart `values.yaml` (`enabled: false`, `project: fairagro-m42`, empty
      `caPath`, `verifyDepth: 1`) and document keys in comments; verify defaults leave client TLS off
- [x] 1.2 Add `templates/snippetsfilter-client-tls.yaml` (or equivalent) gated on HTTPRoute + clientTls; emit NGF
      `SnippetsFilter` with `http.server` optional+CA and `http.server.location` upstream headers (`ssl-client-cert` /
      `$ssl_client_escaped_cert`, `ssl-client-verify` / `$ssl_client_verify`); verify `helm template` without clientTls
      emits no SnippetsFilter
- [x] 1.3 Update `templates/httproute.yaml` to attach `ExtensionRef` to the client-TLS SnippetsFilter when clientTls is
      enabled; verify template output includes the filter only when enabled

## 2. Docs, NOTES, and render smoke

- [x] 2.1 Update `templates/NOTES.txt` and `docs/helmchart_related.md` for Gateway-owned optional client TLS + dual-path
      / #741 deferral; verify NOTES render with clientTls on and off
- [x] 2.2 Extend `charts/test_deploy/values-httproute.yaml` (or sibling) to enable clientTls for render smoke; verify
      `helm template … -f charts/test_deploy/values-httproute.yaml` shows HTTPRoute ExtensionRef + SnippetsFilter and
      minikube `values.yaml` remains Ingress-oriented

## 3. Spec mapping check

- [x] 3.1 Confirm `AGENTS.md` Spec-to-Code Mapping for `helm-httproute` still points at the chart templates (add
      SnippetsFilter path if listed narrowly); verify the row mentions the new template or remains accurate

## Workflow follow-up

- Draft PR after real commits (`Fixes #738`; link #741).
- Archive the change after review requirements are satisfied.
