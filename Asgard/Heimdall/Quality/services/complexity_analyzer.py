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
from Asgard.Heimdall.Quality.services._complexity_visitors import (
    CyclomaticComplexityVisitor,
    CognitiveComplexityVisitor,
)
from Asgard.Heimdall.Quality.services._complexity_report import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory


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
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, source: str
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
            return generate_json_report(result)
        elif format_lower in ("markdown", "md"):
            return generate_markdown_report(result)
        elif format_lower == "text":
            return generate_text_report(result)
        else:
            raise ValueError(f"Unsupported format: {output_format}. Use: text, json, markdown")
