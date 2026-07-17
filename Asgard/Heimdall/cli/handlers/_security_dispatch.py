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
from typing import Any, Dict, List, Optional, Sequence

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

#: Display labels for confidence buckets (qualitative only).
BUCKET_LABELS = {
    "certain": "Certain",
    "probable": "Probable",
    "possible": "Possible",
    "unlikely": "Unlikely",
}


def load_heimdall_yml(scan_path: Path) -> Dict[str, Any]:
    """
    Read `.heimdall.yml` from the scan path (zero-config: absent file is
    simply empty config). Recognized keys:
        test_context_enabled: bool (default True)
        strict_scan_paths: list of regexes forced to production context
    """
    config_file = Path(scan_path) / ".heimdall.yml"
    if not config_file.is_file():
        return {}
    try:
        import yaml
        data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    except Exception:
        return {}
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
        yield scan_path
        return
    for path in sorted(scan_path.rglob("*")):
        if not path.is_file():
            continue
        if suffixes and path.suffix not in suffixes:
            continue
        if not suffixes and path.suffix not in _CODE_EXTENSIONS:
            continue
        rel = str(path.relative_to(scan_path))
        if _is_excluded(rel, exclude_patterns):
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


def run_dispatch_scan(
    scan_path: Path,
    exclude_patterns: Sequence[str] = (),
    include_test_context: bool = False,
    test_context_enabled: bool = True,
    strict_scan_paths: Sequence[str] = (),
) -> List[Dict[str, Any]]:
    """
    Run the 3-layer DispatchEngine across Python files.

    Returns display-ready finding dicts sorted by descending actionable
    priority. Test-context findings are dropped unless
    ``include_test_context`` is set (secrets/L1 findings always survive:
    a live credential in a test file is just as compromised).
    """
    engine = DispatchEngine(
        is_test_context=None if test_context_enabled else False,
        strict_scan_paths=strict_scan_paths,
    )
    entries: List[Dict[str, Any]] = []

    for path in _iter_code_files(scan_path, exclude_patterns,
                                 suffixes={".py"}):
        result = engine.scan_file(path)
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
            ))

    entries.sort(key=lambda e: (-e["priority"], e["file_path"], e["line"]))
    return entries


def _entry(rule_id, severity, confidence, file_path, line, message, cwe,
           context_tag, modifier) -> Dict[str, Any]:
    bucket = confidence_bucket(confidence)
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
