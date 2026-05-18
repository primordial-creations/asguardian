"""ReDoS (Regular Expression Denial of Service) vulnerability scanner."""

import os
import re
from pathlib import Path
from typing import List, Tuple

from Asgard.Heimdall.Security.ReDoS.models.redos_models import (
    ReDoSFinding,
    ReDoSScanConfig,
    ReDoSScanReport,
    ReDoSSeverity,
)

_LANG_EXTENSIONS = {".py": "python", ".js": "javascript", ".ts": "javascript",
                    ".jsx": "javascript", ".tsx": "javascript", ".java": "java",
                    ".rb": "ruby", ".php": "php", ".go": "go", ".cs": "csharp"}

# Patterns that extract regex literals per language
_LANG_EXTRACTION = {
    "python": [
        re.compile(r"re\.(?:match|search|findall|finditer|sub|split)\s*\(\s*r?['\"](.+?)['\"]", re.IGNORECASE),
        re.compile(r"re\.compile\s*\(\s*r?['\"](.+?)['\"]", re.IGNORECASE),
    ],
    "javascript": [
        re.compile(r"new\s+RegExp\s*\(\s*['\"`](.+?)['\"`]", re.IGNORECASE),
        re.compile(r"\.(?:match|replace|search|split)\s*\(\s*/(.+?)/[gimsuy]*", re.IGNORECASE),
    ],
    "java": [
        re.compile(r'Pattern\.compile\s*\(\s*"(.+?)"'),
        re.compile(r'\.matches\s*\(\s*"(.+?)"'),
    ],
    "ruby": [
        re.compile(r"Regexp\.new\s*\(\s*['\"](.+?)['\"]"),
    ],
    "php": [
        re.compile(r"preg_(?:match|replace|split|grep)\s*\(\s*['\"](.+?)['\"]"),
    ],
    "go": [
        re.compile(r"regexp\.(?:Compile|MustCompile)\s*\(\s*`(.+?)`"),
        re.compile(r'regexp\.(?:Compile|MustCompile)\s*\(\s*"(.+?)"'),
    ],
    "csharp": [
        re.compile(r'new\s+Regex\s*\(\s*@?"(.+?)"'),
    ],
}

# Heuristic indicators of vulnerable regex structure
_REDOS_INDICATORS: List[Tuple] = [
    (re.compile(r"\([^)]*[+*][^)]*\)[+*]"), "nested_quantifiers", "CRITICAL",
     "Nested quantifiers (e.g., (a+)+) cause catastrophic backtracking", "Refactor to avoid nested quantifiers"),
    (re.compile(r"\([^)]*\|[^)]*\)[+*]"), "overlapping_alternation", "HIGH",
     "Overlapping alternation with quantifier", "Make alternations mutually exclusive"),
    (re.compile(r"\.\*.*\.\*|\.\+.*\.\+"), "multiple_wildcards", "MEDIUM",
     "Multiple wildcards in pattern", "Use atomic groups or possessive quantifiers"),
    (re.compile(r"\([^)]*\([^)]*[+*][^)]*\)[+*][^)]*\)"), "exponential_pattern", "CRITICAL",
     "Potentially exponential regex structure", "Simplify nested quantifier structure"),
]


def _star_height(pattern: str) -> int:
    max_h = cur = 0
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "(":
            cur += 1
        elif ch == ")":
            if i + 1 < len(pattern) and pattern[i + 1] in "+*?":
                max_h = max(max_h, cur)
            cur = max(0, cur - 1)
        elif ch in "+*":
            max_h = max(max_h, cur)
        i += 1
    return max_h


def _check_vulnerability(regex_str: str) -> List[Tuple[str, str, str, str]]:
    vulns = []
    for compiled, ptype, severity, desc, rec in _REDOS_INDICATORS:
        if compiled.search(regex_str):
            vulns.append((ptype, severity, desc, rec))
    if _star_height(regex_str) > 1:
        vulns.append(("high_star_height", "HIGH", "Regex with star height > 1", "Reduce nesting of quantifiers"))
    return vulns


class ReDoSScanner:
    """Scans source code for regex patterns vulnerable to catastrophic backtracking."""

    def scan(self, config: ReDoSScanConfig) -> ReDoSScanReport:
        findings: List[ReDoSFinding] = []
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
        by_type: dict = {}
        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
            by_type[f.pattern_type] = by_type.get(f.pattern_type, 0) + 1

        return ReDoSScanReport(
            scan_path=str(config.scan_path),
            total_findings=len(findings),
            files_scanned=files_scanned,
            findings=findings,
            by_severity=by_severity,
            by_type=by_type,
        )

    def _scan_file(self, file_path: Path) -> List[ReDoSFinding]:
        lang = _LANG_EXTENSIONS.get(file_path.suffix.lower())
        if not lang or lang not in _LANG_EXTRACTION:
            return []

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        findings: List[ReDoSFinding] = []
        for extraction_re in _LANG_EXTRACTION[lang]:
            for match in extraction_re.finditer(content):
                extracted = match.group(1)
                line_num = content[: match.start()].count("\n") + 1
                for ptype, severity, desc, rec in _check_vulnerability(extracted):
                    findings.append(ReDoSFinding(
                        file_path=str(file_path),
                        line_number=line_num,
                        severity=ReDoSSeverity(severity),
                        pattern_type=ptype,
                        regex_pattern=extracted[:100] + ("..." if len(extracted) > 100 else ""),
                        description=desc,
                        recommendation=rec,
                    ))

        return findings
