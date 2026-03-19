"""
Docker Compose Project Generator Service

Generates docker-compose.yaml files with best practices,
health checks, resource limits, and proper network configuration.
"""

import hashlib
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Compose.models.compose_models import (
    ComposeProject,
    ComposeService,
    ComposeNetwork,
    ComposeVolume,
    GeneratedComposeConfig,
    HealthCheckConfig,
    DeployConfig,
    LoggingConfig,
    RestartPolicy,
)


class ComposeProjectGenerator:
    """Generates Docker Compose project configurations."""

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the compose generator.

        Args:
            output_dir: Directory for saving generated configurations
        """
        self.output_dir = output_dir or "."

    def generate(self, project: ComposeProject) -> GeneratedComposeConfig:
        """
        Generate docker-compose.yaml from project configuration.

        Args:
            project: Compose project configuration

        Returns:
            GeneratedComposeConfig with generated content
        """
        config_json = project.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        project_id = f"{project.name}-{config_hash}"

        compose_dict = self._build_compose_dict(project)
        compose_content = yaml.dump(compose_dict, default_flow_style=False, sort_keys=False)

        validation_results = self._validate_compose(project)
        best_practice_score = self._calculate_best_practice_score(project)

        return GeneratedComposeConfig(
            id=project_id,
            config_hash=config_hash,
            compose_content=compose_content,
            validation_results=validation_results,
            best_practice_score=best_practice_score,
            created_at=datetime.now(),
        )

    def generate_with_override(
        self,
        project: ComposeProject,
        environment: str = "development",
    ) -> GeneratedComposeConfig:
        """
        Generate docker-compose.yaml with environment-specific override.

        Args:
            project: Compose project configuration
            environment: Target environment

        Returns:
            GeneratedComposeConfig with base and override content
        """
        result = self.generate(project)

        override_dict = self._build_override_dict(project, environment)
        override_content = yaml.dump(override_dict, default_flow_style=False, sort_keys=False)

        return GeneratedComposeConfig(
            id=result.id,
            config_hash=result.config_hash,
            compose_content=result.compose_content,
            override_content=override_content,
            validation_results=result.validation_results,
            best_practice_score=result.best_practice_score,
            created_at=result.created_at,
        )

    def generate_simple(
        self,
        name: str,
        services: List[Dict[str, Any]],
    ) -> GeneratedComposeConfig:
        """
        Generate a simple docker-compose.yaml from service definitions.

        Args:
            name: Project name
            services: List of service configurations

        Returns:
            GeneratedComposeConfig with generated content
        """
        compose_services = []
        for svc in services:
            compose_services.append(ComposeService(
                name=svc.get("name", "service"),
                image=svc.get("image"),
                ports=svc.get("ports", []),
                environment=svc.get("environment", {}),
                volumes=svc.get("volumes", []),
                depends_on=svc.get("depends_on", []),
                healthcheck=HealthCheckConfig(
                    test=["CMD", "curl", "-f", f"http://localhost:{svc.get('port', 8080)}/health"],
                ) if svc.get("healthcheck", True) else None,
            ))

        project = ComposeProject(name=name, services=compose_services)
        return self.generate(project)

    def _build_compose_dict(self, project: ComposeProject) -> Dict[str, Any]:
        """Build the docker-compose.yaml dictionary."""
        compose: Dict[str, Any] = {
            "version": project.version,
            "name": project.name,
        }

        # Add extension fields
        if project.extensions.x_common_env:
            compose["x-common-env"] = {"environment": project.extensions.x_common_env}

        if project.extensions.x_common_labels:
            compose["x-common-labels"] = {"labels": project.extensions.x_common_labels}

        if project.extensions.x_logging:
            compose["x-logging"] = self._build_logging_dict(project.extensions.x_logging)

        # Build services
        compose["services"] = {}
        for service in project.services:
            compose["services"][service.name] = self._build_service_dict(service)

        # Build networks
        if project.networks:
            compose["networks"] = {}
            for network in project.networks:
                compose["networks"][network.name] = self._build_network_dict(network)

        # Build volumes
        if project.volumes:
            compose["volumes"] = {}
            for volume in project.volumes:
                compose["volumes"][volume.name] = self._build_volume_dict(volume)

        # Build secrets
        if project.secrets:
            compose["secrets"] = {}
            for secret in project.secrets:
                secret_dict: Dict[str, Any] = {}
                if secret.file:
                    secret_dict["file"] = secret.file
                if secret.external:
                    secret_dict["external"] = True
                if secret.environment:
                    secret_dict["environment"] = secret.environment
                compose["secrets"][secret.name] = secret_dict

        # Build configs
        if project.configs:
            compose["configs"] = {}
            for config in project.configs:
                config_dict: Dict[str, Any] = {"file": config.file}
                if config.external:
                    config_dict["external"] = True
                compose["configs"][config.name] = config_dict

        return compose

    def _build_service_dict(self, service: ComposeService) -> Dict[str, Any]:
        """Build service dictionary."""
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
            svc["ports"] = self._format_ports(service.ports)

        if service.volumes:
            svc["volumes"] = self._format_volumes(service.volumes)

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
            svc["deploy"] = self._build_deploy_dict(service.deploy)

        if service.logging:
            svc["logging"] = self._build_logging_dict(service.logging)

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

    def _build_deploy_dict(self, deploy: DeployConfig) -> Dict[str, Any]:
        """Build deploy configuration dictionary."""
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

    def _build_logging_dict(self, logging: LoggingConfig) -> Dict[str, Any]:
        """Build logging configuration dictionary."""
        return {
            "driver": logging.driver.value,
            "options": logging.options,
        }

    def _build_network_dict(self, network: ComposeNetwork) -> Dict[str, Any]:
        """Build network configuration dictionary."""
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

    def _build_volume_dict(self, volume: ComposeVolume) -> Dict[str, Any]:
        """Build volume configuration dictionary."""
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

    def _format_ports(self, ports: List[Union[str, Any]]) -> List[str]:
        """Format port mappings as strings."""
        formatted = []
        for port in ports:
            if isinstance(port, str):
                formatted.append(port)
            else:
                # Handle PortMapping objects
                port_str = str(port.target)
                if port.published:
                    port_str = f"{port.published}:{port_str}"
                if port.protocol != "tcp":
                    port_str += f"/{port.protocol}"
                formatted.append(port_str)
        return formatted

    def _format_volumes(self, volumes: List[Union[str, Any]]) -> List[str]:
        """Format volume mounts as strings."""
        formatted = []
        for vol in volumes:
            if isinstance(vol, str):
                formatted.append(vol)
            else:
                # Handle VolumeMount objects
                vol_str = f"{vol.source}:{vol.target}"
                if vol.read_only:
                    vol_str += ":ro"
                formatted.append(vol_str)
        return formatted

    def _build_override_dict(
        self, project: ComposeProject, environment: str
    ) -> Dict[str, Any]:
        """Build environment-specific override dictionary."""
        override: Dict[str, Any] = {"version": project.version, "services": {}}

        env_configs = {
            "development": {
                "replicas": 1,
                "cpus": "0.5",
                "memory": "512M",
            },
            "staging": {
                "replicas": 2,
                "cpus": "1",
                "memory": "1G",
            },
            "production": {
                "replicas": 3,
                "cpus": "2",
                "memory": "2G",
            },
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

    def _validate_compose(self, project: ComposeProject) -> List[str]:
        """Validate the compose configuration."""
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

    def _calculate_best_practice_score(self, project: ComposeProject) -> float:
        """Calculate a best practice score for the compose configuration."""
        if not project.services:
            return 0.0

        total_score = 0.0
        max_score = 0.0

        for service in project.services:
            # Health check
            max_score += 20
            if service.healthcheck:
                total_score += 20

            # Restart policy
            max_score += 15
            if service.restart != RestartPolicy.NO:
                total_score += 15

            # Resource limits
            max_score += 15
            if service.deploy and service.deploy.resources:
                total_score += 15

            # Logging configuration
            max_score += 10
            if service.logging:
                total_score += 10

            # Security (no privileged, drop capabilities)
            max_score += 15
            if not service.privileged:
                total_score += 7
            if service.cap_drop:
                total_score += 8

            # Read-only root filesystem
            max_score += 10
            if service.read_only:
                total_score += 10

            # Labels for organization
            max_score += 10
            if service.labels:
                total_score += 10

            # Non-root user
            max_score += 5
            if service.user:
                total_score += 5

        return (total_score / max_score) * 100 if max_score > 0 else 0.0

    def save_to_file(
        self,
        config: GeneratedComposeConfig,
        output_dir: Optional[str] = None,
        filename: str = "docker-compose.yaml",
    ) -> str:
        """
        Save generated compose configuration to file.

        Args:
            config: Generated compose config to save
            output_dir: Override output directory
            filename: Output filename

        Returns:
            Path to the saved file
        """
        target_dir = output_dir or self.output_dir
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(config.compose_content)

        if config.override_content:
            override_path = os.path.join(target_dir, "docker-compose.override.yaml")
            with open(override_path, "w", encoding="utf-8") as f:
                f.write(config.override_content)

        return file_path
