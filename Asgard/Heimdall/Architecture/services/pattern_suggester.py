"""
Heimdall Pattern Suggester Service

Analyses Python classes for structural code smells and signals that indicate
a Gang of Four design pattern would improve the design.

This is complementary to PatternDetector (which finds patterns already implemented).
PatternSuggester identifies pattern *candidates* — code that would benefit from
applying a pattern that has not yet been used.

Signal → Pattern mapping:
  Constructor with 5+ optional params           → Builder
  Long if/elif chain (4+) in a method           → Strategy (or Visitor if isinstance-heavy)
  3+ isinstance() checks in one method          → Visitor
  3+ concrete class instantiations in __init__  → Factory Method
  6+ constructor dependencies                   → Facade or Mediator
  Scattered notification/callback calls         → Observer
  God class spanning 3+ responsibility groups   → Facade
"""

import ast
import time
from pathlib import Path
from typing import List, Optional, Set

from Asgard.Heimdall.Architecture.models.architecture_models import (
    ArchitectureConfig,
    PatternSuggestion,
    PatternSuggestionReport,
)
from Asgard.Heimdall.Architecture.utilities.ast_utils import (
    extract_classes,
    is_abstract_class,
)
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory
from Asgard.Heimdall.Architecture.services._suggester_reporter import (
    generate_text_report as _gen_text,
    generate_json_report as _gen_json,
    generate_markdown_report as _gen_markdown,
)
from Asgard.Heimdall.Architecture.services._suggester_helpers import (
    analyse_class as _analyse_class_fn,
)
from Asgard.Heimdall.Architecture.services._suggester_ast_helpers import (
    _PATTERN_NAME_FRAGMENTS,
)



class PatternSuggester:
    """
    Analyses Python code for structural signals that suggest GoF design pattern candidates.

    Unlike PatternDetector (which reports patterns that ARE implemented),
    PatternSuggester reports code that COULD benefit from applying a pattern.

    Each suggestion includes:
    - The recommended pattern type
    - The class and file where the smell was detected
    - A human-readable rationale explaining why the pattern fits
    - The observable signals (code properties) that triggered the suggestion
    - The expected benefit of applying the pattern
    - A confidence score (0.0–1.0)
    """

    def __init__(self, config: Optional[ArchitectureConfig] = None) -> None:
        self.config = config or ArchitectureConfig()

    def suggest(self, scan_path: Optional[Path] = None) -> PatternSuggestionReport:
        """
        Scan the codebase and return pattern candidate suggestions.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            PatternSuggestionReport with all suggestions.
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start = time.time()
        report = PatternSuggestionReport(scan_path=str(path))

        # Pass 1: collect all class names for cross-file instantiation analysis
        all_class_names: Set[str] = set()
        class_data: Dict[str, Dict] = {}

        for file_path in scan_directory(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            try:
                source = file_path.read_text(encoding="utf-8", errors="ignore")
                classes = extract_classes(source)
                for cls in classes:
                    all_class_names.add(cls.name)
                    class_data[cls.name] = {
                        "node": cls,
                        "file_path": str(file_path),
                    }
            except (SyntaxError, Exception):
                continue

        # Pass 2: analyse each class for pattern candidates
        for class_name, info in class_data.items():
            class_node: ast.ClassDef = info["node"]
            file_path_str: str = info["file_path"]

            # Skip classes whose names already indicate a pattern implementation
            if any(fragment in class_name for fragment in _PATTERN_NAME_FRAGMENTS):
                continue

            # Skip abstract base classes — they ARE part of a pattern (interface role)
            if is_abstract_class(class_node):
                continue

            for suggestion in self._analyse_class(class_node, file_path_str, all_class_names):
                report.add_suggestion(suggestion)

        report.scan_duration_seconds = time.time() - start
        return report

    def _analyse_class(
        self,
        class_node: ast.ClassDef,
        file_path: str,
        all_class_names: Set[str],
    ) -> List[PatternSuggestion]:
        """Analyse a single class and return any pattern suggestions."""
        return _analyse_class_fn(class_node, file_path, all_class_names)

    def suggest_for_class(
        self,
        class_source: str,
        class_name: Optional[str] = None,
    ) -> PatternSuggestionReport:
        """
        Suggest patterns for a single class source string (useful for API callers).

        Args:
            class_source: Python source code containing the class.
            class_name: Optional — restrict to a specific class name.

        Returns:
            PatternSuggestionReport with suggestions.
        """
        report = PatternSuggestionReport()
        classes = extract_classes(class_source)
        if class_name:
            classes = [c for c in classes if c.name == class_name]

        all_names = {c.name for c in classes}
        for cls in classes:
            for s in self._analyse_class(cls, "<string>", all_names):
                report.add_suggestion(s)
        return report

    def generate_report(self, result: PatternSuggestionReport, format: str = "text") -> str:
        """Generate a formatted report from a PatternSuggestionReport."""
        if format == "json":
            return _gen_json(result)
        elif format == "markdown":
            return _gen_markdown(result)
        return _gen_text(result)
