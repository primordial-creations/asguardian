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
    DATASTORE_IMAGES,
    build_service_dict,
    build_network_dict,
    build_volume_dict,
    build_logging_dict,
    build_override_dict,
    has_effective_healthcheck,
    image_family,
    validate_compose,
    calculate_best_practice_score,
)
from Asgard.Volundr.Validation.models.validation_models import (
    ValidationCategory,
    ValidationResult,
    ValidationSeverity,
)
from Asgard.Volundr.Validation.services.scoring_engine import ScoringEngine
from Asgard.Volundr.Validation.services.validation_engine import ValidationEngine


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

        # Adversarial validation + composite scoring of the RENDERED
        # artifact (plan 07): the generator never grades its own intent.
        engine_report = ValidationEngine().validate_compose(
            compose_content, source=f"{project.name}.compose.yaml"
        )
        findings = list(engine_report.results)
        findings.extend(self._policy_findings(project, compose_dict))
        validation_results.extend(f"{r.rule_id}: {r.message}" for r in findings)

        score_report = ScoringEngine().score(
            findings, resources=[s.name for s in project.services],
        )

        return GeneratedComposeConfig(
            id=project_id,
            config_hash=config_hash,
            compose_content=compose_content,
            validation_results=validation_results,
            best_practice_score=score_report.composite,
            score_report=score_report,
            created_at=datetime.now(),
        )

    @staticmethod
    def _policy_findings(
        project: ComposeProject, compose_dict: Dict[str, Any]
    ) -> List[ValidationResult]:
        """Compose production-misconfiguration findings (RESEARCH_10 §5)."""
        findings: List[ValidationResult] = []
        rendered_services = compose_dict.get("services", {})
        for service in project.services:
            rendered = rendered_services.get(service.name, {})
            # Datastores must not publish host ports on all interfaces (§5.4).
            if image_family(service.image) in DATASTORE_IMAGES:
                for port in rendered.get("ports", []):
                    port_str = str(port)
                    if ":" in port_str and not port_str.startswith(("127.0.0.1:", "[::1]:", "::1:")):
                        findings.append(ValidationResult(
                            rule_id="VOL-COMPOSE-EXPOSED",
                            message=(
                                f"Datastore service '{service.name}' publishes "
                                f"host port '{port_str}' on all interfaces"
                            ),
                            severity=ValidationSeverity.ERROR,
                            category=ValidationCategory.SECURITY,
                            resource_name=service.name,
                            context={"target": service.name},
                        ))
            # Bind mounts vs named volumes (§5.3).
            for volume in service.volumes:
                if isinstance(volume, str) and volume.split(":", 1)[0].startswith((".", "/", "~")):
                    findings.append(ValidationResult(
                        rule_id="VOL-COMPOSE-0006",
                        message=(
                            f"Service '{service.name}' uses bind mount "
                            f"'{volume}' — prefer a named volume"
                        ),
                        severity=ValidationSeverity.INFO,
                        category=ValidationCategory.BEST_PRACTICE,
                        resource_name=service.name,
                        context={"target": service.name},
                    ))
            # Volume-permission bootstrap guidance (§5.3).
            named_volumes = {v.name for v in project.volumes}
            uses_named = any(
                isinstance(v, str) and v.split(":", 1)[0] in named_volumes
                for v in service.volumes
            )
            if service.user and uses_named:
                findings.append(ValidationResult(
                    rule_id="VOL-COMPOSE-0007",
                    message=(
                        f"Service '{service.name}' runs as '{service.user}' with a "
                        "named volume — fresh volumes are root-owned and may need "
                        "a permission bootstrap"
                    ),
                    severity=ValidationSeverity.HINT,
                    category=ValidationCategory.RELIABILITY,
                    resource_name=service.name,
                    context={"target": service.name},
                ))
            # Healthcheck-gated dependencies (§5.1).
            for dep in service.depends_on:
                if isinstance(dep, str):
                    target = next(
                        (s for s in project.services if s.name == dep), None
                    )
                    if target is not None and not has_effective_healthcheck(target, project):
                        findings.append(ValidationResult(
                            rule_id="VOL-COMPOSE-0008",
                            message=(
                                f"Service '{service.name}' depends on '{dep}' which "
                                "has no healthcheck — startup gating falls back to "
                                "condition: service_started"
                            ),
                            severity=ValidationSeverity.INFO,
                            category=ValidationCategory.RELIABILITY,
                            resource_name=service.name,
                            context={"target": service.name},
                        ))
        return findings

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
            score_report=result.score_report,
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
        # Compose Specification: the top-level `version:` key is obsolete and
        # deliberately not emitted (VOL-COMPOSE-0001).
        compose: Dict[str, Any] = {
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
            compose["services"][service.name] = build_service_dict(service, project)

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
