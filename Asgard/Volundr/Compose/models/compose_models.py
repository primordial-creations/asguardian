"""
Compose Models for Configuration Generation

Provides Pydantic models for configuring and generating
docker-compose files with best practices.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class RestartPolicy(str, Enum):
    """Container restart policies."""
    NO = "no"
    ALWAYS = "always"
    ON_FAILURE = "on-failure"
    UNLESS_STOPPED = "unless-stopped"


class NetworkDriver(str, Enum):
    """Docker network drivers."""
    BRIDGE = "bridge"
    HOST = "host"
    OVERLAY = "overlay"
    MACVLAN = "macvlan"
    NONE = "none"


class VolumeDriver(str, Enum):
    """Docker volume drivers."""
    LOCAL = "local"
    NFS = "nfs"
    CIFS = "cifs"


class LogDriver(str, Enum):
    """Docker logging drivers."""
    JSON_FILE = "json-file"
    SYSLOG = "syslog"
    JOURNALD = "journald"
    FLUENTD = "fluentd"
    AWSLOGS = "awslogs"
    GCPLOGS = "gcplogs"


class HealthCheckConfig(BaseModel):
    """Container health check configuration."""
    test: List[str] = Field(description="Health check command")
    interval: str = Field(default="30s", description="Check interval")
    timeout: str = Field(default="10s", description="Check timeout")
    retries: int = Field(default=3, description="Number of retries")
    start_period: str = Field(default="10s", description="Start period")
    start_interval: str = Field(default="5s", description="Start interval")


class ResourceLimits(BaseModel):
    """Container resource limits."""
    cpus: str = Field(default="0.5", description="CPU limit")
    memory: str = Field(default="512M", description="Memory limit")
    pids: Optional[int] = Field(default=None, description="PID limit")


class ResourceReservations(BaseModel):
    """Container resource reservations."""
    cpus: str = Field(default="0.25", description="CPU reservation")
    memory: str = Field(default="256M", description="Memory reservation")


class DeployResources(BaseModel):
    """Deploy resource configuration."""
    limits: ResourceLimits = Field(default_factory=ResourceLimits, description="Resource limits")
    reservations: ResourceReservations = Field(
        default_factory=ResourceReservations, description="Resource reservations"
    )


class DeployConfig(BaseModel):
    """Docker Compose deploy configuration."""
    replicas: int = Field(default=1, description="Number of replicas")
    resources: DeployResources = Field(default_factory=DeployResources, description="Resource config")
    restart_policy: Dict[str, Any] = Field(
        default_factory=lambda: {"condition": "on-failure", "max_attempts": 3},
        description="Restart policy"
    )
    update_config: Dict[str, Any] = Field(
        default_factory=lambda: {"parallelism": 1, "delay": "10s", "order": "start-first"},
        description="Update configuration"
    )
    rollback_config: Dict[str, Any] = Field(
        default_factory=lambda: {"parallelism": 1, "delay": "10s"},
        description="Rollback configuration"
    )
    labels: Dict[str, str] = Field(default_factory=dict, description="Deploy labels")


class LoggingConfig(BaseModel):
    """Container logging configuration."""
    driver: LogDriver = Field(default=LogDriver.JSON_FILE, description="Log driver")
    options: Dict[str, str] = Field(
        default_factory=lambda: {"max-size": "10m", "max-file": "3"},
        description="Driver options"
    )


class BuildConfig(BaseModel):
    """Docker build configuration."""
    context: str = Field(default=".", description="Build context")
    dockerfile: str = Field(default="Dockerfile", description="Dockerfile path")
    args: Dict[str, str] = Field(default_factory=dict, description="Build arguments")
    target: Optional[str] = Field(default=None, description="Build target stage")
    cache_from: List[str] = Field(default_factory=list, description="Cache sources")
    labels: Dict[str, str] = Field(default_factory=dict, description="Image labels")


class PortMapping(BaseModel):
    """Port mapping configuration."""
    target: int = Field(description="Container port")
    published: Optional[Union[int, str]] = Field(default=None, description="Host port")
    protocol: str = Field(default="tcp", description="Protocol (tcp/udp)")
    mode: str = Field(default="host", description="Port mode (host/ingress)")


class VolumeMount(BaseModel):
    """Volume mount configuration."""
    type: str = Field(default="volume", description="Mount type (volume/bind/tmpfs)")
    source: str = Field(description="Source (volume name or host path)")
    target: str = Field(description="Mount target in container")
    read_only: bool = Field(default=False, description="Read-only mount")
    consistency: str = Field(default="consistent", description="Mount consistency")


class ComposeService(BaseModel):
    """Docker Compose service configuration."""
    name: str = Field(description="Service name")
    image: Optional[str] = Field(default=None, description="Container image")
    build: Optional[BuildConfig] = Field(default=None, description="Build configuration")
    command: Optional[Union[str, List[str]]] = Field(default=None, description="Override command")
    entrypoint: Optional[Union[str, List[str]]] = Field(default=None, description="Override entrypoint")
    environment: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    env_file: List[str] = Field(default_factory=list, description="Environment files")
    ports: List[Union[str, PortMapping]] = Field(default_factory=list, description="Port mappings")
    volumes: List[Union[str, VolumeMount]] = Field(default_factory=list, description="Volume mounts")
    networks: List[str] = Field(default_factory=list, description="Networks to join")
    depends_on: List[Union[str, Dict[str, Dict[str, str]]]] = Field(
        default_factory=list, description="Service dependencies"
    )
    restart: RestartPolicy = Field(default=RestartPolicy.UNLESS_STOPPED, description="Restart policy")
    healthcheck: Optional[HealthCheckConfig] = Field(default=None, description="Health check")
    deploy: Optional[DeployConfig] = Field(default=None, description="Deploy configuration")
    logging: Optional[LoggingConfig] = Field(default=None, description="Logging configuration")
    labels: Dict[str, str] = Field(default_factory=dict, description="Container labels")
    hostname: Optional[str] = Field(default=None, description="Container hostname")
    container_name: Optional[str] = Field(default=None, description="Container name")
    user: Optional[str] = Field(default=None, description="User to run as")
    working_dir: Optional[str] = Field(default=None, description="Working directory")
    stdin_open: bool = Field(default=False, description="Keep stdin open")
    tty: bool = Field(default=False, description="Allocate TTY")
    privileged: bool = Field(default=False, description="Privileged mode")
    read_only: bool = Field(default=False, description="Read-only root filesystem")
    security_opt: List[str] = Field(default_factory=list, description="Security options")
    cap_add: List[str] = Field(default_factory=list, description="Capabilities to add")
    cap_drop: List[str] = Field(default_factory=list, description="Capabilities to drop")
    sysctls: Dict[str, str] = Field(default_factory=dict, description="Sysctl settings")
    ulimits: Dict[str, Any] = Field(default_factory=dict, description="Ulimit settings")
    extra_hosts: List[str] = Field(default_factory=list, description="Extra /etc/hosts entries")
    secrets: List[str] = Field(default_factory=list, description="Secrets to inject")
    configs: List[str] = Field(default_factory=list, description="Configs to inject")


class IpamConfig(BaseModel):
    """IPAM configuration for networks."""
    driver: str = Field(default="default", description="IPAM driver")
    config: List[Dict[str, str]] = Field(default_factory=list, description="IPAM config")


class ComposeNetwork(BaseModel):
    """Docker Compose network configuration."""
    name: str = Field(description="Network name")
    driver: NetworkDriver = Field(default=NetworkDriver.BRIDGE, description="Network driver")
    driver_opts: Dict[str, str] = Field(default_factory=dict, description="Driver options")
    external: bool = Field(default=False, description="Is external network")
    internal: bool = Field(default=False, description="Internal network only")
    attachable: bool = Field(default=False, description="Attachable network")
    ipam: Optional[IpamConfig] = Field(default=None, description="IPAM configuration")
    labels: Dict[str, str] = Field(default_factory=dict, description="Network labels")


class ComposeVolume(BaseModel):
    """Docker Compose volume configuration."""
    name: str = Field(description="Volume name")
    driver: VolumeDriver = Field(default=VolumeDriver.LOCAL, description="Volume driver")
    driver_opts: Dict[str, str] = Field(default_factory=dict, description="Driver options")
    external: bool = Field(default=False, description="Is external volume")
    labels: Dict[str, str] = Field(default_factory=dict, description="Volume labels")


class ComposeSecret(BaseModel):
    """Docker Compose secret configuration."""
    name: str = Field(description="Secret name")
    file: Optional[str] = Field(default=None, description="Secret file path")
    external: bool = Field(default=False, description="Is external secret")
    environment: Optional[str] = Field(default=None, description="Environment variable source")


class ComposeConfigEntry(BaseModel):
    """Docker Compose config entry."""
    name: str = Field(description="Config name")
    file: str = Field(description="Config file path")
    external: bool = Field(default=False, description="Is external config")


class ComposeConfig(BaseModel):
    """Docker Compose extension configuration."""
    x_common_env: Dict[str, str] = Field(default_factory=dict, description="Common environment vars")
    x_common_labels: Dict[str, str] = Field(default_factory=dict, description="Common labels")
    x_logging: Optional[LoggingConfig] = Field(default=None, description="Common logging")


class ComposeProject(BaseModel):
    """Complete Docker Compose project configuration."""
    name: str = Field(description="Project name")
    version: str = Field(
        default="3.8",
        description=(
            "DEPRECATED and never emitted: the Compose Specification "
            "obsoletes the top-level version key (VOL-COMPOSE-0001)"
        ),
    )
    edge_services: List[str] = Field(
        default_factory=list,
        description=(
            "Only these services may publish ports on all interfaces; "
            "published ports of every other service are rewritten to bind "
            "loopback (127.0.0.1) — RESEARCH_10 §5.4. Empty list keeps "
            "legacy behavior (no rewriting), but datastore exposure is "
            "still flagged (VOL-COMPOSE-EXPOSED)."
        ),
    )
    auto_healthchecks: bool = Field(
        default=True,
        description=(
            "Auto-generate healthchecks for well-known images (postgres, "
            "redis, mysql, mariadb, mongo) so depends_on can be gated on "
            "condition: service_healthy (RESEARCH_10 §5.1)"
        ),
    )
    services: List[ComposeService] = Field(description="Services to define")
    networks: List[ComposeNetwork] = Field(default_factory=list, description="Networks to define")
    volumes: List[ComposeVolume] = Field(default_factory=list, description="Volumes to define")
    secrets: List[ComposeSecret] = Field(default_factory=list, description="Secrets to define")
    configs: List[ComposeConfigEntry] = Field(default_factory=list, description="Configs to define")
    extensions: ComposeConfig = Field(default_factory=ComposeConfig, description="Extension fields")


class GeneratedComposeConfig(BaseModel):
    """Result of Compose configuration generation."""
    id: str = Field(description="Unique configuration ID")
    config_hash: str = Field(description="Hash of the configuration")
    compose_content: str = Field(description="Generated docker-compose.yaml content")
    override_content: Optional[str] = Field(default=None, description="Override file content")
    validation_results: List[str] = Field(default_factory=list, description="Validation issues found")
    best_practice_score: float = Field(ge=0, le=100, description="Best practice compliance score")
    score_report: Optional[Any] = Field(
        default=None,
        description="Composite ScoreReport (plan 07): dimensions, grades, veto, receipts",
    )
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    file_path: Optional[str] = Field(default=None, description="Path where config was saved")

    @property
    def has_issues(self) -> bool:
        """Check if there are validation issues."""
        return len(self.validation_results) > 0
