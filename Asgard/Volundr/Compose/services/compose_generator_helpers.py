from typing import Any, Dict, List, Optional, Union

from Asgard.Volundr.Compose.models.compose_models import (
    ComposeProject,
    ComposeService,
    ComposeNetwork,
    ComposeVolume,
    DeployConfig,
    LoggingConfig,
    RestartPolicy,
)

#: Healthchecks for well-known images (RESEARCH_10 §5.1 table).
KNOWN_IMAGE_HEALTHCHECKS: Dict[str, List[str]] = {
    "postgres": ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres}"],
    "redis": ["CMD", "redis-cli", "ping"],
    "mysql": ["CMD", "mysqladmin", "ping", "-h", "localhost"],
    "mariadb": ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"],
    "mongo": ["CMD-SHELL", 'mongosh --eval "db.adminCommand(\'ping\')" --quiet'],
}

#: Images treated as datastores for the port-exposure policy (§5.4).
DATASTORE_IMAGES = tuple(KNOWN_IMAGE_HEALTHCHECKS)


def image_family(image: Optional[str]) -> Optional[str]:
    """The well-known image family of a service image, if any."""
    if not image:
        return None
    repo = image.split("@", 1)[0].rsplit("/", 1)[-1].split(":", 1)[0].lower()
    return repo if repo in KNOWN_IMAGE_HEALTHCHECKS else None


def auto_healthcheck_dict(service: ComposeService) -> Optional[Dict[str, Any]]:
    """Auto-generated healthcheck for a well-known image (else None)."""
    family = image_family(service.image)
    if family is None:
        return None
    return {
        "test": KNOWN_IMAGE_HEALTHCHECKS[family],
        "interval": "10s",
        "timeout": "5s",
        "retries": 5,
        "start_period": "10s",
    }


def has_effective_healthcheck(service: ComposeService, project: Optional[ComposeProject]) -> bool:
    if service.healthcheck is not None:
        return True
    return bool(
        project is not None
        and project.auto_healthchecks
        and image_family(service.image)
    )


def _loopback_port(port: str) -> str:
    """Rewrite an all-interfaces 'HOST:CONTAINER' publish to loopback."""
    parts = port.split(":")
    if len(parts) == 2 and parts[0] and not parts[0].startswith("["):
        return f"127.0.0.1:{port}"
    return port


def build_service_dict(
    service: ComposeService, project: Optional[ComposeProject] = None
) -> Dict[str, Any]:
    svc: Dict[str, Any] = {}
    if service.image:
        svc["image"] = service.image
    if service.build:
        build_dict: Dict[str, Any] = {"context": service.build.context}
        if service.build.dockerfile != "Dockerfile":
            build_dict["dockerfile"] = service.build.dockerfile
        if service.build.args:
            build_dict["args"] = service.build.args
        if service.build.target:
            build_dict["target"] = service.build.target
        if service.build.cache_from:
            build_dict["cache_from"] = service.build.cache_from
        if service.build.labels:
            build_dict["labels"] = service.build.labels
        svc["build"] = build_dict
    if service.container_name:
        svc["container_name"] = service.container_name
    if service.hostname:
        svc["hostname"] = service.hostname
    if service.command:
        svc["command"] = service.command
    if service.entrypoint:
        svc["entrypoint"] = service.entrypoint
    if service.environment:
        svc["environment"] = service.environment
    if service.env_file:
        svc["env_file"] = service.env_file
    if service.ports:
        ports = format_ports(service.ports)
        # Loopback/edge port policy (RESEARCH_10 §5.4): when edge services
        # are designated, every non-edge published port binds loopback.
        if (
            project is not None
            and project.edge_services
            and service.name not in project.edge_services
        ):
            ports = [_loopback_port(p) for p in ports]
        svc["ports"] = ports
    if service.volumes:
        svc["volumes"] = format_volumes(service.volumes)
    if service.networks:
        svc["networks"] = service.networks
    if service.depends_on:
        svc["depends_on"] = build_depends_on(service.depends_on, project)
    if service.restart != RestartPolicy.NO:
        svc["restart"] = service.restart.value
    if service.healthcheck:
        svc["healthcheck"] = {
            "test": service.healthcheck.test,
            "interval": service.healthcheck.interval,
            "timeout": service.healthcheck.timeout,
            "retries": service.healthcheck.retries,
            "start_period": service.healthcheck.start_period,
        }
    elif project is not None and project.auto_healthchecks:
        auto = auto_healthcheck_dict(service)
        if auto is not None:
            svc["healthcheck"] = auto
    if service.deploy:
        svc["deploy"] = build_deploy_dict(service.deploy)
    if service.logging:
        svc["logging"] = build_logging_dict(service.logging)
    if service.labels:
        svc["labels"] = service.labels
    if service.user:
        svc["user"] = service.user
    if service.working_dir:
        svc["working_dir"] = service.working_dir
    if service.stdin_open:
        svc["stdin_open"] = True
    if service.tty:
        svc["tty"] = True
    if service.privileged:
        svc["privileged"] = True
    if service.read_only:
        svc["read_only"] = True
    if service.security_opt:
        svc["security_opt"] = service.security_opt
    if service.cap_add:
        svc["cap_add"] = service.cap_add
    if service.cap_drop:
        svc["cap_drop"] = service.cap_drop
    if service.sysctls:
        svc["sysctls"] = service.sysctls
    if service.ulimits:
        svc["ulimits"] = service.ulimits
    if service.extra_hosts:
        svc["extra_hosts"] = service.extra_hosts
    if service.secrets:
        svc["secrets"] = service.secrets
    if service.configs:
        svc["configs"] = service.configs
    return svc


