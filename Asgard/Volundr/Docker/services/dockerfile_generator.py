"""
Dockerfile Generator Service — hadolint/CIS-Docker aligned (plan 03).

Hardened by construction (RESEARCH_10):
- BuildKit ``# syntax`` directive always first line (§3.6)
- digest pinning for FROM + Renovate pairing (§3.2, DL3006/DL3007)
- BuildKit ``--mount=type=secret`` / ``--mount=type=ssh``; plaintext
  secret-looking ENV/ARG values are REFUSED unless suppressed
  (VOL-DOCKER-SECRET-ENV)
- ``SHELL -o pipefail`` before piped RUNs (DL4006)
- non-root scaffold with ``useradd -l`` / ``adduser -D`` and a high fixed
  UID (§3.3, DL3002/DL3046); numeric USER for distroless
- package-manager hygiene: same-layer cache cleanup, install flags,
  unpinned-package findings (§3.5, DL3008 family)
- cache-friendly COPY ordering (dependency manifests before source);
  ``COPY . .`` triggers .dockerignore generation + finding

Validation and scoring are delegated to the shared Validation engine —
the generator never grades its own intent, only the rendered artifact.
"""

import hashlib
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from Asgard.Volundr.Docker.models.docker_models import (
    BuildStage,
    DockerfileConfig,
    GeneratedDockerConfig,
    NonRootUser,
)
from Asgard.Volundr.Docker.services._package_manager_pass import (
    apply_package_hygiene,
)
from Asgard.Volundr.Validation.models.suppression_models import SuppressionSet
from Asgard.Volundr.Validation.models.validation_models import (
    ValidationCategory,
    ValidationResult,
    ValidationSeverity,
)
from Asgard.Volundr.Validation.services.dockerfile_validator import (
    DockerfileValidator,
)
from Asgard.Volundr.Validation.services.scoring_engine import ScoringEngine
from Asgard.Volundr.Validation.services.suppression_engine import (
    SuppressionEngine,
    append_comment_receipts,
)

#: ENV/ARG names that look like credentials (CIS Docker 4.10).
_SECRET_NAME_RE = re.compile(
    r"(SECRET|TOKEN|PASSWORD|PASSWD|API_?KEY|ACCESS_?KEY|PRIVATE_?KEY|CREDENTIAL)",
    re.IGNORECASE,
)

#: Dependency manifests copied before source for cache-friendly ordering.
_DEPENDENCY_MANIFESTS = (
    "requirements.txt", "requirements-dev.txt", "pyproject.toml", "poetry.lock",
    "Pipfile", "Pipfile.lock", "setup.py", "setup.cfg",
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "go.mod", "go.sum", "Cargo.toml", "Cargo.lock", "Gemfile", "Gemfile.lock",
)

_DEFAULT_DOCKERIGNORE = """\
.git
.gitignore
.dockerignore
Dockerfile*
docker-compose*.yml
docker-compose*.yaml
**/__pycache__
**/*.pyc
.venv
venv
node_modules
dist
build
.env
.env.*
*.pem
*.key
.idea
.vscode
"""

_RENOVATE_SNIPPET = {
    "$schema": "https://docs.renovatebot.com/renovate-schema.json",
    "extends": ["config:recommended", "docker:pinDigests"],
    "packageRules": [
        {
            "matchDatasources": ["docker"],
            "matchUpdateTypes": ["digest", "minor", "patch"],
            "automerge": False,
        }
    ],
}

_SCAN_WORKFLOW = """\
# Volundr scanner pairing (RESEARCH_04): Trivy gate + CycloneDX SBOM.
# Prefer VEX statements over .trivyignore for accepted findings.
name: image-scan
on:
  push:
    branches: [main]
permissions: {}
jobs:
  scan:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4  # pin to a full commit SHA in your repo
      - name: Build image
        run: docker build -t "$IMAGE" .
        env:
          IMAGE: local/scan-target:ci
      - name: Trivy vulnerability scan (fails on HIGH/CRITICAL)
        run: |
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \\
            aquasec/trivy:latest image --exit-code 1 \\
            --severity HIGH,CRITICAL "$IMAGE"
        env:
          IMAGE: local/scan-target:ci
      - name: SBOM (CycloneDX)
        run: |
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \\
            aquasec/trivy:latest image --format cyclonedx \\
            --output sbom.cdx.json "$IMAGE"
        env:
          IMAGE: local/scan-target:ci
"""


