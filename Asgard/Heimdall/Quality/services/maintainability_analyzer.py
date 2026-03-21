"""
Heimdall Maintainability Index Analyzer Service

Calculates comprehensive maintainability scores using Microsoft's industry-standard
Maintainability Index formula:

MI = 171 - 5.2 * ln(HV) - 0.23 * CC - 16.2 * ln(LOC) + 50 * sin(sqrt(2.4 * CM))

Where:
- HV = Halstead Volume
- CC = Cyclomatic Complexity
- LOC = Lines of Code
- CM = Comment percentage (0-100)

Maintainability Score Interpretation:
- 85-100: Excellent maintainability, easy to modify and extend
- 70-84: Good maintainability, manageable complexity
- 50-69: Moderate maintainability, some challenges expected
- 25-49: Poor maintainability, significant effort required
- 0-24: Critical maintainability, consider rewriting
"""

import ast
import fnmatch
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Heimdall.Quality.models.maintainability_models import (
    FileMaintainability,
    FunctionMaintainability,
    MaintainabilityConfig,
    MaintainabilityLevel,
    MaintainabilityReport,
)
from Asgard.Heimdall.Quality.services._maintainability_helpers import (
    generate_improvement_priorities,
    generate_recommendations,
)
from Asgard.Heimdall.Quality.services._maintainability_report import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)
from Asgard.Heimdall.Quality.services._maintainability_visitor import MaintainabilityVisitor


