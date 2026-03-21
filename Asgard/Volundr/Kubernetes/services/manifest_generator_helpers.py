from typing import Any, Dict, List

from Asgard.Volundr.Kubernetes.models.kubernetes_models import (
    EnvironmentType,
    ManifestConfig,
    SecurityProfile,
    WorkloadType,
)


def generate_service(config: ManifestConfig, base_labels: Dict[str, str]) -> Dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": f"{config.name}-service", "namespace": config.namespace, "labels": base_labels, "annotations": config.annotations},
        "spec": {
            "selector": {"app": config.name},
            "ports": [
                {"name": port.name, "port": port.service_port or port.container_port, "targetPort": port.container_port, "protocol": port.protocol}
                for port in config.ports
            ],
            "type": "ClusterIP",
        },
    }


def generate_configmap(config: ManifestConfig, base_labels: Dict[str, str], cm_name: str) -> Dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": cm_name, "namespace": config.namespace, "labels": base_labels, "annotations": config.annotations},
        "data": {
            "example.conf": f"# Configuration for {config.name}\napp_name: {config.name}\nenvironment: {config.environment.value}\n",
        },
    }


def generate_secret(config: ManifestConfig, base_labels: Dict[str, str], secret_name: str) -> Dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": secret_name, "namespace": config.namespace, "labels": base_labels, "annotations": config.annotations},
        "type": "Opaque",
        "data": {},
    }


def generate_network_policy(config: ManifestConfig, base_labels: Dict[str, str]) -> Dict[str, Any]:
    ingress_ports = [
        {"protocol": port.protocol, "port": port.container_port}
        for port in config.ports
    ]

    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": f"{config.name}-network-policy", "namespace": config.namespace, "labels": base_labels},
        "spec": {
            "podSelector": {"matchLabels": {"app": config.name}},
            "policyTypes": ["Ingress", "Egress"],
            "ingress": [{"from": [{"namespaceSelector": {"matchLabels": {"name": config.namespace}}}], "ports": ingress_ports}],
            "egress": [{"to": [], "ports": [{"protocol": "TCP", "port": 53}, {"protocol": "UDP", "port": 53}]}],
        },
    }


def generate_pdb(config: ManifestConfig, base_labels: Dict[str, str]) -> Dict[str, Any]:
    return {
        "apiVersion": "policy/v1",
        "kind": "PodDisruptionBudget",
        "metadata": {"name": f"{config.name}-pdb", "namespace": config.namespace, "labels": base_labels},
        "spec": {"selector": {"matchLabels": {"app": config.name}}, "minAvailable": max(1, config.replicas // 2)},
    }


def validate_manifests(
    manifests: Dict[str, Dict[str, Any]], config: ManifestConfig
) -> List[str]:
    issues: List[str] = []

    workload_kinds = ["Deployment", "StatefulSet", "DaemonSet"]
    workload_manifest = next(
        (m for m in manifests.values() if m.get("kind") in workload_kinds), None
    )

    if workload_manifest:
        containers = (
            workload_manifest.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("containers", [])
        )
        for container in containers:
            resources = container.get("resources", {})
            if not resources.get("limits"):
                issues.append(f"Container {container.get('name')} missing resource limits")
            if not resources.get("requests"):
                issues.append(f"Container {container.get('name')} missing resource requests")

    if config.security_profile in [SecurityProfile.ENHANCED, SecurityProfile.STRICT, SecurityProfile.ZERO_TRUST]:
        if workload_manifest:
            containers = (
                workload_manifest.get("spec", {})
                .get("template", {})
                .get("spec", {})
                .get("containers", [])
            )
            for container in containers:
                sec_ctx = container.get("securityContext", {})
                if not sec_ctx.get("runAsNonRoot"):
                    issues.append(f"Container {container.get('name')} not configured to run as non-root")
                if not sec_ctx.get("readOnlyRootFilesystem"):
                    issues.append(f"Container {container.get('name')} not using read-only root filesystem")

    if workload_manifest:
        containers = (
            workload_manifest.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("containers", [])
        )
        for container in containers:
            if not container.get("livenessProbe"):
                issues.append(f"Container {container.get('name')} missing liveness probe")
            if not container.get("readinessProbe"):
                issues.append(f"Container {container.get('name')} missing readiness probe")

    return issues


def calculate_best_practice_score(
    manifests: Dict[str, Dict[str, Any]], config: ManifestConfig
) -> float:
    score = 0.0
    max_score = 0.0

    workload_kinds = ["Deployment", "StatefulSet", "DaemonSet"]
    workload_manifest = next(
        (m for m in manifests.values() if m.get("kind") in workload_kinds), None
    )

    if workload_manifest:
        containers = (
            workload_manifest.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("containers", [])
        )

        for container in containers:
            max_score += 20
            resources = container.get("resources", {})
            if resources.get("limits") and resources.get("requests"):
                score += 20
            elif resources.get("limits") or resources.get("requests"):
                score += 10

            max_score += 25
            sec_ctx = container.get("securityContext", {})
            if sec_ctx.get("runAsNonRoot"):
                score += 8
            if sec_ctx.get("readOnlyRootFilesystem"):
                score += 8
            if not sec_ctx.get("allowPrivilegeEscalation", True):
                score += 9

            max_score += 20
            if container.get("livenessProbe"):
                score += 10
            if container.get("readinessProbe"):
                score += 10

    max_score += 15
    if any("networkpolicy" in name for name in manifests.keys()):
        score += 15

    max_score += 10
    if any("service" in name for name in manifests.keys()):
        score += 10

    max_score += 10
    if config.environment == EnvironmentType.PRODUCTION:
        if any("poddisruptionbudget" in name for name in manifests.keys()):
            score += 10
    else:
        score += 10

    return (score / max_score) * 100 if max_score > 0 else 0.0
