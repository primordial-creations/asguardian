"""
Heimdall Requirements Models

Data models for requirements.txt validation and synchronization.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set


class RequirementsSeverity(str, Enum):
    """Severity levels for requirements issues."""
    ERROR = "error"       # Missing critical package
    WARNING = "warning"   # Unused or mismatched package
    INFO = "info"         # Informational


class RequirementsIssueType(str, Enum):
    """Types of requirements issues."""
    MISSING = "missing"           # Package imported but not in requirements
    UNUSED = "unused"             # Package in requirements but not imported
    VERSION_MISMATCH = "version_mismatch"  # Version doesn't match installed
    TRANSITIVE = "transitive"     # Transitive dependency issue


@dataclass
class RequirementsConfig:
    """Configuration for requirements checking."""
    scan_path: Path = field(default_factory=lambda: Path("."))
    requirements_files: List[str] = field(default_factory=lambda: [
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-test.txt",
    ])
    exclude_patterns: List[str] = field(default_factory=lambda: [
        "__pycache__", ".git", ".venv", "venv", "node_modules",
        ".pytest_cache", ".mypy_cache", "dist", "build",
        "*.egg-info", "Hercules",  # Exclude test files by default
    ])
    include_extensions: List[str] = field(default_factory=lambda: [".py"])
    check_unused: bool = True
    check_versions: bool = False
    output_format: str = "text"
    verbose: bool = False

    def __post_init__(self):
        if isinstance(self.scan_path, str):
            self.scan_path = Path(self.scan_path)


@dataclass
class PackageInfo:
    """Information about a Python package."""
    name: str
    version: Optional[str] = None
    version_spec: Optional[str] = None  # e.g., ">=1.0.0"
    source_file: Optional[str] = None   # Which requirements file
    line_number: int = 0
    extras: List[str] = field(default_factory=list)
    is_editable: bool = False


@dataclass
class ImportInfo:
    """Information about an import in source code."""
    package_name: str           # Top-level package name
    import_statement: str       # Full import statement
    file_path: str
    line_number: int
    import_type: str           # "import" or "from_import"


@dataclass
class RequirementsIssue:
    """A single requirements issue."""
    issue_type: RequirementsIssueType
    severity: RequirementsSeverity
    package_name: str
    message: str
    details: Dict = field(default_factory=dict)

    @property
    def location(self) -> str:
        """Human-readable location string."""
        if "file" in self.details:
            return f"{self.details['file']}:{self.details.get('line', 0)}"
        return self.package_name


@dataclass
class RequirementsResult:
    """Complete requirements analysis result."""
    scan_path: str
    scanned_at: datetime
    scan_duration_seconds: float
    config: RequirementsConfig

    # Parsed requirements
    requirements: List[PackageInfo] = field(default_factory=list)
    requirements_files_found: List[str] = field(default_factory=list)

    # Detected imports
    imports: List[ImportInfo] = field(default_factory=list)
    files_scanned: int = 0

    # Issues
    issues: List[RequirementsIssue] = field(default_factory=list)

    # Package mappings
    import_to_package_map: Dict[str, str] = field(default_factory=dict)

    @property
    def missing_packages(self) -> List[RequirementsIssue]:
        """Get all missing package issues."""
        return [i for i in self.issues if i.issue_type == RequirementsIssueType.MISSING]

    @property
    def unused_packages(self) -> List[RequirementsIssue]:
        """Get all unused package issues."""
        return [i for i in self.issues if i.issue_type == RequirementsIssueType.UNUSED]

    @property
    def total_requirements(self) -> int:
        """Total number of packages in requirements."""
        return len(self.requirements)

    @property
    def total_imports(self) -> int:
        """Total number of unique imported packages."""
        return len(set(i.package_name for i in self.imports))

    @property
    def has_issues(self) -> bool:
        """Whether any issues were found."""
        return len(self.issues) > 0

    @property
    def has_errors(self) -> bool:
        """Whether any errors were found."""
        return any(i.severity == RequirementsSeverity.ERROR for i in self.issues)

    @property
    def missing_count(self) -> int:
        """Number of missing packages."""
        return len(self.missing_packages)

    @property
    def unused_count(self) -> int:
        """Number of unused packages."""
        return len(self.unused_packages)

    def get_issues_by_type(self) -> Dict[str, List[RequirementsIssue]]:
        """Group issues by type."""
        result: Dict[str, List[RequirementsIssue]] = {}
        for issue in self.issues:
            key = issue.issue_type.value
            if key not in result:
                result[key] = []
            result[key].append(issue)
        return result

    def get_suggested_additions(self) -> List[str]:
        """Get list of packages to add to requirements."""
        return [i.package_name for i in self.missing_packages]

    def get_suggested_removals(self) -> List[str]:
        """Get list of packages to remove from requirements."""
        return [i.package_name for i in self.unused_packages]
