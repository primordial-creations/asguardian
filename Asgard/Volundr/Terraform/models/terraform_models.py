"""
Terraform Models for Module Generation

Provides Pydantic models for configuring and generating Terraform modules
with multi-cloud support, documentation, and best practices.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from Asgard.Volundr.Validation.models.score_models import ScoreReport
from Asgard.Volundr.Validation.models.suppression_models import Suppression


class CloudProvider(str, Enum):
    """Supported cloud providers."""
    AWS = "aws"
    AZURE = "azurerm"
    GCP = "google"
    KUBERNETES = "kubernetes"
    HELM = "helm"
    VAULT = "vault"


class ResourceCategory(str, Enum):
    """Infrastructure resource categories."""
    COMPUTE = "compute"
    NETWORKING = "networking"
    STORAGE = "storage"
    DATABASE = "database"
    SECURITY = "security"
    MONITORING = "monitoring"
    CONTAINER = "container"
    SERVERLESS = "serverless"


class ModuleComplexity(str, Enum):
    """Module complexity levels."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    ENTERPRISE = "enterprise"


class VariableConfig(BaseModel):
    """Terraform variable configuration."""
    name: str = Field(description="Variable name")
    type: str = Field(default="string", description="Variable type (string, number, bool, list, map, object)")
    description: str = Field(default="", description="Variable description")
    default: Optional[Any] = Field(default=None, description="Default value")
    validation: Optional[str] = Field(default=None, description="Validation condition expression")
    sensitive: bool = Field(default=False, description="Mark as sensitive")


class OutputConfig(BaseModel):
    """Terraform output configuration."""
    name: str = Field(description="Output name")
    description: str = Field(description="Output description")
    value: str = Field(description="Output value expression")
    sensitive: bool = Field(default=False, description="Mark as sensitive")


class ModuleConfig(BaseModel):
    """Configuration for generating Terraform modules."""
    name: str = Field(description="Module name")
    provider: CloudProvider = Field(description="Cloud provider")
    category: ResourceCategory = Field(description="Resource category")
    complexity: ModuleComplexity = Field(default=ModuleComplexity.SIMPLE, description="Module complexity")
    description: str = Field(default="", description="Module description")
    version: str = Field(default="1.0.0", description="Module version")
    variables: List[VariableConfig] = Field(default_factory=list, description="Input variables")
    outputs: List[OutputConfig] = Field(default_factory=list, description="Output values")
    resources: List[str] = Field(default_factory=list, description="Resource types to generate")
    data_sources: List[str] = Field(default_factory=list, description="Data sources to include")
    locals: Dict[str, Any] = Field(default_factory=dict, description="Local values")
    required_providers: Dict[str, str] = Field(default_factory=dict, description="Additional required providers")
    tags: Dict[str, str] = Field(default_factory=dict, description="Default resource tags")
    terraform_version: str = Field(default=">= 1.0", description="Required Terraform version")
    environment_profile: str = Field(
        default="production",
        description="Scoring environment weight profile (production/staging/development/sandbox)",
    )
    suppressions: List[Suppression] = Field(
        default_factory=list,
        description="Reified rule suppressions — the only sanctioned relaxation path",
    )
    sensitive_variables: List[str] = Field(
        default_factory=list,
        description="Extra variable names to mark sensitive=true beyond the generator defaults",
    )
    kms_encryption: bool = Field(
        default=False,
        description="Use KMS (aws:kms) instead of AES256 for generated storage encryption blocks",
    )


class GeneratedModule(BaseModel):
    """Result of Terraform module generation."""
    id: str = Field(description="Unique module ID")
    config_hash: str = Field(description="Hash of the configuration")
    module_files: Dict[str, str] = Field(description="Generated module files (filename -> content)")
    documentation: str = Field(description="Generated README.md content")
    examples: Dict[str, str] = Field(default_factory=dict, description="Example configurations")
    tests: Dict[str, str] = Field(default_factory=dict, description="Test configurations")
    validation_results: List[str] = Field(default_factory=list, description="Validation issues found")
    best_practice_score: float = Field(ge=0, le=100, description="Best practice compliance score")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    output_path: Optional[str] = Field(default=None, description="Path where module was saved")
    score_report: Optional[ScoreReport] = Field(
        default=None, description="Full composite score report from the Validation ScoringEngine"
    )
    applied_suppressions: List[str] = Field(
        default_factory=list,
        description="Rule IDs annihilated by suppressions applied during generation",
    )

    @property
    def has_issues(self) -> bool:
        """Check if there are validation issues."""
        return len(self.validation_results) > 0

    @property
    def file_count(self) -> int:
        """Get the number of generated files."""
        return len(self.module_files)
