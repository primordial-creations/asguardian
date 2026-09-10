"""
CLI wiring helpers for the layered security dispatch engine.

Routes `heimdall security scan` through the 3-layer DispatchEngine
(regex -> AST triggers -> lazy taint), reads `.heimdall.yml` test-context
configuration, counts LOC for v2 score normalization, and renders findings
with qualitative confidence buckets (never raw probabilities) in priority
order.
"""

import fnmatch
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from Asgard.Heimdall.Security.utilities._scan_utils import (
    is_confined_scan_path,
    iter_confined_files,
)
from Asgard.Heimdall.Security.context.test_context import classify_file_context
from Asgard.Heimdall.Security.engine.dispatch import DispatchEngine
from Asgard.Heimdall.Security.normalization.priority import (
    confidence_bucket,
    context_modifier_for_tag,
    priority,
)

#: Extensions counted for size normalization (v2 scoring).
_CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".c", ".h", ".cpp",
    ".java", ".rb", ".rs", ".php", ".cs", ".kt", ".swift",
}

_DEFAULT_EXCLUDES = (
    "__pycache__", "node_modules", ".git", ".venv", "venv",
    "build", "dist", ".next", "coverage",
)

#: Extensions the DispatchEngine actually parses (regex + AST/CST triggers +
#: taint). Mirrors the JS/TS/Java branch in
#: `Asgard.Heimdall.Security.engine.dispatch` plus native Python support.
#: Feeding the engine extensions it can't parse would silently no-op those
#: files, so this MUST stay in sync with that module's supported set.
_DISPATCH_SUPPORTED_EXTENSIONS = frozenset({
    ".py",
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts",
    ".java",
    ".go",
    ".c", ".h",
})

#: Display labels for confidence buckets (qualitative only).
BUCKET_LABELS = {
    "certain": "Certain",
    "probable": "Probable",
    "possible": "Possible",
    "unlikely": "Unlikely",
    "needs_review": "Needs Review",
}


def load_heimdall_yml(scan_path: Path, *, strict: bool = False) -> Dict[str, Any]:
    """
    Read `.heimdall.yml` from the scan path (zero-config: absent file is
    simply empty config). Recognized keys:
        test_context_enabled: bool (default True)
        strict_scan_paths: list of regexes forced to production context
    """
    config_file = Path(scan_path) / ".heimdall.yml"
    if strict and config_file.is_symlink():
        raise ValueError(".heimdall.yml must not be a symlink")
    if not config_file.is_file():
        if strict and config_file.exists():
            raise ValueError(".heimdall.yml must be a regular file")
        return {}
    try:
        import yaml
        data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    except Exception:
        if strict:
            raise
        return {}
    if strict:
        import re
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ValueError(".heimdall.yml must contain an object")
        if "test_context_enabled" in data and type(data["test_context_enabled"]) is not bool:
            raise ValueError("test_context_enabled must be a boolean")
        patterns = data.get("strict_scan_paths", [])
        if not isinstance(patterns, list) or not all(isinstance(item, str) for item in patterns):
            raise ValueError("strict_scan_paths must contain regex strings")
        for pattern in patterns:
            re.compile(pattern)
    return data if isinstance(data, dict) else {}


def _is_excluded(rel_path: str, exclude_patterns: Sequence[str]) -> bool:
    parts = Path(rel_path).parts
    for pattern in list(exclude_patterns) + list(_DEFAULT_EXCLUDES):
        if pattern in parts:
            return True
        if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(
            Path(rel_path).name, pattern
        ):
            return True
    return False


def _iter_code_files(scan_path: Path, exclude_patterns: Sequence[str],
                     suffixes=None):
    scan_path = Path(scan_path)
    if scan_path.is_file():
        if is_confined_scan_path(scan_path, scan_path.parent):
            yield scan_path
        return

    def _skip(path: Path) -> bool:
        try:
            rel = str(path.relative_to(scan_path))
        except ValueError:
            return True
        return _is_excluded(rel, exclude_patterns)

    for path in sorted(iter_confined_files(scan_path, should_skip=_skip)):
        if suffixes and path.suffix not in suffixes:
            continue
        if not suffixes and path.suffix not in _CODE_EXTENSIONS:
            continue
        yield path


def count_lines_of_code(scan_path: Path,
                        exclude_patterns: Sequence[str] = ()) -> int:
    """Total non-empty lines across recognized code files (v2 size norm)."""
    total = 0
    for path in _iter_code_files(scan_path, exclude_patterns):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        total += sum(1 for line in text.splitlines() if line.strip())
    return total


@dataclass
class DispatchScanOutcome:
    """Findings plus whether any file's CST/AST analysis was incomplete."""
    entries: List[Dict[str, Any]] = field(default_factory=list)
    incomplete: bool = False
    parse_failed_files: int = 0
    truncated_files: int = 0


