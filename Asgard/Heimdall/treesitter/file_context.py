"""FileParseContext — parse a file once per scan and pass the tree down.

Crossing the Python/C boundary repeatedly is the tree-sitter bottleneck, so
scanner orchestrators construct **one** ``FileParseContext`` per file and
thread it through ``kwargs["parse_context"]`` to every rule (see
``ast_engine.with_ast_fallback``).

Memory discipline: contexts are scoped to the per-file loop; drop the context
(and thus the tree) before moving to the next file.  Contexts are NOT
picklable — in ``ProcessPoolExecutor`` workers, parse inside the worker and
return only plain finding dataclasses/dicts.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

from Asgard.Heimdall.treesitter._language_loader import get_language_object

#: File-extension → tree-sitter language routing.  ``.tsx`` needs the
#: dedicated ``language_tsx()`` grammar entry point.
EXTENSION_LANGUAGE_MAP = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "tsx",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".rs": "rust",
}


def language_for_path(file_path: Union[str, Path]) -> Optional[str]:
    """Return the tree-sitter language name for *file_path*, or ``None``."""
    return EXTENSION_LANGUAGE_MAP.get(Path(file_path).suffix.lower())


def _to_utf8_bytes(lines: Optional[Sequence[str]], file_path: Union[str, Path]) -> Optional[bytes]:
    """UTF-8 gateway: always hand tree-sitter valid UTF-8 bytes.

    Prefers in-memory *lines*; falls back to reading the file.  Invalid byte
    sequences are replaced rather than propagated (RESEARCH_04 pitfall:
    feeding non-UTF-8 bytes to ``parser.parse`` corrupts offsets).
    """
    if lines is not None:
        try:
            return "\n".join(lines).encode("utf-8", errors="replace")
        except Exception:
            return None
    try:
        raw = Path(file_path).read_bytes()
    except OSError:
        return None
    # Round-trip to guarantee valid UTF-8 for the parser.
    return raw.decode("utf-8", errors="replace").encode("utf-8")


def _collect_error_ranges(root) -> List[Tuple[int, int]]:
    """Return 0-based inclusive (start_line, end_line) spans of ERROR/MISSING nodes.

    Only descends into subtrees that actually contain errors, so this is cheap
    on well-formed files.
    """
    ranges: List[Tuple[int, int]] = []

    def _walk(node) -> None:
        try:
            if node.type == "ERROR" or node.is_missing:
                ranges.append((node.start_point[0], node.end_point[0]))
                return
            if not node.has_error:
                return
        except Exception:
            return
        for child in node.children:
            _walk(child)

    try:
        if root is not None and root.has_error:
            _walk(root)
    except Exception:
        pass
    return ranges


@dataclass
class FileParseContext:
    """One parsed file: source bytes, tree, language, and ERROR spans.

    ``tree``/``root`` are ``None`` when tree-sitter (or the language grammar)
    is unavailable or parsing failed — callers must treat that as "use the
    regex engine", never as an error.
    """

    file_path: str
    language: str
    source_bytes: bytes = b""
    tree: object = None
    root: object = None
    error_ranges: List[Tuple[int, int]] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """True when the parse tree contains ERROR/MISSING nodes."""
        return bool(self.error_ranges)

    def intersects_error(self, start_line: int, end_line: Optional[int] = None) -> bool:
        """True if the 0-based line span intersects any ERROR region.

        Rules should skip findings whose span intersects an ERROR region to
        avoid garbage matches on broken code.
        """
        if end_line is None:
            end_line = start_line
        for err_start, err_end in self.error_ranges:
            if start_line <= err_end and end_line >= err_start:
                return True
        return False

    def node_text(self, node) -> str:
        """Extract the UTF-8 text covered by *node* as a plain ``str``."""
        if node is None:
            return ""
        try:
            return self.source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
        except Exception:
            return ""

    @classmethod
    def parse(
        cls,
        file_path: Union[str, Path],
        lines: Optional[Sequence[str]] = None,
        language: Optional[str] = None,
    ) -> "FileParseContext":
        """Parse *file_path* (or in-memory *lines*) once.

        Never raises: on any failure the returned context has ``tree is None``
        and callers fall back to the regex engine.
        """
        lang = language or language_for_path(file_path) or ""
        ctx = cls(file_path=str(file_path), language=lang)
        if not lang or get_language_object(lang) is None:
            return ctx

        source = _to_utf8_bytes(lines, file_path)
        if source is None:
            return ctx
        ctx.source_bytes = source

        try:
            from Asgard.Heimdall.treesitter._parser_pool import get_parser  # noqa: PLC0415
            parser = get_parser(lang)
            if parser is None:
                return ctx
            tree = parser.parse(source)
            ctx.tree = tree
            ctx.root = tree.root_node
            ctx.error_ranges = _collect_error_ranges(ctx.root)
        except Exception:
            ctx.tree = None
            ctx.root = None
        return ctx
