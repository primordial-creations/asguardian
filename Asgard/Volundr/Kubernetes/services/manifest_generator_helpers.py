"""
Companion-resource builders for the hardened Kubernetes manifest generator.

Always-on companions (per NSA/CISA + CIS 5.x):
- dedicated ServiceAccount with automountServiceAccountToken: false
- default-deny NetworkPolicy with explicit port allows + DNS egress carve-out
- PodDisruptionBudget whenever replicas > 1
- headless Service for StatefulSets

The legacy ``validate_manifests`` / ``calculate_best_practice_score``
functions are retained ONLY for backward compatibility; the generator now
delegates all grading to the adversarial ``Asgard.Volundr.Validation``
engine (generators never grade their own intent).
"""

from typing import Any, Dict, List

from Asgard.Volundr.Kubernetes.models.kubernetes_models import ManifestConfig


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


def generate_headless_service(config: ManifestConfig, base_labels: Dict[str, str]) -> Dict[str, Any]:
    """Headless Service backing a StatefulSet's serviceName reference."""
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": f"{config.name}-headless",
            "namespace": config.namespace,
            "labels": base_labels,
        },
        "spec": {
            "clusterIP": "None",
            "selector": {"app": config.name},
            "ports": [
                {"name": port.name, "port": port.service_port or port.container_port, "targetPort": port.container_port, "protocol": port.protocol}
                for port in config.ports
            ],
        },
    }


def generate_service_account(config: ManifestConfig, base_labels: Dict[str, str]) -> Dict[str, Any]:
    """Dedicated per-workload ServiceAccount (CIS 5.1.5/5.1.6)."""
    return {
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {
            "name": config.service_account or config.name,
            "namespace": config.namespace,
            "labels": base_labels,
        },
        "automountServiceAccountToken": False,
    }


def generate_configmap(config: ManifestConfig, base_labels: Dict[str, str], cm_name: str) -> Dict[str, Any]:
    """ConfigMap with real data: explicit configmap_data, else env_vars, else empty."""
    data: Dict[str, str] = {}
    if cm_name in config.configmap_data:
        data = dict(config.configmap_data[cm_name])
    elif config.env_vars:
        data = dict(config.env_vars)
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": cm_name, "namespace": config.namespace, "labels": base_labels, "annotations": config.annotations},
        "data": data,
    }


def generate_secret(config: ManifestConfig, base_labels: Dict[str, str], secret_name: str) -> Dict[str, Any]:
    """Secret with explicit stringData only — never fabricated values.

    An empty Secret triggers a VOL-K8S-0014 completeness finding in the
    generator instead of silently shipping fake material.
    """
    string_data = dict(config.secret_string_data.get(secret_name, {}))
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": secret_name, "namespace": config.namespace, "labels": base_labels, "annotations": config.annotations},
        "type": "Opaque",
        "stringData": string_data,
    }


def generate_network_policy(config: ManifestConfig, base_labels: Dict[str, str]) -> Dict[str, Any]:
    """Always-on default-deny NetworkPolicy (CIS 5.3.2).

    Starts from default-deny for both directions and adds only:
    - ingress from same-namespace pods on the declared container ports
    - DNS egress carve-out (TCP/UDP 53)
    - explicitly declared ``egress_rules``
    """
    ingress: List[Dict[str, Any]] = []
    if config.ports:
        ingress.append({
            "from": [{"podSelector": {}}],
            "ports": [
                {"protocol": port.protocol, "port": port.container_port}
                for port in config.ports
            ],
        })

    egress: List[Dict[str, Any]] = [
        # DNS carve-out: without this a default-deny egress policy breaks
        # service discovery entirely.
        {"ports": [{"protocol": "TCP", "port": 53}, {"protocol": "UDP", "port": 53}]},
    ]
    for rule in config.egress_rules:
        to: List[Dict[str, Any]] = []
        if rule.cidr:
            to.append({"ipBlock": {"cidr": rule.cidr}})
        selector: Dict[str, Any] = {}
        if rule.namespace_labels:
            selector["namespaceSelector"] = {"matchLabels": dict(rule.namespace_labels)}
        if rule.pod_labels:
            selector["podSelector"] = {"matchLabels": dict(rule.pod_labels)}
        if selector:
            to.append(selector)
        entry: Dict[str, Any] = {}
        if to:
            entry["to"] = to
        if rule.ports:
            entry["ports"] = [
                {"protocol": rule.protocol, "port": p} for p in rule.ports
            ]
        if entry:
            egress.append(entry)

    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": f"{config.name}-network-policy", "namespace": config.namespace, "labels": base_labels},
        "spec": {
            "podSelector": {"matchLabels": {"app": config.name}},
            "policyTypes": ["Ingress", "Egress"],
            "ingress": ingress,
            "egress": egress,
        },
    }


def generate_pdb(config: ManifestConfig, base_labels: Dict[str, str]) -> Dict[str, Any]:
    """PodDisruptionBudget — generated whenever replicas > 1, any environment."""
    spec: Dict[str, Any] = {"selector": {"matchLabels": {"app": config.name}}}
    if config.pdb.max_unavailable is not None:
        spec["maxUnavailable"] = config.pdb.max_unavailable
    else:
        spec["minAvailable"] = (
            config.pdb.min_available
            if config.pdb.min_available is not None
            else max(1, config.replicas // 2)
        )
    return {
        "apiVersion": "policy/v1",
        "kind": "PodDisruptionBudget",
        "metadata": {"name": f"{config.name}-pdb", "namespace": config.namespace, "labels": base_labels},
        "spec": spec,
    }


# ---------------------------------------------------------------------------
# DEPRECATED: legacy self-grading kept only for API backward compatibility.
# The generator delegates scoring/validation to Asgard.Volundr.Validation.
# ---------------------------------------------------------------------------

def validate_manifests(
    manifests: Dict[str, Dict[str, Any]], config: ManifestConfig
) -> List[str]:
    """DEPRECATED — use the Validation engine (`ValidationEngine.validate_kubernetes`)."""
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
            sec_ctx = container.get("securityContext", {})
            if not sec_ctx.get("runAsNonRoot"):
                issues.append(f"Container {container.get('name')} not configured to run as non-root")
            if not sec_ctx.get("readOnlyRootFilesystem"):
                issues.append(f"Container {container.get('name')} not using read-only root filesystem")
            if not container.get("livenessProbe"):
                issues.append(f"Container {container.get('name')} missing liveness probe")
            if not container.get("readinessProbe"):
                issues.append(f"Container {container.get('name')} missing readiness probe")

    return issues


def calculate_best_practice_score(
    manifests: Dict[str, Dict[str, Any]], config: ManifestConfig
) -> float:
    """DEPRECATED — use the Validation engine report score instead."""
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
    if config.replicas > 1:
        if any("poddisruptionbudget" in name for name in manifests.keys()):
            score += 10
    else:
        score += 10

    return (score / max_score) * 100 if max_score > 0 else 0.0
