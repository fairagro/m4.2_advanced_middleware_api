{{/*
Expand the name of the chart.
*/}}
{{- define "advanced-middleware-api.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "advanced-middleware-api.fullname" -}}
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
{{- define "advanced-middleware-api.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "advanced-middleware-api.labels" -}}
helm.sh/chart: {{ include "advanced-middleware-api.chart" . }}
{{ include "advanced-middleware-api.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "advanced-middleware-api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "advanced-middleware-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "advanced-middleware-api.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "advanced-middleware-api.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the CA TLS secret
*/}}
{{- define "advanced-middleware-api.caTlsSecretName" -}}
{{- if .Values.tls.caTlsSecretName }}
{{- .Values.tls.caTlsSecretName }}
{{- else }}
{{- include "advanced-middleware-api.fullname" . }}-ca-secret
{{- end }}
{{- end }}
