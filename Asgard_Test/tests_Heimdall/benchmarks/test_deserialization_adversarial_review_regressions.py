"""Regression tests for the adversarial-review findings on the plan 07.5
deserialization provenance classifier (BLOCKER-1, BLOCKER-2, MAJOR-3) and
the plan 07.6 timing-safe-compare secret lexicon (MAJOR-4).

Each test reproduces the reviewer's exact reported snippet. Prior to the
fix, the scanner used a fixed 15-line textual backward window for
provenance, which was gameable by padding (BLOCKER-1), missed sys.argv /
unconditionally trusted `open(...)` (BLOCKER-2), and produced false
positives from unrelated nearby markers with zero actual dataflow
(MAJOR-3). The fix replaces the textual window with real AST
intraprocedural variable-origin tracking
(`Deserialization/services/_deserialization_ast_analysis.py`).
"""
from pathlib import Path

from Asgard.Heimdall.Security.Auth.models.auth_models import AuthConfig, AuthFindingType
from Asgard.Heimdall.Security.Auth.services.timing_safe_compare import TimingSafeCompareChecker
from Asgard.Heimdall.Security.Deserialization.models.deserialization_models import (
    DeserializationScanConfig,
)
from Asgard.Heimdall.Security.Deserialization.services.deserialization_scanner import (
    DeserializationScanner,
)


def _scan(tmp_path: Path, code: str, filename: str = "app.py"):
    (tmp_path / filename).write_text(code)
    return DeserializationScanner().scan(DeserializationScanConfig(scan_path=tmp_path))


def test_blocker1_padding_beyond_old_window_does_not_launder_rce(tmp_path):
    """BLOCKER-1: `data = request.data` followed by >15 no-op lines before
    `pickle.loads(data)` used to fall outside the old 15-line textual
    window and get laundered to LOW/hotspot. Real dataflow (AST-based)
    must still resolve this as untrusted/CRITICAL regardless of distance."""
    padding = "\n".join(f"    noop_{i} = {i}" for i in range(20))
    code = f"""
import pickle
from flask import request

def handler():
    data = request.data
{padding}
    return pickle.loads(data)
"""
    report = _scan(tmp_path, code)
    assert report.total_findings == 1
    f = report.findings[0]
    assert f.provenance == "untrusted"
    assert f.is_hotspot is False
    assert f.mechanism_id == "deserialization.untrusted"
    assert f.severity == "CRITICAL"


def test_blocker2_sys_argv_through_open_is_untrusted(tmp_path):
    """BLOCKER-2: `argfile = sys.argv[1]; yaml.load(open(argfile).read())`
    used to be misclassified internal because `open(...)` was an
    unconditional internal marker. sys.argv is a real untrusted source
    and open() on a tainted path must not be trusted by default."""
    code = """
import sys
import yaml

def main():
    argfile = sys.argv[1]
    return yaml.load(open(argfile).read())
"""
    report = _scan(tmp_path, code)
    assert report.total_findings == 1
    f = report.findings[0]
    assert f.provenance == "untrusted"
    assert f.is_hotspot is False
    assert f.severity == "CRITICAL"


def test_major3_unrelated_marker_does_not_taint_unrelated_sink(tmp_path):
    """MAJOR-3: an unrelated `request.args['id']` sitting textually near a
    pickle.loads() call on a genuinely internal constant must NOT be
    classified untrusted -- there's zero dataflow between them."""
    code = """
import pickle
from flask import request

LOCAL_TRUSTED_BYTES = b"internal-only-payload"

def handler():
    user_id = request.args['id']
    log_access(user_id)
    local_payload = LOCAL_TRUSTED_BYTES
    return pickle.loads(local_payload)
"""
    report = _scan(tmp_path, code)
    assert report.total_findings == 1
    f = report.findings[0]
    assert f.provenance == "internal"
    assert f.is_hotspot is True
    assert f.severity != "CRITICAL"
    assert f.mechanism_id == "deserialization.hotspot"


def test_major4_pwd_hash_comparison_is_flagged(tmp_path):
    """MAJOR-4: `if pwd_hash == stored_hash:` was missed by the old narrow
    secret lexicon (no `pwd`/`hash` terms)."""
    (tmp_path / "auth.py").write_text(
        "def check(pwd_hash, stored_hash):\n"
        "    if pwd_hash == stored_hash:\n"
        "        return True\n"
        "    return False\n"
    )
    report = TimingSafeCompareChecker().scan(
        tmp_path, AuthConfig(scan_path=tmp_path, exclude_patterns=[])
    )
    assert report.total_issues == 1
    finding = report.findings[0]
    assert finding.finding_type == AuthFindingType.TIMING_UNSAFE_COMPARE.value or (
        finding.finding_type == AuthFindingType.TIMING_UNSAFE_COMPARE
    )


def test_major4_non_secret_comparisons_remain_safe(tmp_path):
    """Keep the existing FP exclusions intact after widening the lexicon:
    status codes and non-secret identity checks must not be flagged."""
    (tmp_path / "app.py").write_text(
        "def handle(status, name):\n"
        "    if status == 200:\n"
        "        pass\n"
        "    if name == 'admin':\n"
        "        pass\n"
    )
    report = TimingSafeCompareChecker().scan(
        tmp_path, AuthConfig(scan_path=tmp_path, exclude_patterns=[])
    )
    assert report.total_issues == 0
