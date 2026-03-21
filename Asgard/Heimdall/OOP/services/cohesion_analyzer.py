"""
Heimdall Cohesion Analyzer Service

Analyzes Python code for cohesion metrics:
- LCOM (Lack of Cohesion of Methods): Measures how related methods are
- LCOM4 (Henderson-Sellers variant): Alternative cohesion calculation

Low cohesion (high LCOM) indicates:
- Class is doing too many unrelated things
- Should potentially be split into multiple classes
- Methods don't work together on shared data
"""

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from Asgard.Heimdall.OOP.models.oop_models import (
    ClassCohesionMetrics,
    OOPConfig,
)
from Asgard.Heimdall.OOP.utilities.class_utils import (
    ClassInfo,
    extract_classes_from_file,
    get_class_attributes,
    get_class_methods,
)
from Asgard.Heimdall.OOP.services._cohesion_helpers import (
    calculate_lcom_ck,
    calculate_lcom_hs,
    suggest_splits as _suggest_splits,
)
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory


class CohesionAnalyzer:
    """
    Analyzes Python code for class cohesion metrics.

    Cohesion measures how closely the methods of a class are related
    to each other. High cohesion is desirable - it means the class
    has a single, well-defined purpose.

    LCOM (Lack of Cohesion of Methods):
    - 0.0 = Perfect cohesion (all methods share attributes)
    - 1.0 = No cohesion (no methods share attributes)
    """

    def __init__(self, config: Optional[OOPConfig] = None):
        """Initialize the cohesion analyzer."""
        self.config = config or OOPConfig()

    def analyze(self, scan_path: Optional[Path] = None) -> List[ClassCohesionMetrics]:
        """
        Analyze cohesion metrics for all classes in the path.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            List of ClassCohesionMetrics for each class
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        results: List[ClassCohesionMetrics] = []

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

    def _analyze_file(self, file_path: Path, root_path: Path) -> List[ClassCohesionMetrics]:
        """Analyze cohesion for all classes in a file."""
        classes = extract_classes_from_file(file_path)
        results = []

        for cls in classes:
            metrics = self._analyze_class(cls, file_path, root_path)
            if metrics:
                results.append(metrics)

        return results

    def _analyze_class(
        self, cls: ClassInfo, file_path: Path, root_path: Path
    ) -> Optional[ClassCohesionMetrics]:
        """Analyze cohesion for a single class."""
        methods = get_class_methods(cls)
        attributes = get_class_attributes(cls)

        regular_methods = [m for m in methods if not m.name.startswith("_")]

        if len(regular_methods) < 2 or len(attributes) < 1:
            lcom = 0.0
            lcom4 = 0.0
        else:
            method_attr_usage: Dict[str, Set[str]] = {}
            for method in regular_methods:
                method_attr_usage[method.name] = method.accessed_attributes & attributes

            lcom = calculate_lcom_ck(method_attr_usage)
            lcom4 = calculate_lcom_hs(method_attr_usage, len(attributes))

        cohesion_level = ClassCohesionMetrics.calculate_cohesion_level(lcom)
        severity = ClassCohesionMetrics.calculate_severity(lcom, self.config.lcom_threshold)

        try:
            relative_path = str(file_path.relative_to(root_path))
        except ValueError:
            relative_path = file_path.name

        return ClassCohesionMetrics(
            class_name=cls.name,
            file_path=str(file_path),
            relative_path=relative_path,
            line_number=cls.line_number,
            lcom=lcom,
            lcom4=lcom4,
            method_count=len(methods),
            attribute_count=len(attributes),
            method_attribute_usage={
                m.name: m.accessed_attributes & attributes for m in methods
            },
            cohesion_level=cohesion_level,
            severity=severity,
        )

    def analyze_file(self, file_path: Path) -> List[ClassCohesionMetrics]:
        """
        Analyze cohesion metrics for a single file.

        Args:
            file_path: Path to the Python file

        Returns:
            List of ClassCohesionMetrics for classes in the file
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File does not exist: {path}")

        return self._analyze_file(path, path.parent)

    def get_low_cohesion_classes(
        self, scan_path: Optional[Path] = None, threshold: Optional[float] = None
    ) -> List[ClassCohesionMetrics]:
        """
        Get classes with low cohesion (high LCOM).

        Args:
            scan_path: Root path to scan
            threshold: LCOM threshold (default: config.lcom_threshold)

        Returns:
            List of classes with LCOM above threshold
        """
        threshold = threshold or self.config.lcom_threshold
        metrics = self.analyze(scan_path)
        return [m for m in metrics if m.lcom > threshold]

    def suggest_splits(
        self, cls_metrics: ClassCohesionMetrics
    ) -> List[Tuple[str, Set[str]]]:
        """
        Suggest how to split a low-cohesion class.

        Groups methods by shared attribute access to suggest
        potential class splits.

        Args:
            cls_metrics: Cohesion metrics for the class

        Returns:
            List of (group_name, method_set) tuples
        """
        return _suggest_splits(cls_metrics)
