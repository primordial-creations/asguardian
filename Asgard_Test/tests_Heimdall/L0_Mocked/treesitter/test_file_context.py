"""Tests for FileParseContext — single-parse-per-file substrate.

All tests pass whether or not the tree-sitter optional dependency is installed.
"""
import pytest

from Asgard.Heimdall.treesitter.ast_engine import is_engine_enabled
from Asgard.Heimdall.treesitter.file_context import (
    EXTENSION_LANGUAGE_MAP,
    FileParseContext,
    language_for_path,
)

requires_ts_python = pytest.mark.skipif(
    not is_engine_enabled("python"), reason="tree-sitter-python not installed"
)


# ---------------------------------------------------------------------------
# language routing
# ---------------------------------------------------------------------------

def test_language_for_path_python():
    assert language_for_path("a/b/c.py") == "python"


def test_language_for_path_tsx_routes_to_tsx_grammar():
    assert language_for_path("component.tsx") == "tsx"


def test_language_for_path_typescript():
    assert language_for_path("mod.ts") == "typescript"


def test_language_for_path_unknown_returns_none():
    assert language_for_path("README.md") is None
    assert language_for_path("no_extension") is None


def test_extension_map_has_no_duplicate_conflicts():
    assert EXTENSION_LANGUAGE_MAP[".tsx"] == "tsx"
    assert EXTENSION_LANGUAGE_MAP[".jsx"] == "javascript"


# ---------------------------------------------------------------------------
# graceful degradation
# ---------------------------------------------------------------------------

def test_parse_unknown_language_returns_context_without_tree():
    ctx = FileParseContext.parse("x.zzz", ["hello"])
    assert ctx.root is None
    assert ctx.tree is None
    assert ctx.has_errors is False


def test_parse_missing_file_does_not_raise():
    ctx = FileParseContext.parse("/nonexistent/definitely/missing.py")
    assert ctx.root is None or ctx.source_bytes == b""


def test_parse_never_raises_on_weird_input():
    ctx = FileParseContext.parse("x.py", ["\x00\udcff weird", "line2"])
    assert isinstance(ctx, FileParseContext)


# ---------------------------------------------------------------------------
# intersects_error
# ---------------------------------------------------------------------------

def test_intersects_error_empty_ranges():
    ctx = FileParseContext(file_path="x.py", language="python")
    assert ctx.intersects_error(0) is False
    assert ctx.intersects_error(0, 100) is False


def test_intersects_error_overlap_logic():
    ctx = FileParseContext(file_path="x.py", language="python", error_ranges=[(5, 8)])
    assert ctx.intersects_error(5) is True
    assert ctx.intersects_error(8) is True
    assert ctx.intersects_error(4) is False
    assert ctx.intersects_error(9) is False
    assert ctx.intersects_error(0, 5) is True
    assert ctx.intersects_error(8, 20) is True
    assert ctx.intersects_error(9, 20) is False
    assert ctx.has_errors is True


# ---------------------------------------------------------------------------
# real parses (only when the optional extra is installed)
# ---------------------------------------------------------------------------

@requires_ts_python
def test_parse_valid_python_produces_tree():
    ctx = FileParseContext.parse("x.py", ["def f():", "    return 1"], "python")
    assert ctx.root is not None
    assert ctx.error_ranges == []
    assert ctx.language == "python"


@requires_ts_python
def test_parse_broken_python_records_error_ranges():
    ctx = FileParseContext.parse("x.py", ["def broken(:", "    pass", "x = 1"], "python")
    assert ctx.root is not None  # error recovery keeps scanning
    assert ctx.has_errors is True


@requires_ts_python
def test_node_text_roundtrip():
    ctx = FileParseContext.parse("x.py", ["value = 42"], "python")
    assert "value = 42" in ctx.node_text(ctx.root)
    assert ctx.node_text(None) == ""
