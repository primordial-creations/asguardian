"""
Helm Chart Generator Service

Generates complete Helm chart structures with templates,
best practices, and comprehensive configurations.
"""

import hashlib
import os
from datetime import datetime
from typing import Dict, List, Optional, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Helm.models.helm_models import (
    GeneratedHelmChart,
    HelmConfig,
)


class ChartGenerator:
    """Generates Helm charts from configuration."""

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the chart generator.

        Args:
            output_dir: Directory for saving generated charts
        """
        self.output_dir = output_dir or "charts"

    def generate(self, config: HelmConfig) -> GeneratedHelmChart:
        """
        Generate a Helm chart based on the provided configuration.

        Args:
            config: Helm chart configuration

        Returns:
            GeneratedHelmChart with all generated files
        """
        config_json = config.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        chart_id = f"{config.chart.name}-{config_hash}"

        chart_files: Dict[str, str] = {}

        # Generate Chart.yaml
        chart_files["Chart.yaml"] = self._generate_chart_yaml(config)

        # Generate values.yaml
        chart_files["values.yaml"] = self._generate_values_yaml(config)

        # Generate templates
        chart_files["templates/deployment.yaml"] = self._generate_deployment_template(config)
        chart_files["templates/service.yaml"] = self._generate_service_template(config)

        if config.generate_helpers:
            chart_files["templates/_helpers.tpl"] = self._generate_helpers_template(config)

        if config.generate_notes:
            chart_files["templates/NOTES.txt"] = self._generate_notes_template(config)

        if config.include_service_account:
            chart_files["templates/serviceaccount.yaml"] = self._generate_serviceaccount_template(config)

        if config.include_hpa:
            chart_files["templates/hpa.yaml"] = self._generate_hpa_template(config)

        if config.values.ingress.enabled or config.chart.name:
            chart_files["templates/ingress.yaml"] = self._generate_ingress_template(config)

        if config.include_network_policy:
            chart_files["templates/networkpolicy.yaml"] = self._generate_networkpolicy_template(config)

        if config.include_pdb:
            chart_files["templates/pdb.yaml"] = self._generate_pdb_template(config)

        if config.include_configmap:
            chart_files["templates/configmap.yaml"] = self._generate_configmap_template(config)

        if config.include_secret:
            chart_files["templates/secret.yaml"] = self._generate_secret_template(config)

        if config.generate_tests:
            chart_files["templates/tests/test-connection.yaml"] = self._generate_test_template(config)

        # Generate .helmignore
        chart_files[".helmignore"] = self._generate_helmignore()

        validation_results = self._validate_chart(chart_files, config)
        best_practice_score = self._calculate_best_practice_score(chart_files, config)

        return GeneratedHelmChart(
            id=chart_id,
            config_hash=config_hash,
            chart_files=chart_files,
            validation_results=validation_results,
            best_practice_score=best_practice_score,
            created_at=datetime.now(),
        )

    def _generate_chart_yaml(self, config: HelmConfig) -> str:
        """Generate Chart.yaml content."""
        chart_data = {
            "apiVersion": config.chart.api_version,
            "name": config.chart.name,
            "description": config.chart.description or f"A Helm chart for {config.chart.name}",
            "type": config.chart.type.value,
            "version": config.chart.version,
            "appVersion": config.chart.app_version,
        }

        if config.chart.keywords:
            chart_data["keywords"] = config.chart.keywords

        if config.chart.home:
            chart_data["home"] = config.chart.home

        if config.chart.sources:
            chart_data["sources"] = config.chart.sources

        if config.chart.maintainers:
            chart_data["maintainers"] = [
                {k: v for k, v in m.model_dump().items() if v is not None}
                for m in config.chart.maintainers
            ]

        if config.chart.icon:
            chart_data["icon"] = config.chart.icon

        if config.chart.kube_version:
            chart_data["kubeVersion"] = config.chart.kube_version

        if config.chart.annotations:
            chart_data["annotations"] = config.chart.annotations

        if config.chart.dependencies:
            chart_data["dependencies"] = []
            for dep in config.chart.dependencies:
                dep_data = {
                    "name": dep.name,
                    "version": dep.version,
                    "repository": dep.repository,
                }
                if dep.condition:
                    dep_data["condition"] = dep.condition
                if dep.tags:
                    dep_data["tags"] = dep.tags
                if dep.alias:
                    dep_data["alias"] = dep.alias
                chart_data["dependencies"].append(dep_data)

        return cast(str, yaml.dump(chart_data, default_flow_style=False, sort_keys=False))

    def _generate_values_yaml(self, config: HelmConfig) -> str:
        """Generate values.yaml content."""
        values = config.values
        values_data = {
            "replicaCount": values.replica_count,
            "image": {
                "repository": values.image_repository,
                "pullPolicy": values.image_pull_policy,
                "tag": values.image_tag if values.image_tag != "latest" else '""',
            },
            "imagePullSecrets": [{"name": s} for s in values.image_pull_secrets] if values.image_pull_secrets else [],
            "nameOverride": values.name_override,
            "fullnameOverride": values.fullname_override,
            "serviceAccount": {
                "create": values.service_account_create,
                "annotations": values.service_account_annotations,
                "name": values.service_account_name,
            },
            "podAnnotations": values.pod_annotations,
            "podLabels": values.pod_labels,
            "podSecurityContext": {
                "fsGroup": values.pod_security_context.fs_group,
            },
            "securityContext": {
                "runAsNonRoot": values.security_context.run_as_non_root,
                "runAsUser": values.security_context.run_as_user,
                "readOnlyRootFilesystem": values.security_context.read_only_root_filesystem,
                "allowPrivilegeEscalation": values.security_context.allow_privilege_escalation,
                "capabilities": {"drop": ["ALL"]},
            },
            "service": {
                "type": values.service.type,
                "port": values.service.port,
            },
            "ingress": {
                "enabled": values.ingress.enabled,
                "className": values.ingress.class_name or "",
                "annotations": values.ingress.annotations,
                "hosts": values.ingress.hosts or [
                    {"host": f"chart-example.local", "paths": [{"path": "/", "pathType": "ImplementationSpecific"}]}
                ],
                "tls": values.ingress.tls,
            },
            "resources": {
                "limits": {
                    "cpu": values.resources.limits.cpu,
                    "memory": values.resources.limits.memory,
                },
                "requests": {
                    "cpu": values.resources.requests.cpu,
                    "memory": values.resources.requests.memory,
                },
            },
            "autoscaling": {
                "enabled": values.autoscaling.enabled,
                "minReplicas": values.autoscaling.min_replicas,
                "maxReplicas": values.autoscaling.max_replicas,
                "targetCPUUtilizationPercentage": values.autoscaling.target_cpu_utilization,
            },
            "livenessProbe": {
                "httpGet": {
                    "path": values.liveness_probe.path,
                    "port": values.liveness_probe.port,
                },
                "initialDelaySeconds": values.liveness_probe.initial_delay_seconds,
                "periodSeconds": values.liveness_probe.period_seconds,
                "timeoutSeconds": values.liveness_probe.timeout_seconds,
                "failureThreshold": values.liveness_probe.failure_threshold,
            },
            "readinessProbe": {
                "httpGet": {
                    "path": values.readiness_probe.path,
                    "port": values.readiness_probe.port,
                },
                "initialDelaySeconds": values.readiness_probe.initial_delay_seconds,
                "periodSeconds": values.readiness_probe.period_seconds,
                "timeoutSeconds": values.readiness_probe.timeout_seconds,
                "successThreshold": values.readiness_probe.success_threshold,
            },
            "nodeSelector": values.node_selector,
            "tolerations": values.tolerations,
            "affinity": values.affinity,
        }

        if values.autoscaling.target_memory_utilization:
            values_data["autoscaling"]["targetMemoryUtilizationPercentage"] = values.autoscaling.target_memory_utilization

        if values.env:
            values_data["env"] = values.env

        if values.volumes:
            values_data["volumes"] = values.volumes

        if values.volume_mounts:
            values_data["volumeMounts"] = values.volume_mounts

        if values.extra_config:
            values_data.update(values.extra_config)

        return cast(str, yaml.dump(values_data, default_flow_style=False, sort_keys=False))

    def _generate_helpers_template(self, config: HelmConfig) -> str:
        """Generate _helpers.tpl content."""
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

    def _generate_deployment_template(self, config: HelmConfig) -> str:
        """Generate deployment.yaml template."""
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

    def _generate_service_template(self, config: HelmConfig) -> str:
        """Generate service.yaml template."""
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

    def _generate_serviceaccount_template(self, config: HelmConfig) -> str:
        """Generate serviceaccount.yaml template."""
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

    def _generate_hpa_template(self, config: HelmConfig) -> str:
        """Generate hpa.yaml template."""
        name = config.chart.name
        return f'''{{{{- if .Values.autoscaling.enabled }}}}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{{{- include "{name}.fullname" . }}}}
  labels:
    {{{{- include "{name}.labels" . | nindent 4 }}}}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{{{- include "{name}.fullname" . }}}}
  minReplicas: {{{{ .Values.autoscaling.minReplicas }}}}
  maxReplicas: {{{{ .Values.autoscaling.maxReplicas }}}}
  metrics:
    {{{{- if .Values.autoscaling.targetCPUUtilizationPercentage }}}}
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{{{ .Values.autoscaling.targetCPUUtilizationPercentage }}}}
    {{{{- end }}}}
    {{{{- if .Values.autoscaling.targetMemoryUtilizationPercentage }}}}
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: {{{{ .Values.autoscaling.targetMemoryUtilizationPercentage }}}}
    {{{{- end }}}}
{{{{- end }}}}
'''

    def _generate_ingress_template(self, config: HelmConfig) -> str:
        """Generate ingress.yaml template."""
        name = config.chart.name
        return f'''{{{{- if .Values.ingress.enabled -}}}}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{{{- include "{name}.fullname" . }}}}
  labels:
    {{{{- include "{name}.labels" . | nindent 4 }}}}
  {{{{- with .Values.ingress.annotations }}}}
  annotations:
    {{{{- toYaml . | nindent 4 }}}}
  {{{{- end }}}}
spec:
  {{{{- if .Values.ingress.className }}}}
  ingressClassName: {{{{ .Values.ingress.className }}}}
  {{{{- end }}}}
  {{{{- if .Values.ingress.tls }}}}
  tls:
    {{{{- range .Values.ingress.tls }}}}
    - hosts:
        {{{{- range .hosts }}}}
        - {{{{ . | quote }}}}
        {{{{- end }}}}
      secretName: {{{{ .secretName }}}}
    {{{{- end }}}}
  {{{{- end }}}}
  rules:
    {{{{- range .Values.ingress.hosts }}}}
    - host: {{{{ .host | quote }}}}
      http:
        paths:
          {{{{- range .paths }}}}
          - path: {{{{ .path }}}}
            pathType: {{{{ .pathType }}}}
            backend:
              service:
                name: {{{{- include "{name}.fullname" $ }}}}
                port:
                  number: {{{{ $.Values.service.port }}}}
          {{{{- end }}}}
    {{{{- end }}}}
{{{{- end }}}}
'''

    def _generate_networkpolicy_template(self, config: HelmConfig) -> str:
        """Generate networkpolicy.yaml template."""
        name = config.chart.name
        return f'''{{{{- if .Values.networkPolicy.enabled -}}}}
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{{{- include "{name}.fullname" . }}}}
  labels:
    {{{{- include "{name}.labels" . | nindent 4 }}}}
spec:
  podSelector:
    matchLabels:
      {{{{- include "{name}.selectorLabels" . | nindent 6 }}}}
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector: {{{{}}}}
      ports:
        - protocol: TCP
          port: {{{{ .Values.service.port }}}}
  egress:
    - to:
        - namespaceSelector: {{{{}}}}
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
{{{{- end }}}}
'''

    def _generate_pdb_template(self, config: HelmConfig) -> str:
        """Generate pdb.yaml template."""
        name = config.chart.name
        return f'''{{{{- if .Values.podDisruptionBudget.enabled -}}}}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{{{- include "{name}.fullname" . }}}}
  labels:
    {{{{- include "{name}.labels" . | nindent 4 }}}}
spec:
  {{{{- if .Values.podDisruptionBudget.minAvailable }}}}
  minAvailable: {{{{ .Values.podDisruptionBudget.minAvailable }}}}
  {{{{- end }}}}
  {{{{- if .Values.podDisruptionBudget.maxUnavailable }}}}
  maxUnavailable: {{{{ .Values.podDisruptionBudget.maxUnavailable }}}}
  {{{{- end }}}}
  selector:
    matchLabels:
      {{{{- include "{name}.selectorLabels" . | nindent 6 }}}}
{{{{- end }}}}
'''

    def _generate_configmap_template(self, config: HelmConfig) -> str:
        """Generate configmap.yaml template."""
        name = config.chart.name
        return f'''{{{{- if .Values.configMap.enabled -}}}}
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{{{- include "{name}.fullname" . }}}}
  labels:
    {{{{- include "{name}.labels" . | nindent 4 }}}}
data:
  {{{{- range $key, $value := .Values.configMap.data }}}}
  {{{{ $key }}}}: |
    {{{{ $value | nindent 4 }}}}
  {{{{- end }}}}
{{{{- end }}}}
'''

    def _generate_secret_template(self, config: HelmConfig) -> str:
        """Generate secret.yaml template."""
        name = config.chart.name
        return f'''{{{{- if .Values.secret.enabled -}}}}
apiVersion: v1
kind: Secret
metadata:
  name: {{{{- include "{name}.fullname" . }}}}
  labels:
    {{{{- include "{name}.labels" . | nindent 4 }}}}
type: {{{{ .Values.secret.type | default "Opaque" }}}}
data:
  {{{{- range $key, $value := .Values.secret.data }}}}
  {{{{ $key }}}}: {{{{ $value | b64enc }}}}
  {{{{- end }}}}
{{{{- end }}}}
'''

    def _generate_notes_template(self, config: HelmConfig) -> str:
        """Generate NOTES.txt content."""
        name = config.chart.name
        return f'''1. Get the application URL by running these commands:
{{{{- if .Values.ingress.enabled }}}}
{{{{- range $host := .Values.ingress.hosts }}}}
  {{{{- range .paths }}}}
  http{{{{ if $.Values.ingress.tls }}}}s{{{{ end }}}}://{{{{ $host.host }}}}{{{{ .path }}}}
  {{{{- end }}}}
{{{{- end }}}}
{{{{- else if contains "NodePort" .Values.service.type }}}}
  export NODE_PORT=$(kubectl get --namespace {{{{ .Release.Namespace }}}} -o jsonpath="{{{{.spec.ports[0].nodePort}}}}" services {{{{- include "{name}.fullname" . }}}})
  export NODE_IP=$(kubectl get nodes --namespace {{{{ .Release.Namespace }}}} -o jsonpath="{{{{.items[0].status.addresses[0].address}}}}")
  echo http://$NODE_IP:$NODE_PORT
{{{{- else if contains "LoadBalancer" .Values.service.type }}}}
     NOTE: It may take a few minutes for the LoadBalancer IP to be available.
           You can watch its status by running 'kubectl get --namespace {{{{ .Release.Namespace }}}} svc -w {{{{- include "{name}.fullname" . }}}}'
  export SERVICE_IP=$(kubectl get svc --namespace {{{{ .Release.Namespace }}}} {{{{- include "{name}.fullname" . }}}} --template "{{{{{{range (index .status.loadBalancer.ingress 0)}}}}{{{{.}}}}{{{{end}}}}}}")
  echo http://$SERVICE_IP:{{{{ .Values.service.port }}}}
{{{{- else if contains "ClusterIP" .Values.service.type }}}}
  export POD_NAME=$(kubectl get pods --namespace {{{{ .Release.Namespace }}}} -l "app.kubernetes.io/name={{{{- include "{name}.name" . }}}},app.kubernetes.io/instance={{{{ .Release.Name }}}}" -o jsonpath="{{{{.items[0].metadata.name}}}}")
  export CONTAINER_PORT=$(kubectl get pod --namespace {{{{ .Release.Namespace }}}} $POD_NAME -o jsonpath="{{{{.spec.containers[0].ports[0].containerPort}}}}")
  echo "Visit http://127.0.0.1:8080 to use your application"
  kubectl --namespace {{{{ .Release.Namespace }}}} port-forward $POD_NAME 8080:$CONTAINER_PORT
{{{{- end }}}}
'''

    def _generate_test_template(self, config: HelmConfig) -> str:
        """Generate test-connection.yaml template."""
        name = config.chart.name
        return f'''apiVersion: v1
kind: Pod
metadata:
  name: "{{{{- include "{name}.fullname" . }}}}-test-connection"
  labels:
    {{{{- include "{name}.labels" . | nindent 4 }}}}
  annotations:
    "helm.sh/hook": test
spec:
  containers:
    - name: wget
      image: busybox
      command: ['wget']
      args: ['{{{{- include "{name}.fullname" . }}}}:{{{{ .Values.service.port }}}}']
  restartPolicy: Never
'''

    def _generate_helmignore(self) -> str:
        """Generate .helmignore content."""
        return '''# Patterns to ignore when building packages.
# This supports shell glob matching, relative path matching, and
# negation (prefixed with !). Only one pattern per line.
.DS_Store
# Common VCS dirs
.git/
.gitignore
.bzr/
.bzrignore
.hg/
.hgignore
.svn/
# Common backup files
*.swp
*.bak
*.tmp
*.orig
*~
# Various IDEs
.project
.idea/
*.tmproj
.vscode/
# Test files
tests/
# Documentation
*.md
!README.md
'''

    def _validate_chart(self, chart_files: Dict[str, str], config: HelmConfig) -> List[str]:
        """Validate the generated chart for common issues."""
        issues: List[str] = []

        if "Chart.yaml" not in chart_files:
            issues.append("Missing Chart.yaml")

        if "values.yaml" not in chart_files:
            issues.append("Missing values.yaml")

        if "templates/deployment.yaml" not in chart_files:
            issues.append("Missing deployment template")

        if "templates/_helpers.tpl" not in chart_files:
            issues.append("Missing _helpers.tpl - chart naming may be inconsistent")

        chart_yaml = chart_files.get("Chart.yaml", "")
        if "version:" not in chart_yaml:
            issues.append("Chart.yaml missing version")
        if "appVersion:" not in chart_yaml:
            issues.append("Chart.yaml missing appVersion")

        values_yaml = chart_files.get("values.yaml", "")
        if "resources:" not in values_yaml:
            issues.append("values.yaml missing resource definitions")

        return issues

    def _calculate_best_practice_score(self, chart_files: Dict[str, str], config: HelmConfig) -> float:
        """Calculate a best practice score for the generated chart."""
        score = 0.0
        max_score = 0.0

        # Essential files present
        max_score += 20
        essential_files = ["Chart.yaml", "values.yaml", "templates/deployment.yaml", "templates/service.yaml"]
        for f in essential_files:
            if f in chart_files:
                score += 5

        # Helper template
        max_score += 10
        if "templates/_helpers.tpl" in chart_files:
            score += 10

        # Security context defined
        max_score += 15
        values_yaml = chart_files.get("values.yaml", "")
        if "securityContext:" in values_yaml:
            score += 15

        # Resources defined
        max_score += 15
        if "resources:" in values_yaml and "limits:" in values_yaml:
            score += 15

        # Health probes
        max_score += 15
        if "livenessProbe:" in values_yaml and "readinessProbe:" in values_yaml:
            score += 15

        # Service account
        max_score += 10
        if "templates/serviceaccount.yaml" in chart_files:
            score += 10

        # Tests
        max_score += 10
        if "templates/tests/test-connection.yaml" in chart_files:
            score += 10

        # Documentation
        max_score += 5
        if "templates/NOTES.txt" in chart_files:
            score += 5

        return (score / max_score) * 100 if max_score > 0 else 0.0

    def save_to_directory(self, chart: GeneratedHelmChart, output_dir: Optional[str] = None) -> str:
        """
        Save generated Helm chart to directory.

        Args:
            chart: Generated Helm chart to save
            output_dir: Override output directory

        Returns:
            Path to the saved chart directory
        """
        target_dir = output_dir or self.output_dir
        chart_name = chart.id.rsplit("-", 1)[0]
        chart_dir = os.path.join(target_dir, chart_name)

        for file_path, content in chart.chart_files.items():
            full_path = os.path.join(chart_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

        return chart_dir
