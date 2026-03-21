"""Helm chart extra template generators + validation/scoring."""

from typing import Dict, List

from Asgard.Volundr.Helm.models.helm_models import HelmConfig


def generate_hpa_template(config: HelmConfig) -> str:
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


def generate_ingress_template(config: HelmConfig) -> str:
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


def generate_networkpolicy_template(config: HelmConfig) -> str:
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


def generate_pdb_template(config: HelmConfig) -> str:
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


def generate_configmap_template(config: HelmConfig) -> str:
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


def generate_secret_template(config: HelmConfig) -> str:
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


def generate_notes_template(config: HelmConfig) -> str:
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


def generate_test_template(config: HelmConfig) -> str:
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


def generate_helmignore() -> str:
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


def validate_chart(chart_files: Dict[str, str], config: HelmConfig) -> List[str]:
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


def calculate_best_practice_score(chart_files: Dict[str, str], config: HelmConfig) -> float:
    score = 0.0
    max_score = 0.0

    max_score += 20
    essential_files = ["Chart.yaml", "values.yaml", "templates/deployment.yaml", "templates/service.yaml"]
    for f in essential_files:
        if f in chart_files:
            score += 5

    max_score += 10
    if "templates/_helpers.tpl" in chart_files:
        score += 10

    max_score += 15
    values_yaml = chart_files.get("values.yaml", "")
    if "securityContext:" in values_yaml:
        score += 15

    max_score += 15
    if "resources:" in values_yaml and "limits:" in values_yaml:
        score += 15

    max_score += 15
    if "livenessProbe:" in values_yaml and "readinessProbe:" in values_yaml:
        score += 15

    max_score += 10
    if "templates/serviceaccount.yaml" in chart_files:
        score += 10

    max_score += 10
    if "templates/tests/test-connection.yaml" in chart_files:
        score += 10

    max_score += 5
    if "templates/NOTES.txt" in chart_files:
        score += 5

    return (score / max_score) * 100 if max_score > 0 else 0.0