class DockerfileGenerator:
    """Generates hardened Dockerfiles from configuration."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or "."

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pinned_from(stage: BuildStage) -> str:
        if not stage.base_image_digest:
            return stage.base_image
        digest = stage.base_image_digest
        if not digest.startswith("sha256:"):
            digest = f"sha256:{digest}"
        base = stage.base_image.split("@", 1)[0]
        return f"{base}@{digest}"

    @staticmethod
    def _is_alpine(image: str) -> bool:
        return "alpine" in image.lower()

    @staticmethod
    def _is_distroless(image: str) -> bool:
        return "distroless" in image.lower() or "scratch" == image.split(":")[0].lower()

    @staticmethod
    def _mount_flags(stage: BuildStage) -> str:
        flags: List[str] = []
        for mount in stage.secret_mounts:
            flag = f"--mount=type=secret,id={mount.id}"
            if mount.target:
                flag += f",target={mount.target}"
            if mount.required:
                flag += ",required=true"
            flags.append(flag)
        if stage.ssh_mount:
            flags.append("--mount=type=ssh")
        return " ".join(flags)

    @staticmethod
    def _ordered_copies(stage: BuildStage) -> Tuple[List[Dict[str, str]], bool]:
        """Cache-friendly ordering: dependency manifests, then the rest,
        with whole-context copies last. Returns (copies, copies_whole_context)."""
        manifests, others, whole = [], [], []
        for copy_cmd in stage.copy_commands:
            src = copy_cmd.get("src", ".")
            base = src.rstrip("/").rsplit("/", 1)[-1]
            if src.strip() == ".":
                whole.append(copy_cmd)
            elif base in _DEPENDENCY_MANIFESTS:
                manifests.append(copy_cmd)
            else:
                others.append(copy_cmd)
        return manifests + others + whole, bool(whole)

    def _scan_secret_env(self, config: DockerfileConfig) -> List[ValidationResult]:
        findings: List[ValidationResult] = []
        candidates: List[Tuple[str, str, str]] = [
            ("ARG", name, value) for name, value in config.args.items()
        ]
        for stage in config.stages:
            candidates.extend(
                (f"ENV (stage '{stage.name}')", name, value)
                for name, value in stage.env_vars.items()
            )
        for where, name, value in candidates:
            if _SECRET_NAME_RE.search(name) and value:
                findings.append(ValidationResult(
                    rule_id="VOL-DOCKER-SECRET-ENV",
                    message=(
                        f"{where} '{name}' looks like a plaintext secret — "
                        "it would be baked into image layers"
                    ),
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.SECURITY,
                    suggestion=(
                        "Use a BuildKit secret mount "
                        "(secret_mounts=[SecretMount(id=...)]) instead."
                    ),
                    context={"target": name},
                ))
        return findings

    # ------------------------------------------------------------------

    def generate(self, config: DockerfileConfig) -> GeneratedDockerConfig:
        """Generate a hardened Dockerfile; refuses plaintext secret ENV/ARG
        values unless explicitly suppressed (VOL-DOCKER-SECRET-ENV)."""
        config_json = config.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        config_id = f"{config.name}-dockerfile-{config_hash}"

        completeness: List[ValidationResult] = []
        content: List[str] = [f"# syntax=docker/dockerfile:{config.syntax_version}"]
        copies_whole_context = False

        for arg_name, arg_default in config.args.items():
            content.append(f"ARG {arg_name}={arg_default}")
        if config.args:
            content.append("")

        for i, stage in enumerate(config.stages):
            is_final = i == len(config.stages) - 1
            from_ref = self._pinned_from(stage)
            distroless = self._is_distroless(stage.base_image)

            if stage.base_image_digest is None:
                completeness.append(ValidationResult(
                    rule_id="VOL-DOCKER-DIGEST",
                    message=(
                        f"Stage '{stage.name}' base image "
                        f"'{stage.base_image}' is pinned by tag, not digest"
                    ),
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.BEST_PRACTICE,
                    context={"target": stage.name},
                ))

            if stage.name:
                content.append(f"FROM {from_ref} AS {stage.name}")
            else:
                content.append(f"FROM {from_ref}")
            content.append(f"WORKDIR {stage.workdir}")
            content.append("")

            # Package hygiene pass over this stage's RUN commands.
            run_commands, pkg_findings = apply_package_hygiene(
                stage.run_commands, stage.name
            )
            completeness.extend(pkg_findings)

            # DL4006: pipefail before piped RUNs (not for distroless: no shell).
            if (
                config.shell_pipefail
                and not distroless
                and any("|" in cmd for cmd in run_commands)
            ):
                shell = "/bin/ash" if self._is_alpine(stage.base_image) else "/bin/bash"
                content.append(f'SHELL ["{shell}", "-o", "pipefail", "-c"]')
                content.append("")

            for env_name, env_value in stage.env_vars.items():
                content.append(f"ENV {env_name}={env_value}")
            if stage.env_vars:
                content.append("")

            if stage.copy_from and stage.copy_src and stage.copy_dst:
                content.append(
                    f"COPY --from={stage.copy_from} {stage.copy_src} {stage.copy_dst}"
                )
                content.append("")

            ordered, whole = self._ordered_copies(stage)
            copies_whole_context = copies_whole_context or whole
            for copy_cmd in ordered:
                src = copy_cmd.get("src", ".")
                dst = copy_cmd.get("dst", ".")
                chown = copy_cmd.get("chown")
                if chown:
                    content.append(f"COPY --chown={chown} {src} {dst}")
                else:
                    content.append(f"COPY {src} {dst}")
            if ordered:
                content.append("")

            mounts = self._mount_flags(stage)
            run_prefix = f"RUN {mounts} " if mounts else "RUN "
            if config.optimize_layers and run_commands:
                combined_run = " && \\\n    ".join(run_commands)
                content.append(f"{run_prefix}{combined_run}")
                content.append("")
            else:
                for run_cmd in run_commands:
                    content.append(f"{run_prefix}{run_cmd}")
                if run_commands:
                    content.append("")

            if is_final:
                content.extend(self._final_stage_tail(config, stage, distroless))
            content.append("")

        dockerfile_content = "\n".join(content).strip() + "\n"

        # ------------------------------------------------------------------
        # Adversarial validation + reified suppressions (never self-graded).
        # ------------------------------------------------------------------
        secret_findings = self._scan_secret_env(config)
        validator_report = DockerfileValidator().validate_content(
            dockerfile_content, source=f"{config.name}.Dockerfile"
        )
        findings = list(validator_report.results) + completeness + secret_findings

        outcome = SuppressionEngine(
            SuppressionSet(suppressions=list(config.suppressions))
        ).apply(findings)
        surviving = outcome.all_results

        # Refusal contract: plaintext secrets fail generation unless suppressed.
        blocked = [r for r in surviving if r.rule_id == "VOL-DOCKER-SECRET-ENV"]
        if blocked:
            raise ValueError(
                "Refusing to generate: plaintext secret-looking ENV/ARG values "
                f"({', '.join(sorted(str(b.context.get('target')) for b in blocked))}). "
                "Use BuildKit secret mounts, or add a justified suppression for "
                "VOL-DOCKER-SECRET-ENV."
            )

        applied = outcome.applied
        if applied:
            dockerfile_content = append_comment_receipts(
                dockerfile_content, [s for s, _ in applied]
            )

        score_report = ScoringEngine().score(
            surviving,
            resources=[stage.name or f"stage-{i}" for i, stage in enumerate(config.stages)],
            suppressed=applied,
        )

        return GeneratedDockerConfig(
            id=config_id,
            config_hash=config_hash,
            dockerfile_content=dockerfile_content,
            validation_results=[f"{r.rule_id}: {r.message}" for r in surviving],
            best_practice_score=score_report.composite,
            score_report=score_report,
            applied_suppressions=sorted({s.rule for s, _ in applied}),
            dockerignore_content=(
                _DEFAULT_DOCKERIGNORE
                if (copies_whole_context and config.emit_dockerignore)
                else None
            ),
            renovate_snippet=(
                json.dumps(_RENOVATE_SNIPPET, indent=2)
                if config.emit_renovate_config else None
            ),
            scan_workflow_content=_SCAN_WORKFLOW if config.emit_scan_workflow else None,
            created_at=datetime.now(),
        )

    def _final_stage_tail(
        self, config: DockerfileConfig, stage: BuildStage, distroless: bool
    ) -> List[str]:
        """USER scaffold, EXPOSE, HEALTHCHECK, LABELs, ENTRYPOINT/CMD."""
        tail: List[str] = []

        if config.use_non_root:
            if stage.user:
                # Respect an explicitly configured user verbatim.
                tail.append(f"USER {stage.user}")
                tail.append("")
            else:
                non_root = config.non_root or NonRootUser()
                if distroless:
                    # Distroless has no shell/useradd; numeric USER only.
                    tail.append(f"USER {non_root.uid}:{non_root.uid}")
                    tail.append("")
                else:
                    if non_root.create:
                        if self._is_alpine(stage.base_image):
                            tail.append(
                                f"RUN adduser -D -u {non_root.uid} {non_root.name}"
                            )
                        else:
                            # -l avoids a huge sparse faillog for high UIDs (DL3046).
                            tail.append(
                                f"RUN useradd -l -u {non_root.uid} -m {non_root.name}"
                            )
                    tail.append(f"USER {non_root.name}")
                    tail.append("")

        for port in stage.expose_ports:
            tail.append(f"EXPOSE {port}")
        if stage.expose_ports:
            tail.append("")

        if config.healthcheck:
            hc = config.healthcheck
            hc_cmd = hc.get("test", ["CMD", "echo", "ok"])
            hc_cmd_str = " ".join(hc_cmd) if isinstance(hc_cmd, list) else hc_cmd
            tail.append(
                f"HEALTHCHECK --interval={hc.get('interval', '30s')} "
                f"--timeout={hc.get('timeout', '10s')} "
                f"--start-period={hc.get('start_period', '5s')} "
                f"--retries={hc.get('retries', 3)} {hc_cmd_str}"
            )
            tail.append("")

        for label_key, label_value in config.labels.items():
            tail.append(f'LABEL {label_key}="{label_value}"')
        if config.labels:
            tail.append("")

        if stage.entrypoint:
            entrypoint_str = ", ".join(f'"{e}"' for e in stage.entrypoint)
            tail.append(f"ENTRYPOINT [{entrypoint_str}]")
        if stage.cmd:
            cmd_str = ", ".join(f'"{c}"' for c in stage.cmd)
            tail.append(f"CMD [{cmd_str}]")
        return tail

    def save_to_file(
        self,
        docker_config: GeneratedDockerConfig,
        output_dir: Optional[str] = None,
        filename: str = "Dockerfile",
    ) -> str:
        """Save generated Dockerfile (and companion files) to disk."""
        target_dir = output_dir or self.output_dir
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(docker_config.dockerfile_content or "")

        if docker_config.dockerignore_content:
            with open(
                os.path.join(target_dir, ".dockerignore"), "w", encoding="utf-8"
            ) as f:
                f.write(docker_config.dockerignore_content)

        return file_path
