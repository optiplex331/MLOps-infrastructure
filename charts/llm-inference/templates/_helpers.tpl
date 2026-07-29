{{/* Return the chart name used in labels and resource names. */}}
{{- define "llm-inference.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Return the stable resource name used by the single release. */}}
{{- define "llm-inference.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "llm-inference.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{/* Return the chart label without characters that are invalid in a label. */}}
{{- define "llm-inference.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Return the common label set for every namespaced resource. */}}
{{- define "llm-inference.labels" -}}
helm.sh/chart: {{ include "llm-inference.chart" . }}
app.kubernetes.io/name: {{ include "llm-inference.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end -}}

{{/* Return the selector label shared by the Deployment and Service. */}}
{{- define "llm-inference.selectorLabels" -}}
app.kubernetes.io/name: {{ include "llm-inference.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/* Fail before rendering a Deployment with a mutable or absent model revision. */}}
{{- define "llm-inference.validateModelRevision" -}}
{{- $revision := required "model.revision is required and must be a pinned Hugging Face commit" .Values.model.revision -}}
{{- if not (regexMatch "^[0-9a-f]{40}$" $revision) -}}
{{- fail "model.revision must be a lowercase 40-character Hugging Face commit" -}}
{{- end -}}
{{- end -}}

{{/* Fail before rendering a Deployment with a mutable or absent image identity. */}}
{{- define "llm-inference.validateImage" -}}
{{- $digest := required "image.digest is required and must be immutable" .Values.image.digest -}}
{{- if not (regexMatch "^sha256:[0-9a-f]{64}$" $digest) -}}
{{- fail "image.digest must match sha256:<64 lowercase hexadecimal characters>" -}}
{{- end -}}
{{- end -}}
