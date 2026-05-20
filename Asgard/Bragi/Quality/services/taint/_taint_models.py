"""Dataclasses for taint analysis results."""

from dataclasses import dataclass, field


@dataclass
class TaintPath:
    source_line: int
    sink_line: int
    variable: str
    confidence: float
    source_pattern: str
    sink_pattern: str
    language: str


@dataclass
class TaintFinding:
    rule_id: str
    line: int
    message: str
    severity: str  # "error" if confidence >= 0.85, else "warning"
    confidence: float
    path: TaintPath


@dataclass
class TaintConfig:
    threshold: float = 0.70
    max_function_lines: int = 500
    rules: dict = field(default_factory=dict)


@dataclass
class TaintReport:
    findings: list
    files_scanned: int
    functions_scanned: int
