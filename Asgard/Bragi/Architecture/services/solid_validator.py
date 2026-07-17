"""
Heimdall SOLID Validator Service

Validates adherence to SOLID principles in Python code.
"""

import ast
import time
from pathlib import Path
from typing import List, Optional, Set

from Asgard.Bragi.Architecture.models.architecture_models import (
    ArchitectureConfig,
    SOLIDPrinciple,
    SOLIDReport,
    SOLIDViolation,
    ViolationSeverity,
)
from Asgard.Bragi.Architecture.utilities.ast_utils import (
    extract_classes,
    get_class_methods,
    get_public_methods,
)
from Asgard.Bragi.Quality.utilities.file_utils import scan_directory
from Asgard.Bragi.Architecture.services._solid_reporter import (
    generate_text_report as _gen_text,
    generate_json_report as _gen_json,
    generate_markdown_report as _gen_markdown,
)
from Asgard.Bragi.Architecture.services._solid_checks import (
    extract_method_prefixes,
    check_ocp,
    check_lsp,
    check_isp,
    check_dip,
)
from Asgard.Bragi.Architecture.services._solid_detectors import (
    is_visitor_class,
    is_utility_class,
)
from Asgard.Bragi.Architecture.services._generic_solid_checks import (
    check_srp_method_count,
    check_isp_interface_size,
    check_dip_concrete_instantiation,
    check_ocp_type_checking,
)
from Asgard.Bragi.Architecture.services._treesitter_solid_checks import (
    check_srp_lcom4,
    check_isp_fat_interface,
    check_dip_concrete_dependency,
    check_ocp_type_dispatch,
)
from Asgard.Heimdall.treesitter._language_loader import is_available as _ts_available
from Asgard.Shared.common.language_registry import EXTENSION_TO_LANGUAGE
from Asgard.Bragi.Architecture.cir.builder import build_file_cir
from Asgard.Bragi.Architecture.evaluators import evaluate_file as _evaluate_cir


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
        """Check Single Responsibility Principle."""
        # Visitor classes have many visit_* methods by design
        if is_visitor_class(class_node):
            return []

        violations = []
        methods = get_class_methods(class_node)
        public_methods = get_public_methods(class_node)

        # Utility/facade classes get 2x the normal thresholds
        is_util = is_utility_class(class_node.name)
        method_threshold = self.config.max_method_count * 2 if is_util else self.config.max_method_count
        public_threshold = self.config.max_public_methods * 2 if is_util else self.config.max_public_methods

        if len(methods) > method_threshold:
            violations.append(SOLIDViolation(
                principle=SOLIDPrinciple.SRP,
                class_name=class_node.name,
                file_path=str(file_path),
                line_number=class_node.lineno,
                message=f"Class has {len(methods)} methods (threshold: {method_threshold})",
                severity=ViolationSeverity.MODERATE,
                suggestion="Consider splitting this class into smaller, focused classes",
            ))

        if len(public_methods) > public_threshold:
            violations.append(SOLIDViolation(
                principle=SOLIDPrinciple.SRP,
                class_name=class_node.name,
                file_path=str(file_path),
                line_number=class_node.lineno,
                message=f"Class has {len(public_methods)} public methods (threshold: {public_threshold})",
                severity=ViolationSeverity.LOW,
                suggestion="Consider reducing the public interface",
            ))

        prefixes = self._extract_method_prefixes(methods)  # type: ignore[arg-type]
        responsibility_threshold = self.config.max_class_responsibilities + 2 if is_util else self.config.max_class_responsibilities
        if len(prefixes) > responsibility_threshold:
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

    # ------------------------------------------------------------------
    # Multi-language generic analysis
    # ------------------------------------------------------------------

    def analyze_file_generic(
        self,
        file_path: Path,
        language: str,
    ) -> List[SOLIDViolation]:
        """
        Run generic regex-based SOLID checks on a single non-Python file.

        Args:
            file_path: Path to the source file.
            language: Language identifier (e.g. "java", "go", "typescript").

        Returns:
            List of SOLIDViolation found in the file.
        """
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return []

        path_str = str(file_path)
        source = "\n".join(lines)
        all_rules = {
            "solid.srp-lcom4": True,
            "solid.isp-fat-interface": True,
            "solid.dip-concrete-dependency": True,
            "solid.ocp-type-dispatch": True,
        }

        # CIR pipeline (plan 02): one extraction pass -> language-agnostic
        # ClassInfo/MethodInfo -> pure-Python evaluators with confidence
        # grades. Falls back to the legacy tree-sitter ad-hoc-walk checks,
        # then to regex, when CIR extraction has no handler for `language`
        # or the parse fails.
        file_info = build_file_cir(path_str, source, language)
        if file_info is not None and file_info.classes:
            return _evaluate_cir(file_info)

        if _ts_available(language):
            raw = []
            raw.extend(check_srp_lcom4(path_str, source, language, all_rules))
            raw.extend(check_isp_fat_interface(path_str, source, language, all_rules))
            raw.extend(check_dip_concrete_dependency(path_str, source, language, all_rules))
            raw.extend(check_ocp_type_dispatch(path_str, source, language, all_rules))
            return [_dict_to_violation(d, path_str) for d in raw]

        violations: List[SOLIDViolation] = []
        violations.extend(check_srp_method_count(path_str, lines, language, threshold=self.config.max_public_methods))
        violations.extend(check_isp_interface_size(path_str, lines, language))
        violations.extend(check_dip_concrete_instantiation(path_str, lines, language))
        violations.extend(check_ocp_type_checking(path_str, lines, language))
        return violations

    def analyze_multilang(
        self,
        scan_path: Optional[Path] = None,
        extensions: Optional[List[str]] = None,
    ) -> SOLIDReport:
        """
        Scan non-Python source files for SOLID violations using regex heuristics.

        Args:
            scan_path: Root directory to scan (defaults to config.scan_path).
            extensions: File extensions to scan (e.g. [".java", ".go"]).
                        Defaults to a broad set of common compiled/scripted languages.

        Returns:
            SOLIDReport containing all found violations.
        """
        from Asgard.Bragi.Quality.utilities.file_utils import scan_directory

        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        target_extensions = extensions or [
            ".java", ".cs", ".go", ".rb", ".js", ".ts", ".jsx", ".tsx", ".php", ".kt",
        ]

        start_time = time.time()
        report = SOLIDReport(scan_path=str(path))

        for file_path in scan_directory(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=target_extensions,
        ):
            language = EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower())
            if not language or language == "python":
                continue

            for v in self.analyze_file_generic(file_path, language):
                report.add_violation(v)

        report.scan_duration_seconds = time.time() - start_time
        return report

    def generate_report(self, result: SOLIDReport, format: str = "text") -> str:
        """Generate a formatted report."""
        if format == "json":
            return _gen_json(result)
        elif format == "markdown":
            return _gen_markdown(result)
        else:
            return _gen_text(result)


_RULE_TO_PRINCIPLE = {
    "solid.srp-lcom4": SOLIDPrinciple.SRP,
    "solid.isp-fat-interface": SOLIDPrinciple.ISP,
    "solid.dip-concrete-dependency": SOLIDPrinciple.DIP,
    "solid.ocp-type-dispatch": SOLIDPrinciple.OCP,
}

_SEVERITY_MAP = {
    "warning": ViolationSeverity.MODERATE,
    "error": ViolationSeverity.HIGH,
}


def _dict_to_violation(d: dict, file_path: str) -> SOLIDViolation:
    return SOLIDViolation(
        principle=_RULE_TO_PRINCIPLE.get(d["rule_id"], SOLIDPrinciple.SRP),
        class_name="<file>",
        file_path=file_path,
        line_number=d["line"],
        message=d["message"],
        severity=_SEVERITY_MAP.get(d["severity"], ViolationSeverity.MODERATE),
        suggestion="",
    )
