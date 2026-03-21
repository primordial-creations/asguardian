"""
Asgard Configuration Models - Base and Global

Base configuration models used across all Asgard modules.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class OutputFormat(str, Enum):
    """Output format options for analysis results."""
    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    GITHUB = "github"


class ScreenshotFormat(str, Enum):
    """Screenshot format options for visual testing."""
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"


class BrowserType(str, Enum):
    """Browser types for visual testing."""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class CICDPlatform(str, Enum):
    """CI/CD platform options."""
    GITHUB_ACTIONS = "github_actions"
    GITLAB_CI = "gitlab_ci"
    JENKINS = "jenkins"
    AZURE_DEVOPS = "azure_devops"
    CIRCLECI = "circleci"


class TerraformBackend(str, Enum):
    """Terraform backend options."""
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE_BLOB = "azure_blob"
    CONSUL = "consul"
    KUBERNETES = "kubernetes"


class GlobalConfig(BaseModel):
    """Global configuration shared across all modules."""
    model_config = {"use_enum_values": True}

    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            "__pycache__",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "build",
            "dist",
            "*.pyc",
            "*.pyo",
            ".tox",
            ".eggs",
            "*.egg-info",
        ],
        description="Glob patterns to exclude from analysis"
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.TEXT,
        description="Default output format for analysis results"
    )
    verbose: bool = Field(default=False, description="Enable verbose output")
    parallel: bool = Field(default=False, description="Enable parallel processing")
    workers: Optional[int] = Field(default=None, description="Number of worker processes (defaults to CPU count - 1)")
    incremental: bool = Field(default=False, description="Enable incremental scanning using cache")
    cache_path: str = Field(default=".asgard-cache.json", description="Path to cache file")