class MaintainabilityAnalyzer:
    """
    Calculates maintainability index using Microsoft's formula.

    The Maintainability Index provides an objective measure of how easy code
    is to understand, modify, and maintain. Higher scores indicate better
    maintainability.

    Usage:
        analyzer = MaintainabilityAnalyzer()
        report = analyzer.analyze(Path("./src"))

        print(f"Overall MI: {report.overall_index:.2f}")
        for file in report.file_results:
            if file.maintainability_level in ["poor", "critical"]:
                print(f"  {file.filename}: {file.maintainability_index:.2f}")
    """

    def __init__(self, config: Optional[MaintainabilityConfig] = None):
        """
        Initialize maintainability analyzer.

        Args:
            config: Configuration for analysis. If None, uses defaults.
        """
        self.config = config or MaintainabilityConfig()
        self.thresholds = self.config.thresholds
        self.weights = self.config.get_language_weights()

    def analyze(self, path: Path) -> MaintainabilityReport:
        """
        Analyze a directory for maintainability.

        Args:
            path: Path to directory to analyze

        Returns:
            MaintainabilityReport with complete analysis

        Raises:
            FileNotFoundError: If path does not exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        start_time = datetime.now()
        report = MaintainabilityReport(scan_path=str(path))

        for root, dirs, files in os.walk(path):
            root_path = Path(root)

            dirs[:] = [
                d for d in dirs
                if not any(self._matches_pattern(d, p) for p in self.config.exclude_patterns)
            ]

            for file in files:
                if not self._should_analyze_file(file):
                    continue

                file_path = root_path / file
                try:
                    file_result = self._analyze_file(file_path)
                    if file_result:
                        report.add_file_result(file_result)
                except Exception:
                    pass

        if report.file_results:
            all_indices = [f.maintainability_index for f in report.file_results]
            report.overall_index = sum(all_indices) / len(all_indices)
            report.average_index = report.overall_index
            report.overall_level = self._get_maintainability_level(report.overall_index)

            all_functions: List[FunctionMaintainability] = []
            for file_result in report.file_results:
                all_functions.extend(file_result.functions)

            all_functions.sort(key=lambda f: f.maintainability_index)
            report.worst_functions = all_functions[:20]

        report.improvement_priorities = generate_improvement_priorities(report)

        report.scan_duration_seconds = (datetime.now() - start_time).total_seconds()

        return report

    def analyze_single_file(self, file_path: Path) -> Optional[FileMaintainability]:
        """
        Analyze a single file for maintainability.

        Args:
            file_path: Path to Python file

        Returns:
            FileMaintainability result or None if analysis fails
        """
        return self._analyze_file(file_path)

    def _analyze_file(self, file_path: Path) -> Optional[FileMaintainability]:
        """Analyze a single file."""
        try:
            source = file_path.read_text(encoding='utf-8')
            tree = ast.parse(source)

            visitor = MaintainabilityVisitor(
                str(file_path),
                include_halstead=self.config.include_halstead,
                include_comments=self.config.include_comments
            )
            visitor.visit(tree)

            functions = []
            for func_data in visitor.functions:
                func_result = self._calculate_maintainability(func_data, str(file_path))
                functions.append(func_result)

            file_metrics = visitor.get_file_metrics()

            if functions:
                avg_mi = sum(f.maintainability_index for f in functions) / len(functions)
            else:
                file_result = self._calculate_maintainability(file_metrics, str(file_path))
                avg_mi = file_result.maintainability_index

            return FileMaintainability(
                file_path=str(file_path),
                maintainability_index=avg_mi,
                maintainability_level=self._get_maintainability_level(avg_mi),
                total_lines=file_metrics.get('total_lines', visitor.file_lines),
                code_lines=file_metrics.get('loc', visitor.code_lines),
                comment_lines=file_metrics.get('comment_lines', visitor.file_comments),
                comment_percentage=file_metrics.get('comment_percentage', 0),
                function_count=len(functions),
                average_function_mi=avg_mi,
                functions=functions,
            )

        except SyntaxError:
            return None
        except Exception:
            return None

    def _calculate_maintainability(self, metrics_data: Dict, file_path: str) -> FunctionMaintainability:
        """Calculate maintainability index for given metrics."""
        cyclomatic_complexity = metrics_data.get('complexity', 1)
        lines_of_code = max(metrics_data.get('loc', 1), 1)
        halstead_volume = max(metrics_data.get('halstead_volume', 20), 1)
        comment_percentage = max(metrics_data.get('comment_percentage', 0), 0.1)

        complexity_weight = self.weights.complexity_weight
        volume_weight = self.weights.volume_weight
        loc_weight = self.weights.loc_weight
        comment_factor = self.weights.comment_factor

        complexity_score = complexity_weight * cyclomatic_complexity
        volume_score = volume_weight * math.log(halstead_volume)
        loc_score = loc_weight * math.log(lines_of_code)
        comment_score = comment_factor * math.sin(math.sqrt(2.4 * comment_percentage))

        maintainability_index = 171 - volume_score - complexity_score - loc_score + comment_score
        maintainability_index = max(0, min(100, maintainability_index))

        level = self._get_maintainability_level(maintainability_index)
        recs = generate_recommendations(
            maintainability_index, cyclomatic_complexity, lines_of_code,
            halstead_volume, comment_percentage
        )

        return FunctionMaintainability(
            name=metrics_data.get('name', 'unknown'),
            file_path=file_path,
            line_number=metrics_data.get('line_number', 1),
            maintainability_index=maintainability_index,
            cyclomatic_complexity=cyclomatic_complexity,
            lines_of_code=lines_of_code,
            halstead_volume=halstead_volume,
            comment_percentage=comment_percentage,
            complexity_score=complexity_score,
            volume_score=volume_score,
            loc_score=loc_score,
            comment_score=comment_score,
            maintainability_level=level,
            recommendations=recs,
        )

    def _get_maintainability_level(self, index: float) -> MaintainabilityLevel:
        """Determine maintainability level based on index."""
        if index >= self.thresholds.excellent:
            return MaintainabilityLevel.EXCELLENT
        elif index >= self.thresholds.good:
            return MaintainabilityLevel.GOOD
        elif index >= self.thresholds.moderate:
            return MaintainabilityLevel.MODERATE
        elif index >= self.thresholds.poor:
            return MaintainabilityLevel.POOR
        else:
            return MaintainabilityLevel.CRITICAL

    def _should_analyze_file(self, filename: str) -> bool:
        """Check if file should be analyzed based on extension and patterns."""
        has_valid_ext = any(filename.endswith(ext) for ext in self.config.include_extensions)
        if not has_valid_ext:
            return False

        if any(self._matches_pattern(filename, p) for p in self.config.exclude_patterns):
            return False

        if not self.config.include_tests:
            if filename.startswith("test_") or filename.endswith("_test.py"):
                return False

        return True

    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Check if name matches exclude pattern."""
        return fnmatch.fnmatch(name, pattern)

    def generate_report(self, report: MaintainabilityReport, output_format: str = "text") -> str:
        """
        Generate formatted maintainability report.

        Args:
            report: MaintainabilityReport to format
            output_format: Report format (text, json, markdown)

        Returns:
            Formatted report string

        Raises:
            ValueError: If output format is not supported
        """
        format_lower = output_format.lower()
        if format_lower == "json":
            return generate_json_report(report)
        elif format_lower == "markdown" or format_lower == "md":
            return generate_markdown_report(report)
        elif format_lower == "text":
            return generate_text_report(report)
        else:
            raise ValueError(f"Unsupported format: {output_format}. Use: text, json, markdown")
