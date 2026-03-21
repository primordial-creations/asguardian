"""
Heimdall Taint Analysis Visitor

AST visitor and helper functions for intra-function taint tracking.
"""

import ast
from typing import Dict, List, Optional, Set, Tuple

from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import (
    TaintFlow,
    TaintFlowStep,
    TaintSinkType,
    TaintSourceType,
)
from Asgard.Heimdall.Security.TaintAnalysis.services._taint_patterns import (
    SANITIZER_NAMES,
    SINK_CWE,
    SINK_OWASP,
    SINK_PATTERNS,
    SINK_TITLES,
    SOURCE_CALL_NAMES,
    SOURCE_PATTERNS,
)


def _attr_chain(node: ast.AST) -> str:
    """Flatten an attribute access chain into a dotted string (e.g. 'request.args.get')."""
    if isinstance(node, ast.Attribute):
        parent = _attr_chain(node.value)
        if parent:
            return f"{parent}.{node.attr}"
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _get_code_snippet(lines: List[str], line_number: int) -> str:
    """Get a code snippet around a given line number (1-indexed)."""
    idx = line_number - 1
    if 0 <= idx < len(lines):
        return lines[idx].strip()
    return ""


def _is_sanitizer_call(node: ast.AST, custom_sanitizers: Set[str]) -> bool:
    """Check if a node represents a call to a known sanitizer function."""
    if not isinstance(node, ast.Call):
        return False
    call_name = _attr_chain(node.func)
    all_sanitizers = SANITIZER_NAMES | custom_sanitizers
    return call_name in all_sanitizers or any(s in call_name for s in all_sanitizers)


def _get_source_type_for_node(node: ast.AST, custom_sources: Set[str]) -> Optional[TaintSourceType]:
    """Check if an AST node represents a taint source, return the source type if so."""
    chain = _attr_chain(node)

    for pattern, source_type in SOURCE_PATTERNS:
        if chain == pattern or chain.startswith(pattern):
            return source_type

    if isinstance(node, ast.Call):
        func_name = _attr_chain(node.func)
        if func_name in SOURCE_CALL_NAMES:
            return SOURCE_CALL_NAMES[func_name]
        for custom in custom_sources:
            if func_name == custom or func_name.endswith(f".{custom}"):
                return TaintSourceType.HTTP_PARAMETER

    return None


def _get_sink_type_for_call(func_chain: str, custom_sinks: Set[str]) -> Optional[Tuple[TaintSinkType, str]]:
    """Check if a function call chain is a known taint sink."""
    for pattern, (sink_type, severity) in SINK_PATTERNS.items():
        if func_chain == pattern or func_chain.endswith(f".{pattern}") or func_chain.startswith(pattern):
            return sink_type, severity
    for custom in custom_sinks:
        if func_chain == custom or func_chain.endswith(f".{custom}"):
            return TaintSinkType.SQL_QUERY, "high"
    return None


