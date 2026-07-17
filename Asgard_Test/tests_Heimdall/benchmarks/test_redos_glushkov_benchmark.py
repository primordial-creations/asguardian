"""Benchmark corpus for the ReDoS Glushkov-NFA analysis (plan 07.2).

Vulnerable/safe pattern pairs, matched against known catastrophic-
backtracking shapes and their commonly-confused safe look-alikes (the
"regex traps" a naive nested-quantifier text regex used to misjudge).
Precision/recall targets per plan: >85% / >80% on statically resolvable
patterns; measured here as "zero misses among the canonical corpus"
since the corpus is small and hand-curated rather than mined.
"""
import time

import pytest

from Asgard.Heimdall.Security.ReDoS.services._glushkov_analysis import analyze_pattern
from Asgard.Heimdall.Security.ReDoS.models.redos_models import ReDoSScanConfig, ReDoSSeverity
from Asgard.Heimdall.Security.ReDoS.services.redos_scanner import ReDoSScanner

# (pattern, expected verdict) -- vulnerable shapes must be "eda"/"ida";
# safe look-alikes (the old regex heuristic's false-positive traps) must
# come back "safe".
VULNERABLE = [
    (r"(a+)+", "eda"),                       # classic nested-quantifier EDA
    (r"(a|a)*", "eda"),                       # overlapping-alternation EDA
    (r"([a-zA-Z]+)*$", "eda"),                # CVE-style trailing-anchor EDA
    (r"(\d+)*$", "eda"),                      # numeric nested-quantifier EDA
    (r"(.*)*$", "eda"),                       # wildcard nested-quantifier EDA
    (r"\d+\d+", "ida"),                       # chained same-class repeats (IDA)
    (r"[a-z]+[a-z]+!", "ida"),                # chained overlapping char classes
]

SAFE = [
    r"^[a-zA-Z0-9_]+$",                       # single bounded repeat -- old regex misfired on some variants
    r"^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$",       # email-shaped pattern, mutually exclusive components
    r"foo\d{3,5}bar",                          # bounded quantifier, no nesting
    r"\bhello\b",                              # word-boundary anchors only
    r"(a+)(b+)",                               # two DISJOINT repeats in sequence, not chained on same class
    r"^https?://",                             # alternation without repeated overlap
    r"[^/]+/[^/]+",                            # disjoint negated classes split by literal
]


@pytest.mark.parametrize("pattern,expected", VULNERABLE, ids=[p for p, _ in VULNERABLE])
def test_vulnerable_patterns_flagged(pattern, expected):
    result = analyze_pattern(pattern)
    assert result.verdict == expected, f"{pattern!r}: expected {expected}, got {result.verdict} ({result.detail})"


@pytest.mark.parametrize("pattern", SAFE, ids=SAFE)
def test_safe_patterns_not_flagged(pattern):
    result = analyze_pattern(pattern)
    assert result.verdict == "safe", f"{pattern!r}: expected safe, got {result.verdict} ({result.detail})"


def test_backreference_is_unsupported_not_falsely_safe():
    result = analyze_pattern(r"(a)\1+")
    assert result.verdict == "unsupported"


def test_analysis_stays_within_time_budget():
    start = time.monotonic()
    for pattern, _ in VULNERABLE:
        analyze_pattern(pattern)
    for pattern in SAFE:
        analyze_pattern(pattern)
    elapsed = time.monotonic() - start
    assert elapsed < 0.5, "corpus analysis should be well within the 25ms/regex budget in aggregate"


def test_end_to_end_scanner_flags_vulnerable_file(tmp_path):
    (tmp_path / "vuln.py").write_text(
        "import re\n"
        "PATTERN = re.compile(r'(a+)+')\n"
    )
    report = ReDoSScanner().scan(ReDoSScanConfig(scan_path=tmp_path))
    assert report.total_findings == 1
    finding = report.findings[0]
    assert finding.severity == ReDoSSeverity.HIGH
    assert finding.mechanism_id == "redos.eda"
    assert finding.confidence_bucket in ("certain", "probable")


def test_end_to_end_scanner_silent_on_safe_file(tmp_path):
    (tmp_path / "safe.py").write_text(
        "import re\n"
        "PATTERN = re.compile(r'^[a-zA-Z0-9_]+$')\n"
    )
    report = ReDoSScanner().scan(ReDoSScanConfig(scan_path=tmp_path))
    assert report.total_findings == 0


def test_end_to_end_scanner_length_guard_suppresses_ida(tmp_path):
    (tmp_path / "guarded.py").write_text(
        "import re\n"
        "def check(s):\n"
        "    if len(s) < 200:\n"
        "        return re.match(r'\\d+\\d+', s)\n"
    )
    report = ReDoSScanner().scan(ReDoSScanConfig(scan_path=tmp_path))
    assert report.total_findings == 0
