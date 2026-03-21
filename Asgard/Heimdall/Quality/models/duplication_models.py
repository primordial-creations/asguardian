"""
Heimdall Duplication Analysis Models

Pydantic models for code duplication detection and analysis.
"""

from enum import Enum
from pathlib import Path
from typing import List, Optional, Set
from datetime import datetime

from pydantic import BaseModel, Field


class DuplicationType(str, Enum):
    """Type of code duplication."""
    EXACT = "exact"          # Identical code (Type 1)
    STRUCTURAL = "structural"  # Same structure, different names (Type 2)
    SIMILAR = "similar"       # Similar code with modifications (Type 3)


class DuplicationSeverity(str, Enum):
    """Severity levels for duplication violations."""
    LOW = "low"           # 2 duplicates
    MODERATE = "moderate"  # 3-4 duplicates
    HIGH = "high"         # 5-7 duplicates
    CRITICAL = "critical"  # 8+ duplicates


class CodeBlock(BaseModel):
    """Represents a block of code for duplication analysis."""
    file_path: str = Field(..., description="Absolute path to the file")
    relative_path: str = Field(..., description="Path relative to scan root")
    start_line: int = Field(..., description="Starting line number")
    end_line: int = Field(..., description="Ending line number")
    content: str = Field(..., description="The actual code content")
    tokens: List[str] = Field(default_factory=list, description="Tokenized code")
    normalized_tokens: List[str] = Field(default_factory=list, description="Normalized tokens")
    hash_value: str = Field(..., description="Hash of normalized tokens")
    line_count: int = Field(..., description="Number of lines in block")

    class Config:
        use_enum_values = True

    @property
    def location(self) -> str:
        """Return a readable location string."""
        return f"{self.relative_path}:{self.start_line}-{self.end_line}"


class DuplicationMatch(BaseModel):
    """Represents a match between two duplicate code blocks."""
    original: CodeBlock = Field(..., description="The original code block")
    duplicate: CodeBlock = Field(..., description="The duplicate code block")
    similarity: float = Field(..., description="Similarity score (0.0-1.0)")
    match_type: DuplicationType = Field(..., description="Type of duplication")
    common_tokens: int = Field(0, description="Number of common tokens")

    class Config:
        use_enum_values = True

    @property
    def is_same_file(self) -> bool:
        """Check if both blocks are in the same file."""
        return self.original.file_path == self.duplicate.file_path


class CloneFamily(BaseModel):
    """A group of code blocks that are duplicates of each other."""
    blocks: List[CodeBlock] = Field(default_factory=list, description="All blocks in this clone family")
    representative: Optional[CodeBlock] = Field(None, description="Representative block for this family")
    match_type: DuplicationType = Field(..., description="Type of duplication")
    average_similarity: float = Field(1.0, description="Average similarity between blocks")
    severity: DuplicationSeverity = Field(..., description="Severity based on count")
    total_duplicated_lines: int = Field(0, description="Total lines of duplicated code")

    class Config:
        use_enum_values = True

    @classmethod
    def calculate_severity(cls, block_count: int) -> DuplicationSeverity:
        """Calculate severity based on number of duplicates."""
        if block_count <= 2:
            return DuplicationSeverity.LOW
        elif block_count <= 4:
            return DuplicationSeverity.MODERATE
        elif block_count <= 7:
            return DuplicationSeverity.HIGH
        else:
            return DuplicationSeverity.CRITICAL

    def add_block(self, block: CodeBlock) -> None:
        """Add a block to this clone family."""
        self.blocks.append(block)
        if self.representative is None:
            self.representative = block
        self.total_duplicated_lines += block.line_count
        self.severity = self.calculate_severity(len(self.blocks))

    @property
    def file_count(self) -> int:
        """Number of unique files in this family."""
        return len(set(b.file_path for b in self.blocks))

    @property
    def block_count(self) -> int:
        """Number of blocks in this family."""
        return len(self.blocks)


class DuplicationResult(BaseModel):
    """Complete result of duplication analysis."""
    total_files_scanned: int = Field(0, description="Number of files scanned")
    total_blocks_analyzed: int = Field(0, description="Total code blocks analyzed")
    total_clone_families: int = Field(0, description="Number of clone families found")
    total_duplicated_lines: int = Field(0, description="Total lines of duplicated code")
    duplication_percentage: float = Field(0.0, description="Percentage of code that is duplicated")
    scan_path: str = Field(..., description="Root path that was scanned")
    clone_families: List[CloneFamily] = Field(default_factory=list, description="All clone families")
    files_with_duplicates: List[str] = Field(default_factory=list, description="Files containing duplicates")
    scan_duration_seconds: float = Field(0.0, description="Time taken for the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")
    min_block_size: int = Field(6, description="Minimum block size used")
    similarity_threshold: float = Field(0.85, description="Similarity threshold used")

    class Config:
        use_enum_values = True

    def add_clone_family(self, family: CloneFamily) -> None:
        """Add a clone family to the result."""
        self.clone_families.append(family)
        self.total_clone_families += 1
        self.total_duplicated_lines += family.total_duplicated_lines

        # Track files with duplicates
        for block in family.blocks:
            if block.relative_path not in self.files_with_duplicates:
                self.files_with_duplicates.append(block.relative_path)

    @property
    def has_duplicates(self) -> bool:
        """Check if any duplicates were found."""
        return self.total_clone_families > 0

    @property
    def compliance_rate(self) -> float:
        """Calculate percentage of code that is NOT duplicated."""
        return 100.0 - self.duplication_percentage

    def get_families_by_severity(self) -> dict:
        """Group clone families by severity level."""
        result: dict = {
            DuplicationSeverity.CRITICAL.value: [],
            DuplicationSeverity.HIGH.value: [],
            DuplicationSeverity.MODERATE.value: [],
            DuplicationSeverity.LOW.value: [],
        }
        for family in self.clone_families:
            result[family.severity].append(family)
        return result

    @property
    def worst_families(self) -> List[CloneFamily]:
        """Return top 10 worst clone families by block count."""
        return sorted(self.clone_families, key=lambda f: f.block_count, reverse=True)[:10]


class DuplicationConfig(BaseModel):
    """Configuration for duplication detection."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    min_block_size: int = Field(6, description="Minimum lines for duplication detection")
    similarity_threshold: float = Field(0.85, description="Minimum similarity (0.0-1.0)")
    output_format: str = Field("text", description="Output format: text, json, or markdown")
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
            "test_",
            "_test.py",
        ],
        description="Patterns to exclude from analysis"
    )
    include_tests: bool = Field(False, description="Include test files in analysis")
    max_files: int = Field(1000, description="Maximum files to analyze")
    verbose: bool = Field(False, description="Show all clone families, not just worst")

    class Config:
        use_enum_values = True
