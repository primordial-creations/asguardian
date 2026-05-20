"""
Heimdall RFC Analyzer Service

Analyzes Python code for:
- RFC (Response for a Class): Methods in class + methods called by those methods
- WMC (Weighted Methods per Class): Sum of cyclomatic complexity of all methods

High RFC indicates:
- Class has many potential responses to messages
- High complexity in understanding behavior
- More effort to test completely

High WMC indicates:
- Class has high aggregate complexity
- Methods are individually complex
- Potential maintenance burden
"""

import ast
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Bragi.OOP.models.oop_models import (
    ClassRFCMetrics,
    OOPConfig,
    OOPSeverity,
)
from Asgard.Bragi.OOP.utilities.class_utils import (
    ClassInfo,
    extract_classes_from_file,
    get_class_methods,
    MethodInfo,
)
from Asgard.Bragi.Quality.utilities.file_utils import scan_directory


class RFCAnalyzer:
    """
    Analyzes Python code for RFC and WMC metrics.

    Response for a Class (RFC):
    - Counts methods that can be executed in response to a message
    - Includes the class's methods plus methods they call
    - Higher RFC = more complex testing and understanding

    Weighted Methods per Class (WMC):
    - Sum of cyclomatic complexity of all methods
    - Measures total complexity "weight" of the class
    - Higher WMC = more complex class
    """

    def __init__(self, config: Optional[OOPConfig] = None):
        """Initialize the RFC analyzer."""
        self.config = config or OOPConfig()

    def analyze(self, scan_path: Optional[Path] = None) -> List[ClassRFCMetrics]:
        """
        Analyze RFC and WMC metrics for all classes in the path.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            List of ClassRFCMetrics for each class
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        results: List[ClassRFCMetrics] = []

        # Build exclude patterns
        exclude_patterns = list(self.config.exclude_patterns)
        if not self.config.include_tests:
            exclude_patterns.extend(["test_", "_test.py", "tests/", "conftest.py"])

        for file_path in scan_directory(
            path,
            exclude_patterns=exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            try:
                file_results = self._analyze_file(file_path, path)
                results.extend(file_results)
            except (SyntaxError, Exception):
                continue

        return results

    def _analyze_file(self, file_path: Path, root_path: Path) -> List[ClassRFCMetrics]:
        """Analyze RFC/WMC for all classes in a file."""
        classes = extract_classes_from_file(file_path)
        results = []

        for cls in classes:
            metrics = self._analyze_class(cls, file_path, root_path)
            if metrics:
                results.append(metrics)

        return results

    def _analyze_class(
        self, cls: ClassInfo, file_path: Path, root_path: Path
    ) -> Optional[ClassRFCMetrics]:
        """Analyze RFC and WMC for a single class."""
        methods = get_class_methods(cls)

        # Calculate WMC: sum of cyclomatic complexity
        wmc = sum(m.complexity for m in methods)
        method_complexities = {m.name: m.complexity for m in methods}

        # Calculate RFC: methods + called methods
        # Collect all methods called by this class's methods
        called_methods: Set[str] = set()

        for method in methods:
            # Add self.method() calls
            called_methods.update(method.called_methods)

            # Add external calls (other.method())
            # We count these as part of RFC too
            # Extract just the method name from external calls
            for call in getattr(method, "external_calls", set()) if hasattr(method, "external_calls") else set():
                if "." in call:
                    called_methods.add(call.split(".")[-1])
                else:
                    called_methods.add(call)

        # RFC = number of methods + number of distinct methods called
        method_count = len(methods)
        rfc = method_count + len(called_methods)

        severity = ClassRFCMetrics.calculate_severity(
            rfc, wmc, self.config.rfc_threshold, self.config.wmc_threshold
        )

        try:
            relative_path = str(file_path.relative_to(root_path))
        except ValueError:
            relative_path = file_path.name

        return ClassRFCMetrics(
            class_name=cls.name,
            file_path=str(file_path),
            relative_path=relative_path,
            line_number=cls.line_number,
            rfc=rfc,
            wmc=wmc,
            method_count=method_count,
            methods_called=called_methods,
            method_complexities=method_complexities,
            severity=severity,
        )

    def analyze_file(self, file_path: Path) -> List[ClassRFCMetrics]:
        """
        Analyze RFC/WMC metrics for a single file.

        Args:
            file_path: Path to the Python file

        Returns:
            List of ClassRFCMetrics for classes in the file
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File does not exist: {path}")

        return self._analyze_file(path, path.parent)

    def get_high_rfc_classes(
        self, scan_path: Optional[Path] = None, threshold: Optional[int] = None
    ) -> List[ClassRFCMetrics]:
        """
        Get classes with high RFC.

        Args:
            scan_path: Root path to scan
            threshold: RFC threshold (default: config.rfc_threshold)

        Returns:
            List of classes with RFC above threshold
        """
        threshold = threshold or self.config.rfc_threshold
        metrics = self.analyze(scan_path)

        return [m for m in metrics if m.rfc > threshold]

    def get_high_wmc_classes(
        self, scan_path: Optional[Path] = None, threshold: Optional[int] = None
    ) -> List[ClassRFCMetrics]:
        """
        Get classes with high WMC.

        Args:
            scan_path: Root path to scan
            threshold: WMC threshold (default: config.wmc_threshold)

        Returns:
            List of classes with WMC above threshold
        """
        threshold = threshold or self.config.wmc_threshold
        metrics = self.analyze(scan_path)

        return [m for m in metrics if m.wmc > threshold]

    def get_complexity_hotspots(
        self, scan_path: Optional[Path] = None, top_n: int = 10
    ) -> List[ClassRFCMetrics]:
        """
        Get the top N most complex classes by WMC.

        Args:
            scan_path: Root path to scan
            top_n: Number of classes to return

        Returns:
            List of top N classes by WMC
        """
        metrics = self.analyze(scan_path)
        sorted_metrics = sorted(metrics, key=lambda m: m.wmc, reverse=True)
        return sorted_metrics[:top_n]

    def get_method_complexity_breakdown(
        self, cls_metrics: ClassRFCMetrics
    ) -> List[Dict[str, int]]:
        """
        Get complexity breakdown for each method in a class.

        Args:
            cls_metrics: RFC metrics for the class

        Returns:
            List of {name, complexity} dicts sorted by complexity
        """
        breakdown = [
            {"name": name, "complexity": complexity}
            for name, complexity in cls_metrics.method_complexities.items()
        ]

        return sorted(breakdown, key=lambda x: x["complexity"], reverse=True)
