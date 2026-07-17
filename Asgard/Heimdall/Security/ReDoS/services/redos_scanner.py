"""ReDoS (Regular Expression Denial of Service) vulnerability scanner.

Analysis core is Glushkov-NFA EDA/IDA ambiguity analysis (plan 07.2,
``_glushkov_analysis.py``) rather than the old "nested quantifier" line
regex, which DEEPTHINK_09 rates ~40% FP / "unfit". Pattern *extraction*
(finding the `re.compile(...)`-shaped call and pulling out the literal
string) still uses per-language regex, since that part is a simple,
low-FP text match and not where the false positives came from; dynamic
(non-literal) patterns are silently skipped here per the plan -- a
constant-folded f-string/concat would need the AST/taint layer and is
deferred to a separate CWE-400 regex-injection rule, not this scanner.
"""

import os
import re
import time
from pathlib import Path
from typing import List, Tuple

from Asgard.Heimdall.Security.ReDoS.models.redos_models import (
    ReDoSFinding,
    ReDoSScanConfig,
    ReDoSScanReport,
    ReDoSSeverity,
)
from Asgard.Heimdall.Security.ReDoS.services._glushkov_analysis import analyze_pattern
from Asgard.Heimdall.Security.normalization.priority import confidence_bucket

# Wall-clock budget per plan 07.2: ~25ms/regex, ~100ms/file.
_PER_REGEX_BUDGET_S = 0.025
_PER_FILE_BUDGET_S = 0.100

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

# A dominating length guard near the pattern's use-site (`len(x) < N`,
# slicing) neutralises IDA's polynomial blow-up in practice (plan 07.2
# step 3). Detecting a *dominating* guard precisely needs the call-site
# AST; this scanner only sees an extracted string, so it uses a bounded
# proximity heuristic on the surrounding source instead -- documented as
# approximate, never used to suppress EDA (which is unconditional).
_LENGTH_GUARD_RE = re.compile(r"len\([^)]{1,80}\)\s*[<>]=?\s*\d{1,6}|\[:?\d{1,6}\]")


def _check_vulnerability(
    regex_str: str, context_window: str = ""
) -> List[Tuple[str, str, str, str, float, str]]:
    """Run the Glushkov-NFA analysis. Returns
    ``(pattern_type, severity, description, recommendation, confidence, mechanism_id)``
    tuples -- zero or one per pattern (a pattern is either safe, EDA, or
    IDA; it cannot be both)."""
    start = time.monotonic()
    length_guarded = bool(_LENGTH_GUARD_RE.search(context_window))
    try:
        result = analyze_pattern(regex_str, length_guarded=length_guarded)
    except Exception:  # noqa: BLE001 - analysis must never crash the scan
        return []
    if time.monotonic() - start > _PER_REGEX_BUDGET_S * 4:
        # Analysis overran its budget by a wide margin -- treat as
        # unsupported rather than trust a possibly-truncated verdict.
        return []

    if result.verdict == "eda":
        return [(
            "catastrophic_backtracking", "HIGH",
            f"Exponential (EDA) regex ambiguity: {result.detail}",
            "Rewrite to remove the nested/overlapping repeat, or use RE2 "
            "(linear-time engine) or a possessive-quantifier rewrite.",
            0.9, "redos.eda",
        )]
    if result.verdict == "ida":
        return [(
            "polynomial_backtracking", "LOW",
            f"Polynomial (IDA) regex ambiguity: {result.detail}",
            "Add a bounding length check before matching, rewrite the "
            "chained repeats to be mutually exclusive, or use RE2/timeouts.",
            0.6, "redos.ida",
        )]
    # "safe" and "unsupported" both report nothing: "unsupported" (back-
    # references, oversized patterns) is a documented false negative, not
    # a claim of safety -- see module docstring.
    return []


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
        file_start = time.monotonic()
        lines = content.splitlines()
        for extraction_re in _LANG_EXTRACTION[lang]:
            for match in extraction_re.finditer(content):
                if time.monotonic() - file_start > _PER_FILE_BUDGET_S * 20:
                    return findings  # generous multiple of the per-file budget; stop pathological files
                extracted = match.group(1)
                line_num = content[: match.start()].count("\n") + 1
                window = "\n".join(lines[max(0, line_num - 3):line_num])
                for ptype, severity, desc, rec, conf, mech in _check_vulnerability(extracted, window):
                    findings.append(ReDoSFinding(
                        file_path=str(file_path),
                        line_number=line_num,
                        severity=ReDoSSeverity(severity),
                        pattern_type=ptype,
                        regex_pattern=extracted[:100] + ("..." if len(extracted) > 100 else ""),
                        description=desc,
                        recommendation=rec,
                        confidence=conf,
                        confidence_bucket=confidence_bucket(conf),
                        mechanism_id=mech,
                    ))

        return findings
