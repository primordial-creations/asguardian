"""
Heimdall Code Smell Detector Service

Detects code smells and anti-patterns based on Martin Fowler's taxonomy.
Implements detection for 20+ common code smells across all categories:
- Bloaters: Large methods, classes, parameters
- OO Abusers: Misuse of OO principles
- Change Preventers: Make changes difficult
- Dispensables: Unnecessary code
- Couplers: Excessive coupling
"""

import ast
import os
import fnmatch
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

from Asgard.Heimdall.Quality.models.smell_models import (
    CodeSmell,
    SmellCategory,
    SmellConfig,
    SmellReport,
    SmellSeverity,
)
from Asgard.Heimdall.Quality.utilities.file_utils import DEFAULT_EXCLUDE_DIRS
from Asgard.Heimdall.Quality.services._code_smell_visitor import SmellVisitor
from Asgard.Heimdall.Quality.services._code_smell_report import (
    generate_text_report,
    generate_json_report,
    generate_markdown_report,
    generate_html_report,
)


class CodeSmellDetector:
    """
    Detects various code smells and anti-patterns.

    Implements detection for 20+ common code smells across all categories:
    - Bloaters: Large methods, classes, parameters
    - OO Abusers: Misuse of OO principles
    - Change Preventers: Make changes difficult
    - Dispensables: Unnecessary code
    - Couplers: Excessive coupling

    Usage:
        detector = CodeSmellDetector()
        report = detector.analyze(Path("./src"))

        for smell in report.detected_smells:
            print(f"{smell.name} at {smell.location}")
    """

    def __init__(self, config: Optional[SmellConfig] = None):
        """
        Initialize code smell detector.

        Args:
            config: Configuration for smell detection. If None, uses defaults.
        """
        self.config = config or SmellConfig()

    def analyze(self, path: Path) -> SmellReport:
        """
        Analyze a file or directory for code smells.

        Args:
            path: Path to file or directory to analyze

        Returns:
            SmellReport with all detected smells

        Raises:
            FileNotFoundError: If path does not exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        start_time = datetime.now()
        report = SmellReport(scan_path=str(path))

        if path.is_file():
            smells = self._analyze_file(path)
            for smell in smells:
                report.add_smell(smell)
        else:
            self._analyze_directory(path, report)

        report.scan_duration_seconds = (datetime.now() - start_time).total_seconds()

        file_smell_counts: Dict[str, int] = defaultdict(int)
        for smell in report.detected_smells:
            file_smell_counts[smell.file_path] += 1

        report.most_problematic_files = sorted(
            file_smell_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        report.remediation_priorities = self._generate_remediation_priorities(report.detected_smells)

        return report

    def analyze_single_file(self, file_path: Path) -> SmellReport:
        """
        Analyze a single file for code smells.

        Args:
            file_path: Path to Python file

        Returns:
            SmellReport with detected smells
        """
        return self.analyze(file_path)

    def _analyze_file(self, file_path: Path) -> List[CodeSmell]:
        """
        Analyze a single file for code smells.

        Args:
            file_path: Path to Python file

        Returns:
            List of detected code smells
        """
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)

            visitor = SmellVisitor(
                file_path=str(file_path.absolute()),
                thresholds=self.config.thresholds,
                categories=self.config.get_enabled_categories(),
            )
            visitor.visit(tree)

            smells = visitor.smells + visitor.get_feature_envy_smells()

            filtered_smells = [
                smell
                for smell in smells
                if self._severity_level(smell.severity) >= self._severity_level(self.config.severity_filter)
            ]

            return filtered_smells

        except SyntaxError:
            return []
        except Exception:
            return []

    def _analyze_directory(self, directory: Path, report: SmellReport) -> None:
        """
        Analyze all Python files in a directory.

        Args:
            directory: Directory to analyze
            report: Report to add smells to
        """
        all_exclude_patterns = list(self.config.exclude_patterns) + list(DEFAULT_EXCLUDE_DIRS)

        for root, dirs, files in os.walk(directory):
            root_path = Path(root)

            dirs[:] = [
                d
                for d in dirs
                if not any(self._matches_pattern(d, pattern) for pattern in all_exclude_patterns)
            ]

            for file in files:
                if not self._should_analyze_file(file):
                    continue

                if any(self._matches_pattern(file, pattern) for pattern in self.config.exclude_patterns):
                    continue

                file_path = root_path / file
                smells = self._analyze_file(file_path)
                for smell in smells:
                    report.add_smell(smell)

    def _should_analyze_file(self, filename: str) -> bool:
        """Check if file should be analyzed based on extension."""
        if self.config.include_extensions:
            return any(filename.endswith(ext) for ext in self.config.include_extensions)
        return filename.endswith(".py")

    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Check if name matches exclude pattern."""
        return fnmatch.fnmatch(name, pattern)

    def _severity_level(self, severity) -> int:
        """Convert severity to numeric level for comparison."""
        if isinstance(severity, str):
            severity = SmellSeverity(severity)
        levels = {
            SmellSeverity.LOW: 1,
            SmellSeverity.MEDIUM: 2,
            SmellSeverity.HIGH: 3,
            SmellSeverity.CRITICAL: 4,
        }
        return levels.get(severity, 1)

    def _generate_remediation_priorities(self, smells: List[CodeSmell]) -> List[str]:
        """
        Generate prioritized remediation recommendations.

        Args:
            smells: List of detected smells

        Returns:
            List of prioritized remediation actions
        """
        priorities = []

        smell_counts: Dict[str, int] = defaultdict(int)
        critical_smells = []
        high_smells = []

        for smell in smells:
            smell_counts[smell.name] += 1
            sev = smell.severity if isinstance(smell.severity, str) else smell.severity.value
            if sev == SmellSeverity.CRITICAL.value:
                critical_smells.append(smell)
            elif sev == SmellSeverity.HIGH.value:
                high_smells.append(smell)

        if critical_smells:
            priorities.append(f"CRITICAL: Address {len(critical_smells)} critical smells immediately")

        if high_smells:
            priorities.append(f"HIGH: Review {len(high_smells)} high-severity smells")

        common_smells = sorted(smell_counts.items(), key=lambda x: x[1], reverse=True)
        if common_smells:
            top_smell = common_smells[0]
            if top_smell[1] > 5:
                priorities.append(f"Focus on '{top_smell[0]}' ({top_smell[1]} occurrences)")

        category_counts: Dict[str, int] = defaultdict(int)
        for smell in smells:
            cat = smell.category if isinstance(smell.category, str) else smell.category.value
            category_counts[cat] += 1

        if category_counts.get(SmellCategory.BLOATERS.value, 0) > 10:
            priorities.append("High number of bloater smells - focus on code size reduction")

        if category_counts.get(SmellCategory.COUPLERS.value, 0) > 5:
            priorities.append("Coupling issues detected - improve modularity and reduce dependencies")

        if category_counts.get(SmellCategory.DISPENSABLES.value, 0) > 5:
            priorities.append("Dispensable code detected - remove dead code and unused elements")

        if category_counts.get(SmellCategory.CHANGE_PREVENTERS.value, 0) > 3:
            priorities.append("Change preventers found - refactor to improve maintainability")

        return priorities

    def generate_report(self, report: SmellReport, output_format: str = "text") -> str:
        """
        Generate formatted code smell report.

        Args:
            report: SmellReport to format
            output_format: Report format (text, json, markdown, html)

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
        elif format_lower == "html":
            return generate_html_report(report, self._severity_level)
        elif format_lower == "text":
            return generate_text_report(report)
        else:
            raise ValueError(f"Unsupported format: {output_format}. Use: text, json, markdown, html")
