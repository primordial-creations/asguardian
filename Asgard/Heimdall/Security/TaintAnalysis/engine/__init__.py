"""CST-backed taint engine for non-Python languages (JS/TS, Java)."""

from Asgard.Heimdall.Security.TaintAnalysis.engine.cst_taint_visitor import (
    CstFunctionTaintVisitor,
    scan_java_source,
    scan_js_ts_source,
)

__all__ = [
    "CstFunctionTaintVisitor",
    "scan_java_source",
    "scan_js_ts_source",
]
