"""Input validation vulnerability scanner."""

import ast
import os
import re
from pathlib import Path
from typing import List

from Asgard.Heimdall.Security.InputValidation.models.input_validation_models import (
    InputValidationFinding,
    InputValidationScanConfig,
    InputValidationScanReport,
    InputValidationSeverity,
)
from Asgard.Heimdall.Security.InputValidation.services._validation_barrier_analysis import (
    scan_validation_barriers,
)
from Asgard.Heimdall.Security.context.test_context import is_test_context
from Asgard.Heimdall.Security.normalization.priority import confidence_bucket

_VALIDATION_PATTERNS: dict = {
    "type_coercion": [
        (r"parseInt\s*\(\s*(?:req\.|request\.|params\.|body\.|query\.)[^,)]+\s*\)", "MEDIUM", "unsafe_parseint", "parseInt without radix or validation", "Add radix parameter and validate input"),
        (r"Number\s*\(\s*(?:req\.|request\.|params\.|body\.)", "MEDIUM", "unsafe_number_coercion", "Number coercion without validation", "Validate numeric input before coercion"),
        (r"(?:JSON\.parse|json\.loads)\s*\(\s*(?:req\.|request\.|body\.|params\.)", "HIGH", "unsafe_json_parse", "JSON parsing without error handling", "Wrap JSON parsing in try-catch/except"),
    ],
    "array_access": [
        (r"\[\s*(?:req\.|request\.|params\.|query\.|body\.)[^\]]+\s*\]", "MEDIUM", "unvalidated_array_index", "Array access with user input", "Validate array index bounds"),
    ],
    "regex_input": [
        (r"(?:new\s+RegExp|re\.compile)\s*\(\s*(?:req\.|request\.|params\.|body\.)", "HIGH", "user_controlled_regex", "Regex created from user input (ReDoS risk)", "Sanitize or avoid user-controlled regex"),
    ],
    "file_operations": [
        (r"(?:readFile|writeFile|open|fopen)\s*\(\s*(?:req\.|request\.|params\.)", "CRITICAL", "path_from_input", "File path from user input", "Validate and sanitize file paths"),
        (r"path\.join\s*\([^)]*(?:req\.|request\.|params\.)", "HIGH", "path_join_from_input", "Path construction with user input", "Use path.basename() and validate"),
    ],
    "url_operations": [
        (r"(?:fetch|axios|http\.get|requests\.get)\s*\(\s*(?:req\.|request\.|params\.|body\.)", "HIGH", "ssrf_input", "HTTP request with user-controlled URL", "Validate URL against allowlist"),
    ],
    "database_queries": [
        (r"(?:query|execute|cursor\.execute)\s*\(\s*['\"].*\+.*(?:req\.|request\.|params\.)", "CRITICAL", "sql_string_concat", "SQL query string concatenation with user input", "Use parameterized queries"),
        (r"(?:query|execute)\s*\(\s*`[^`]*\$\{(?:req\.|request\.|params\.)", "CRITICAL", "sql_template_literal", "SQL query via template literal with user input", "Use parameterized queries"),
    ],
    "command_execution": [
        (r"(?:exec|spawn|system|shell_exec|os\.system)\s*\(\s*(?:req\.|request\.|params\.|body\.)", "CRITICAL", "command_injection_input", "Command execution with user input", "Never use user input in shell commands"),
        (r"subprocess\.(?:run|call|Popen)\s*\([^)]*(?:req\.|request\.)", "CRITICAL", "subprocess_input", "Subprocess with user input", "Avoid user input in subprocess calls"),
    ],
    "template_injection": [
        (r"(?:render_template_string|Template)\s*\(\s*(?:req\.|request\.|params\.|f['\"])", "CRITICAL", "ssti", "Server-side template injection", "Never render user input as template"),
        (r"jinja2\.Template\s*\(\s*(?:req\.|request\.|params\.)", "CRITICAL", "jinja2_ssti", "Jinja2 SSTI with user input", "Use safe template rendering"),
    ],
    "length_validation": [
        (r"(?:req\.|request\.|params\.)\w+(?!\s*\.\s*(?:length|size|len))", "LOW", "no_length_check", "Input used without length validation", "Validate input length before processing"),
    ],
}


