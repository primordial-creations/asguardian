"""
Sourcemap Loader - YAML/JSON loading that preserves (line, column) per node.

Uses `yaml.compose` (which also parses JSON, a YAML subset) to build a
side-table mapping json-path pointers to 1-based (line, column) marks.
Best-effort: unmapped paths are simply absent — a lookup returns None,
never a wrong position.
"""

from pathlib import Path
from typing import Any, Optional

import yaml

SourceMap = dict[str, tuple[int, int]]


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _walk(node: "yaml.Node", path: str, sourcemap: SourceMap) -> None:
    sourcemap[path or "/"] = (node.start_mark.line + 1, node.start_mark.column + 1)
    if isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            key = str(getattr(key_node, "value", key_node))
            child = f"{path}/{_escape(key)}"
            sourcemap[child] = (key_node.start_mark.line + 1, key_node.start_mark.column + 1)
            _walk(value_node, child, sourcemap)
    elif isinstance(node, yaml.SequenceNode):
        for index, item in enumerate(node.value):
            _walk(item, f"{path}/{index}", sourcemap)


def build_sourcemap(text: str) -> SourceMap:
    """Build a json-path -> (line, column) map for a YAML/JSON document."""
    sourcemap: SourceMap = {}
    try:
        root = yaml.compose(text)
    except yaml.YAMLError:
        return sourcemap
    if root is not None:
        _walk(root, "", sourcemap)
    return sourcemap


def load_with_sourcemap(path: str | Path) -> tuple[Any, SourceMap]:
    """Load a YAML/JSON file returning (data, sourcemap)."""
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return data, build_sourcemap(text)


def lookup(sourcemap: SourceMap, json_path: str) -> tuple[Optional[int], Optional[int]]:
    """
    Look up the position of a json path, falling back to the deepest
    mapped ancestor. Returns (None, None) when nothing matches.
    """
    candidate = json_path if json_path.startswith("/") else f"/{json_path}"
    while True:
        if candidate in sourcemap:
            return sourcemap[candidate]
        if candidate in ("", "/"):
            return (None, None)
        candidate = candidate.rsplit("/", 1)[0] or "/"


def annotate_findings(findings, sourcemap: SourceMap) -> None:
    """Fill line/column on findings from a sourcemap (in place)."""
    for finding in findings:
        if finding.coordinates.line is None:
            line, column = lookup(sourcemap, finding.coordinates.json_path)
            finding.coordinates.line = line
            finding.coordinates.column = column