def build_depends_on(
    depends_on: List[Union[str, Dict[str, Dict[str, str]]]],
    project: Optional[ComposeProject],
) -> Union[List[Any], Dict[str, Dict[str, str]]]:
    """Healthcheck-gated depends_on (RESEARCH_10 §5.1).

    String dependencies whose target has an (explicit or auto-generated)
    healthcheck render long-form with ``condition: service_healthy``;
    others get ``condition: service_started``. Explicit dict entries pass
    through untouched. Without project context, legacy short form is kept.
    """
    if project is None:
        return depends_on
    services_by_name = {s.name: s for s in project.services}
    gated: Dict[str, Dict[str, str]] = {}
    for dep in depends_on:
        if isinstance(dep, dict):
            for name, condition in dep.items():
                gated[name] = dict(condition)
            continue
        target = services_by_name.get(dep)
        healthy = target is not None and has_effective_healthcheck(target, project)
        gated[dep] = {
            "condition": "service_healthy" if healthy else "service_started"
        }
    return gated


def build_deploy_dict(deploy: DeployConfig) -> Dict[str, Any]:
    return {
        "replicas": deploy.replicas,
        "resources": {
            "limits": {"cpus": deploy.resources.limits.cpus, "memory": deploy.resources.limits.memory},
            "reservations": {"cpus": deploy.resources.reservations.cpus, "memory": deploy.resources.reservations.memory},
        },
        "restart_policy": deploy.restart_policy,
        "update_config": deploy.update_config,
        "rollback_config": deploy.rollback_config,
    }


def build_logging_dict(logging: LoggingConfig) -> Dict[str, Any]:
    return {"driver": logging.driver.value, "options": logging.options}


def build_network_dict(network: ComposeNetwork) -> Dict[str, Any]:
    net: Dict[str, Any] = {}
    if network.external:
        net["external"] = True
        return net
    if network.driver.value != "bridge":
        net["driver"] = network.driver.value
    if network.driver_opts:
        net["driver_opts"] = network.driver_opts
    if network.internal:
        net["internal"] = True
    if network.attachable:
        net["attachable"] = True
    if network.ipam:
        net["ipam"] = {"driver": network.ipam.driver, "config": network.ipam.config}
    if network.labels:
        net["labels"] = network.labels
    return net if net else {}


def build_volume_dict(volume: ComposeVolume) -> Dict[str, Any]:
    vol: Dict[str, Any] = {}
    if volume.external:
        vol["external"] = True
        return vol
    if volume.driver.value != "local":
        vol["driver"] = volume.driver.value
    if volume.driver_opts:
        vol["driver_opts"] = volume.driver_opts
    if volume.labels:
        vol["labels"] = volume.labels
    return vol if vol else {}


def format_ports(ports: List[Union[str, Any]]) -> List[str]:
    formatted = []
    for port in ports:
        if isinstance(port, str):
            formatted.append(port)
        else:
            port_str = str(port.target)
            if port.published:
                port_str = f"{port.published}:{port_str}"
            if port.protocol != "tcp":
                port_str += f"/{port.protocol}"
            formatted.append(port_str)
    return formatted


def format_volumes(volumes: List[Union[str, Any]]) -> List[str]:
    formatted = []
    for vol in volumes:
        if isinstance(vol, str):
            formatted.append(vol)
        else:
            vol_str = f"{vol.source}:{vol.target}"
            if vol.read_only:
                vol_str += ":ro"
            formatted.append(vol_str)
    return formatted


def build_override_dict(project: ComposeProject, environment: str) -> Dict[str, Any]:
    # Compose Specification: the top-level `version:` key is obsolete and
    # deliberately not emitted (VOL-COMPOSE-0001).
    override: Dict[str, Any] = {"services": {}}
    env_configs = {
        "development": {"replicas": 1, "cpus": "0.5", "memory": "512M"},
        "staging": {"replicas": 2, "cpus": "1", "memory": "1G"},
        "production": {"replicas": 3, "cpus": "2", "memory": "2G"},
    }
    config = env_configs.get(environment, env_configs["development"])
    for service in project.services:
        override["services"][service.name] = {
            "deploy": {
                "replicas": config["replicas"],
                "resources": {"limits": {"cpus": config["cpus"], "memory": config["memory"]}},
            },
            "environment": {"ENVIRONMENT": environment},
        }
    return override


def validate_compose(project: ComposeProject) -> List[str]:
    issues: List[str] = []
    if not project.services:
        issues.append("No services defined")
    for service in project.services:
        if not service.image and not service.build:
            issues.append(f"Service {service.name} has no image or build configuration")
        if service.privileged:
            issues.append(f"Service {service.name} uses privileged mode - security concern")
        if not service.healthcheck:
            issues.append(f"Service {service.name} has no health check defined")
        if service.restart == RestartPolicy.NO:
            issues.append(f"Service {service.name} has no restart policy")
    return issues


def calculate_best_practice_score(project: ComposeProject) -> float:
    if not project.services:
        return 0.0
    total_score = 0.0
    max_score = 0.0
    for service in project.services:
        max_score += 20
        if service.healthcheck:
            total_score += 20
        max_score += 15
        if service.restart != RestartPolicy.NO:
            total_score += 15
        max_score += 15
        if service.deploy and service.deploy.resources:
            total_score += 15
        max_score += 10
        if service.logging:
            total_score += 10
        max_score += 15
        if not service.privileged:
            total_score += 7
        if service.cap_drop:
            total_score += 8
        max_score += 10
        if service.read_only:
            total_score += 10
        max_score += 10
        if service.labels:
            total_score += 10
        max_score += 5
        if service.user:
            total_score += 5
    return (total_score / max_score) * 100 if max_score > 0 else 0.0
