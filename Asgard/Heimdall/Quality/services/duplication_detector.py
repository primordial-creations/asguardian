"""
Heimdall Duplication Detector Service

Detects code duplication using token-based analysis and similarity algorithms.

Duplication Types:
- Type 1 (Exact): Identical code blocks
- Type 2 (Structural): Same structure with different variable names
- Type 3 (Similar): Similar code with modifications
"""

import time
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Quality.models.duplication_models import (
    DuplicationConfig,
    DuplicationResult,
)
from Asgard.Heimdall.Quality.services._duplication_helpers import (
    extract_blocks_from_file,
    find_clone_families,
)
from Asgard.Heimdall.Quality.services._duplication_report import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory


class DuplicationDetector:
    """
    Detects code duplication using token-based analysis.

    Supports:
    - Exact match detection (Type 1 clones)
    - Structural similarity detection (Type 2 clones)
    - Near-miss detection (Type 3 clones)
    """

    def __init__(self, config: Optional[DuplicationConfig] = None):
        """
        Initialize the duplication detector.

        Args:
            config: Detection configuration. Uses defaults if not provided.
        """
        self.config = config or DuplicationConfig()

    def analyze(self, scan_path: Optional[Path] = None) -> DuplicationResult:
        """
        Perform duplication analysis on the specified path.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            DuplicationResult containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        result = DuplicationResult(
            scan_path=str(path),
            min_block_size=self.config.min_block_size,
            similarity_threshold=self.config.similarity_threshold,
        )

        all_blocks = []
        files_scanned = 0
        total_lines = 0

        exclude_patterns = list(self.config.exclude_patterns)
        if not self.config.include_tests:
            exclude_patterns.extend(["test_", "_test.py", "tests/", "conftest.py"])

        for file_path in scan_directory(
            path,
            exclude_patterns=exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            if files_scanned >= self.config.max_files:
                break

            try:
                blocks, line_count = extract_blocks_from_file(file_path, path, self.config)
                all_blocks.extend(blocks)
                total_lines += line_count
                files_scanned += 1
            except Exception:
                continue

        result.total_files_scanned = files_scanned
        result.total_blocks_analyzed = len(all_blocks)

        if all_blocks:
            clone_families = find_clone_families(all_blocks, self.config)
            for family in clone_families:
                result.add_clone_family(family)

        if total_lines > 0:
            result.duplication_percentage = (result.total_duplicated_lines / total_lines) * 100

        result.scan_duration_seconds = time.time() - start_time

        result.clone_families.sort(
            key=lambda f: (f.block_count, f.total_duplicated_lines),
            reverse=True
        )

        return result

    def analyze_single_file(self, file_path: Path) -> DuplicationResult:
        """
        Analyze a single file for internal duplication.

        Args:
            file_path: Path to the file

        Returns:
            DuplicationResult with findings

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File does not exist: {path}")

        start_time = time.time()

        result = DuplicationResult(
            scan_path=str(path.parent),
            min_block_size=self.config.min_block_size,
            similarity_threshold=self.config.similarity_threshold,
        )

        try:
            blocks, total_lines = extract_blocks_from_file(path, path.parent, self.config)
            result.total_files_scanned = 1
            result.total_blocks_analyzed = len(blocks)

            if blocks:
                clone_families = find_clone_families(blocks, self.config)
                for family in clone_families:
                    result.add_clone_family(family)

            if total_lines > 0:
                result.duplication_percentage = (
                    result.total_duplicated_lines / total_lines
                ) * 100

        except Exception:
            pass

        result.scan_duration_seconds = time.time() - start_time
        return result

    def generate_report(self, result: DuplicationResult, output_format: str = "text") -> str:
        """
        Generate formatted duplication analysis report.

        Args:
            result: DuplicationResult to format
            output_format: Report format - text, json, or markdown

        Returns:
            Formatted report string

        Raises:
            ValueError: If output format is not supported
        """
        format_lower = output_format.lower()
        if format_lower == "json":
            return generate_json_report(result)
        elif format_lower in ("markdown", "md"):
            return generate_markdown_report(result)
        elif format_lower == "text":
            return generate_text_report(result)
        else:
            raise ValueError(f"Unsupported format: {output_format}. Use: text, json, markdown")
