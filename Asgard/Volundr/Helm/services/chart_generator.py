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
from Asgard.Volundr.Helm.services.chart_generator_helpers import (
    generate_helpers_template,
    generate_deployment_template,
    generate_service_template,
    generate_serviceaccount_template,
    generate_hpa_template,
    generate_ingress_template,
    generate_networkpolicy_template,
    generate_pdb_template,
    generate_configmap_template,
    generate_secret_template,
    generate_notes_template,
    generate_test_template,
    generate_helmignore,
    validate_chart,
    calculate_best_practice_score,  # noqa: F401  (deprecated, kept for API compat)
)
from Asgard.Volundr.Validation.models.rule_registry import default_registry
from Asgard.Volundr.Validation.models.validation_models import (
    ValidationCategory,
    ValidationResult,
    ValidationSeverity,
)
from Asgard.Volundr.Validation.services.scoring_engine import ScoringEngine


def _issues_to_findings(issues: List[str], target: str) -> List[ValidationResult]:
    """Convert 'RULE-ID: message' issue strings into scoreable findings
    (mirrors GitOps.services.argocd_generator._issues_to_findings)."""
    registry = default_registry()
    findings: List[ValidationResult] = []
    for issue in issues:
        rule_id, sep, message = issue.partition(":")
        rule_id = rule_id.strip()
        rule = registry.get(rule_id) if sep else None
        if rule is not None:
            findings.append(ValidationResult(
                rule_id=rule_id,
                message=message.strip(),
                severity=rule.severity.to_validation_severity(),
                category=rule.category,
                resource_name=target,
                suggestion=rule.remediation or None,
                context={"target": target},
            ))
        else:
            findings.append(ValidationResult(
                rule_id="helm-check",
                message=issue,
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.BEST_PRACTICE,
                resource_name=target,
                context={"target": target},
            ))
    return findings


