"""
CI/CD Pipeline Generator Service

Generates zero-trust CI/CD pipeline configurations for multiple platforms.
Rendered GitHub Actions workflows are validated and scored adversarially by
the shared Volundr Validation engine — the generator never grades its own
intent. Reified suppressions are the only relaxation mechanism and leave
``# volundr:suppress`` comment receipts in the artifact.
"""

import hashlib
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from Asgard.Volundr.CICD.models.cicd_models import (
    CICDPlatform,
    GeneratedPipeline,
    PipelineConfig,
)
from Asgard.Volundr.CICD.services.pipeline_generator_helpers import (
    calculate_best_practice_score,
    generate_azure_devops,
    generate_circleci,
    generate_github_actions_files,
    generate_gitlab_ci,
    generate_jenkins,
    validate_pipeline,
)
from Asgard.Volundr.Validation.models.suppression_models import SuppressionSet
from Asgard.Volundr.Validation.services.suppression_engine import (
    append_comment_receipts,
)
from Asgard.Volundr.Validation.services.validation_engine import ValidationEngine


class PipelineGenerator:
    """Generates CI/CD pipelines from configuration."""

    PLATFORM_FILE_PATHS = {
        CICDPlatform.GITHUB_ACTIONS: ".github/workflows/{name}.yml",
        CICDPlatform.GITLAB_CI: ".gitlab-ci.yml",
        CICDPlatform.AZURE_DEVOPS: "azure-pipelines.yml",
        CICDPlatform.JENKINS: "Jenkinsfile",
        CICDPlatform.CIRCLECI: ".circleci/config.yml",
    }

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or "."

    def _render(self, config: PipelineConfig) -> Tuple[str, Dict[str, str], str]:
        """Render platform files; returns (primary_content, files, primary_path)."""
        name = config.name.lower().replace(" ", "-")
        if config.platform == CICDPlatform.GITHUB_ACTIONS:
            primary, files = generate_github_actions_files(config)
            primary_path = next(iter(files))
            return primary, files, primary_path

        if config.platform == CICDPlatform.GITLAB_CI:
            content = generate_gitlab_ci(config)
        elif config.platform == CICDPlatform.AZURE_DEVOPS:
            content = generate_azure_devops(config)
        elif config.platform == CICDPlatform.JENKINS:
            content = generate_jenkins(config)
        elif config.platform == CICDPlatform.CIRCLECI:
            content = generate_circleci(config)
        else:
            primary, files = generate_github_actions_files(config)
            primary_path = next(iter(files))
            return primary, files, primary_path

        path = self.PLATFORM_FILE_PATHS[config.platform].format(name=name)
        return content, {path: content}, path

    def generate(self, config: PipelineConfig) -> GeneratedPipeline:
        config_json = config.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        pipeline_id = f"{config.name}-{config.platform.value}-{config_hash}"

        primary, files, primary_path = self._render(config)

        # Suppression receipts: declared relaxations are stamped into the
        # artifact as machine-readable comments (YAML platforms only).
        if config.suppressions and config.platform != CICDPlatform.JENKINS:
            files = {
                path: append_comment_receipts(content, config.suppressions)
                for path, content in files.items()
            }
            primary = files[primary_path]

        validation_results = validate_pipeline(primary, config)
        if config.platform == CICDPlatform.GITHUB_ACTIONS:
            # Adversarial validation of the rendered artifact through the
            # shared engine; suppressions are applied there (warning
            # annihilation with hygiene findings for stale/expired ones).
            engine = ValidationEngine(
                suppressions=SuppressionSet(suppressions=list(config.suppressions)),
            )
            scores: List[float] = []
            for path, content in files.items():
                report = engine.validate_pipeline(content, source=path)
                scores.append(report.score)
                validation_results.extend(
                    f"{r.rule_id}: {r.message}" for r in report.results
                )
            best_practice_score = min(scores) if scores else 100.0
        else:
            best_practice_score = calculate_best_practice_score(config)

        return GeneratedPipeline(
            id=pipeline_id,
            config_hash=config_hash,
            platform=config.platform,
            pipeline_content=primary,
            file_path=primary_path,
            files=files,
            validation_results=validation_results,
            best_practice_score=best_practice_score,
            created_at=datetime.now(),
        )

    def save_to_file(self, pipeline: GeneratedPipeline, output_dir: Optional[str] = None) -> str:
        target_dir = output_dir or self.output_dir
        files = pipeline.files or {pipeline.file_path: pipeline.pipeline_content}

        primary_path = os.path.join(target_dir, pipeline.file_path)
        for rel_path, content in files.items():
            file_path = os.path.join(target_dir, rel_path)
            os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

        return primary_path
