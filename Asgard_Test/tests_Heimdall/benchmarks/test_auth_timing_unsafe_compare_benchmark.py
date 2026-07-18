"""Benchmark corpus for the non-constant-time secret comparison check (plan 07.6b)."""
from pathlib import Path

from Asgard.Heimdall.Security.Auth.models.auth_models import AuthConfig, AuthFindingType
from Asgard.Heimdall.Security.Auth.services.timing_safe_compare import TimingSafeCompareChecker


def _scan(tmp_path: Path, code: str):
    (tmp_path / "app.py").write_text(code)
    # pytest's tmp_path directories are named "test_<nodeid>..." which the
    # scanner's default GAIA-style "test_*"/"*Test" exclude globs match
    # against ancestor path segments (a pre-existing scan_directory_for_
    # security quirk, out of scope here) -- disable excludes for this
    # isolated single-file fixture scan.
    return TimingSafeCompareChecker().scan(tmp_path, AuthConfig(scan_path=tmp_path, exclude_patterns=[]))


def test_password_hash_equality_is_flagged(tmp_path):
    report = _scan(tmp_path, """
def check(user_password_hash, submitted_hash):
    if user_password_hash == submitted_hash:
        return True
    return False
""")
    hits = [f for f in report.findings if f.finding_type == AuthFindingType.TIMING_UNSAFE_COMPARE.value]
    assert hits
    assert hits[0].mechanism_id == "auth.timing_unsafe_compare"
    assert hits[0].cwe_id == "CWE-208"


def test_hmac_compare_digest_is_not_flagged(tmp_path):
    report = _scan(tmp_path, """
import hmac

def check(expected_sig, provided_sig):
    return hmac.compare_digest(expected_sig, provided_sig)
""")
    assert report.total_issues == 0


def test_unrelated_equality_is_not_flagged(tmp_path):
    report = _scan(tmp_path, """
def check(role):
    if role == "admin":
        return True
    return False
""")
    assert report.total_issues == 0


def test_none_check_on_token_is_not_flagged(tmp_path):
    # Existence check, not a value comparison -- excluded to cut an FP class.
    report = _scan(tmp_path, """
def check(auth_token):
    if auth_token == None:
        return False
""")
    assert report.total_issues == 0


def test_api_key_comparison_is_flagged(tmp_path):
    report = _scan(tmp_path, """
def check(request, stored_api_key):
    if request.headers.get("X-Api-Key") == stored_api_key:
        return True
""")
    hits = [f for f in report.findings if f.finding_type == AuthFindingType.TIMING_UNSAFE_COMPARE.value]
    assert hits
