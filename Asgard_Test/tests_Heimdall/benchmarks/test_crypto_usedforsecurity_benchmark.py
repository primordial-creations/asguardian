"""Benchmark corpus for the crypto `usedforsecurity=False` context check
(plan 07.4). Vulnerable/safe pairs: MD5/SHA1 used with and without the
stdlib's own security-intent escape hatch.

Uses ``tempfile.TemporaryDirectory`` rather than pytest's ``tmp_path``:
the scanner's default ``exclude_patterns`` filters out any path segment
matching ``test_*`` (deliberately, so it doesn't flag its own fixtures'
intentionally-vulnerable code) -- pytest's per-test ``tmp_path`` dirs are
named after the test function and would trip that same filter, so the
existing crypto test suite already uses randomly-named temp dirs.
"""
import tempfile
from pathlib import Path

from Asgard.Heimdall.Security.services.cryptographic_validation_service import (
    CryptographicValidationService,
)


def _scan(code: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "app.py").write_text(code)
        return CryptographicValidationService().scan(tmp_path)


def test_md5_without_usedforsecurity_is_flagged():
    report = _scan("import hashlib\nh = hashlib.md5(password).hexdigest()\n")
    assert any(f.algorithm == "MD5" for f in report.findings)


def test_md5_with_usedforsecurity_false_is_not_flagged():
    report = _scan(
        "import hashlib\nh = hashlib.md5(blob, usedforsecurity=False).hexdigest()\n",
    )
    assert not any(f.algorithm == "MD5" for f in report.findings)


def test_sha1_with_usedforsecurity_false_is_not_flagged():
    report = _scan(
        "import hashlib\nh = hashlib.sha1(blob, usedforsecurity=False).hexdigest()\n",
    )
    assert not any(f.algorithm == "SHA-1" for f in report.findings)


def test_sha1_without_usedforsecurity_is_still_flagged():
    report = _scan("import hashlib\nh = hashlib.sha1(token).hexdigest()\n")
    assert any(f.algorithm == "SHA-1" for f in report.findings)


def test_usedforsecurity_true_is_still_flagged():
    # Explicit True should NOT suppress -- only an explicit False does.
    report = _scan(
        "import hashlib\nh = hashlib.md5(password, usedforsecurity=True).hexdigest()\n",
    )
    assert any(f.algorithm == "MD5" for f in report.findings)


# BLOCKER-2 regression (adversarial review): a successful AST parse that
# finds no `usedforsecurity=False` kwarg used to fall through to a
# textual regex fallback that matched inside comments.
def test_usedforsecurity_false_in_comment_is_still_flagged():
    report = _scan(
        "import hashlib\nh = hashlib.md5(password)  # usedforsecurity=False\n",
    )
    assert any(f.algorithm == "MD5" for f in report.findings), (
        "a comment is not a kwarg -- must not suppress the real MD5 finding"
    )


# BLOCKER-3 regression (adversarial review): the AST loop used to return
# True as soon as ANY Call in the parsed window had `usedforsecurity=False`,
# not necessarily the matched hash call itself.
def test_usedforsecurity_false_on_unrelated_adjacent_call_is_still_flagged():
    report = _scan(
        "import hashlib\n"
        "h = hashlib.md5(pw).hexdigest()\n"
        "other_call(y, usedforsecurity=False)\n"
    )
    assert any(f.algorithm == "MD5" for f in report.findings), (
        "usedforsecurity=False on a different, unrelated call must not "
        "suppress the MD5 finding"
    )
