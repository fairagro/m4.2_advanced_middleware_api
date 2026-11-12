# On helm charts

## Ingress and Gateway API (dual-path)

The chart can expose the API in two independently flagged ways:

| Path                    | Values                  | Role today                                                                                                                                                                                                                                              |
| ----------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Classic Ingress         | `api.ingress.enabled`   | Local minikube smoke; optional nginx client mTLS (`api.ingress.mtlsEnabled`) and Ingress TLS Secrets from `api.tls.*`                                                                                                                                   |
| Gateway API `HTTPRoute` | `api.httpRoute.enabled` | Attach to a platform-owned parent (typically `ListenerSet` `fairagro-https` in `kube-gateway-api`). Server TLS for `*.fairagro.net` stays on the platform ListenerSet / wildcard cert — the chart does **not** create a `Certificate` for that hostname |

Defaults leave both off (`enabled: false`). Deploy overlays supply cluster-specific `parentRefs` and `hostnames`; chart
defaults stay cluster-agnostic (no elise/fizz/draven/gangplank hardcoding).

**ListenerSet allowlist:** the Helm release namespace must be allowed by the target ListenerSet (current platform
inventories use `fairagro-advanced-middleware`). Routes from other namespaces are not accepted.

**Client mTLS cutover** to NGINX Gateway Fabric is a **platform** follow-up. Until then, keep Ingress (with mTLS) if
clients need cert auth; HTTPRoute can run in parallel for Gateway TLS exposure.

**Render check (no live Gateway):**

```bash
helm template api-test ./charts/fairagro-advanced-middleware-api-chart \
  -f charts/test_deploy/values-httproute.yaml
```

Minikube installs continue to use `charts/test_deploy/values.yaml` (Ingress only).

### IDE: Helm templates vs YAML

Chart `templates/*.yaml` files are Helm Go templates. Red Hat YAML false-positives on `{{ … }}` are fixed by treating
those paths as language `helm` (Kubernetes Tools) plus suppressing the extension’s missing-kubeconfig toast when no
cluster is configured. That belongs in **synced Devinfra** `.vscode` / Dev Container settings — not product-local forks
of allowlisted paths.

## RabbitMQ non-root defaults

