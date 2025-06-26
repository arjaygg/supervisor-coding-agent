{{/*
Expand the name of the chart.
*/}}
{{- define "supervisor-agent.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "supervisor-agent.fullname" -}}
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
{{- define "supervisor-agent.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "supervisor-agent.labels" -}}
helm.sh/chart: {{ include "supervisor-agent.chart" . }}
{{ include "supervisor-agent.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "supervisor-agent.selectorLabels" -}}
app.kubernetes.io/name: {{ include "supervisor-agent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "supervisor-agent.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "supervisor-agent.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the database URL
*/}}
{{- define "supervisor-agent.databaseUrl" -}}
{{- if .Values.postgresql.enabled }}
postgresql://{{ .Values.postgresql.auth.username }}:{{ .Values.postgresql.auth.password }}@{{ include "supervisor-agent.fullname" . }}-postgresql:5432/{{ .Values.postgresql.auth.database }}
{{- else }}
postgresql://{{ .Values.externalDatabase.username }}:{{ .Values.externalDatabase.password }}@{{ .Values.externalDatabase.host }}:{{ .Values.externalDatabase.port }}/{{ .Values.externalDatabase.database }}
{{- end }}
{{- end }}

{{/*
Create the Redis URL
*/}}
{{- define "supervisor-agent.redisUrl" -}}
{{- if .Values.redis.enabled }}
redis://:{{ .Values.redis.auth.password }}@{{ include "supervisor-agent.fullname" . }}-redis-master:6379/0
{{- else }}
redis://:{{ .Values.externalRedis.password }}@{{ .Values.externalRedis.host }}:{{ .Values.externalRedis.port }}/0
{{- end }}
{{- end }}

{{/*
Generate JWT secret key
*/}}
{{- define "supervisor-agent.jwtSecret" -}}
{{- if .Values.config.security.jwtSecret }}
{{- .Values.config.security.jwtSecret }}
{{- else }}
{{- randAlphaNum 64 }}
{{- end }}
{{- end }}

{{/*
Create PostgreSQL connection parameters for migrations
*/}}
{{- define "supervisor-agent.postgresqlParams" -}}
{{- if .Values.postgresql.enabled }}
PGHOST={{ include "supervisor-agent.fullname" . }}-postgresql
PGPORT=5432
PGUSER={{ .Values.postgresql.auth.username }}
PGPASSWORD={{ .Values.postgresql.auth.password }}
PGDATABASE={{ .Values.postgresql.auth.database }}
{{- else }}
PGHOST={{ .Values.externalDatabase.host }}
PGPORT={{ .Values.externalDatabase.port }}
PGUSER={{ .Values.externalDatabase.username }}
PGPASSWORD={{ .Values.externalDatabase.password }}
PGDATABASE={{ .Values.externalDatabase.database }}
{{- end }}
{{- end }}

{{/*
Return the proper image name for the init container
*/}}
{{- define "supervisor-agent.initImage" -}}
{{- if .Values.migration.image.repository }}
{{- printf "%s:%s" .Values.migration.image.repository (.Values.migration.image.tag | default .Chart.AppVersion) }}
{{- else }}
{{- printf "%s/%s:%s" .Values.image.registry .Values.image.repository (.Values.image.tag | default .Chart.AppVersion) }}
{{- end }}
{{- end }}

{{/*
Create environment-specific configuration
*/}}
{{- define "supervisor-agent.environment" -}}
{{- if eq .Values.env "production" }}
production
{{- else if eq .Values.env "staging" }}
staging
{{- else }}
development
{{- end }}
{{- end }}