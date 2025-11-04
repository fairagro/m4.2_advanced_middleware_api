# On helm charts

## Helm chart testing

This section is about a local test installation of the middleware api using helm.
The needed tools are included in the dev container.

### Preparations

Some files need for the test installation can be found in the folder `helmchart/advanced-middleware-api`.
First we will need to create a temporary self-signed server certificate in this folder:

```bash
FQDN=chart-example.local

cat > helmchart/advanced-middleware-api/server.conf <<EOF
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
    -keyout helmchart/advanced-middleware-api/server.key \
    -out helmchart/advanced-middleware-api/server.crt \
    -config helmchart/advanced-middleware-api/server.conf \
    -extensions v3_req
```

We also need a CA certificate and a client key/certificate pair for mTLS:

```bash
openssl genrsa -out helmchart/advanced-middleware-api/ca.key 2048
openssl req -x509 -new -nodes \
    -key helmchart/advanced-middleware-api/ca.key \
    -sha256 -days 365 \
    -out helmchart/advanced-middleware-api/ca.crt \
    -subj "/CN=chart-example-ca"
openssl genrsa -out helmchart/advanced-middleware-api/client.key 2048
openssl req -new \
    -key helmchart/advanced-middleware-api/client.key \
    -out helmchart/advanced-middleware-api/client.csr \
    -subj "/CN=chart-example-client"
openssl x509 -req \
    -in helmchart/advanced-middleware-api/client.csr \
    -CA helmchart/advanced-middleware-api/ca.crt \
    -CAkey helmchart/advanced-middleware-api/ca.key \
    -CAcreateserial \
    -out helmchart/advanced-middleware-api/client.crt \
    -days 365 -sha256
```

### Installation

Now we can execute the installation:

```bash
docker build . -t advanced-middleware-api:test
minikube delete --all --purge   # only if we have trouble starting minikube
minikube start --driver=docker --cni=calico
minikube addons enable ingress
minikube image load advanced-middleware-api:test
helm install api-test ./helmchart/advanced-middleware-api -f helmchart/test_deploy/values.yaml
```

Note that the value file `helmchart/test_deploy/values.yaml` references the local docker image `advanced_middleware_api:test`.

### Test the api service

Now that the service is hopefully up and running in the dev container, you can test from within the dev container.

#### Basic liveness check (no client certificate required)

```bash
curl -k -H "Host: ${FQDN}" https://$(minikube ip)/v1/liveness
```

#### mTLS authentication test

For endpoints requiring client certificate authentication:

```bash
curl -k \
    --resolve ${FQDN}:443:$(minikube ip) \
    --cert helmchart/advanced-middleware-api/client.crt \
    --key helmchart/advanced-middleware-api/client.key \
     https://${FQDN}/v1/whoami
```

**✅ Use OpenSSL instead** (this works reliably):

```bash
# Method 2: Using OpenSSL (recommended for mTLS)
echo -e "GET /v1/whoami HTTP/1.1\r\nHost: ${FQDN}\r\nAccept: application/json\r\nConnection: close\r\n\r\n" | \
openssl s_client \
    -connect $(minikube ip):443 \
    -cert helmchart/advanced-middleware-api/client.crt \
    -key helmchart/advanced-middleware-api/client.key \
    -servername ${FQDN} \
    -ign_eof \
    2>/dev/null | grep -A 20 "HTTP/1.1"
```

**Expected successful response:**

```json
{"client_id":"chart-example-client","message":"Client authenticated successfully"}
```
