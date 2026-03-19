"""
Heimdall SOLID Validator Service

Validates adherence to SOLID principles in Python code.
"""

import ast
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

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
    get_class_attributes,
    get_method_attributes,
    get_class_bases,
    get_constructor_params,
    is_abstract_class,
    get_abstract_methods,
    get_imports,
)
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory


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
        prefixes = set()
        responsibility_words = {
            "get", "set", "is", "has", "can",  # Accessors (single responsibility)
            "validate", "check", "verify",  # Validation
            "create", "build", "make", "generate",  # Creation
            "parse", "process", "transform", "convert",  # Processing
            "save", "load", "read", "write", "store",  # Persistence
            "send", "receive", "notify", "dispatch",  # Communication
            "render", "display", "show", "format",  # Presentation
            "calculate", "compute", "analyze",  # Computation
        }

        for method in methods:
            name = method.name
            if name.startswith("_"):
                continue

            # Extract first word
            parts = []
            current = []
            for char in name:
                if char == "_":
                    if current:
                        parts.append("".join(current).lower())
                        current = []
                elif char.isupper() and current:
                    parts.append("".join(current).lower())
                    current = [char.lower()]
                else:
                    current.append(char.lower())
            if current:
                parts.append("".join(current))

            if parts and parts[0] in responsibility_words:
                # Group similar responsibilities
                prefix = parts[0]
                if prefix in {"get", "set", "is", "has", "can"}:
                    continue  # Skip accessor methods
                if prefix in {"validate", "check", "verify"}:
                    prefixes.add("validation")
                elif prefix in {"create", "build", "make", "generate"}:
                    prefixes.add("creation")
                elif prefix in {"parse", "process", "transform", "convert"}:
                    prefixes.add("processing")
                elif prefix in {"save", "load", "read", "write", "store"}:
                    prefixes.add("persistence")
                elif prefix in {"send", "receive", "notify", "dispatch"}:
                    prefixes.add("communication")
                elif prefix in {"render", "display", "show", "format"}:
                    prefixes.add("presentation")
                elif prefix in {"calculate", "compute", "analyze"}:
                    prefixes.add("computation")

        return prefixes

    def _check_ocp(
        self,
        class_node: ast.ClassDef,
        file_path: Path,
        source: str
    ) -> List[SOLIDViolation]:
        """
        Check Open/Closed Principle.

        A class should be open for extension but closed for modification.
        Indicators of OCP violation:
        - Large switch/if-elif chains on type
        - Checking isinstance for multiple types
        - No use of polymorphism for variations
        """
        violations = []

        for method in get_class_methods(class_node):
            # Check for long if-elif chains
            if_chain_length = self._count_if_chain(method)
            if if_chain_length >= 4:
                violations.append(SOLIDViolation(
                    principle=SOLIDPrinciple.OCP,
                    class_name=class_node.name,
                    file_path=str(file_path),
                    line_number=method.lineno,
                    message=f"Method '{method.name}' has {if_chain_length} branches - consider polymorphism",
                    severity=ViolationSeverity.MODERATE,
                    suggestion="Replace conditionals with polymorphism using a strategy pattern",
                ))

            # Check for isinstance chains
            isinstance_count = self._count_isinstance_checks(method)
            if isinstance_count >= 3:
                violations.append(SOLIDViolation(
                    principle=SOLIDPrinciple.OCP,
                    class_name=class_node.name,
                    file_path=str(file_path),
                    line_number=method.lineno,
                    message=f"Method '{method.name}' has {isinstance_count} isinstance checks",
                    severity=ViolationSeverity.MODERATE,
                    suggestion="Use polymorphism instead of type checking",
                ))

        return violations

    def _count_if_chain(self, method: ast.FunctionDef) -> int:
        """Count the length of if-elif chains."""
        max_chain = 0

        for node in ast.walk(method):
            if isinstance(node, ast.If):
                chain = 1
                current = node
                while current.orelse:
                    if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                        chain += 1
                        current = current.orelse[0]
                    else:
                        if current.orelse:
                            chain += 1  # else branch
                        break
                max_chain = max(max_chain, chain)

        return max_chain

    def _count_isinstance_checks(self, method: ast.FunctionDef) -> int:
        """Count isinstance calls in a method."""
        count = 0
        for node in ast.walk(method):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "isinstance":
                    count += 1
        return count

    def _check_lsp(
        self,
        class_node: ast.ClassDef,
        file_path: Path,
        source: str
    ) -> List[SOLIDViolation]:
        """
        Check Liskov Substitution Principle.

        Subtypes must be substitutable for their base types.
        Indicators of LSP violation:
        - Overriding methods that throw NotImplementedError
        - Overriding methods with different signatures
        - Methods that check self type
        """
        violations = []
        bases = get_class_bases(class_node)

        if not bases or bases == ["object"]:
            return violations  # No base class to violate

        for method in get_class_methods(class_node):
            # Check for NotImplementedError raises
            for node in ast.walk(method):
                if isinstance(node, ast.Raise):
                    if isinstance(node.exc, ast.Call):
                        if isinstance(node.exc.func, ast.Name):
                            if node.exc.func.id == "NotImplementedError":
                                violations.append(SOLIDViolation(
                                    principle=SOLIDPrinciple.LSP,
                                    class_name=class_node.name,
                                    file_path=str(file_path),
                                    line_number=node.lineno,
                                    message=f"Method '{method.name}' raises NotImplementedError in derived class",
                                    severity=ViolationSeverity.HIGH,
                                    suggestion="Override method with proper implementation or use abstract base class",
                                ))

            # Check for self type checking
            for node in ast.walk(method):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "type":
                        if len(node.args) == 1:
                            if isinstance(node.args[0], ast.Name) and node.args[0].id == "self":
                                violations.append(SOLIDViolation(
                                    principle=SOLIDPrinciple.LSP,
                                    class_name=class_node.name,
                                    file_path=str(file_path),
                                    line_number=node.lineno,
                                    message=f"Method '{method.name}' checks type(self)",
                                    severity=ViolationSeverity.MODERATE,
                                    suggestion="Avoid type checking on self in derived classes",
                                ))

        return violations

    def _check_isp(
        self,
        class_node: ast.ClassDef,
        file_path: Path,
        source: str
    ) -> List[SOLIDViolation]:
        """
        Check Interface Segregation Principle.

        Clients should not be forced to depend on interfaces they don't use.
        Indicators of ISP violation:
        - Abstract classes with many abstract methods
        - Classes implementing empty/pass methods
        """
        violations = []

        # Check if this is an abstract class
        if is_abstract_class(class_node):
            abstract_methods = get_abstract_methods(class_node)
            if len(abstract_methods) > 7:
                violations.append(SOLIDViolation(
                    principle=SOLIDPrinciple.ISP,
                    class_name=class_node.name,
                    file_path=str(file_path),
                    line_number=class_node.lineno,
                    message=f"Interface has {len(abstract_methods)} abstract methods",
                    severity=ViolationSeverity.MODERATE,
                    suggestion="Split into smaller, focused interfaces",
                ))

        # Check for empty method implementations
        empty_methods = []
        for method in get_class_methods(class_node):
            if self._is_empty_method(method):
                empty_methods.append(method.name)

        if len(empty_methods) >= 3:
            violations.append(SOLIDViolation(
                principle=SOLIDPrinciple.ISP,
                class_name=class_node.name,
                file_path=str(file_path),
                line_number=class_node.lineno,
                message=f"Class has {len(empty_methods)} empty methods: {', '.join(empty_methods[:3])}",
                severity=ViolationSeverity.HIGH,
                suggestion="This class may be implementing an interface it doesn't need",
            ))

        return violations

    def _is_empty_method(self, method: ast.FunctionDef) -> bool:
        """Check if a method body is empty (just pass or ...)."""
        if len(method.body) == 1:
            stmt = method.body[0]
            if isinstance(stmt, ast.Pass):
                return True
            if isinstance(stmt, ast.Expr):
                if isinstance(stmt.value, ast.Constant):
                    if stmt.value.value is ...:
                        return True
        return False

    def _check_dip(
        self,
        class_node: ast.ClassDef,
        file_path: Path,
        source: str
    ) -> List[SOLIDViolation]:
        """
        Check Dependency Inversion Principle.

        High-level modules should not depend on low-level modules.
        Both should depend on abstractions.
        Indicators of DIP violation:
        - Instantiating concrete classes in constructor
        - Direct imports of concrete implementations
        - No dependency injection
        """
        violations = []

        # Check constructor for direct instantiation
        for method in get_class_methods(class_node):
            if method.name == "__init__":
                instantiations = self._find_instantiations(method)

                # Filter out standard types
                concrete_deps = [
                    i for i in instantiations
                    if i not in {"list", "dict", "set", "tuple", "str", "int", "float", "bool"}
                    and not i.startswith("_")
                ]

                if len(concrete_deps) > 3:
                    violations.append(SOLIDViolation(
                        principle=SOLIDPrinciple.DIP,
                        class_name=class_node.name,
                        file_path=str(file_path),
                        line_number=method.lineno,
                        message=f"Constructor instantiates {len(concrete_deps)} concrete dependencies",
                        severity=ViolationSeverity.MODERATE,
                        suggestion="Use dependency injection instead of direct instantiation",
                    ))

        # Check for too many dependencies
        params = get_constructor_params(class_node)
        if len(params) > self.config.max_dependencies:
            violations.append(SOLIDViolation(
                principle=SOLIDPrinciple.DIP,
                class_name=class_node.name,
                file_path=str(file_path),
                line_number=class_node.lineno,
                message=f"Class has {len(params)} constructor dependencies (threshold: {self.config.max_dependencies})",
                severity=ViolationSeverity.LOW,
                suggestion="Consider using a facade or splitting the class",
            ))

        return violations

    def _find_instantiations(self, method: ast.FunctionDef) -> List[str]:
        """Find class instantiations in a method."""
        instantiations = []

        for node in ast.walk(method):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    # Check if it looks like a class (PascalCase)
                    name = node.func.id
                    if name[0].isupper():
                        instantiations.append(name)
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                    if name[0].isupper():
                        instantiations.append(name)

        return instantiations

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
        """
        Generate a formatted report.

        Args:
            result: SOLIDReport to format
            format: Output format ("text", "json", "markdown")

        Returns:
            Formatted report string
        """
        if format == "json":
            return self._generate_json_report(result)
        elif format == "markdown":
            return self._generate_markdown_report(result)
        else:
            return self._generate_text_report(result)

    def _generate_text_report(self, result: SOLIDReport) -> str:
        """Generate text format report."""
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  HEIMDALL SOLID PRINCIPLES REPORT")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"  Scan Path:      {result.scan_path}")
        lines.append(f"  Total Classes:  {result.total_classes}")
        lines.append(f"  Total Violations: {result.total_violations}")
        lines.append("")

        for principle in SOLIDPrinciple:
            violations = result.violations_by_principle[principle]
            if violations:
                lines.append("-" * 70)
                lines.append(f"  {violations[0].principle_name}")
                lines.append("-" * 70)
                lines.append("")

                for v in violations:
                    lines.append(f"  [{v.severity.value.upper()}] {v.class_name}")
                    lines.append(f"    File: {v.file_path}:{v.line_number}")
                    lines.append(f"    {v.message}")
                    if v.suggestion:
                        lines.append(f"    Suggestion: {v.suggestion}")
                    lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)

    def _generate_json_report(self, result: SOLIDReport) -> str:
        """Generate JSON format report."""
        output = {
            "scan_path": result.scan_path,
            "scanned_at": result.scanned_at.isoformat(),
            "total_classes": result.total_classes,
            "total_violations": result.total_violations,
            "violations": [
                {
                    "principle": v.principle.value,
                    "class_name": v.class_name,
                    "file_path": v.file_path,
                    "line_number": v.line_number,
                    "message": v.message,
                    "severity": v.severity.value,
                    "suggestion": v.suggestion,
                }
                for v in result.violations
            ],
        }

        return json.dumps(output, indent=2)

    def _generate_markdown_report(self, result: SOLIDReport) -> str:
        """Generate Markdown format report."""
        lines = []
        lines.append("# Heimdall SOLID Principles Report")
        lines.append("")
        lines.append(f"- **Scan Path:** `{result.scan_path}`")
        lines.append(f"- **Total Classes:** {result.total_classes}")
        lines.append(f"- **Total Violations:** {result.total_violations}")
        lines.append("")

        for principle in SOLIDPrinciple:
            violations = result.violations_by_principle[principle]
            if violations:
                lines.append(f"## {violations[0].principle_name}")
                lines.append("")
                lines.append("| Class | File | Message | Severity |")
                lines.append("|-------|------|---------|----------|")

                for v in violations:
                    lines.append(
                        f"| {v.class_name} | {v.file_path}:{v.line_number} | "
                        f"{v.message} | {v.severity.value.upper()} |"
                    )

                lines.append("")

        return "\n".join(lines)
