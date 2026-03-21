"""
Heimdall Pattern Detector Service

Detects design patterns in Python code.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Heimdall.Architecture.models.architecture_models import (
    ArchitectureConfig,
    PatternReport,
)
from Asgard.Heimdall.Architecture.utilities.ast_utils import extract_classes
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory
from Asgard.Heimdall.Architecture.services._pattern_reporter import (
    generate_text_report as _gen_text,
    generate_json_report as _gen_json,
    generate_markdown_report as _gen_markdown,
)
from Asgard.Heimdall.Architecture.services._pattern_detectors import (
    detect_singleton,
    detect_factory,
    detect_builder,
    detect_adapter,
    detect_decorator,
    detect_facade,
    detect_strategy,
    detect_observer,
    detect_command,
)


class PatternDetector:
    """
    Detects design patterns in Python code.

    Supports detection of:
    - Creational patterns (Singleton, Factory, Builder)
    - Structural patterns (Adapter, Decorator, Facade)
    - Behavioral patterns (Strategy, Observer, Command)
    """

    def __init__(self, config: Optional[ArchitectureConfig] = None):
        """Initialize the pattern detector."""
        self.config = config or ArchitectureConfig()

    def detect(self, scan_path: Optional[Path] = None) -> PatternReport:
        """
        Detect design patterns in the codebase.

        Args:
            scan_path: Root path to scan

        Returns:
            PatternReport with detected patterns
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()
        report = PatternReport(scan_path=str(path))

        all_classes: Dict[str, Dict] = {}

        for file_path in scan_directory(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            try:
                source = file_path.read_text(encoding="utf-8", errors="ignore")
                classes = extract_classes(source)

                for class_node in classes:
                    all_classes[class_node.name] = {
                        "node": class_node,
                        "file_path": str(file_path),
                        "source": source,
                    }
            except (SyntaxError, Exception):
                continue

        for class_name, class_info in all_classes.items():
            class_node = class_info["node"]
            file_path = class_info["file_path"]

            patterns = []
            patterns.extend(detect_singleton(class_node, file_path))
            patterns.extend(detect_factory(class_node, file_path, all_classes))
            patterns.extend(detect_builder(class_node, file_path))
            patterns.extend(detect_adapter(class_node, file_path, all_classes))
            patterns.extend(detect_decorator(class_node, file_path, all_classes))
            patterns.extend(detect_facade(class_node, file_path))
            patterns.extend(detect_strategy(class_node, file_path, all_classes))
            patterns.extend(detect_observer(class_node, file_path))
            patterns.extend(detect_command(class_node, file_path, all_classes))

            for pattern in patterns:
                report.add_pattern(pattern)

        report.scan_duration_seconds = time.time() - start_time
        return report

    def detect_in_class(
        self,
        class_source: str,
        class_name: Optional[str] = None
    ) -> PatternReport:
        """
        Detect patterns in a single class.

        Args:
            class_source: Python source code
            class_name: Optional specific class name

        Returns:
            PatternReport with detected patterns
        """
        report = PatternReport()

        classes = extract_classes(class_source)
        if class_name:
            classes = [c for c in classes if c.name == class_name]

        all_classes = {
            c.name: {
                "node": c,
                "file_path": "<string>",
                "source": class_source,
            }
            for c in classes
        }

        for class_node in classes:
            patterns = []
            patterns.extend(detect_singleton(class_node, "<string>"))
            patterns.extend(detect_factory(class_node, "<string>", all_classes))
            patterns.extend(detect_builder(class_node, "<string>"))
            patterns.extend(detect_adapter(class_node, "<string>", all_classes))
            patterns.extend(detect_decorator(class_node, "<string>", all_classes))
            patterns.extend(detect_facade(class_node, "<string>"))
            patterns.extend(detect_strategy(class_node, "<string>", all_classes))
            patterns.extend(detect_observer(class_node, "<string>"))
            patterns.extend(detect_command(class_node, "<string>", all_classes))

            for pattern in patterns:
                report.add_pattern(pattern)

        return report

    def generate_report(self, result: PatternReport, format: str = "text") -> str:
        """Generate a formatted report."""
        if format == "json":
            return _gen_json(result)
        elif format == "markdown":
            return _gen_markdown(result)
        else:
            return _gen_text(result)
