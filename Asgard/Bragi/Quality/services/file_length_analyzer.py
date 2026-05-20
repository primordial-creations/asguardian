"""
Heimdall File Length Analyzer Service

Core service for analyzing code file lengths and generating quality reports.
"""

import time
from pathlib import Path
from typing import List, Optional

from Asgard.Bragi.Quality.models.analysis_models import (
    AnalysisConfig,
    AnalysisResult,
    FileAnalysis,
    SeverityLevel,
)
from Asgard.Bragi.Quality.utilities.file_utils import (
    count_lines,
    get_file_extension,
    scan_directory,
)


class FileAnalyzer:
    """
    Analyzes code files for quality metrics.

    Currently supports:
    - File length analysis (line count threshold)

    Future support planned:
    - Cyclomatic complexity
    - Cognitive complexity
    - Code duplication detection
    - Code smell detection
    - Technical debt calculation
    """

    def __init__(self, config: Optional[AnalysisConfig] = None):
        """
        Initialize the file analyzer.

        Args:
            config: Analysis configuration. Uses defaults if not provided.
        """
        self.config = config or AnalysisConfig()

    def analyze(self, scan_path: Optional[Path] = None) -> AnalysisResult:
        """
        Perform file length analysis on the specified path.

        Uses per-extension thresholds when configured (e.g., CSS files
        get a higher threshold than Python files).

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            AnalysisResult containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        result = AnalysisResult(
            default_threshold=self.config.threshold,
            extension_thresholds=self.config.extension_thresholds.copy(),
            scan_path=str(path),
            skipped_patterns=self.config.exclude_patterns,
        )

        # Scan all files
        for file_path in scan_directory(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            result.increment_files_scanned()

            try:
                line_count = count_lines(file_path)
            except IOError:
                # Skip files we can't read
                continue

            # Get the appropriate threshold for this file's extension
            extension = get_file_extension(file_path)
            file_threshold = self.config.get_threshold_for_extension(extension)

            if line_count > file_threshold:
                lines_over = line_count - file_threshold
                analysis = FileAnalysis(
                    file_path=str(file_path),
                    line_count=line_count,
                    threshold=file_threshold,
                    lines_over=lines_over,
                    severity=FileAnalysis.calculate_severity(lines_over),
                    file_extension=extension,
                    relative_path=str(file_path.relative_to(path)),
                )
                result.add_violation(analysis)
            elif result.longest_file is None or line_count > (result.longest_file.line_count if result.longest_file else 0):
                # Track the longest compliant file too for context
                pass

        result.scan_duration_seconds = time.time() - start_time

        # Sort violations by line count (worst first)
        result.violations.sort(key=lambda x: x.line_count, reverse=True)

        return result

    def get_scan_preview(self, scan_path: Optional[Path] = None) -> List[Path]:
        """
        Get a preview of files that would be scanned (dry run).

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            List of file paths that would be analyzed
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        return list(scan_directory(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ))
