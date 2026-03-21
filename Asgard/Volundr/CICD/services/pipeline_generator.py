"""
CI/CD Pipeline Generator Service

Generates CI/CD pipeline configurations for multiple platforms
with deployment strategies and best practices.
"""

import hashlib
import os
from datetime import datetime
from typing import Optional

from Asgard.Volundr.CICD.models.cicd_models import (
    CICDPlatform,
    GeneratedPipeline,
    PipelineConfig,
)
from Asgard.Volundr.CICD.services.pipeline_generator_helpers import (
    calculate_best_practice_score,
    generate_azure_devops,
    generate_github_actions,
    generate_gitlab_ci,
    generate_jenkins,
    validate_pipeline,
)


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

    def generate(self, config: PipelineConfig) -> GeneratedPipeline:
        config_json = config.model_dump_json()
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        pipeline_id = f"{config.name}-{config.platform.value}-{config_hash}"

        if config.platform == CICDPlatform.GITHUB_ACTIONS:
            pipeline_content = generate_github_actions(config)
        elif config.platform == CICDPlatform.GITLAB_CI:
            pipeline_content = generate_gitlab_ci(config)
        elif config.platform == CICDPlatform.AZURE_DEVOPS:
            pipeline_content = generate_azure_devops(config)
        elif config.platform == CICDPlatform.JENKINS:
            pipeline_content = generate_jenkins(config)
        else:
            pipeline_content = generate_github_actions(config)

        file_path = self.PLATFORM_FILE_PATHS.get(
            config.platform, ".github/workflows/{name}.yml"
        ).format(name=config.name.lower().replace(" ", "-"))

        validation_results = validate_pipeline(pipeline_content, config)
        best_practice_score = calculate_best_practice_score(config)

        return GeneratedPipeline(
            id=pipeline_id,
            config_hash=config_hash,
            platform=config.platform,
            pipeline_content=pipeline_content,
            file_path=file_path,
            validation_results=validation_results,
            best_practice_score=best_practice_score,
            created_at=datetime.now(),
        )

    def save_to_file(self, pipeline: GeneratedPipeline, output_dir: Optional[str] = None) -> str:
        target_dir = output_dir or self.output_dir
        file_path = os.path.join(target_dir, pipeline.file_path)

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(pipeline.pipeline_content)

        return file_path