The chart RabbitMQ Deployment defaults to an **Alpine management** image (`rabbitmq:4.3.4-management-alpine`) and runs
as the image user **uid 100 / gid 101** (`rabbitmq.podSecurityContext.fsGroup: 101`,
`rabbitmq.securityContext.runAsNonRoot/runAsUser/runAsGroup`). That matches the official alpine passwd entry (spike:
[infra#21](https://github.com/fairagro/m4.2_infrastructure/issues/21)).

**Broker major bump:** chart defaults previously used `rabbitmq:3.12-management`. Moving to `4.3.4-management-alpine` is
a RabbitMQ **3 → 4** jump as well as an alpine/UID change — review broker compatibility before upgrading existing
releases.

If you override `rabbitmq.image` to a **Debian**-style tag (e.g. `rabbitmq:*-management` without `-alpine`), set
matching UIDs in `rabbitmq.securityContext` / `podSecurityContext` — Debian images commonly use a different uid (often
999), and the alpine defaults will be wrong.

## Helm chart testing

This section is about a local test installation of the middleware api using helm. The needed tools are included in the
dev container.

### Preparations

Some files needed for the test installation live in `charts/fairagro-advanced-middleware-api-chart`. First we will need
to create a temporary self-signed server certificate in this folder:

```bash
FQDN=chart-example.local

cat > charts/fairagro-advanced-middleware-api-chart/server.conf <<EOF
[req]
FQDN=chart-example.local
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = ${FQDN}

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = ${FQDN}
EOF

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout charts/fairagro-advanced-middleware-api-chart/server.key \
    -out charts/fairagro-advanced-middleware-api-chart/server.crt \
    -config charts/fairagro-advanced-middleware-api-chart/server.conf \
    -extensions v3_req
```

We also need a CA certificate and a client key/certificate pair for mTLS:

```bash
cat > charts/fairagro-advanced-middleware-api-chart/client_ext.conf <<EOF
[ client_ext ]
extendedKeyUsage = critical,clientAuth
keyUsage = digitalSignature
1.3.6.1.4.1.64609.1.1 = ASN1:SEQUENCE:custom_strings

[ custom_strings ]
s1 = UTF8:bonares
s2 = UTF8:edal
s3 = UTF8:edaphobase
s4 = UTF8:openagrar
s5 = UTF8:publisso
s6 = UTF8:thunen_atlas
EOF

openssl genrsa -out charts/fairagro-advanced-middleware-api-chart/ca.key 2048
openssl req -x509 -new -nodes \
    -key charts/fairagro-advanced-middleware-api-chart/ca.key \
    -sha256 -days 365 \
    -out charts/fairagro-advanced-middleware-api-chart/ca.crt \
    -subj "/CN=chart-example-ca"
openssl genrsa -out charts/fairagro-advanced-middleware-api-chart/client.key 2048
openssl req -new \
    -key charts/fairagro-advanced-middleware-api-chart/client.key \
    -out charts/fairagro-advanced-middleware-api-chart/client.csr \
    -subj "/CN=chart-example-client"
openssl x509 -req \
    -in charts/fairagro-advanced-middleware-api-chart/client.csr \
    -CA charts/fairagro-advanced-middleware-api-chart/ca.crt \
    -CAkey charts/fairagro-advanced-middleware-api-chart/ca.key \
    -CAcreateserial \
    -out charts/fairagro-advanced-middleware-api-chart/client.crt \
    -days 365 -sha256 \
    -extfile charts/fairagro-advanced-middleware-api-chart/client_ext.conf \
    -extensions client_ext
```

### Installation

Now we can execute the installation:

```bash
source scripts/load-versions-env.sh
docker build -f docker/Dockerfile.api \
  --build-arg PYTHON_VERSION="$PYTHON_VERSION" \
  --build-arg ALPINE_VERSION="$ALPINE_VERSION" \
  --build-arg ALPINE_MINOR="$ALPINE_MINOR" \
  --build-arg PIP_VERSION="$PIP_VERSION" \
  --build-arg UV_VERSION="$UV_VERSION" \
  -t fairagro-advanced-middleware-api:test .
minikube delete --all --purge   # only if we have trouble starting minikube
minikube start --driver=docker --cni=calico
minikube addons enable ingress
minikube image load fairagro-advanced-middleware-api:test
sops exec-env dev_environment/secrets.enc.yaml \
    "helm install api-test ./charts/fairagro-advanced-middleware-api-chart \
    -f charts/test_deploy/values.yaml \
    --set rabbitmq.auth.user=\"$\RABBITMQ_DEFAULT_USER\" \
    --set rabbitmq.auth.password=\"\$RABBITMQ_DEFAULT_PASS\" \
    --set couchdb.auth.username=\"\$COUCHDB_USER\" \
    --set couchdb.auth.password=\"\$COUCHDB_PASSWORD\""
```

Note that the value file `charts/test_deploy/values.yaml` references the local docker image
`fairagro-advanced-middleware-api:test`.

### Test the api service

Now that the service is hopefully up and running in the dev container, you can test from within the dev container.

#### Basic liveness check (no client certificate required)

```bash
curl -k -H "Host: ${FQDN}" https://$(minikube ip)/v3/liveness
```

#### mTLS authentication test

For endpoints requiring client certificate authentication:

```bash
curl -k \
    --resolve ${FQDN}:443:$(minikube ip) \
    --cert charts/fairagro-advanced-middleware-api-chart/client.crt \
    --key charts/fairagro-advanced-middleware-api-chart/client.key \
     https://${FQDN}/v3/whoami
```

**✅ Use OpenSSL instead** (this works reliably):

```bash
# Method 2: Using OpenSSL (recommended for mTLS)
echo -e "GET /v3/whoami HTTP/1.1\r\nHost: ${FQDN}\r\nAccept: application/json\r\nConnection: close\r\n\r\n" | \
openssl s_client \
    -connect $(minikube ip):443 \
    -cert charts/fairagro-advanced-middleware-api-chart/client.crt \
    -key charts/fairagro-advanced-middleware-api-chart/client.key \
    -servername ${FQDN} \
    -ign_eof \
    2>/dev/null | grep -A 20 "HTTP/1.1"
```

**Expected successful response:**

```json
{
  "client_id": "chart-example-client",
  "message": "Client authenticated successfully",
  "accessible_rdis": ["example-rdi"]
}
```
