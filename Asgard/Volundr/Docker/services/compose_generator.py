"""
Docker Compose Generator Service

Generates docker-compose.yml files with service orchestration,
networking, and volume configurations.
"""

import hashlib
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Docker.models.docker_models import (
    ComposeConfig,
    GeneratedDockerConfig,
)


class ComposeGenerator:
    """Generates docker-compose.yml from configuration."""

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the compose generator.

        Args:
            output_dir: Directory for saving generated compose files
        """
        self.output_dir = output_dir or "."

    def generate(self, config: ComposeConfig) -> GeneratedDockerConfig:
        """
        Generate a docker-compose.yml based on the provided configuration.

        Args:
            config: Compose configuration

        Returns:
            GeneratedDockerConfig with generated content
        """
        config_json = config.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        config_id = f"compose-{config_hash}"

        compose_dict: Dict[str, Any] = {}

        services: Dict[str, Any] = {}
        for svc in config.services:
            svc_dict: Dict[str, Any] = {}

            if svc.image:
                svc_dict["image"] = svc.image

            if svc.build:
                svc_dict["build"] = svc.build

            if svc.ports:
                svc_dict["ports"] = svc.ports

            if svc.environment:
                svc_dict["environment"] = svc.environment

            if svc.env_file:
                svc_dict["env_file"] = svc.env_file

            if svc.volumes:
                svc_dict["volumes"] = svc.volumes

            if svc.depends_on:
                svc_dict["depends_on"] = svc.depends_on

            if svc.networks:
                svc_dict["networks"] = svc.networks

            if svc.restart:
                svc_dict["restart"] = svc.restart

            if svc.healthcheck:
                svc_dict["healthcheck"] = svc.healthcheck

            if svc.deploy:
                svc_dict["deploy"] = svc.deploy

            if svc.labels:
                svc_dict["labels"] = svc.labels

            if svc.command:
                svc_dict["command"] = svc.command

            services[svc.name] = svc_dict

        compose_dict["services"] = services

        if config.networks:
            networks: Dict[str, Any] = {}
            for net in config.networks:
                if net.external:
                    networks[net.name] = {"external": True}
                else:
                    net_dict: Dict[str, Any] = {"driver": net.driver}
                    if net.ipam:
                        net_dict["ipam"] = net.ipam
                    networks[net.name] = net_dict
            compose_dict["networks"] = networks

        if config.volumes:
            volumes: Dict[str, Any] = {}
            for vol in config.volumes:
                if vol.external:
                    volumes[vol.name] = {"external": True}
                else:
                    vol_dict: Dict[str, Any] = {"driver": vol.driver}
                    if vol.driver_opts:
                        vol_dict["driver_opts"] = vol.driver_opts
                    volumes[vol.name] = vol_dict
            compose_dict["volumes"] = volumes

        if config.configs:
            compose_dict["configs"] = config.configs

        if config.secrets:
            compose_dict["secrets"] = config.secrets

        compose_content = yaml.dump(compose_dict, default_flow_style=False, sort_keys=False, allow_unicode=True)

        validation_results = self._validate_compose(compose_dict, config)
        best_practice_score = self._calculate_best_practice_score(compose_dict, config)

        return GeneratedDockerConfig(
            id=config_id,
            config_hash=config_hash,
            compose_content=compose_content,
            validation_results=validation_results,
            best_practice_score=best_practice_score,
            created_at=datetime.now(),
        )

    def _validate_compose(self, compose_dict: Dict[str, Any], config: ComposeConfig) -> List[str]:
        """Validate the generated compose file for common issues."""
        issues: List[str] = []

        if not compose_dict.get("services"):
            issues.append("Compose file has no services defined")

        for svc in config.services:
            svc_config = compose_dict.get("services", {}).get(svc.name, {})

            if not svc_config.get("image") and not svc_config.get("build"):
                issues.append(f"Service '{svc.name}' has neither image nor build defined")

            if not svc_config.get("restart"):
                issues.append(f"Service '{svc.name}' has no restart policy")

            for dep in svc.depends_on:
                if dep not in [s.name for s in config.services]:
                    issues.append(f"Service '{svc.name}' depends on undefined service '{dep}'")

        return issues

    def _calculate_best_practice_score(self, compose_dict: Dict[str, Any], config: ComposeConfig) -> float:
        """Calculate a best practice score for the generated compose file."""
        score = 0.0
        max_score = 0.0

        services = compose_dict.get("services", {})

        for svc_name, svc_config in services.items():
            max_score += 20
            if svc_config.get("restart"):
                score += 20

            max_score += 15
            if svc_config.get("healthcheck"):
                score += 15

            max_score += 15
            if svc_config.get("deploy", {}).get("resources"):
                score += 15

            max_score += 10
            if svc_config.get("labels"):
                score += 10

        max_score += 20
        if config.networks:
            score += 20
        elif any(svc.networks for svc in config.services):
            score += 10

        max_score += 20
        if config.volumes:
            score += 20
        elif any(svc.volumes for svc in config.services):
            score += 10

        return (score / max_score) * 100 if max_score > 0 else 0.0

    def save_to_file(
        self, docker_config: GeneratedDockerConfig, output_dir: Optional[str] = None, filename: str = "docker-compose.yml"
    ) -> str:
        """
        Save generated docker-compose.yml to file.

        Args:
            docker_config: Generated Docker config to save
            output_dir: Override output directory
            filename: Compose filename

        Returns:
            Path to the saved file
        """
        target_dir = output_dir or self.output_dir
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(docker_config.compose_content or "")

        return file_path