class ChartGenerator:
    """Generates Helm charts from configuration."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or "charts"

    def generate(self, config: HelmConfig) -> GeneratedHelmChart:
        config_json = config.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        chart_id = f"{config.chart.name}-{config_hash}"

        chart_files: Dict[str, str] = {}

        values_data = self._build_values_data(config)
        chart_files["Chart.yaml"] = self._generate_chart_yaml(config)
        chart_files["values.yaml"] = cast(
            str, yaml.dump(values_data, default_flow_style=False, sort_keys=False)
        )
        chart_files["values.schema.json"] = self._generate_values_schema(values_data)
        chart_files["templates/deployment.yaml"] = generate_deployment_template(config)
        chart_files["templates/service.yaml"] = generate_service_template(config)

        if config.generate_helpers:
            chart_files["templates/_helpers.tpl"] = generate_helpers_template(config)

        if config.generate_notes:
            chart_files["templates/NOTES.txt"] = generate_notes_template(config)

        if config.include_service_account:
            chart_files["templates/serviceaccount.yaml"] = generate_serviceaccount_template(config)

        if config.include_hpa:
            chart_files["templates/hpa.yaml"] = generate_hpa_template(config)

        if config.values.ingress.enabled or config.chart.name:
            chart_files["templates/ingress.yaml"] = generate_ingress_template(config)

        if config.include_network_policy:
            chart_files["templates/networkpolicy.yaml"] = generate_networkpolicy_template(config)

        if config.include_pdb:
            chart_files["templates/pdb.yaml"] = generate_pdb_template(config)

        if config.include_configmap:
            chart_files["templates/configmap.yaml"] = generate_configmap_template(config)

        if config.include_secret:
            chart_files["templates/secret.yaml"] = generate_secret_template(config)

        if config.generate_tests:
            chart_files["templates/tests/test-connection.yaml"] = generate_test_template(config)

        chart_files[".helmignore"] = generate_helmignore()

        validation_results = validate_chart(chart_files, config)
        # Never grade the generator's own intent (plan 07): route the
        # structural findings through the shared composite scorer instead
        # of the legacy fixed-weight percentage.
        findings = _issues_to_findings(validation_results, config.chart.name)
        score_report = ScoringEngine().score(findings, resources=[config.chart.name])
        best_practice_score = score_report.composite

        return GeneratedHelmChart(
            id=chart_id,
            config_hash=config_hash,
            chart_files=chart_files,
            validation_results=validation_results,
            best_practice_score=best_practice_score,
            created_at=datetime.now(),
        )

    def _generate_chart_yaml(self, config: HelmConfig) -> str:
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
        values_data = self._build_values_data(config)
        return cast(str, yaml.dump(values_data, default_flow_style=False, sort_keys=False))

    def _build_values_data(self, config: HelmConfig) -> Dict[str, object]:
        values = config.values
        values_data: Dict[str, object] = {
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
            "podSecurityContext": {"fsGroup": values.pod_security_context.fs_group},
            "securityContext": {
                "runAsNonRoot": values.security_context.run_as_non_root,
                "runAsUser": values.security_context.run_as_user,
                "readOnlyRootFilesystem": values.security_context.read_only_root_filesystem,
                "allowPrivilegeEscalation": values.security_context.allow_privilege_escalation,
                "capabilities": {"drop": ["ALL"]},
            },
            "service": {"type": values.service.type, "port": values.service.port},
            "ingress": {
                "enabled": values.ingress.enabled,
                "className": values.ingress.class_name or "",
                "annotations": values.ingress.annotations,
                "hosts": values.ingress.hosts or [
                    {"host": "chart-example.local", "paths": [{"path": "/", "pathType": "ImplementationSpecific"}]}
                ],
                "tls": values.ingress.tls,
            },
            "resources": {
                "limits": {"cpu": values.resources.limits.cpu, "memory": values.resources.limits.memory},
                "requests": {"cpu": values.resources.requests.cpu, "memory": values.resources.requests.memory},
            },
            "autoscaling": {
                "enabled": values.autoscaling.enabled,
                "minReplicas": values.autoscaling.min_replicas,
                "maxReplicas": values.autoscaling.max_replicas,
                "targetCPUUtilizationPercentage": values.autoscaling.target_cpu_utilization,
            },
            "livenessProbe": {
                "httpGet": {"path": values.liveness_probe.path, "port": values.liveness_probe.port},
                "initialDelaySeconds": values.liveness_probe.initial_delay_seconds,
                "periodSeconds": values.liveness_probe.period_seconds,
                "timeoutSeconds": values.liveness_probe.timeout_seconds,
                "failureThreshold": values.liveness_probe.failure_threshold,
            },
            "readinessProbe": {
                "httpGet": {"path": values.readiness_probe.path, "port": values.readiness_probe.port},
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

        return values_data

    def _generate_values_schema(self, values_data: Dict[str, object]) -> str:
        """Generate a draft-07 ``values.schema.json`` from the rendered
        ``values.yaml`` structure (plan 05: `helm lint`/`helm install
        --dry-run` catch malformed values before they reach the cluster).

        Types/required-ness are inferred from the generator's own output
        rather than hand-maintained, so the schema never drifts from the
        values it is meant to validate.
        """
        import json as _json

        def _schema_for(value: object) -> Dict[str, object]:
            if isinstance(value, bool):
                return {"type": "boolean"}
            if isinstance(value, int):
                return {"type": "integer"}
            if isinstance(value, float):
                return {"type": "number"}
            if isinstance(value, str):
                return {"type": "string"}
            if isinstance(value, list):
                item_schema = _schema_for(value[0]) if value else {}
                return {"type": "array", "items": item_schema}
            if isinstance(value, dict):
                properties = {k: _schema_for(v) for k, v in value.items()}
                return {
                    "type": "object",
                    "properties": properties,
                    "additionalProperties": True,
                }
            return {}

        schema: Dict[str, object] = {
            "$schema": "https://json-schema.org/draft-07/schema#",
            "title": "Values",
            "type": "object",
            "properties": {k: _schema_for(v) for k, v in values_data.items()},
            "additionalProperties": True,
        }
        return _json.dumps(schema, indent=2) + "\n"

    def save_to_directory(self, chart: GeneratedHelmChart, output_dir: Optional[str] = None) -> str:
        target_dir = output_dir or self.output_dir
        chart_name = chart.id.rsplit("-", 1)[0]
        chart_dir = os.path.join(target_dir, chart_name)

        for file_path, content in chart.chart_files.items():
            full_path = os.path.join(chart_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

        return chart_dir
