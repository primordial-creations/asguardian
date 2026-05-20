"""
Heimdall Dependencies Models

Data models for dependency analysis.
"""

from Asgard.Bragi.Dependencies.models.dependency_models import (
    DependencyConfig,
    DependencyInfo,
    DependencyReport,
    DependencySeverity,
    DependencyType,
    ModuleDependencies,
)
from Asgard.Bragi.Dependencies.models.requirements_models import (
    ImportInfo,
    PackageInfo,
    RequirementsConfig,
    RequirementsIssue,
    RequirementsIssueType,
    RequirementsResult,
    RequirementsSeverity,
)
from Asgard.Bragi.Dependencies.models.license_models import (
    LicenseCategory,
    LicenseConfig,
    LicenseIssue,
    LicenseIssueType,
    LicenseResult,
    LicenseSeverity,
    PackageLicense,
)

__all__ = [
    "DependencyConfig",
    "DependencyInfo",
    "DependencyReport",
    "DependencySeverity",
    "DependencyType",
    "ModuleDependencies",
    # Requirements analysis
    "ImportInfo",
    "PackageInfo",
    "RequirementsConfig",
    "RequirementsIssue",
    "RequirementsIssueType",
    "RequirementsResult",
    "RequirementsSeverity",
    # License analysis
    "LicenseCategory",
    "LicenseConfig",
    "LicenseIssue",
    "LicenseIssueType",
    "LicenseResult",
    "LicenseSeverity",
    "PackageLicense",
]