class _FunctionTaintVisitor(ast.NodeVisitor):
    """
    AST visitor that tracks taint within a single function.

    Builds a taint map: variable_name -> (TaintFlowStep, TaintSourceType)
    as it walks the function body, and records sink hits.
    """

    def __init__(
        self,
        file_path: str,
        func_name: str,
        lines: List[str],
        initial_taint: Optional[Dict[str, Tuple[TaintFlowStep, TaintSourceType]]] = None,
        custom_sources: Optional[Set[str]] = None,
        custom_sinks: Optional[Set[str]] = None,
        custom_sanitizers: Optional[Set[str]] = None,
    ):
        self.file_path = file_path
        self.func_name = func_name
        self.lines = lines
        self.taint_map: Dict[str, Tuple[TaintFlowStep, TaintSourceType]] = dict(initial_taint or {})
        self.custom_sources: Set[str] = custom_sources or set()
        self.custom_sinks: Set[str] = custom_sinks or set()
        self.custom_sanitizers: Set[str] = custom_sanitizers or set()
        self.found_flows: List[Tuple[TaintFlow, str]] = []

    def _make_step(self, line_number: int, step_type: str, variable_name: str) -> TaintFlowStep:
        return TaintFlowStep(
            file_path=self.file_path,
            line_number=line_number,
            function_name=self.func_name,
            step_type=step_type,
            code_snippet=_get_code_snippet(self.lines, line_number),
            variable_name=variable_name,
        )

    def _is_tainted(self, node: ast.AST) -> bool:
        """Check if an AST node refers to a tainted variable."""
        if isinstance(node, ast.Name):
            return node.id in self.taint_map
        if isinstance(node, ast.Attribute):
            chain = _attr_chain(node)
            if chain in self.taint_map:
                return True
            if isinstance(node.value, ast.Name) and node.value.id in self.taint_map:
                return True
        if isinstance(node, ast.Subscript):
            return self._is_tainted(node.value)
        if isinstance(node, ast.Call):
            return self._is_tainted(node.func)
        if isinstance(node, ast.JoinedStr):
            for val in ast.walk(node):
                if isinstance(val, ast.FormattedValue) and self._is_tainted(val.value):
                    return True
        if isinstance(node, ast.BinOp):
            return self._is_tainted(node.left) or self._is_tainted(node.right)
        if isinstance(node, ast.IfExp):
            return self._is_tainted(node.body) or self._is_tainted(node.orelse)
        return False

    def _get_taint_source(self, node: ast.AST) -> Optional[Tuple[TaintFlowStep, TaintSourceType]]:
        """Get taint source for a tainted node (first tainted variable found)."""
        if isinstance(node, ast.Name):
            return self.taint_map.get(node.id)
        if isinstance(node, ast.Attribute):
            chain = _attr_chain(node)
            if chain in self.taint_map:
                return self.taint_map[chain]
            if isinstance(node.value, ast.Name) and node.value.id in self.taint_map:
                return self.taint_map[node.value.id]
        if isinstance(node, ast.Subscript):
            return self._get_taint_source(node.value)
        if isinstance(node, ast.Call):
            return self._get_taint_source(node.func)
        if isinstance(node, ast.JoinedStr):
            for val in ast.walk(node):
                if isinstance(val, ast.FormattedValue):
                    result = self._get_taint_source(val.value)
                    if result:
                        return result
        if isinstance(node, ast.BinOp):
            left = self._get_taint_source(node.left)
            if left:
                return left
            return self._get_taint_source(node.right)
        return None

    def _taint_variable(
        self,
        var_name: str,
        line_number: int,
        source_step: TaintFlowStep,
        source_type: TaintSourceType,
    ) -> None:
        """Mark a variable as tainted."""
        self.taint_map[var_name] = (source_step, source_type)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Handle assignments: detect sources and propagate taint."""
        line_number = node.lineno

        source_type = _get_source_type_for_node(node.value, self.custom_sources)
        if source_type is not None:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    source_step_named = self._make_step(line_number, "source", target.id)
                    self.taint_map[target.id] = (source_step_named, source_type)

        if isinstance(node.value, ast.Call):
            source_type = _get_source_type_for_node(node.value, self.custom_sources)
            if source_type is not None:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        source_step = self._make_step(line_number, "source", target.id)
                        self.taint_map[target.id] = (source_step, source_type)

        if isinstance(node.value, ast.Call) and _is_sanitizer_call(
            node.value, self.custom_sanitizers
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.taint_map.pop(target.id, None)
        elif self._is_tainted(node.value):
            taint_info = self._get_taint_source(node.value)
            if taint_info:
                original_step, src_type = taint_info
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self._taint_variable(target.id, line_number, original_step, src_type)

        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Handle augmented assignments (+=, etc.)."""
        if self._is_tainted(node.value):
            taint_info = self._get_taint_source(node.value)
            if taint_info and isinstance(node.target, ast.Name):
                original_step, src_type = taint_info
                self._taint_variable(node.target.id, node.lineno, original_step, src_type)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Handle function calls: detect sinks and track cross-function taint."""
        func_chain = _attr_chain(node.func)

        sink_result = _get_sink_type_for_call(func_chain, self.custom_sinks)
        if sink_result is not None:
            sink_type, severity = sink_result

            all_args = list(node.args) + [kw.value for kw in node.keywords]
            for arg in all_args:
                if self._is_tainted(arg):
                    taint_info = self._get_taint_source(arg)
                    if taint_info:
                        original_step, src_type = taint_info
                        sink_step = self._make_step(node.lineno, "sink", func_chain)

                        sanitizer_present = any(
                            _is_sanitizer_call(a, self.custom_sanitizers)
                            for a in all_args
                        )

                        flow = TaintFlow(
                            source_type=src_type,
                            sink_type=sink_type,
                            severity=severity,
                            source_location=original_step,
                            sink_location=sink_step,
                            intermediate_steps=[],
                            title=SINK_TITLES.get(sink_type, "Tainted Data Flow"),
                            description=(
                                f"Tainted data from {src_type} source reaches "
                                f"{sink_type} sink without sanitization."
                            ),
                            cwe_id=SINK_CWE.get(sink_type, ""),
                            owasp_category=SINK_OWASP.get(sink_type, ""),
                            sanitizers_present=sanitizer_present,
                        )
                        var_name = ""
                        if isinstance(arg, ast.Name):
                            var_name = arg.id
                        self.found_flows.append((flow, var_name))
                        break

        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        """Track tainted return values (for cross-function propagation)."""
        self.generic_visit(node)
