"""
Generic (non-Python) complexity analysis via Pygments tokenization.

Approximates cyclomatic complexity by counting control-flow keywords.
Works for any language Pygments can lex: Java, Go, JS/TS, Ruby, PHP, C#, Rust, etc.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

try:
    from pygments import lex
    from pygments.lexers import get_lexer_for_filename, guess_lexer
    from pygments.token import Token
    from pygments.util import ClassNotFound
    _PYGMENTS_AVAILABLE = True
except ImportError:
    _PYGMENTS_AVAILABLE = False

# Control-flow keywords that each add 1 to cyclomatic complexity
_CC_KEYWORDS = frozenset({
    "if", "elif", "else", "for", "while", "do", "switch", "case",
    "catch", "except", "finally", "when", "unless", "until",
    "select", "default", "rescue", "&&", "||", "and", "or",
})

# Regex that matches the start of a function/method across many languages
_FUNC_START = re.compile(
    r"^\s*(?:(?:public|private|protected|static|async|export|override|abstract|final"
    r"|def|func|fn|fun|sub|void|int|str|bool|float|double|long|short|char|byte"
    r"|unsigned|signed|inline|virtual|override)\s+)*"
    r"(?:def|function|func|fn|fun|sub|void|int|str|bool|float|double|"
    r"long|short|char|byte|object|string|var|let|const)\s+"
    r"([A-Za-z_]\w*)\s*\(",
    re.MULTILINE,
)


@dataclass
class GenericFunctionComplexity:
    name: str
    start_line: int
    end_line: int
    cyclomatic_complexity: int
    cognitive_complexity: int
    line_count: int


def analyse_file(file_path: Path) -> List[GenericFunctionComplexity]:
    """Return per-function complexity for any Pygments-supported language."""
    if not _PYGMENTS_AVAILABLE:
        return _regex_fallback(file_path)

    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    try:
        lexer = get_lexer_for_filename(str(file_path))
    except ClassNotFound:
        try:
            lexer = guess_lexer(source)
        except ClassNotFound:
            return _regex_fallback(file_path)

    tokens = list(lex(source, lexer))
    lines = source.splitlines()
    return _extract_functions(tokens, lines, str(file_path))


def _extract_functions(tokens, lines: List[str], file_path: str) -> List[GenericFunctionComplexity]:
    boundaries: List[Tuple[int, str]] = []
    src = "\n".join(lines)
    for m in _FUNC_START.finditer(src):
        lineno = src[: m.start()].count("\n") + 1
        boundaries.append((lineno, m.group(1)))

    if not boundaries:
        cc, cog = _score_tokens(tokens)
        return [GenericFunctionComplexity(
            name="<module>",
            start_line=1,
            end_line=len(lines),
            cyclomatic_complexity=cc,
            cognitive_complexity=cog,
            line_count=len(lines),
        )]

    results = []
    for i, (start, name) in enumerate(boundaries):
        end = boundaries[i + 1][0] - 1 if i + 1 < len(boundaries) else len(lines)
        try:
            from pygments.lexers import get_lexer_for_filename
            lexer = get_lexer_for_filename(file_path)
            from pygments import lex as _lex
            func_tokens = list(_lex("\n".join(lines[start - 1: end]), lexer))
        except Exception:
            func_tokens = tokens
        cc, cog = _score_tokens(func_tokens)
        results.append(GenericFunctionComplexity(
            name=name,
            start_line=start,
            end_line=end,
            cyclomatic_complexity=cc,
            cognitive_complexity=cog,
            line_count=end - start + 1,
        ))
    return results


def _score_tokens(tokens) -> Tuple[int, int]:
    cc = 1
    cog = 0
    nesting = 0
    for ttype, value in tokens:
        v = value.strip().lower()
        if ttype in Token.Keyword or ttype in Token.Operator:
            if v in _CC_KEYWORDS:
                cc += 1
                cog += 1 + nesting
            if value in ("{", "do", "begin", "then"):
                nesting += 1
            elif value in ("}", "end"):
                nesting = max(0, nesting - 1)
    return cc, cog


def _regex_fallback(file_path: Path) -> List[GenericFunctionComplexity]:
    """Simple line-counting fallback when Pygments is unavailable."""
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    cc = 1 + sum(
        1 for line in lines
        if re.search(r"\b(if|else|for|while|switch|catch|case)\b", line)
    )
    return [GenericFunctionComplexity(
        name="<module>",
        start_line=1,
        end_line=len(lines),
        cyclomatic_complexity=cc,
        cognitive_complexity=cc,
        line_count=len(lines),
    )]