def collect_dispatch_scan(
    scan_path: Path,
    exclude_patterns: Sequence[str] = (),
    include_test_context: bool = False,
    test_context_enabled: bool = True,
    strict_scan_paths: Sequence[str] = (),
) -> DispatchScanOutcome:
    """Run DispatchEngine and record parse-failed / truncated files."""
    engine = DispatchEngine(
        is_test_context=None if test_context_enabled else False,
        strict_scan_paths=strict_scan_paths,
    )
    outcome = DispatchScanOutcome()
    entries = outcome.entries

    for path in _iter_code_files(scan_path, exclude_patterns,
                                 suffixes=_DISPATCH_SUPPORTED_EXTENSIONS):
        result = engine.scan_file(path)
        if result.parse_failed:
            outcome.parse_failed_files += 1
            outcome.incomplete = True
        if result.analysis_truncated:
            outcome.truncated_files += 1
            outcome.incomplete = True
        tag = classify_file_context(str(path), strict_scan_paths)
        tag_value = getattr(tag, "value", str(tag))
        is_test = str(tag_value).lower() != "production"
        modifier = context_modifier_for_tag(tag_value)

        for f in result.structural_findings:
            if is_test and not include_test_context and f.layer != 1:
                continue
            entries.append(_entry(
                rule_id=f.rule_id, severity=f.severity,
                confidence=f.confidence, file_path=f.file_path,
                line=f.line_number, message=f.message, cwe=f.cwe_id,
                context_tag=tag_value,
                modifier=1.0 if f.layer == 1 else modifier,
            ))
        for flow in result.taint_flows:
            if is_test and not include_test_context:
                continue
            sink = flow.sink_location
            src = getattr(flow.source_type, "value", flow.source_type)
            snk = getattr(flow.sink_type, "value", flow.sink_type)
            entries.append(_entry(
                rule_id=f"taint.{src}->{snk}",
                severity=str(flow.severity),
                confidence=float(flow.confidence),
                file_path=sink.file_path, line=sink.line_number,
                message=f"Tainted {src} data reaches {snk} sink",
                cwe=getattr(flow, "cwe_id", ""), context_tag=tag_value,
                modifier=modifier,
                # Preserve the epistemic "needs review" bucket for dynamic
                # constructs (eval/reflection/dynamic dispatch) instead of
                # re-bucketing it to "possible" by the confidence float.
                bucket_override=getattr(flow, "confidence_bucket", None),
            ))

    entries.sort(key=lambda e: (-e["priority"], e["file_path"], e["line"]))
    return outcome


def mark_incomplete_security_report(result: Any, outcome: DispatchScanOutcome) -> None:
    """Fail closed: incomplete CST must not look like score 100 / passing."""
    if not outcome.incomplete:
        return
    errors = getattr(result, "domain_errors", None)
    if errors is None:
        result.domain_errors = []
        errors = result.domain_errors
    errors.append({
        "domain": "cst_dispatch",
        "exception_type": "incomplete",
        "message": (
            f"CST analysis incomplete (parse_failed={outcome.parse_failed_files}, "
            f"truncated={outcome.truncated_files})"
        ),
    })
    if float(getattr(result, "security_score", 100) or 0) >= 100:
        result.security_score = 0.0
        if hasattr(result, "legacy_score"):
            result.legacy_score = 0.0
        if hasattr(result, "security_score_v2"):
            result.security_score_v2 = 0.0


def run_dispatch_scan(
    scan_path: Path,
    exclude_patterns: Sequence[str] = (),
    include_test_context: bool = False,
    test_context_enabled: bool = True,
    strict_scan_paths: Sequence[str] = (),
) -> List[Dict[str, Any]]:
    """
    Run the 3-layer DispatchEngine across every language it supports
    (Python, JS/TS, Java — see ``_DISPATCH_SUPPORTED_EXTENSIONS``).

    Returns display-ready finding dicts sorted by descending actionable
    priority. Test-context findings are dropped unless
    ``include_test_context`` is set (secrets/L1 findings always survive:
    a live credential in a test file is just as compromised).
    """
    return collect_dispatch_scan(
        scan_path,
        exclude_patterns=exclude_patterns,
        include_test_context=include_test_context,
        test_context_enabled=test_context_enabled,
        strict_scan_paths=strict_scan_paths,
    ).entries


def _entry(rule_id, severity, confidence, file_path, line, message, cwe,
           context_tag, modifier, bucket_override=None) -> Dict[str, Any]:
    # Plan 10 s4: apply the persisted calibration map (if configured via
    # HEIMDALL_CALIBRATION_MAP) to convert raw heuristic confidence into an
    # empirical probability BEFORE bucketing/priority. Identity by default.
    # Epistemic bucket overrides ("needs review" for dynamic constructs)
    # are preserved untouched -- calibration never mutes them.
    from Asgard.Heimdall.Security.normalization.calibration import (
        calibrate_confidence,
    )
    confidence = calibrate_confidence(confidence)
    bucket = bucket_override if bucket_override in BUCKET_LABELS else confidence_bucket(confidence)
    return {
        "rule_id": rule_id,
        "severity": str(severity).lower(),
        "confidence": BUCKET_LABELS[bucket],  # qualitative only, never raw %
        "priority": round(priority(severity, confidence, modifier), 1),
        "file_path": str(file_path),
        "line": int(line),
        "message": message,
        "cwe_id": cwe,
        "context": context_tag,
    }


def format_dispatch_text(entries: List[Dict[str, Any]],
                         limit: Optional[int] = 50) -> str:
    """Human-readable dispatch section, priority-ordered."""
    lines = [
        "",
        "-" * 70,
        "  DISPATCH ENGINE FINDINGS (priority order)",
        "-" * 70,
        "",
    ]
    if not entries:
        lines.append("  No dispatch-engine findings.")
    shown = entries if limit is None else entries[:limit]
    for e in shown:
        lines.append(
            f"  [{e['severity'].upper()}] [{e['confidence']}] "
            f"(priority {e['priority']:g}) {e['rule_id']}"
        )
        lines.append(f"    {e['file_path']}:{e['line']}  {e['message']}")
        if e.get("cwe_id"):
            lines.append(f"    {e['cwe_id']}")
        lines.append("")
    if limit is not None and len(entries) > limit:
        lines.append(f"  ... and {len(entries) - limit} lower-priority findings.")
    return "\n".join(lines)
