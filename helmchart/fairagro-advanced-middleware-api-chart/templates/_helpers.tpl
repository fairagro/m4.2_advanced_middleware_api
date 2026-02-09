{{/*
Expand the name of the chart.
*/}}
{{- define "fairagro-advanced-middleware-api-chart.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "fairagro-advanced-middleware-api-chart.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "fairagro-advanced-middleware-api-chart.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "fairagro-advanced-middleware-api-chart.labels" -}}
helm.sh/chart: {{ include "fairagro-advanced-middleware-api-chart.chart" . }}
{{ include "fairagro-advanced-middleware-api-chart.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "fairagro-advanced-middleware-api-chart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "fairagro-advanced-middleware-api-chart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "fairagro-advanced-middleware-api-chart.serviceAccountName" -}}
{{- default (include "fairagro-advanced-middleware-api-chart.fullname" .) .Values.api.serviceAccount.name }}
{{- end }}

{{/*
Create the name of the Celery worker service account to use
*/}}
{{- define "fairagro-advanced-middleware-api-chart.celeryServiceAccountName" -}}
{{- if .Values.celery.worker.serviceAccount.name }}
{{- .Values.celery.worker.serviceAccount.name }}
{{- else }}
{{- printf "%s-celery-worker" (include "fairagro-advanced-middleware-api-chart.fullname" .) }}
{{- end }}
{{- end }}

{{/*
Create the name of the CA TLS secret
*/}}
{{- define "fairagro-advanced-middleware-api-chart.caTlsSecretName" -}}
{{- if .Values.api.tls.caTlsSecretName }}
{{- .Values.api.tls.caTlsSecretName }}
{{- else }}
{{- include "fairagro-advanced-middleware-api-chart.fullname" . }}-ca-secret
{{- end }}
{{- end }}

{{/*
Compute Celery broker URL based on enabled RabbitMQ or provided override.
*/}}
{{- define "fairagro-advanced-middleware-api-chart.celeryBrokerUrl" -}}
{{- $fullname := include "fairagro-advanced-middleware-api-chart.fullname" . -}}
{{- $celeryConfig := default (dict) .Values.config.celery -}}
{{- $brokerOverride := default .Values.celery.brokerUrl $celeryConfig.broker_url -}}
{{- if .Values.rabbitmq.enabled -}}
	{{- $rabbitAuth := default (dict) .Values.rabbitmq.auth -}}
	{{- $user := default "" $rabbitAuth.username -}}
	{{- $pass := default "" $rabbitAuth.password -}}
	{{- $existing := default "" $rabbitAuth.existingSecret -}}
	{{- if $brokerOverride -}}
		{{- $brokerOverride -}}
	{{- else if $existing -}}
		{{- if and $user $pass -}}
			{{- $userEsc := urlquery $user -}}
			{{- $passEsc := urlquery $pass -}}
			{{- printf "amqp://%s:%s@%s-rabbitmq:5672//" $userEsc $passEsc $fullname -}}
		{{- else -}}
			{{- required "Provide rabbitmq.auth.username/password when rabbitmq.auth.existingSecret is set, or set config.celery.broker_url" $brokerOverride -}}
		{{- end -}}
	{{- else -}}
		{{- $userEsc := urlquery (required "rabbitmq.auth.username is required when not using an existing secret" $user) -}}
		{{- $passEsc := urlquery (required "rabbitmq.auth.password is required when not using an existing secret" $pass) -}}
		{{- printf "amqp://%s:%s@%s-rabbitmq:5672//" $userEsc $passEsc $fullname -}}
	{{- end }}
{{- else }}
{{- required "Set config.celery.broker_url when rabbitmq.enabled=false" $brokerOverride -}}
{{- end }}
{{- end }}

{{/*
Compute Celery result backend based on enabled Redis or provided override.
*/}}
{{- define "fairagro-advanced-middleware-api-chart.celeryResultBackend" -}}
{{- $fullname := include "fairagro-advanced-middleware-api-chart.fullname" . -}}
{{- $celeryConfig := default (dict) .Values.config.celery -}}
{{- $backendOverride := default .Values.celery.resultBackend $celeryConfig.result_backend -}}
{{- if .Values.redis.enabled -}}
	{{- $redisAuth := default (dict) .Values.redis.auth -}}
	{{- $pass := default "" $redisAuth.password -}}
	{{- $existing := default "" $redisAuth.existingSecret -}}
	{{- if $backendOverride -}}
		{{- $backendOverride -}}
	{{- else if $existing -}}
		{{- if $pass -}}
			{{- $passEsc := urlquery $pass -}}
			{{- printf "redis://:%s@%s-redis:6379/0" $passEsc $fullname -}}
		{{- else -}}
			{{- required "Provide redis.auth.password when redis.auth.existingSecret is set, or set config.celery.result_backend" $backendOverride -}}
		{{- end -}}
	{{- else -}}
		{{- $passEsc := urlquery (required "redis.auth.password is required when not using an existing secret" $pass) -}}
		{{- printf "redis://:%s@%s-redis:6379/0" $passEsc $fullname -}}
	{{- end }}
{{- else }}
{{- required "Set config.celery.result_backend when redis.enabled=false" $backendOverride -}}
{{- end }}
{{- end }}

{{/*
Compute CouchDB URL based on enabled CouchDB or provided override.
*/}}
{{- define "fairagro-advanced-middleware-api-chart.couchdbUrl" -}}
{{- $fullname := include "fairagro-advanced-middleware-api-chart.fullname" . -}}
{{- $couchConfig := default (dict) .Values.config.couchdb -}}
{{- if $couchConfig.url -}}
	{{- $couchConfig.url -}}
{{- else if .Values.couchdb.enabled -}}
	{{- printf "http://%s-couchdb:%d" $fullname (int .Values.couchdb.service.port) -}}
{{- else -}}
	{{- required "Provide config.couchdb.url or enable couchdb" $couchConfig.url -}}
{{- end -}}
{{- end }}

{{/*
Get the CouchDB secret name.
*/}}
{{- define "fairagro-advanced-middleware-api-chart.couchdbSecretName" -}}
{{- $couchAuth := default (dict) .Values.couchdb.auth -}}
{{- default (printf "%s-couchdb-auth" (include "fairagro-advanced-middleware-api-chart.fullname" .)) $couchAuth.existingSecret -}}
{{- end }}

{{/*
Get the CouchDB user key.
*/}}
{{- define "fairagro-advanced-middleware-api-chart.couchdbUserKey" -}}
{{- $couchAuth := default (dict) .Values.couchdb.auth -}}
{{- default "username" $couchAuth.usernameKey -}}
{{- end }}

{{/*
Get the CouchDB password key.
*/}}
{{- define "fairagro-advanced-middleware-api-chart.couchdbPasswordKey" -}}
{{- $couchAuth := default (dict) .Values.couchdb.auth -}}
{{- default "password" $couchAuth.passwordKey -}}
{{- end }}

{{/*
CouchDB environment variables
*/}}
{{- define "fairagro-advanced-middleware-api-chart.couchdbEnvVars" -}}
- name: COUCHDB_URL
  value: {{ include "fairagro-advanced-middleware-api-chart.couchdbUrl" . | quote }}
- name: COUCHDB_USER
  valueFrom:
    secretKeyRef:
      name: {{ include "fairagro-advanced-middleware-api-chart.couchdbSecretName" . }}
      key: {{ include "fairagro-advanced-middleware-api-chart.couchdbUserKey" . }}
- name: COUCHDB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "fairagro-advanced-middleware-api-chart.couchdbSecretName" . }}
      key: {{ include "fairagro-advanced-middleware-api-chart.couchdbPasswordKey" . }}
{{- end }}
