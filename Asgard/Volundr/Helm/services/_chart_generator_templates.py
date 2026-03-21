"""Helm chart template generators - core templates (helpers, deployment, service, etc.)."""

from Asgard.Volundr.Helm.models.helm_models import HelmConfig


def generate_helpers_template(config: HelmConfig) -> str:
    name = config.chart.name
    return f'''{{{{/*
Expand the name of the chart.
*/}}}}
{{{{- define "{name}.name" -}}}}
{{{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}

{{{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}}}
{{{{- define "{name}.fullname" -}}}}
{{{{- if .Values.fullnameOverride }}}}
{{{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}}}
{{{{- else }}}}
{{{{- $name := default .Chart.Name .Values.nameOverride }}}}
{{{{- if contains $name .Release.Name }}}}
{{{{- .Release.Name | trunc 63 | trimSuffix "-" }}}}
{{{{- else }}}}
{{{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}
{{{{- end }}}}
{{{{- end }}}}

{{{{/*
Create chart name and version as used by the chart label.
*/}}}}
{{{{- define "{name}.chart" -}}}}
{{{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}

{{{{/*
Common labels
*/}}}}
{{{{- define "{name}.labels" -}}}}
helm.sh/chart: {{{{- include "{name}.chart" . }}}}
{{{{ include "{name}.selectorLabels" . }}}}
{{{{- if .Chart.AppVersion }}}}
app.kubernetes.io/version: {{{{ .Chart.AppVersion | quote }}}}
{{{{- end }}}}
app.kubernetes.io/managed-by: {{{{ .Release.Service }}}}
{{{{- end }}}}

{{{{/*
Selector labels
*/}}}}
{{{{- define "{name}.selectorLabels" -}}}}
app.kubernetes.io/name: {{{{- include "{name}.name" . }}}}
app.kubernetes.io/instance: {{{{ .Release.Name }}}}
{{{{- end }}}}

{{{{/*
Create the name of the service account to use
*/}}}}
{{{{- define "{name}.serviceAccountName" -}}}}
{{{{- if .Values.serviceAccount.create }}}}
{{{{- default (include "{name}.fullname" .) .Values.serviceAccount.name }}}}
{{{{- else }}}}
{{{{- default "default" .Values.serviceAccount.name }}}}
{{{{- end }}}}
{{{{- end }}}}
'''


def generate_deployment_template(config: HelmConfig) -> str:
    name = config.chart.name
    return f'''apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{{{- include "{name}.fullname" . }}}}
  labels:
    {{{{- include "{name}.labels" . | nindent 4 }}}}
spec:
  {{{{- if not .Values.autoscaling.enabled }}}}
  replicas: {{{{ .Values.replicaCount }}}}
  {{{{- end }}}}
  selector:
    matchLabels:
      {{{{- include "{name}.selectorLabels" . | nindent 6 }}}}
  template:
    metadata:
      {{{{- with .Values.podAnnotations }}}}
      annotations:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      labels:
        {{{{- include "{name}.labels" . | nindent 8 }}}}
        {{{{- with .Values.podLabels }}}}
        {{{{- toYaml . | nindent 8 }}}}
        {{{{- end }}}}
    spec:
      {{{{- with .Values.imagePullSecrets }}}}
      imagePullSecrets:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      serviceAccountName: {{{{- include "{name}.serviceAccountName" . }}}}
      securityContext:
        {{{{- toYaml .Values.podSecurityContext | nindent 8 }}}}
      containers:
        - name: {{{{ .Chart.Name }}}}
          securityContext:
            {{{{- toYaml .Values.securityContext | nindent 12 }}}}
          image: "{{{{ .Values.image.repository }}}}:{{{{ .Values.image.tag | default .Chart.AppVersion }}}}"
          imagePullPolicy: {{{{ .Values.image.pullPolicy }}}}
          ports:
            - name: http
              containerPort: {{{{ .Values.service.port }}}}
              protocol: TCP
          livenessProbe:
            {{{{- toYaml .Values.livenessProbe | nindent 12 }}}}
          readinessProbe:
            {{{{- toYaml .Values.readinessProbe | nindent 12 }}}}
          resources:
            {{{{- toYaml .Values.resources | nindent 12 }}}}
          {{{{- with .Values.env }}}}
          env:
            {{{{- toYaml . | nindent 12 }}}}
          {{{{- end }}}}
          {{{{- with .Values.volumeMounts }}}}
          volumeMounts:
            {{{{- toYaml . | nindent 12 }}}}
          {{{{- end }}}}
      {{{{- with .Values.volumes }}}}
      volumes:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      {{{{- with .Values.nodeSelector }}}}
      nodeSelector:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      {{{{- with .Values.affinity }}}}
      affinity:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      {{{{- with .Values.tolerations }}}}
      tolerations:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
'''


def generate_service_template(config: HelmConfig) -> str:
    name = config.chart.name
    return f'''apiVersion: v1
kind: Service
metadata:
  name: {{{{- include "{name}.fullname" . }}}}
  labels:
    {{{{- include "{name}.labels" . | nindent 4 }}}}
spec:
  type: {{{{ .Values.service.type }}}}
  ports:
    - port: {{{{ .Values.service.port }}}}
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{{{- include "{name}.selectorLabels" . | nindent 4 }}}}
'''


def generate_serviceaccount_template(config: HelmConfig) -> str:
    name = config.chart.name
    return f'''{{{{- if .Values.serviceAccount.create -}}}}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{{{- include "{name}.serviceAccountName" . }}}}
  labels:
    {{{{- include "{name}.labels" . | nindent 4 }}}}
  {{{{- with .Values.serviceAccount.annotations }}}}
  annotations:
    {{{{- toYaml . | nindent 4 }}}}
  {{{{- end }}}}
automountServiceAccountToken: true
{{{{- end }}}}
'''
