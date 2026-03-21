import ast
from typing import Dict, List, Optional

from Asgard.Heimdall.Quality.models.library_usage_models import (
    ForbiddenImportSeverity,
    ForbiddenImportViolation,
)


class ForbiddenImportVisitor(ast.NodeVisitor):
    """
    AST visitor that detects forbidden library imports.

    Walks the AST and identifies import statements for modules that
    should be using wrapper libraries instead.
    """

    def __init__(
        self,
        file_path: str,
        source_lines: List[str],
        forbidden_modules: Dict[str, str],
        default_severity: ForbiddenImportSeverity,
    ):
        """
        Initialize the forbidden import visitor.

        Args:
            file_path: Path to the file being analyzed
            source_lines: Source code lines for extracting context
            forbidden_modules: Mapping of forbidden module names to remediation
            default_severity: Default severity for violations
        """
        self.file_path = file_path
        self.source_lines = source_lines
        self.forbidden_modules = forbidden_modules
        self.default_severity = default_severity
        self.violations: List[ForbiddenImportViolation] = []

    def _get_code_snippet(self, line_number: int, context: int = 2) -> str:
        """Extract code snippet around the line."""
        start = max(0, line_number - context - 1)
        end = min(len(self.source_lines), line_number + context)
        lines = self.source_lines[start:end]
        return "\n".join(lines)

    def _get_import_statement(self, node: ast.stmt) -> str:
        """Extract the import statement text from source."""
        if node.lineno <= len(self.source_lines):
            line = self.source_lines[node.lineno - 1].strip()
            return line
        return ""

    def _check_module_forbidden(self, module_name: str) -> Optional[str]:
        """
        Check if a module name is forbidden.

        Returns the remediation message if forbidden, None otherwise.
        """
        if not module_name:
            return None

        if module_name in self.forbidden_modules:
            return self.forbidden_modules[module_name]

        for forbidden, remediation in self.forbidden_modules.items():
            if module_name.startswith(f"{forbidden}."):
                return remediation

        return None

    def _record_violation(
        self,
        node: ast.stmt,
        module_name: str,
        remediation: str,
    ) -> None:
        """Record a forbidden import violation."""
        self.violations.append(ForbiddenImportViolation(
            file_path=self.file_path,
            line_number=node.lineno,
            column=node.col_offset,
            import_statement=self._get_import_statement(node),
            module_name=module_name,
            severity=self.default_severity,
            remediation=remediation,
            code_snippet=self._get_code_snippet(node.lineno),
        ))

    def visit_Import(self, node: ast.Import) -> None:
        """Handle 'import X' statements."""
        for alias in node.names:
            module_name = alias.name
            remediation = self._check_module_forbidden(module_name)
            if remediation:
                self._record_violation(node, module_name, remediation)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Handle 'from X import Y' statements."""
        if node.module:
            remediation = self._check_module_forbidden(node.module)
            if remediation:
                self._record_violation(node, node.module, remediation)
        self.generic_visit(node)
