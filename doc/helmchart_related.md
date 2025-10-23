# On helm charts

## Helm chart testing

This section is about a local test installation of the middleware api using helm.
The needed tools are included in the dev container.

### Preparations

Some files need for the test installation can be found in the folder `helmchart/advanced-middleware-api`.
First we will need to create a temporary self-signed server certificate in this folder:

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout helmchart/advanced-middleware-api/tls.key \
  -out helmchart/advanced-middleware-api/tls.crt \
  -subj "/CN=chart-example.local"
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
minikube start
minikube addons enable ingress
minikube image load advanced-middleware-api:test
helm install api-test ./helmchart/advanced-middleware-api -f helmchart/advanced-middleware-api/values.yaml
```

Note that the file value `helmchart/advanced-middleware-api/values.yaml` references the local docker image `advanced_middleware_api:test`.

### Test the api service

Now that the service is hopefully up and running in the dev container, you can test from within the dev container:

```bash
curl -k \
    --cert helmchart/advanced-middleware-api/client.crt \
    --key helmchart/advanced-middleware-api/client.key \
    -H "Host: chart-example.local" \
    https://$(minikube ip)/v1/liveness
```

Unfortunately I was not able to find a solution how to access the service from the host.
