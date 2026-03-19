"""
Heimdall Complexity Analyzer Service

Analyzes Python code for cyclomatic and cognitive complexity.

Cyclomatic Complexity (McCabe):
- Measures the number of linearly independent paths through code
- Formula: CC = E - N + 2P (edges - nodes + 2 * connected components)
- Simplified: Count decision points + 1

Cognitive Complexity (SonarSource):
- Measures how difficult code is for humans to understand
- Penalizes nested structures and breaks in linear flow
- More accurate for modern code patterns
"""

import ast
import json
import time
from pathlib import Path
from typing import List, Optional, Tuple

from Asgard.Heimdall.Quality.models.complexity_models import (
    ComplexityConfig,
    ComplexityResult,
    ComplexitySeverity,
    FileComplexityAnalysis,
    FunctionComplexity,
)
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory


class CyclomaticComplexityVisitor(ast.NodeVisitor):
    """
    AST visitor that calculates cyclomatic complexity for Python functions.

    Cyclomatic complexity counts decision points:
    - if/elif statements
    - for/while loops
    - try/except blocks
    - boolean operators (and/or)
    - comprehensions
    - ternary expressions
    """

    def __init__(self):
        self.complexity = 1  # Base complexity

    def visit_If(self, node: ast.If) -> None:
        """Count if statements."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Count for loops."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        """Count while loops."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Count except handlers."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        """Count boolean operators (and/or add paths)."""
        # Each additional operand adds a path
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        """Count comprehension loops."""
        self.complexity += 1
        # Count ifs in comprehension
        self.complexity += len(node.ifs)
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        """Count ternary expressions."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        """Count assert statements as decision points."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        """Count match statement cases (Python 3.10+)."""
        # Each case is a decision point
        self.complexity += len(node.cases)
        self.generic_visit(node)


class CognitiveComplexityVisitor(ast.NodeVisitor):
    """
    AST visitor that calculates cognitive complexity for Python functions.

    Cognitive complexity differs from cyclomatic by:
    - Incrementing for nesting (nested structures are harder to understand)
    - Not counting structures that don't break linear flow
    - Penalizing recursion and breaks in control flow

    Based on SonarSource's cognitive complexity methodology.
    """

    def __init__(self):
        self.complexity = 0
        self.nesting_level = 0
        self._in_boolean_sequence = False

    def _increment(self, base: int = 1) -> None:
        """Add to complexity with nesting penalty."""
        self.complexity += base + self.nesting_level

    def _increment_nesting(self) -> None:
        """Increase nesting level."""
        self.nesting_level += 1

    def _decrement_nesting(self) -> None:
        """Decrease nesting level."""
        self.nesting_level = max(0, self.nesting_level - 1)

    def visit_If(self, node: ast.If) -> None:
        """Count if statements with nesting penalty."""
        self._increment()
        self._increment_nesting()
        for child in node.body:
            self.visit(child)
        self._decrement_nesting()

        # Handle elif chain (doesn't add nesting)
        for child in node.orelse:
            if isinstance(child, ast.If):
                self._increment(1)  # elif without nesting penalty
                self._increment_nesting()
                for subchild in child.body:
                    self.visit(subchild)
                self._decrement_nesting()
                # Continue to next elif
                for subchild in child.orelse:
                    if isinstance(subchild, ast.If):
                        continue
                    self.visit(subchild)
            else:
                # else block
                self.visit(child)

    def visit_For(self, node: ast.For) -> None:
        """Count for loops with nesting penalty."""
        self._increment()
        self._increment_nesting()
        for child in node.body:
            self.visit(child)
        self._decrement_nesting()
        for child in node.orelse:
            self.visit(child)

    def visit_While(self, node: ast.While) -> None:
        """Count while loops with nesting penalty."""
        self._increment()
        self._increment_nesting()
        for child in node.body:
            self.visit(child)
        self._decrement_nesting()
        for child in node.orelse:
            self.visit(child)

    def visit_Try(self, node: ast.Try) -> None:
        """Count try blocks with nesting penalty."""
        self._increment_nesting()
        for child in node.body:
            self.visit(child)
        self._decrement_nesting()

        # Each except handler
        for handler in node.handlers:
            self._increment()
            self._increment_nesting()
            for child in handler.body:
                self.visit(child)
            self._decrement_nesting()

        # Finally block doesn't add complexity
        for child in node.finalbody:
            self.visit(child)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        """
        Count boolean operator sequences.

        Only the first in a sequence adds complexity.
        Mixing and/or adds complexity.
        """
        if not self._in_boolean_sequence:
            self._increment(1)  # Without nesting for boolean ops
            self._in_boolean_sequence = True

        # Check for mixed operators
        self.generic_visit(node)
        self._in_boolean_sequence = False

    def visit_Break(self, node: ast.Break) -> None:
        """Break statements add complexity (interrupts flow)."""
        self._increment(1)

    def visit_Continue(self, node: ast.Continue) -> None:
        """Continue statements add complexity (interrupts flow)."""
        self._increment(1)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        """Lambda adds nesting but not base complexity."""
        self._increment_nesting()
        self.generic_visit(node)
        self._decrement_nesting()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        """List comprehensions add complexity."""
        self._increment()
        self._increment_nesting()
        self.generic_visit(node)
        self._decrement_nesting()

    def visit_DictComp(self, node: ast.DictComp) -> None:
        """Dict comprehensions add complexity."""
        self._increment()
        self._increment_nesting()
        self.generic_visit(node)
        self._decrement_nesting()

    def visit_SetComp(self, node: ast.SetComp) -> None:
        """Set comprehensions add complexity."""
        self._increment()
        self._increment_nesting()
        self.generic_visit(node)
        self._decrement_nesting()

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        """Generator expressions add complexity."""
        self._increment()
        self._increment_nesting()
        self.generic_visit(node)
        self._decrement_nesting()

    def visit_IfExp(self, node: ast.IfExp) -> None:
        """Ternary expressions add complexity."""
        self._increment()
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        """Match statements (Python 3.10+)."""
        self._increment()
        self._increment_nesting()
        for case in node.cases:
            self._increment(1)
            for child in case.body:
                self.visit(child)
        self._decrement_nesting()


class ComplexityAnalyzer:
    """
    Analyzes Python code for cyclomatic and cognitive complexity.

    Scans Python files and calculates complexity metrics for each
    function and method, identifying those that exceed thresholds.
    """

    def __init__(self, config: Optional[ComplexityConfig] = None):
        """
        Initialize the complexity analyzer.

        Args:
            config: Analysis configuration. Uses defaults if not provided.
        """
        self.config = config or ComplexityConfig()

    def analyze(self, scan_path: Optional[Path] = None) -> ComplexityResult:
        """
        Perform complexity analysis on the specified path.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            ComplexityResult containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        result = ComplexityResult(
            cyclomatic_threshold=self.config.cyclomatic_threshold,
            cognitive_threshold=self.config.cognitive_threshold,
            scan_path=str(path),
        )

        # Determine include extensions
        include_extensions = self.config.include_extensions or [".py"]

        # Build exclude patterns
        exclude_patterns = list(self.config.exclude_patterns)
        if not self.config.include_tests:
            exclude_patterns.extend(["test_", "_test.py", "tests/", "conftest.py"])

        # Scan Python files
        for file_path in scan_directory(
            path,
            exclude_patterns=exclude_patterns,
            include_extensions=include_extensions,
        ):
            try:
                file_analysis = self._analyze_file(file_path, path)
                if file_analysis.total_functions > 0:
                    result.add_file_analysis(file_analysis)
            except SyntaxError:
                # Skip files with syntax errors
                continue
            except Exception:
                # Skip files that can't be analyzed
                continue

        result.scan_duration_seconds = time.time() - start_time

        # Sort violations by max complexity (worst first)
        result.violations.sort(key=lambda f: f.max_complexity, reverse=True)

        return result

    def _analyze_file(self, file_path: Path, root_path: Path) -> FileComplexityAnalysis:
        """
        Analyze a single Python file.

        Args:
            file_path: Path to the Python file
            root_path: Root path for relative path calculation

        Returns:
            FileComplexityAnalysis with per-function metrics
        """
        analysis = FileComplexityAnalysis(
            file_path=str(file_path),
            relative_path=str(file_path.relative_to(root_path)),
        )

        source = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(file_path))

        # Find all functions and methods
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_analysis = self._analyze_function(node, source)

                # Determine if it's a method (inside a class)
                class_name = self._get_parent_class(tree, node)
                if class_name:
                    func_analysis.is_method = True
                    func_analysis.class_name = class_name

                analysis.add_function(func_analysis)

                # Check if it violates thresholds
                if (func_analysis.cyclomatic_complexity > self.config.cyclomatic_threshold or
                    func_analysis.cognitive_complexity > self.config.cognitive_threshold):
                    analysis.add_violation(func_analysis)

        return analysis

    def _analyze_function(
        self, node: ast.FunctionDef, source: str
    ) -> FunctionComplexity:
        """
        Analyze complexity of a single function.

        Args:
            node: AST node for the function
            source: Source code of the file

        Returns:
            FunctionComplexity with metrics
        """
        # Calculate cyclomatic complexity
        cc_visitor = CyclomaticComplexityVisitor()
        cc_visitor.visit(node)
        cyclomatic = cc_visitor.complexity

        # Calculate cognitive complexity
        cog_visitor = CognitiveComplexityVisitor()
        cog_visitor.visit(node)
        cognitive = cog_visitor.complexity

        # Determine severity based on max complexity
        max_complexity = max(cyclomatic, cognitive)
        severity = FunctionComplexity.calculate_severity(max_complexity)

        return FunctionComplexity(
            name=node.name,
            line_number=node.lineno,
            end_line=node.end_lineno or node.lineno,
            cyclomatic_complexity=cyclomatic,
            cognitive_complexity=cognitive,
            severity=severity,
        )

    def _get_parent_class(self, tree: ast.Module, func_node: ast.AST) -> Optional[str]:
        """
        Find the parent class of a function node if it's a method.

        Args:
            tree: Full AST of the file
            func_node: Function node to find parent of

        Returns:
            Class name if function is a method, None otherwise
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if item is func_node:
                        return node.name
                    # Check nested functions
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for nested in ast.walk(item):
                            if nested is func_node and nested is not item:
                                return node.name
        return None

    def analyze_single_file(self, file_path: Path) -> FileComplexityAnalysis:
        """
        Analyze a single Python file.

        Args:
            file_path: Path to the Python file

        Returns:
            FileComplexityAnalysis with metrics

        Raises:
            FileNotFoundError: If file doesn't exist
            SyntaxError: If file has syntax errors
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File does not exist: {path}")

        return self._analyze_file(path, path.parent)

    def get_function_complexity(
        self, source: str, function_name: str
    ) -> Optional[FunctionComplexity]:
        """
        Get complexity for a specific function from source code.

        Args:
            source: Python source code
            function_name: Name of the function to analyze

        Returns:
            FunctionComplexity if found, None otherwise
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == function_name:
                    return self._analyze_function(node, source)

        return None

    def generate_report(self, result: ComplexityResult, output_format: str = "text") -> str:
        """
        Generate formatted complexity analysis report.

        Args:
            result: ComplexityResult to format
            output_format: Report format - text, json, or markdown

        Returns:
            Formatted report string

        Raises:
            ValueError: If output format is not supported
        """
        format_lower = output_format.lower()
        if format_lower == "json":
            return self._generate_json_report(result)
        elif format_lower in ("markdown", "md"):
            return self._generate_markdown_report(result)
        elif format_lower == "text":
            return self._generate_text_report(result)
        else:
            raise ValueError(f"Unsupported format: {output_format}. Use: text, json, markdown")

    def _generate_text_report(self, result: ComplexityResult) -> str:
        """Generate plain text complexity report."""
        lines = [
            "=" * 70,
            "  HEIMDALL COMPLEXITY ANALYSIS REPORT",
            "=" * 70,
            "",
            f"  Scan Path:    {result.scan_path}",
            f"  Scanned At:   {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"  Duration:     {result.scan_duration_seconds:.2f}s",
            "",
            "-" * 70,
            "  SUMMARY",
            "-" * 70,
            "",
            f"  Files Scanned:         {result.total_files_scanned}",
            f"  Functions Analyzed:    {result.total_functions_analyzed}",
            f"  Files With Violations: {result.files_with_violations}",
            f"  Total Violations:      {result.total_violations}",
            f"  Compliance Rate:       {result.compliance_rate:.1f}%",
            f"  Thresholds:            Cyclomatic={result.cyclomatic_threshold}, Cognitive={result.cognitive_threshold}",
            f"  Averages:              CC={result.average_cyclomatic:.1f}, COG={result.average_cognitive:.1f}",
            f"  Maximums:              CC={result.max_cyclomatic}, COG={result.max_cognitive}",
            "",
            "-" * 70,
            "  METRIC DEFINITIONS",
            "-" * 70,
            "",
            "  Cyclomatic Complexity (CC): Counts the number of independent paths through",
            "    a function. Each branch (if/for/while/except/and/or) adds 1. A function",
            "    with CC=1 is perfectly linear. Higher values mean harder to test and maintain.",
            "",
            "  Cognitive Complexity (COG): Measures how hard the code is for a human to",
            "    read. Penalises nesting depth and non-linear control flow more than CC does.",
            "",
            "  SEVERITY THRESHOLDS",
            f"    (thresholds configured: CC={result.cyclomatic_threshold}, COG={result.cognitive_threshold})",
            f"    MODERATE  -- CC or COG exceeds threshold",
            f"    HIGH      -- CC or COG exceeds threshold x 1.5",
            f"    VERY_HIGH -- CC or COG exceeds threshold x 2",
            f"    CRITICAL  -- CC or COG exceeds threshold x 3",
            "",
        ]

        if result.has_violations:
            lines.extend(["-" * 70, "  VIOLATIONS (worst first)", "-" * 70, ""])
            by_severity = result.get_violations_by_severity()
            for severity in [
                ComplexitySeverity.CRITICAL.value,
                ComplexitySeverity.VERY_HIGH.value,
                ComplexitySeverity.HIGH.value,
                ComplexitySeverity.MODERATE.value,
            ]:
                violations = by_severity[severity]
                if violations:
                    lines.append(f"  [{severity.upper()}]")
                    for v in violations:
                        name = v.qualified_name if hasattr(v, 'qualified_name') else v.name
                        lines.append(f"    {name:<50} Line {v.line_number:>5}  CC={v.cyclomatic_complexity:>3} COG={v.cognitive_complexity:>3}")
                    lines.append("")
        else:
            lines.extend(["  All functions are within the complexity thresholds.", ""])

        lines.extend(["=" * 70, ""])
        return "\n".join(lines)

    def _generate_json_report(self, result: ComplexityResult) -> str:
        """Generate JSON complexity report."""
        violations_data = []
        for v in result.violations:
            violations_data.append({
                "name": v.name,
                "qualified_name": v.qualified_name if hasattr(v, 'qualified_name') else v.name,
                "class_name": v.class_name,
                "line_number": v.line_number,
                "end_line": v.end_line,
                "cyclomatic_complexity": v.cyclomatic_complexity,
                "cognitive_complexity": v.cognitive_complexity,
                "severity": v.severity if isinstance(v.severity, str) else v.severity.value,
            })

        report_data = {
            "scan_info": {
                "scan_path": result.scan_path,
                "scanned_at": result.scanned_at.isoformat(),
                "duration_seconds": result.scan_duration_seconds,
            },
            "summary": {
                "total_files_scanned": result.total_files_scanned,
                "total_functions_analyzed": result.total_functions_analyzed,
                "files_with_violations": result.files_with_violations,
                "total_violations": result.total_violations,
                "compliance_rate": round(result.compliance_rate, 2),
                "cyclomatic_threshold": result.cyclomatic_threshold,
                "cognitive_threshold": result.cognitive_threshold,
                "average_cyclomatic": round(result.average_cyclomatic, 2),
                "average_cognitive": round(result.average_cognitive, 2),
                "max_cyclomatic": result.max_cyclomatic,
                "max_cognitive": result.max_cognitive,
            },
            "violations": violations_data,
        }
        return json.dumps(report_data, indent=2)

    def _generate_markdown_report(self, result: ComplexityResult) -> str:
        """Generate Markdown complexity report."""
        lines = [
            "# Heimdall Complexity Analysis Report",
            "",
            f"**Scan Path:** `{result.scan_path}`",
            f"**Generated:** {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Duration:** {result.scan_duration_seconds:.2f} seconds",
            "",
            "## Summary",
            "",
            f"**Files Scanned:** {result.total_files_scanned}",
            f"**Functions Analyzed:** {result.total_functions_analyzed}",
            f"**Total Violations:** {result.total_violations}",
            f"**Compliance Rate:** {result.compliance_rate:.1f}%",
            f"**Thresholds:** Cyclomatic={result.cyclomatic_threshold}, Cognitive={result.cognitive_threshold}",
            "",
        ]

        if result.has_violations:
            lines.extend([
                "## Violations",
                "",
                "| Function | Line | Cyclomatic | Cognitive | Severity |",
                "|----------|------|-----------|-----------|----------|",
            ])
            for v in result.violations:
                name = v.qualified_name if hasattr(v, 'qualified_name') else v.name
                sev = v.severity if isinstance(v.severity, str) else v.severity.value
                lines.append(f"| `{name}` | {v.line_number} | {v.cyclomatic_complexity} | {v.cognitive_complexity} | {sev} |")
            lines.append("")
        else:
            lines.extend(["All functions are within the complexity thresholds.", ""])

        return "\n".join(lines)
