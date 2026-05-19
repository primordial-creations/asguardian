"""Top-level taint analyzer.

Walks a directory tree, extracts function bodies by indentation/brace
heuristic, runs TaintEngine on each, and aggregates TaintFindings.

Intra-function only; inter-function flows and aliasing are not tracked.
"""

import os
import re
from pathlib import Path

from Asgard.Heimdall.Quality.services.taint._taint_engine import TaintEngine
from Asgard.Heimdall.Quality.services.taint._taint_models import (
    TaintConfig,
    TaintFinding,
    TaintPath,
    TaintReport,
)

_EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
}

# Patterns that signal the start of a function/method definition per language.
_FUNC_START_PATTERNS: dict[str, re.Pattern] = {
    "python": re.compile(r"^(\s*)def\s+\w+"),
    "javascript": re.compile(r"^(\s*)(?:function\s+\w+|(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>|\w+\s*=>))"),
    "typescript": re.compile(r"^(\s*)(?:function\s+\w+|(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>|\w+\s*=>)|(?:public|private|protected|async)?\s*\w+\s*\([^)]*\)\s*(?::\s*\w+)?\s*\{)"),
    "java": re.compile(r"^(\s*)(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+\w+\s*\("),
    "go": re.compile(r"^(\s*)func\s+"),
    "ruby": re.compile(r"^(\s*)def\s+\w+"),
    "php": re.compile(r"^(\s*)(?:public|private|protected|static|\s)*function\s+\w+"),
    "csharp": re.compile(r"^(\s*)(?:public|private|protected|internal|static|async|\s)+[\w<>\[\]?]+\s+\w+\s*\("),
}

_DEFAULT_FUNC_PATTERN = re.compile(r"^(\s*)(?:def|func|function)\s+\w+")


def _detect_language(file_path: str) -> str | None:
    ext = Path(file_path).suffix.lower()
    return _EXTENSION_TO_LANGUAGE.get(ext)


def _extract_function_bodies(lines: list[str], language: str) -> list[tuple[int, list[str]]]:
    """
    Return (start_lineno_1based, body_lines) for each function found.

    Python uses indentation; brace-languages use a simple brace counter so
    we collect everything between the opening { and its matching }.
    For languages without braces we fall back to indentation.
    """
    pattern = _FUNC_START_PATTERNS.get(language, _DEFAULT_FUNC_PATTERN)
    brace_languages = {"javascript", "typescript", "java", "go", "php", "csharp"}
    functions = []

    i = 0
    while i < len(lines):
        m = pattern.match(lines[i])
        if m:
            start = i
            if language in brace_languages:
                depth = 0
                body: list[str] = []
                for j in range(i, len(lines)):
                    body.append(lines[j])
                    depth += lines[j].count("{") - lines[j].count("}")
                    if j > i and depth <= 0:
                        functions.append((start + 1, body))
                        i = j + 1
                        break
                else:
                    functions.append((start + 1, body))
                    i = len(lines)
                continue
            else:
                # Indentation-based (Python, Ruby)
                indent = len(m.group(1))
                body = [lines[i]]
                j = i + 1
                while j < len(lines):
                    stripped = lines[j].rstrip()
                    if stripped == "":
                        body.append(lines[j])
                        j += 1
                        continue
                    current_indent = len(lines[j]) - len(lines[j].lstrip())
                    if current_indent <= indent and pattern.match(lines[j]):
                        break
                    body.append(lines[j])
                    j += 1
                functions.append((start + 1, body))
                i = j
                continue
        i += 1

    return functions


def _path_to_finding(path: TaintPath, threshold: float) -> TaintFinding | None:
    if path.confidence < threshold:
        return None
    severity = "error" if path.confidence >= 0.85 else "warning"
    rule_id = f"taint.{path.language}.source-to-sink"
    message = (
        f"Tainted variable '{path.variable}' flows from source (line {path.source_line}) "
        f"to sink (line {path.sink_line}) with confidence {path.confidence:.2f}"
    )
    return TaintFinding(
        rule_id=rule_id,
        line=path.sink_line,
        message=message,
        severity=severity,
        confidence=path.confidence,
        path=path,
    )


class TaintAnalyzer:
    """
    Scans source files for intra-function taint flows.

    Intra-function only; inter-function flows and aliasing are not tracked.
    """

    def __init__(self, config: TaintConfig | None = None) -> None:
        self._config = config or TaintConfig()
        self._engine = TaintEngine()

    def analyze(self, scan_path: str, language: str | None = None) -> TaintReport:
        path = Path(scan_path)
        findings: list[TaintFinding] = []
        files_scanned = 0
        functions_scanned = 0

        if path.is_file():
            file_list = [path]
        else:
            file_list = [p for p in path.rglob("*") if p.is_file()]

        for file_path in file_list:
            lang = language or _detect_language(str(file_path))
            if lang is None:
                continue

            try:
                source = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            lines = source.splitlines()
            files_scanned += 1

            functions = _extract_function_bodies(lines, lang)
            if not functions:
                # Treat the whole file as a single body when no functions found
                functions = [(1, lines)]

            for start_lineno, body_lines in functions:
                if len(body_lines) > self._config.max_function_lines:
                    continue

                functions_scanned += 1
                body_text = "\n".join(body_lines)
                taint_paths = self._engine.analyze_function(
                    source_text=body_text,
                    language=lang,
                    function_node_text=body_text,
                )

                for tp in taint_paths:
                    # Adjust line numbers to be file-relative
                    adjusted = TaintPath(
                        source_line=tp.source_line + start_lineno - 1,
                        sink_line=tp.sink_line + start_lineno - 1,
                        variable=tp.variable,
                        confidence=tp.confidence,
                        source_pattern=tp.source_pattern,
                        sink_pattern=tp.sink_pattern,
                        language=tp.language,
                    )
                    finding = _path_to_finding(adjusted, self._config.threshold)
                    if finding is not None:
                        findings.append(finding)

        return TaintReport(
            findings=findings,
            files_scanned=files_scanned,
            functions_scanned=functions_scanned,
        )
