"""
Heimdall SOLID Validator Service

Validates adherence to SOLID principles in Python code.
"""

import ast
import time
from pathlib import Path
from typing import List, Optional, Set

from Asgard.Heimdall.Architecture.models.architecture_models import (
    ArchitectureConfig,
    SOLIDPrinciple,
    SOLIDReport,
    SOLIDViolation,
    ViolationSeverity,
)
from Asgard.Heimdall.Architecture.utilities.ast_utils import (
    extract_classes,
    get_class_methods,
    get_public_methods,
)
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory
from Asgard.Heimdall.Architecture.services._solid_reporter import (
    generate_text_report as _gen_text,
    generate_json_report as _gen_json,
    generate_markdown_report as _gen_markdown,
)
from Asgard.Heimdall.Architecture.services._solid_checks import (
    extract_method_prefixes,
    check_ocp,
    check_lsp,
    check_isp,
    check_dip,
)


class SOLIDValidator:
    """
    Validates SOLID principles in Python code.

    SOLID Principles:
    - SRP: Single Responsibility Principle
    - OCP: Open/Closed Principle
    - LSP: Liskov Substitution Principle
    - ISP: Interface Segregation Principle
    - DIP: Dependency Inversion Principle
    """

    def __init__(self, config: Optional[ArchitectureConfig] = None):
        """Initialize the SOLID validator."""
        self.config = config or ArchitectureConfig()

    def validate(self, scan_path: Optional[Path] = None) -> SOLIDReport:
        """
        Validate SOLID principles for all classes.

        Args:
            scan_path: Root path to scan

        Returns:
            SOLIDReport with all violations
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()
        report = SOLIDReport(scan_path=str(path))

        for file_path in scan_directory(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            try:
                source = file_path.read_text(encoding="utf-8", errors="ignore")
                classes = extract_classes(source)

                for class_node in classes:
                    report.total_classes += 1

                    # Check each SOLID principle
                    violations = []
                    violations.extend(self._check_srp(class_node, file_path, source))
                    violations.extend(self._check_ocp(class_node, file_path, source))
                    violations.extend(self._check_lsp(class_node, file_path, source))
                    violations.extend(self._check_isp(class_node, file_path, source))
                    violations.extend(self._check_dip(class_node, file_path, source))

                    for v in violations:
                        report.add_violation(v)

            except (SyntaxError, Exception):
                continue

        report.scan_duration_seconds = time.time() - start_time
        return report

    def _check_srp(
        self,
        class_node: ast.ClassDef,
        file_path: Path,
        source: str
    ) -> List[SOLIDViolation]:
        """
        Check Single Responsibility Principle.

        A class should have only one reason to change.
        Indicators of SRP violation:
        - Too many public methods
        - Too many responsibilities (method name prefixes)
        - High number of dependencies
        """
        violations = []
        methods = get_class_methods(class_node)
        public_methods = get_public_methods(class_node)

        # Check method count
        if len(methods) > self.config.max_method_count:
            violations.append(SOLIDViolation(
                principle=SOLIDPrinciple.SRP,
                class_name=class_node.name,
                file_path=str(file_path),
                line_number=class_node.lineno,
                message=f"Class has {len(methods)} methods (threshold: {self.config.max_method_count})",
                severity=ViolationSeverity.MODERATE,
                suggestion="Consider splitting this class into smaller, focused classes",
            ))

        # Check public method count
        if len(public_methods) > self.config.max_public_methods:
            violations.append(SOLIDViolation(
                principle=SOLIDPrinciple.SRP,
                class_name=class_node.name,
                file_path=str(file_path),
                line_number=class_node.lineno,
                message=f"Class has {len(public_methods)} public methods (threshold: {self.config.max_public_methods})",
                severity=ViolationSeverity.LOW,
                suggestion="Consider reducing the public interface",
            ))

        # Check for multiple responsibilities via method name prefixes
        prefixes = self._extract_method_prefixes(methods)
        if len(prefixes) > self.config.max_class_responsibilities:
            violations.append(SOLIDViolation(
                principle=SOLIDPrinciple.SRP,
                class_name=class_node.name,
                file_path=str(file_path),
                line_number=class_node.lineno,
                message=f"Class appears to have {len(prefixes)} responsibilities: {', '.join(sorted(prefixes))}",
                severity=ViolationSeverity.HIGH,
                suggestion="Split class by responsibility",
            ))

        return violations

    def _extract_method_prefixes(self, methods: List[ast.FunctionDef]) -> Set[str]:
        """Extract responsibility prefixes from method names."""
        return extract_method_prefixes(methods)

    def _check_ocp(self, class_node: ast.ClassDef, file_path: Path, source: str) -> List[SOLIDViolation]:
        """Check Open/Closed Principle."""
        return check_ocp(class_node, file_path)

    def _check_lsp(self, class_node: ast.ClassDef, file_path: Path, source: str) -> List[SOLIDViolation]:
        """Check Liskov Substitution Principle."""
        return check_lsp(class_node, file_path)

    def _check_isp(self, class_node: ast.ClassDef, file_path: Path, source: str) -> List[SOLIDViolation]:
        """Check Interface Segregation Principle."""
        return check_isp(class_node, file_path)

    def _check_dip(self, class_node: ast.ClassDef, file_path: Path, source: str) -> List[SOLIDViolation]:
        """Check Dependency Inversion Principle."""
        return check_dip(class_node, file_path, self.config.max_dependencies)

    def validate_class(
        self,
        class_source: str,
        class_name: Optional[str] = None
    ) -> SOLIDReport:
        """
        Validate SOLID principles for a single class.

        Args:
            class_source: Python source code containing the class
            class_name: Optional specific class to validate

        Returns:
            SOLIDReport with violations
        """
        report = SOLIDReport()

        classes = extract_classes(class_source)
        if class_name:
            classes = [c for c in classes if c.name == class_name]

        for class_node in classes:
            report.total_classes += 1
            file_path = Path("<string>")

            violations = []
            violations.extend(self._check_srp(class_node, file_path, class_source))
            violations.extend(self._check_ocp(class_node, file_path, class_source))
            violations.extend(self._check_lsp(class_node, file_path, class_source))
            violations.extend(self._check_isp(class_node, file_path, class_source))
            violations.extend(self._check_dip(class_node, file_path, class_source))

            for v in violations:
                report.add_violation(v)

        return report

    def generate_report(self, result: SOLIDReport, format: str = "text") -> str:
        """Generate a formatted report."""
        if format == "json":
            return _gen_json(result)
        elif format == "markdown":
            return _gen_markdown(result)
        else:
            return _gen_text(result)
