"""
Volundr CICD Module

Provides template-based generation of CI/CD pipeline configurations including:
- GitHub Actions workflows
- GitLab CI/CD pipelines
- Azure DevOps pipelines
- Jenkins pipelines
- Deployment strategies (blue-green, canary, rolling)
"""

from Asgard.Volundr.CICD.models.cicd_models import (
    CICDPlatform,
    OIDCConfig,
    OIDCProvider,
    PipelineStage,
    DeploymentStrategy,
    PipelineConfig,
    GeneratedPipeline,
    TriggerConfig,
    TriggerType,
    StepConfig,
)
from Asgard.Volundr.CICD.services.pipeline_generator import PipelineGenerator

__all__ = [
    "CICDPlatform",
    "OIDCConfig",
    "OIDCProvider",
    "PipelineStage",
    "DeploymentStrategy",
    "PipelineConfig",
    "GeneratedPipeline",
    "TriggerConfig",
    "TriggerType",
    "StepConfig",
    "PipelineGenerator",
]
