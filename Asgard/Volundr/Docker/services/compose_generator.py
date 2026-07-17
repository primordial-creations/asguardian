"""
DEPRECATED Compose generator shim (plan 03 dedup).

``Asgard.Volundr.Compose`` (ComposeProject + ComposeProjectGenerator) is
the single Compose engine. This module keeps the legacy
``Docker.ComposeGenerator`` API importable for one deprecation cycle by
converting the legacy Docker-module models into Compose-module models and
delegating generation — there is no longer a second implementation.

Legacy behavior preserved for callers:
- ``GeneratedDockerConfig`` result shape (compose_content, id containing
  "compose", validation_results, best_practice_score);
- compose-spec output (the obsolete top-level ``version:`` key is never
  emitted, per VOL-COMPOSE-0001).
"""

import hashlib
import os
import warnings
from datetime import datetime
from typing import Any, Dict, List, Optional

from Asgard.Volundr.Compose.models.compose_models import (
    BuildConfig,
    ComposeNetwork,
    ComposeProject,
    ComposeSecret,
    ComposeConfigEntry,
    ComposeService,
    ComposeVolume,
    DeployConfig,
    HealthCheckConfig,
    IpamConfig,
    LoggingConfig,  # noqa: F401  (re-export parity with the old module)
    NetworkDriver,
    RestartPolicy,
    VolumeDriver,
)
from Asgard.Volundr.Compose.services.compose_generator import (
    ComposeProjectGenerator,
)
from Asgard.Volundr.Docker.models.docker_models import (
    ComposeConfig,
    ComposeServiceConfig,
    GeneratedDockerConfig,
)

_DEPRECATION_MESSAGE = (
    "Asgard.Volundr.Docker.ComposeGenerator is deprecated; use "
    "Asgard.Volundr.Compose.ComposeProjectGenerator (the single Compose "
    "engine). This shim will be removed after one deprecation cycle."
)


def _filter_kwargs(model_cls: Any, data: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only keys the target pydantic model knows."""
    return {k: v for k, v in data.items() if k in model_cls.model_fields}


def _convert_service(svc: ComposeServiceConfig) -> ComposeService:
    healthcheck = None
    if svc.healthcheck:
        healthcheck = HealthCheckConfig(
            **_filter_kwargs(HealthCheckConfig, dict(svc.healthcheck))
        )
    deploy = None
    if svc.deploy:
        deploy = DeployConfig.model_validate(
            _filter_kwargs(DeployConfig, dict(svc.deploy))
        )
    build = None
    if svc.build:
        build = BuildConfig(**_filter_kwargs(BuildConfig, dict(svc.build)))
    try:
        restart = RestartPolicy(svc.restart)
    except ValueError:
        restart = RestartPolicy.UNLESS_STOPPED
    return ComposeService(
        name=svc.name,
        image=svc.image,
        build=build,
        ports=list(svc.ports),
        environment=dict(svc.environment),
        env_file=list(svc.env_file),
        volumes=list(svc.volumes),
        depends_on=list(svc.depends_on),
        networks=list(svc.networks),
        restart=restart,
        healthcheck=healthcheck,
        deploy=deploy,
        labels=dict(svc.labels),
        command=svc.command,
    )


def _convert_project(config: ComposeConfig) -> ComposeProject:
    networks = []
    for net in config.networks:
        try:
            driver = NetworkDriver(net.driver)
        except ValueError:
            driver = NetworkDriver.BRIDGE
        ipam = None
        if net.ipam:
            ipam = IpamConfig(**_filter_kwargs(IpamConfig, dict(net.ipam)))
        networks.append(ComposeNetwork(
            name=net.name, driver=driver, external=net.external, ipam=ipam,
        ))
    volumes = []
    for vol in config.volumes:
        try:
            vol_driver = VolumeDriver(vol.driver)
        except ValueError:
            vol_driver = VolumeDriver.LOCAL
        volumes.append(ComposeVolume(
            name=vol.name, driver=vol_driver,
            driver_opts=dict(vol.driver_opts), external=vol.external,
        ))
    secrets = [
        ComposeSecret(
            name=name,
            file=(value or {}).get("file"),
            external=bool((value or {}).get("external", False)),
        )
        for name, value in config.secrets.items()
    ]
    configs = [
        ComposeConfigEntry(
            name=name,
            file=(value or {}).get("file", ""),
            external=bool((value or {}).get("external", False)),
        )
        for name, value in config.configs.items()
        if (value or {}).get("file") or (value or {}).get("external")
    ]
    return ComposeProject(
        name="compose",
        services=[_convert_service(s) for s in config.services],
        networks=networks,
        volumes=volumes,
        secrets=secrets,
        configs=configs,
        # Legacy Docker-module behavior: no edge/loopback rewriting and no
        # auto-healthchecks — callers migrate to ComposeProject for those.
        auto_healthchecks=False,
    )


class ComposeGenerator:
    """DEPRECATED: delegates to Compose.ComposeProjectGenerator."""

    def __init__(self, output_dir: Optional[str] = None):
        warnings.warn(_DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=2)
        self.output_dir = output_dir or "."
        self._delegate = ComposeProjectGenerator(output_dir=self.output_dir)

    def generate(self, config: ComposeConfig) -> GeneratedDockerConfig:
        config_json = config.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]

        project = _convert_project(config)
        result = self._delegate.generate(project)

        return GeneratedDockerConfig(
            id=f"compose-{config_hash}",
            config_hash=config_hash,
            compose_content=result.compose_content,
            validation_results=result.validation_results,
            best_practice_score=result.best_practice_score,
            score_report=result.score_report,
            created_at=datetime.now(),
        )

    def save_to_file(
        self,
        docker_config: GeneratedDockerConfig,
        output_dir: Optional[str] = None,
        filename: str = "docker-compose.yml",
    ) -> str:
        target_dir = output_dir or self.output_dir
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(docker_config.compose_content or "")
        return file_path


__all__: List[str] = ["ComposeGenerator"]
