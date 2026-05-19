"""One Parser instance per language, lazily created and reused.

CRITICAL memory rule
--------------------
Tree-sitter Node objects hold a reference back to the underlying parse tree
which, in turn, owns the source bytes.  Callers MUST extract all needed values
(text, line numbers, column numbers, node type strings …) as plain Python
primitives (``str``, ``int``, ``bytes``) before their function returns.

**Never** store a Node in a class attribute, module-level dict, or any other
long-lived container.  Violating this rule causes stale or corrupt data when
the source bytes are later reparsed or freed.
"""
from pathlib import Path
from typing import Optional, Tuple

from Asgard.Heimdall.treesitter._language_loader import get_language_object

_PARSERS: dict = {}  # language -> Parser (lazy init)


def _get_or_create_parser(language: str):
    """Return the cached Parser for *language*, creating it on first call.

    Returns ``None`` if the language binding is unavailable.
    """
    if language in _PARSERS:
        return _PARSERS[language]

    lang_obj = get_language_object(language)
    if lang_obj is None:
        return None

    try:
        from tree_sitter import Parser  # noqa: PLC0415
        parser = Parser(lang_obj)
        _PARSERS[language] = parser
        return parser
    except Exception:
        return None


def get_parser(language: str):
    """Return the shared ``Parser`` for *language*, or ``None`` if unavailable.

    IMPORTANT: the returned Parser is shared across all callers.  Do not
    call ``set_language`` on it; use :func:`parse_source` or
    :func:`parse_file` instead.
    """
    return _get_or_create_parser(language)


def parse_source(source: bytes, language: str):
    """Parse *source* bytes and return the root ``Node``, or ``None``.

    Returns ``None`` gracefully when tree-sitter is not installed or the
    language binding is unavailable.

    CRITICAL: the caller MUST extract all needed values as primitives before
    the calling function returns.  See module docstring for details.
    """
    parser = _get_or_create_parser(language)
    if parser is None:
        return None
    try:
        tree = parser.parse(source)
        return tree.root_node
    except Exception:
        return None


def parse_file(file_path: Path, language: str) -> Tuple:
    """Read *file_path* and parse it.

    Returns ``(root_node, source_bytes)`` on success, or ``(None, b'')`` when
    tree-sitter is unavailable or the file cannot be read.

    CRITICAL: the caller MUST extract all needed values as primitives before
    the calling function returns.  See module docstring for details.
    """
    try:
        source = Path(file_path).read_bytes()
    except OSError:
        return (None, b"")

    root = parse_source(source, language)
    if root is None:
        return (None, b"")
    return (root, source)
