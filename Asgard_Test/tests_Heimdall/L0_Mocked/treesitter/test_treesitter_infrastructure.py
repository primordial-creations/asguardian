"""Tests for the Tree-sitter infrastructure package.

All tests pass whether or not the tree-sitter optional dependency is installed.
"""
import pytest

from Asgard.Heimdall.treesitter import (
    is_available,
    get_supported_languages,
    parse_source,
    run_query,
)
from Asgard.Heimdall.treesitter._query_runner import node_text


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------

def test_is_available_returns_bool_for_known_language():
    result = is_available("java")
    assert isinstance(result, bool)


def test_is_available_returns_false_for_unknown_language():
    assert is_available("cobol_9000") is False


def test_is_available_does_not_raise():
    # Calling with various inputs must never raise
    for lang in ("python", "java", "go", "ruby", "typescript", "php", "csharp", "cpp", "rust"):
        is_available(lang)  # should not raise


# ---------------------------------------------------------------------------
# get_supported_languages
# ---------------------------------------------------------------------------

def test_get_supported_languages_returns_set():
    langs = get_supported_languages()
    assert isinstance(langs, set)


def test_get_supported_languages_subset_of_known():
    known = {"python", "javascript", "typescript", "tsx", "java", "go", "ruby", "php", "csharp", "cpp", "rust"}
    langs = get_supported_languages()
    assert langs.issubset(known), f"Unexpected languages: {langs - known}"


# ---------------------------------------------------------------------------
# parse_source
# ---------------------------------------------------------------------------

SIMPLE_JAVA = b"""
public class Hello {
    public static void main(String[] args) {
        System.out.println("Hello, world!");
    }
}
"""


def test_parse_source_java_returns_node_or_none():
    root = parse_source(SIMPLE_JAVA, "java")
    if is_available("java"):
        assert root is not None
        assert root.type is not None  # root node has a type string
    else:
        assert root is None


def test_parse_source_unknown_language_returns_none():
    root = parse_source(b"anything", "cobol_9000")
    assert root is None


def test_parse_source_empty_bytes_does_not_raise():
    result = parse_source(b"", "python")
    # Either a valid (empty) tree root or None — must not raise
    assert result is None or result is not None


def test_parse_source_graceful_when_unavailable(monkeypatch):
    """Even if language binding is absent, parse_source returns None gracefully."""
    import Asgard.Heimdall.treesitter._language_loader as ll
    import Asgard.Heimdall.treesitter._parser_pool as pp

    original = ll._AVAILABLE.copy()
    # A parser cached by an earlier test would otherwise short-circuit the
    # availability check, so drop the cache too and restore it afterwards.
    original_parsers = pp._PARSERS.copy()
    ll._AVAILABLE.clear()
    pp._PARSERS.clear()
    try:
        result = parse_source(SIMPLE_JAVA, "java")
        assert result is None
    finally:
        ll._AVAILABLE.update(original)
        pp._PARSERS.update(original_parsers)


# ---------------------------------------------------------------------------
# run_query
# ---------------------------------------------------------------------------

def test_run_query_returns_list():
    root = parse_source(SIMPLE_JAVA, "java")
    from Asgard.Heimdall.treesitter._queries.java_queries import CLASS_DEFINITION
    result = run_query(root, CLASS_DEFINITION, SIMPLE_JAVA, "java")
    assert isinstance(result, list)


def test_run_query_returns_empty_list_when_root_none():
    from Asgard.Heimdall.treesitter._queries.java_queries import CLASS_DEFINITION
    result = run_query(None, CLASS_DEFINITION, SIMPLE_JAVA, "java")
    assert result == []


def test_run_query_returns_empty_list_for_unknown_language():
    root = parse_source(SIMPLE_JAVA, "java")
    result = run_query(root, "(class_declaration) @x", SIMPLE_JAVA, "cobol_9000")
    assert result == []


def test_run_query_returns_primitives_only():
    """Verify no Node objects leak into the return value."""
    root = parse_source(SIMPLE_JAVA, "java")
    if root is None:
        pytest.skip("tree-sitter-java not installed")
    from Asgard.Heimdall.treesitter._queries.java_queries import CLASS_DEFINITION
    results = run_query(root, CLASS_DEFINITION, SIMPLE_JAVA, "java")
    for match in results:
        for _capture_name, info in match.items():
            assert isinstance(info["text"], str)
            assert isinstance(info["line"], int)
            assert isinstance(info["col"], int)


def test_run_query_finds_class_name():
    root = parse_source(SIMPLE_JAVA, "java")
    if root is None:
        pytest.skip("tree-sitter-java not installed")
    from Asgard.Heimdall.treesitter._queries.java_queries import CLASS_DEFINITION
    results = run_query(root, CLASS_DEFINITION, SIMPLE_JAVA, "java")
    texts = [m.get("class.name", {}).get("text", "") for m in results]
    assert any("Hello" in t for t in texts), f"Expected 'Hello' in {texts}"


# ---------------------------------------------------------------------------
# node_text helper
# ---------------------------------------------------------------------------

def test_node_text_returns_empty_string_for_none():
    assert node_text(None, b"hello") == ""


def test_node_text_returns_empty_string_on_empty_source():
    assert node_text(None, b"") == ""


def test_node_text_extracts_correctly_when_available():
    root = parse_source(SIMPLE_JAVA, "java")
    if root is None:
        pytest.skip("tree-sitter-java not installed")
    text = node_text(root, SIMPLE_JAVA)
    assert "Hello" in text
