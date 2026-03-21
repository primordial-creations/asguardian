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
from Asgard.Volundr.Compose.services.compose_generator_helpers import (
    build_service_dict,
    build_network_dict,
    build_volume_dict,
    build_logging_dict,
    build_override_dict,
    validate_compose,
    calculate_best_practice_score,
)


class ComposeProjectGenerator:
    """Generates Docker Compose project configurations."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or "."

    def generate(self, project: ComposeProject) -> GeneratedComposeConfig:
        config_json = project.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        project_id = f"{project.name}-{config_hash}"

        compose_dict = self._build_compose_dict(project)
        compose_content = yaml.dump(compose_dict, default_flow_style=False, sort_keys=False)

        validation_results = validate_compose(project)
        best_practice_score = calculate_best_practice_score(project)

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
        result = self.generate(project)

        override_dict = build_override_dict(project, environment)
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
        compose: Dict[str, Any] = {
            "version": project.version,
            "name": project.name,
        }

        if project.extensions.x_common_env:
            compose["x-common-env"] = {"environment": project.extensions.x_common_env}

        if project.extensions.x_common_labels:
            compose["x-common-labels"] = {"labels": project.extensions.x_common_labels}

        if project.extensions.x_logging:
            compose["x-logging"] = build_logging_dict(project.extensions.x_logging)

        compose["services"] = {}
        for service in project.services:
            compose["services"][service.name] = build_service_dict(service)

        if project.networks:
            compose["networks"] = {}
            for network in project.networks:
                compose["networks"][network.name] = build_network_dict(network)

        if project.volumes:
            compose["volumes"] = {}
            for volume in project.volumes:
                compose["volumes"][volume.name] = build_volume_dict(volume)

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

        if project.configs:
            compose["configs"] = {}
            for config in project.configs:
                config_dict: Dict[str, Any] = {"file": config.file}
                if config.external:
                    config_dict["external"] = True
                compose["configs"][config.name] = config_dict

        return compose

    def save_to_file(
        self,
        config: GeneratedComposeConfig,
        output_dir: Optional[str] = None,
        filename: str = "docker-compose.yaml",
    ) -> str:
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
