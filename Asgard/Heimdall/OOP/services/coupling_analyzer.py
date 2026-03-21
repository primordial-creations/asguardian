"""
Heimdall Coupling Analyzer Service

Analyzes Python code for coupling metrics:
- CBO (Coupling Between Objects): Count of classes this class is coupled to
- Ca (Afferent Coupling): Number of classes that depend on this class
- Ce (Efferent Coupling): Number of classes this class depends on
- I (Instability): Ce / (Ca + Ce) - ranges from 0 (stable) to 1 (unstable)

Coupling occurs when a class:
- Inherits from another class
- Uses another class as a type (parameters, return types, variables)
- Calls methods on another class
- Creates instances of another class
- Accesses attributes of another class
"""

import ast
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Heimdall.OOP.models.oop_models import (
    ClassCouplingMetrics,
    OOPConfig,
)
from Asgard.Heimdall.OOP.utilities.class_utils import (
    ClassInfo,
    extract_classes_from_file,
    get_imports_from_file,
)
from Asgard.Heimdall.OOP.services._coupling_visitor import CouplingVisitor
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory


class CouplingAnalyzer:
    """
    Analyzes Python code for class coupling metrics.

    Coupling Between Objects (CBO) measures how many other classes a class
    is coupled to. High coupling indicates:
    - Difficult to test in isolation
    - Changes ripple through the codebase
    - Hard to reuse independently
    """

    def __init__(self, config: Optional[OOPConfig] = None):
        """Initialize the coupling analyzer."""
        self.config = config or OOPConfig()

    def analyze(self, scan_path: Optional[Path] = None) -> List[ClassCouplingMetrics]:
        """
        Analyze coupling metrics for all classes in the path.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            List of ClassCouplingMetrics for each class
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        all_classes: Dict[str, Dict] = {}
        file_classes: Dict[str, List[ClassInfo]] = {}
        file_imports: Dict[str, Set[str]] = {}

        exclude_patterns = list(self.config.exclude_patterns)
        if not self.config.include_tests:
            exclude_patterns.extend(["test_", "_test.py", "tests/", "conftest.py"])

        for file_path in scan_directory(
            path,
            exclude_patterns=exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            try:
                classes = extract_classes_from_file(file_path)
                file_classes[str(file_path)] = classes

                imports, from_imports = get_imports_from_file(file_path)
                imported_names: Set[str] = set()
                for names in from_imports.values():
                    imported_names.update(names)
                file_imports[str(file_path)] = imported_names

                for cls in classes:
                    all_classes[cls.name] = {
                        "file": str(file_path),
                        "relative": str(file_path.relative_to(path)),
                        "line": cls.line_number,
                        "info": cls,
                    }
            except (SyntaxError, Exception):
                continue

        all_class_names = set(all_classes.keys())

        results: List[ClassCouplingMetrics] = []
        coupling_to: Dict[str, Set[str]] = {}
        coupling_from: Dict[str, Set[str]] = {}

        for class_name, class_data in all_classes.items():
            file_path = Path(class_data["file"])

            try:
                source = file_path.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source)
            except (SyntaxError, Exception):
                continue

            imported_names = file_imports.get(str(file_path), set())
            visitor = CouplingVisitor(class_name, all_class_names, imported_names)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    visitor.visit(node)
                    break

            coupling_to[class_name] = visitor.coupled_classes

        for class_name in all_class_names:
            coupling_from[class_name] = set()

        for class_name, coupled_classes in coupling_to.items():
            for coupled in coupled_classes:
                if coupled in coupling_from:
                    coupling_from[coupled].add(class_name)

        for class_name, class_data in all_classes.items():
            ce = len(coupling_to.get(class_name, set()))
            ca = len(coupling_from.get(class_name, set()))
            cbo = ce
            instability = ce / (ca + ce) if (ca + ce) > 0 else 0.0

            coupling_level = ClassCouplingMetrics.calculate_coupling_level(cbo)
            severity = ClassCouplingMetrics.calculate_severity(cbo, self.config.cbo_threshold)

            metrics = ClassCouplingMetrics(
                class_name=class_name,
                file_path=class_data["file"],
                relative_path=class_data["relative"],
                line_number=class_data["line"],
                cbo=cbo,
                afferent_coupling=ca,
                efferent_coupling=ce,
                instability=instability,
                coupled_to=coupling_to.get(class_name, set()),
                coupled_from=coupling_from.get(class_name, set()),
                coupling_level=coupling_level,
                severity=severity,
            )
            results.append(metrics)

        _ = time.time() - start_time
        return results

    def analyze_file(self, file_path: Path) -> List[ClassCouplingMetrics]:
        """
        Analyze coupling metrics for a single file.

        Note: This provides limited results since afferent coupling
        requires knowledge of other files.

        Args:
            file_path: Path to the Python file

        Returns:
            List of ClassCouplingMetrics for classes in the file
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File does not exist: {path}")

        classes = extract_classes_from_file(path)
        all_class_names = {cls.name for cls in classes}
        imports, from_imports = get_imports_from_file(path)
        imported_names: Set[str] = set()
        for names in from_imports.values():
            imported_names.update(names)

        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
        except (SyntaxError, Exception):
            return []

        results = []
        coupling_to: Dict[str, Set[str]] = {}

        for cls in classes:
            visitor = CouplingVisitor(cls.name, all_class_names, imported_names)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == cls.name:
                    visitor.visit(node)
                    break
            coupling_to[cls.name] = visitor.coupled_classes

        coupling_from: Dict[str, Set[str]] = {cls.name: set() for cls in classes}
        for class_name, coupled in coupling_to.items():
            for c in coupled:
                if c in coupling_from:
                    coupling_from[c].add(class_name)

        for cls in classes:
            ce = len(coupling_to.get(cls.name, set()))
            ca = len(coupling_from.get(cls.name, set()))
            cbo = ce
            instability = ce / (ca + ce) if (ca + ce) > 0 else 0.0
            coupling_level = ClassCouplingMetrics.calculate_coupling_level(cbo)
            severity = ClassCouplingMetrics.calculate_severity(cbo, self.config.cbo_threshold)

            metrics = ClassCouplingMetrics(
                class_name=cls.name,
                file_path=str(path),
                relative_path=path.name,
                line_number=cls.line_number,
                cbo=cbo,
                afferent_coupling=ca,
                efferent_coupling=ce,
                instability=instability,
                coupled_to=coupling_to.get(cls.name, set()),
                coupled_from=coupling_from.get(cls.name, set()),
                coupling_level=coupling_level,
                severity=severity,
            )
            results.append(metrics)

        return results
