from typing import Any, Dict, List, Union

from Asgard.Volundr.Compose.models.compose_models import (
    ComposeProject,
    ComposeService,
    ComposeNetwork,
    ComposeVolume,
    DeployConfig,
    LoggingConfig,
    RestartPolicy,
)


def build_service_dict(service: ComposeService) -> Dict[str, Any]:
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
        svc["ports"] = format_ports(service.ports)

    if service.volumes:
        svc["volumes"] = format_volumes(service.volumes)

    if service.networks:
        svc["networks"] = service.networks

    if service.depends_on:
        svc["depends_on"] = service.depends_on

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


def build_deploy_dict(deploy: DeployConfig) -> Dict[str, Any]:
    return {
        "replicas": deploy.replicas,
        "resources": {
            "limits": {
                "cpus": deploy.resources.limits.cpus,
                "memory": deploy.resources.limits.memory,
            },
            "reservations": {
                "cpus": deploy.resources.reservations.cpus,
                "memory": deploy.resources.reservations.memory,
            },
        },
        "restart_policy": deploy.restart_policy,
        "update_config": deploy.update_config,
        "rollback_config": deploy.rollback_config,
    }


def build_logging_dict(logging: LoggingConfig) -> Dict[str, Any]:
    return {
        "driver": logging.driver.value,
        "options": logging.options,
    }


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
        net["ipam"] = {
            "driver": network.ipam.driver,
            "config": network.ipam.config,
        }

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
    override: Dict[str, Any] = {"version": project.version, "services": {}}

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
                "resources": {
                    "limits": {
                        "cpus": config["cpus"],
                        "memory": config["memory"],
                    },
                },
            },
            "environment": {
                "ENVIRONMENT": environment,
            },
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