class InputValidationScanner:
    """Scans source code for input validation vulnerabilities."""

    def __init__(self) -> None:
        self._compiled: dict = {}
        for category, patterns in _VALIDATION_PATTERNS.items():
            self._compiled[category] = [
                (re.compile(p, re.IGNORECASE), sev, ptype, desc, rec)
                for p, sev, ptype, desc, rec in patterns
            ]

    def scan(self, config: InputValidationScanConfig) -> InputValidationScanReport:
        findings: List[InputValidationFinding] = []
        files_scanned = 0
        target = config.scan_path
        skip = set(config.skip_dirs)

        if target.is_file():
            findings = self._scan_file(target)
            files_scanned = 1
        else:
            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if d not in skip]
                for name in files:
                    fp = Path(root) / name
                    ff = self._scan_file(fp)
                    if ff:
                        findings.extend(ff)
                        files_scanned += 1

        by_severity: dict = {}
        by_category: dict = {}
        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
            by_category[f.category] = by_category.get(f.category, 0) + 1

        return InputValidationScanReport(
            scan_path=str(config.scan_path),
            total_findings=len(findings),
            files_scanned=files_scanned,
            findings=findings,
            by_severity=by_severity,
            by_category=by_category,
        )

    def _scan_file(self, file_path: Path) -> List[InputValidationFinding]:
        if file_path.suffix.lower() not in {".py", ".js", ".ts", ".jsx", ".tsx", ".php", ".java", ".rb", ".go", ".cs"}:
            return []
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        lines = content.splitlines()
        in_test_context = is_test_context(str(file_path))

        findings: List[InputValidationFinding] = []
        for line_num, line in enumerate(lines, 1):
            for category, patterns in self._compiled.items():
                for regex, sev, ptype, desc, rec in patterns:
                    if regex.search(line):
                        confidence = 0.3 if in_test_context else 0.6
                        findings.append(InputValidationFinding(
                            file_path=str(file_path),
                            line_number=line_num,
                            severity=InputValidationSeverity(sev),
                            category=category,
                            issue_type=ptype,
                            code_snippet=line.strip()[:150],
                            description=desc,
                            recommendation=rec,
                            mechanism_id=f"input_validation.{category}.{ptype}",
                            confidence=confidence,
                            confidence_bucket=confidence_bucket(confidence),
                        ))
                        break

        if file_path.suffix == ".py":
            findings.extend(self._scan_validation_barriers(file_path, content, lines, in_test_context))

        return findings

    def _scan_validation_barriers(
        self, file_path: Path, content: str, lines: List[str], in_test_context: bool,
    ) -> List[InputValidationFinding]:
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        findings: List[InputValidationFinding] = []
        for barrier_finding in scan_validation_barriers(tree, lines):
            confidence = barrier_finding.confidence
            severity = barrier_finding.severity
            if in_test_context and not barrier_finding.is_advisory:
                # Plan 07.12/08: honor test-context by downgrading, never
                # suppressing -- test fixtures can still exercise a real
                # bypassable code path that ships to production.
                confidence = min(confidence, 0.2)
                severity = "LOW"

            findings.append(InputValidationFinding(
                file_path=str(file_path),
                line_number=barrier_finding.line_number,
                severity=InputValidationSeverity(severity),
                category="validation_barrier",
                issue_type=barrier_finding.issue_type,
                code_snippet=barrier_finding.snippet,
                description=barrier_finding.description,
                recommendation=barrier_finding.recommendation,
                mechanism_id=barrier_finding.mechanism_id,
                confidence=confidence,
                confidence_bucket=confidence_bucket(confidence),
                is_advisory=barrier_finding.is_advisory,
                cwe_id=barrier_finding.cwe_id,
            ))
        return findings
