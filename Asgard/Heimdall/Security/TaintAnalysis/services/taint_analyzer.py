"""
Heimdall Taint Analyzer Service

Performs intra-function and cross-function taint analysis using Python's AST module
to track untrusted data from sources to dangerous sinks.
"""

import ast
import fnmatch
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import (
    TaintConfig,
    TaintFlow,
    TaintFlowStep,
    TaintReport,
    TaintSinkType,
    TaintSourceType,
)
from Asgard.Heimdall.Security.TaintAnalysis.services._taint_patterns import (
    SOURCE_PATTERNS,
    SOURCE_CALL_NAMES,
    SINK_PATTERNS,
    SANITIZER_NAMES,
    SINK_SEVERITY,
    SINK_CWE,
    SINK_OWASP,
    SINK_TITLES,
)
from Asgard.Heimdall.Security.TaintAnalysis.services._taint_visitor import (
    _FunctionTaintVisitor,
    _attr_chain,
    _get_source_type_for_node,
    _get_sink_type_for_call,
    _is_sanitizer_call,
)


def _should_exclude(path: Path, exclude_patterns: List[str]) -> bool:
    """Check if a path should be excluded from scanning."""
    path_str = str(path)
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(path.name, pattern):
            return True
        if fnmatch.fnmatch(path_str, f"*{pattern}*"):
            return True
        if pattern in path_str:
            return True
    return False


def _collect_python_files(scan_path: Path, exclude_patterns: List[str]) -> List[Path]:
    """Collect all Python files under scan_path, respecting exclusions."""
    files: List[Path] = []
    for py_file in scan_path.rglob("*.py"):
        if not _should_exclude(py_file, exclude_patterns):
            files.append(py_file)
    return sorted(files)


class TaintAnalyzer:
    """
    Performs taint analysis on Python source code.

    Tracks untrusted data from sources (HTTP parameters, env vars, user input, etc.)
    through propagation paths to dangerous sinks (SQL, shell, eval, etc.).

    Supports:
    - Full intra-function tracking
    - Cross-function tracking within the same file (call graph)
    - Best-effort cross-file tracking for known sink patterns
    """

    def __init__(self, config: Optional[TaintConfig] = None):
        """
        Initialize the taint analyzer.

        Args:
            config: Taint analysis configuration. Uses defaults if not provided.
        """
        self.config = config or TaintConfig()
        self._custom_sources = set(self.config.custom_sources)
        self._custom_sinks = set(self.config.custom_sinks)
        self._custom_sanitizers = set(self.config.custom_sanitizers)

    def scan(self, scan_path: Optional[Path] = None) -> TaintReport:
        """
        Scan the specified path for taint flows.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            TaintReport containing all taint flows found.

        Raises:
            FileNotFoundError: If the scan path does not exist.
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = TaintReport(scan_path=str(path))

        python_files = _collect_python_files(path, self.config.exclude_patterns)
        report.files_analyzed = len(python_files)

        for file_path in python_files:
            flows = self._analyze_file(file_path)
            for flow in flows:
                if self._severity_meets_threshold(flow.severity):
                    report.add_flow(flow)

        severity_order = {"critical": 0, "high": 1, "medium": 2}
        report.flows.sort(
            key=lambda f: (
                severity_order.get(f.severity, 3),
                f.source_location.file_path,
                f.source_location.line_number,
            )
        )

        report.scan_duration_seconds = time.time() - start_time
        return report

    def _analyze_file(self, file_path: Path) -> List[TaintFlow]:
        """
        Analyze a single Python file for taint flows.

        Args:
            file_path: Path to the Python file.

        Returns:
            List of TaintFlow objects found in the file.
        """
        flows: List[TaintFlow] = []

        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
        except (IOError, OSError):
            return flows

        lines = source.splitlines()

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            return flows

        file_path_str = str(file_path)

        functions: Dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions[node.name] = node

        module_visitor = _FunctionTaintVisitor(
            file_path=file_path_str,
            func_name="<module>",
            lines=lines,
            initial_taint={},
            custom_sources=self._custom_sources,
            custom_sinks=self._custom_sinks,
            custom_sanitizers=self._custom_sanitizers,
        )
        for stmt in tree.body:
            module_visitor.visit(stmt)
        for flow, _ in module_visitor.found_flows:
            flows.append(flow)
        module_level_taint = module_visitor.taint_map

        for func_name, func_node in functions.items():
            func_flows = self._analyze_function(
                func_node=func_node,
                file_path_str=file_path_str,
                lines=lines,
                initial_taint=module_level_taint if self.config.track_cross_function else {},
            )
            flows.extend(func_flows)

        return flows

    def _analyze_function(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path_str: str,
        lines: List[str],
        initial_taint: Optional[Dict[str, Tuple[TaintFlowStep, TaintSourceType]]] = None,
    ) -> List[TaintFlow]:
        """
        Analyze a single function for taint flows.

        Args:
            func_node: The AST function definition node.
            file_path_str: String path of the file.
            lines: Source lines for snippet extraction.
            initial_taint: Initial taint map from outer scope.

        Returns:
            List of TaintFlow objects found in the function.
        """
        visitor = _FunctionTaintVisitor(
            file_path=file_path_str,
            func_name=func_node.name,
            lines=lines,
            initial_taint=initial_taint,
            custom_sources=self._custom_sources,
            custom_sinks=self._custom_sinks,
            custom_sanitizers=self._custom_sanitizers,
        )
        visitor.visit(func_node)
        return [flow for flow, _ in visitor.found_flows]

    def _severity_meets_threshold(self, severity: str) -> bool:
        """Check if a severity meets the configured minimum threshold."""
        order = {"critical": 0, "high": 1, "medium": 2}
        min_order = order.get(self.config.min_severity, 2)
        finding_order = order.get(severity, 3)
        return finding_order <= min_order
