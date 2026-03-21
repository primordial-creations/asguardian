"""
Heimdall Code Smell Analysis Models

Pydantic models for code smell detection based on Martin Fowler's taxonomy.

Categories:
1. Bloaters - Large methods, classes, parameters
2. Object-Oriented Abusers - Misuse of OO principles
3. Change Preventers - Make changes difficult
4. Dispensables - Unnecessary code
5. Couplers - Excessive coupling
"""

import os
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from datetime import datetime

from pydantic import BaseModel, Field


class SmellSeverity(str, Enum):
    """Code smell severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SmellCategory(str, Enum):
    """Categories of code smells based on Martin Fowler's taxonomy."""
    BLOATERS = "bloaters"               # Large methods, classes, parameters
    OO_ABUSERS = "oo_abusers"           # Misuse of OO principles
    CHANGE_PREVENTERS = "change_preventers"  # Make changes difficult
    DISPENSABLES = "dispensables"       # Unnecessary code
    COUPLERS = "couplers"               # Excessive coupling


class CodeSmell(BaseModel):
    """Represents a detected code smell."""
    name: str = Field(..., description="Name of the code smell")
    category: SmellCategory = Field(..., description="Category of the smell")
    severity: SmellSeverity = Field(..., description="Severity level")
    file_path: str = Field(..., description="Absolute path to file")
    line_number: int = Field(..., description="Line where smell is detected")
    description: str = Field(..., description="Description of the smell")
    evidence: str = Field(..., description="Specific evidence for this detection")
    remediation: str = Field(..., description="Suggested remediation")
    confidence: float = Field(1.0, description="Detection confidence (0.0-1.0)")

    class Config:
        use_enum_values = True

    @property
    def location(self) -> str:
        """Return a readable location string."""
        return f"{os.path.basename(self.file_path)}:{self.line_number}"


class SmellReport(BaseModel):
    """Complete code smell analysis report."""
    total_smells: int = Field(0, description="Total number of smells detected")
    smells_by_severity: Dict[str, int] = Field(default_factory=dict, description="Count by severity")
    smells_by_category: Dict[str, int] = Field(default_factory=dict, description="Count by category")
    detected_smells: List[CodeSmell] = Field(default_factory=list, description="All detected smells")
    most_problematic_files: List[Tuple[str, int]] = Field(default_factory=list, description="Files with most smells")
    remediation_priorities: List[str] = Field(default_factory=list, description="Priority remediation actions")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")

    class Config:
        use_enum_values = True

    def add_smell(self, smell: CodeSmell) -> None:
        """Add a smell to the report."""
        self.detected_smells.append(smell)
        self.total_smells += 1

        # Update severity count
        sev = smell.severity if isinstance(smell.severity, str) else smell.severity.value
        self.smells_by_severity[sev] = self.smells_by_severity.get(sev, 0) + 1

        # Update category count
        cat = smell.category if isinstance(smell.category, str) else smell.category.value
        self.smells_by_category[cat] = self.smells_by_category.get(cat, 0) + 1

    @property
    def has_smells(self) -> bool:
        """Check if any smells were detected."""
        return self.total_smells > 0

    @property
    def critical_count(self) -> int:
        """Get count of critical smells."""
        return self.smells_by_severity.get(SmellSeverity.CRITICAL.value, 0)

    @property
    def high_count(self) -> int:
        """Get count of high severity smells."""
        return self.smells_by_severity.get(SmellSeverity.HIGH.value, 0)

    def get_smells_by_severity(self, severity: SmellSeverity) -> List[CodeSmell]:
        """Get all smells of a specific severity."""
        target = severity if isinstance(severity, str) else severity.value
        return [s for s in self.detected_smells if s.severity == target]

    def get_smells_by_category(self, category: SmellCategory) -> List[CodeSmell]:
        """Get all smells of a specific category."""
        target = category if isinstance(category, str) else category.value
        return [s for s in self.detected_smells if s.category == target]


class SmellThresholds(BaseModel):
    """Configurable thresholds for smell detection."""
    # Bloaters thresholds
    long_method_lines: int = Field(50, description="Max lines for a method")
    long_method_statements: int = Field(30, description="Max statements in a method")
    large_class_methods: int = Field(20, description="Max methods in a class")
    large_class_lines: int = Field(500, description="Max lines in a class")
    long_parameter_list: int = Field(6, description="Max parameters for a function")
    data_clumps_threshold: int = Field(3, description="Min occurrences for data clump")

    # Couplers thresholds
    feature_envy_calls: int = Field(5, description="Max calls to external object")
    message_chains_length: int = Field(3, description="Max chained method calls")

    # Change preventers thresholds
    shotgun_surgery_changes: int = Field(5, description="Max files affected by one change")

    # Dispensables thresholds
    duplicate_code_threshold: float = Field(0.8, description="Similarity threshold for duplicates")

    # Complexity thresholds
    complex_conditional_operators: int = Field(3, description="Max boolean operators in condition")


class SmellConfig(BaseModel):
    """Configuration for code smell detection."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    smell_categories: Optional[List[str]] = Field(
        None,
        description="Categories to check (None = all)"
    )
    severity_filter: SmellSeverity = Field(
        SmellSeverity.LOW,
        description="Minimum severity to report"
    )
    thresholds: SmellThresholds = Field(
        default_factory=SmellThresholds,  # type: ignore[arg-type]
        description="Detection thresholds"
    )
    output_format: str = Field("text", description="Output format: text, json, markdown, html")
    include_extensions: Optional[List[str]] = Field(
        default_factory=lambda: [".py"],
        description="File extensions to include"
    )
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            "__pycache__",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "build",
            "dist",
            "migrations",
            "test_*",
            "*_test.py",
        ],
        description="Patterns to exclude"
    )
    include_tests: bool = Field(False, description="Include test files")
    verbose: bool = Field(False, description="Show all smells, not just worst")

    class Config:
        use_enum_values = True

    def get_enabled_categories(self) -> List[str]:
        """Get list of enabled smell categories."""
        if self.smell_categories:
            return self.smell_categories
        return [cat.value for cat in SmellCategory]
