"""
Internal Canonical Model (ICM) for the four-tier validation engine.

Version-specific input shapes (K8s workload kinds, Compose services,
pipeline jobs) are normalized into these canonical models so semantic
rules are written exactly once. Two value primitives support honest
handling of unknown data:

- ``COMPUTED`` — the value exists but is unknowable until apply time
  (Terraform ``after_unknown``, templated values).
- ``TAINTED`` — the node came from a schema version newer than the engine
  knows (version skew); assertions must not fail-open on it.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class _Sentinel:
    """Singleton sentinel base for unknown-value primitives."""

    _label = "<sentinel>"

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return self._label

    def __bool__(self) -> bool:
        # Sentinels are never truthy: default-deny means an unknown value
        # can never satisfy a presence-of-safety assertion by accident.
        return False


class Computed(_Sentinel):
    _label = "<computed>"


class Tainted(_Sentinel):
    _label = "<tainted>"


COMPUTED = Computed()
TAINTED = Tainted()


def is_computed(value: Any) -> bool:
    return isinstance(value, Computed)


def is_tainted(value: Any) -> bool:
    return isinstance(value, Tainted)


def is_unknown(value: Any) -> bool:
    return isinstance(value, _Sentinel)


class CanonicalContainer(BaseModel):
    """A container normalized from any K8s workload kind."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(default="unknown")
    image: Any = Field(default=None)
    init: bool = Field(default=False, description="Is an initContainer")
    run_as_non_root: Any = Field(default=None)
    privileged: Any = Field(default=None)
    allow_privilege_escalation: Any = Field(default=None)
    read_only_root_filesystem: Any = Field(default=None)
    capabilities_drop: Any = Field(default=None)
    seccomp_profile_type: Any = Field(default=None)
    has_resource_limits: Any = Field(default=None)
    has_resource_requests: Any = Field(default=None)
    tainted: bool = Field(default=False)
    source_path: str = Field(default="", description="Dot path in the source doc")
    line_number: Optional[int] = Field(default=None)


class CanonicalWorkload(BaseModel):
    """A K8s workload normalized across all five workload kinds."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    kind: str
    name: str = Field(default="unknown")
    api_version: str = Field(default="")
    containers: List[CanonicalContainer] = Field(default_factory=list)
    pod_seccomp_profile_type: Any = Field(default=None)
    automount_service_account_token: Any = Field(default=None)
    host_network: Any = Field(default=None)
    host_pid: Any = Field(default=None)
    host_ipc: Any = Field(default=None)
    pod_spec_path: str = Field(default="spec", description="Dot path to the PodSpec")
    tainted: bool = Field(default=False)
    file_path: Optional[str] = Field(default=None)
    line_number: Optional[int] = Field(default=None)


class CanonicalNetworkRule(BaseModel):
    """A normalized network exposure rule (Service port, Compose port, Ingress)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source: str = Field(default="")
    host_interface: Optional[str] = Field(default=None)
    host_port: Any = Field(default=None)
    container_port: Any = Field(default=None)
    tainted: bool = Field(default=False)


class CanonicalComposeService(BaseModel):
    """A Compose service normalized from the Compose Specification."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    image: Any = Field(default=None)
    privileged: Any = Field(default=None)
    network_mode: Any = Field(default=None)
    ports: List[CanonicalNetworkRule] = Field(default_factory=list)
    read_only: Any = Field(default=None)
    cap_drop: Any = Field(default=None)
    tainted: bool = Field(default=False)
    line_number: Optional[int] = Field(default=None)


class CanonicalPipelineStep(BaseModel):
    """A single pipeline step (e.g. a GH Actions `uses:`/`run:` step)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(default="")
    uses: Any = Field(default=None)
    run: Any = Field(default=None)
    tainted: bool = Field(default=False)
    line_number: Optional[int] = Field(default=None)


class CanonicalPipelineJob(BaseModel):
    """A pipeline job normalized from CI YAML (GH Actions first)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    permissions: Any = Field(default=None, description="Job-level permissions block")
    workflow_permissions: Any = Field(default=None, description="Workflow-level permissions")
    timeout_minutes: Any = Field(default=None)
    steps: List[CanonicalPipelineStep] = Field(default_factory=list)
    tainted: bool = Field(default=False)
    line_number: Optional[int] = Field(default=None)


class CanonicalDocument(BaseModel):
    """Container for everything normalized out of one source document."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    workloads: List[CanonicalWorkload] = Field(default_factory=list)
    compose_services: List[CanonicalComposeService] = Field(default_factory=list)
    pipeline_jobs: List[CanonicalPipelineJob] = Field(default_factory=list)
    raw: Dict[str, Any] = Field(default_factory=dict)
