"""
Tier 3 normalizer: raw K8s manifest dicts -> Internal Canonical Model.

Handles the nested PodSpec paths of all workload kinds so semantic rules
are written once against CanonicalWorkload:

    Pod          spec
    Deployment   spec.template.spec
    StatefulSet  spec.template.spec
    DaemonSet    spec.template.spec
    ReplicaSet   spec.template.spec
    Job          spec.template.spec
    CronJob      spec.jobTemplate.spec.template.spec
"""

from typing import Any, Dict, List, Optional, Set

from Asgard.Volundr.Validation.models.canonical_models import (
    TAINTED,
    CanonicalContainer,
    CanonicalWorkload,
)

POD_SPEC_PATHS: Dict[str, str] = {
    "Pod": "spec",
    "Deployment": "spec.template.spec",
    "StatefulSet": "spec.template.spec",
    "DaemonSet": "spec.template.spec",
    "ReplicaSet": "spec.template.spec",
    "Job": "spec.template.spec",
    "CronJob": "spec.jobTemplate.spec.template.spec",
}

WORKLOAD_KINDS: Set[str] = set(POD_SPEC_PATHS.keys())


def _dig(data: Dict[str, Any], dotted: str) -> Dict[str, Any]:
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return {}
        node = node.get(part, {})
    return node if isinstance(node, dict) else {}


def _normalize_container(
    container: Dict[str, Any],
    pod_sc: Dict[str, Any],
    path: str,
    tainted: bool,
    init: bool,
    line_map: Optional[Dict[str, int]] = None,
) -> CanonicalContainer:
    sc = container.get("securityContext") or {}
    resources = container.get("resources") or {}
    caps = (sc.get("capabilities") or {}).get("drop")
    seccomp = (sc.get("seccompProfile") or {}).get("type")
    pod_seccomp = (pod_sc.get("seccompProfile") or {}).get("type")

    def eff(key: str) -> Any:
        """Container securityContext value, falling back to pod-level."""
        if key in sc:
            return sc[key]
        return pod_sc.get(key)

    value_or_tainted = (lambda v: TAINTED if tainted and v is None else v)
    return CanonicalContainer(
        name=container.get("name", "unknown"),
        image=container.get("image"),
        init=init,
        run_as_non_root=value_or_tainted(eff("runAsNonRoot")),
        privileged=value_or_tainted(sc.get("privileged")),
        allow_privilege_escalation=value_or_tainted(sc.get("allowPrivilegeEscalation")),
        read_only_root_filesystem=value_or_tainted(sc.get("readOnlyRootFilesystem")),
        capabilities_drop=value_or_tainted(caps),
        seccomp_profile_type=value_or_tainted(seccomp or pod_seccomp),
        has_resource_limits=bool(resources.get("limits")),
        has_resource_requests=bool(resources.get("requests")),
        tainted=tainted,
        source_path=path,
        line_number=(line_map or {}).get(path),
    )


def normalize_manifest(
    manifest: Dict[str, Any],
    file_path: Optional[str] = None,
    tainted: bool = False,
    line_map: Optional[Dict[str, int]] = None,
) -> Optional[CanonicalWorkload]:
    """Normalize a single K8s manifest dict into a CanonicalWorkload.

    Returns None for non-workload kinds.
    """
    kind = manifest.get("kind", "")
    if kind not in WORKLOAD_KINDS:
        return None

    pod_spec_path = POD_SPEC_PATHS[kind]
    pod_spec = _dig(manifest, pod_spec_path)
    pod_sc = pod_spec.get("securityContext") or {}
    metadata = manifest.get("metadata") or {}
    line_map = line_map or {}

    containers: List[CanonicalContainer] = []
    for i, c in enumerate(pod_spec.get("containers") or []):
        if isinstance(c, dict):
            path = f"{pod_spec_path}.containers[{i}]"
            containers.append(
                _normalize_container(c, pod_sc, path, tainted, False, line_map)
            )
    for i, c in enumerate(pod_spec.get("initContainers") or []):
        if isinstance(c, dict):
            path = f"{pod_spec_path}.initContainers[{i}]"
            containers.append(
                _normalize_container(c, pod_sc, path, tainted, True, line_map)
            )

    def val(key: str) -> Any:
        v = pod_spec.get(key)
        return TAINTED if tainted and v is None else v

    return CanonicalWorkload(
        kind=kind,
        name=metadata.get("name", "unknown"),
        api_version=manifest.get("apiVersion", ""),
        containers=containers,
        pod_seccomp_profile_type=(pod_sc.get("seccompProfile") or {}).get("type"),
        automount_service_account_token=val("automountServiceAccountToken"),
        host_network=val("hostNetwork"),
        host_pid=val("hostPID"),
        host_ipc=val("hostIPC"),
        pod_spec_path=pod_spec_path,
        tainted=tainted,
        file_path=file_path,
        line_number=line_map.get(""),
    )
