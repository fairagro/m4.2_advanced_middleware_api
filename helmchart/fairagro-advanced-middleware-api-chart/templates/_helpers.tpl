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
{{- $brokerOverride := .Values.celery.brokerUrl -}}
{{- if .Values.rabbitmq.enabled -}}
	{{- $rabbitAuth := default (dict) .Values.rabbitmq.auth -}}
	{{- $user := default "" $rabbitAuth.username -}}
	{{- $pass := default "" $rabbitAuth.password -}}
	{{- $existing := default "" $rabbitAuth.existingSecret -}}
	{{- if and $existing (or (eq $user "") (eq $pass "")) -}}
		{{- required "Provide rabbitmq.auth.username/password when rabbitmq.auth.existingSecret is set, or set celery.brokerUrl" $brokerOverride -}}
	{{- else -}}
		{{- $u := default "guest" $user -}}
		{{- $p := default "guest" $pass -}}
		{{- printf "amqp://%s:%s@%s-rabbitmq:5672//" $u $p $fullname -}}
	{{- end -}}
{{- else -}}
{{- required "Set celery.brokerUrl when rabbitmq.enabled=false" $brokerOverride -}}
{{- end -}}
{{- end }}

{{/*
Compute Celery result backend based on enabled Redis or provided override.
*/}}
{{- define "fairagro-advanced-middleware-api-chart.celeryResultBackend" -}}
{{- $fullname := include "fairagro-advanced-middleware-api-chart.fullname" . -}}
{{- $backendOverride := default .Values.celery.resultBackend .Values.resultBackend -}}
{{- if .Values.redis.enabled -}}
	{{- $redisAuth := default (dict) .Values.redis.auth -}}
	{{- $pass := default "" $redisAuth.password -}}
	{{- $existing := default "" $redisAuth.existingSecret -}}
	{{- if and $existing (eq $pass "") -}}
		{{- required "Provide redis.auth.password when redis.auth.existingSecret is set, or set resultBackend" $backendOverride -}}
	{{- else if $pass -}}
		{{- printf "redis://:%s@%s-redis:6379/0" $pass $fullname -}}
	{{- else -}}
		{{- printf "redis://%s-redis:6379/0" $fullname -}}
	{{- end -}}
{{- else -}}
{{- required "Set resultBackend when redis.enabled=false" $backendOverride -}}
{{- end -}}
{{- end }}
