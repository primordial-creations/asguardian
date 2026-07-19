"""
Heimdall Multi-Language Coverage Extractor

Extends coverage analysis beyond Python's ``ast``-only extractor to
JavaScript/TypeScript and Go, per ``_Docs/Planning/Heimdall`` (the CIR
already extracts classes/methods for these languages;
``Asgard/Bragi/Architecture/cir/builder.py`` is reused here rather than
reimplementing per-language parsing).

Two things are extracted per production/test file:

1. Production methods — class/struct methods (via the CIR) plus top-level
   functions (via a tree-sitter query, since the CIR is class-centric).
2. Test "signals" — every called-identifier name found inside a test file.
   This mirrors the existing Python heuristic in
   ``method_extractor.find_tested_methods``: a test is considered to cover
   a production method/function if the test file *calls* something with
   that name anywhere in its body. Results are represented as synthetic
   :class:`MethodInfo` objects so they plug directly into the existing
   language-agnostic ``is_method_covered`` / ``build_test_name_set`` gap
   analysis helpers.

Degrades honestly: if the tree-sitter grammar for a language is
unavailable, every function here returns ``[]`` rather than fabricating
data — callers should surface that as INSUFFICIENT_DATA, not a fake 0%/100%.
"""
from pathlib import Path
from typing import List, Set

from Asgard.Bragi.Architecture.cir.builder import build_file_cir
from Asgard.Bragi.Coverage.models.coverage_models import MethodInfo, MethodType
from Asgard.Heimdall.treesitter._language_loader import is_available
from Asgard.Heimdall.treesitter._parser_pool import parse_source
from Asgard.Heimdall.treesitter._query_runner import run_query_all

#: Languages this module can extract methods/tests for. Other CIR languages
#: (java, csharp, ruby, php, rust, cpp) are covered by OOP's cir_metrics.py
#: but don't yet have coverage-specific test-file conventions wired here;
#: they honestly fall through to "unsupported" rather than a guessed answer.
SUPPORTED_LANGUAGES = {"javascript", "typescript", "go"}

_FUNCTION_DECLARATION_QUERIES = {
    "javascript": '(function_declaration name: (identifier) @func.name) @func.def',
    "typescript": '(function_declaration name: (identifier) @func.name) @func.def',
    "go": '(function_declaration name: (identifier) @func.name) @func.def',
}

# Plain-identifier call expressions, e.g. `Foo(x)` / `foo(x)` — not covered
# by the shared per-language CALL_EXPRESSION queries, which target
# receiver/member calls (`obj.Foo()`, `this.foo()`).
_PLAIN_CALL_QUERIES = {
    "javascript": '(call_expression function: (identifier) @call.name) @call',
    "typescript": '(call_expression function: (identifier) @call.name) @call',
    "go": '(call_expression function: (identifier) @call.name) @call',
}

# Member/selector call expressions, e.g. `obj.foo()` / `this.foo()`.
_MEMBER_CALL_QUERIES = {
    "javascript": (
        '(call_expression function: (member_expression '
        'property: (property_identifier) @call.name)) @call'
    ),
    "typescript": (
        '(call_expression function: (member_expression '
        'property: (property_identifier) @call.name)) @call'
    ),
    "go": (
        '(call_expression function: (selector_expression '
        'field: (field_identifier) @call.name)) @call'
    ),
}


def is_test_file(file_path: Path, language: str) -> bool:
    """Honest, convention-based test-file detection per language."""
    name = Path(file_path).name
    parts = Path(file_path).parts

    if language == "go":
        return name.endswith("_test.go")

    if language in ("javascript", "typescript"):
        stem_markers = (".test.", ".spec.")
        if any(marker in name for marker in stem_markers):
            return True
        if "__tests__" in parts:
            return True
        return False

    return False


def _is_private_name(name: str, language: str) -> MethodType:
    if language == "go":
        # Go's exported/unexported convention: leading uppercase = public.
        return MethodType.PUBLIC if name[:1].isupper() else MethodType.PRIVATE
    if name.startswith("_"):
        return MethodType.PRIVATE
    return MethodType.PUBLIC


def extract_production_methods(
    source: str, file_path: str, language: str
) -> List[MethodInfo]:
    """Extract class/struct methods (via the CIR) + top-level functions.

    Returns ``[]`` when *language* isn't supported here or the tree-sitter
    grammar is unavailable — callers must treat that as "not measured", not
    "zero methods".
    """
    if language not in SUPPORTED_LANGUAGES or not is_available(language):
        return []

    methods: List[MethodInfo] = []
    seen = set()

    file_info = build_file_cir(file_path, source, language)
    if file_info is not None:
        for cls in file_info.classes:
            for m in cls.methods:
                key = (cls.name, m.name, m.start_line)
                if key in seen:
                    continue
                seen.add(key)
                methods.append(MethodInfo(
                    name=m.name,
                    class_name=cls.name,
                    file_path=file_path,
                    line_number=m.start_line,
                    method_type=MethodType.PUBLIC if m.is_public else MethodType.PRIVATE,
                    complexity=1,
                    has_branches=False,
                    branch_count=0,
                    parameter_count=m.param_count,
                    is_async=False,
                    language=language,
                ))

    source_bytes = source.encode("utf-8")
    root = parse_source(source_bytes, language)
    query = _FUNCTION_DECLARATION_QUERIES.get(language)
    if root is not None and query:
        for capture in run_query_all(root, query, source_bytes, language):
            name_info = capture.get("func.name")
            if not name_info:
                continue
            name = name_info["text"]
            key = (None, name, name_info["line"] + 1)
            if key in seen:
                continue
            seen.add(key)
            methods.append(MethodInfo(
                name=name,
                class_name=None,
                file_path=file_path,
                line_number=name_info["line"] + 1,
                method_type=_is_private_name(name, language),
                complexity=1,
                has_branches=False,
                branch_count=0,
                parameter_count=0,
                is_async=False,
                language=language,
            ))

    return methods


def extract_test_signal_methods(
    source: str, file_path: str, language: str
) -> List[MethodInfo]:
    """Extract synthetic "test methods" representing what a test file calls.

    Each distinct called-identifier name inside the test file becomes a
    synthetic :class:`MethodInfo` whose ``.name`` is that identifier, so the
    existing ``is_method_covered`` / ``build_test_name_set`` string-matching
    helpers (shared with the Python path) treat "this test file calls
    `fooBar(...)`" as evidence that `fooBar` is covered — the same
    call-based heuristic ``method_extractor.find_tested_methods`` uses for
    Python.

    Returns ``[]`` when the language/grammar isn't supported.
    """
    if language not in SUPPORTED_LANGUAGES or not is_available(language):
        return []

    source_bytes = source.encode("utf-8")
    root = parse_source(source_bytes, language)
    if root is None:
        return []

    called: Set[str] = set()
    for query in (
        _PLAIN_CALL_QUERIES.get(language),
        _MEMBER_CALL_QUERIES.get(language),
    ):
        if not query:
            continue
        for capture in run_query_all(root, query, source_bytes, language):
            name_info = capture.get("call.name")
            if name_info and name_info["text"]:
                called.add(name_info["text"])

    return [
        MethodInfo(
            name=name,
            class_name=None,
            file_path=file_path,
            line_number=0,
            method_type=MethodType.PUBLIC,
            language=language,
        )
        for name in called
    ]
