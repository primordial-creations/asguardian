"""
L6 Industry Benchmark Tests for Heimdall Security Scanners.

Validates scanner quality against OWASP CWE fixture corpus:
- True Positive Rate (TPR) >= 70%  (bad/ fixtures must be detected)
- False Positive Rate (FPR) <= 30% (safe/ fixtures must NOT be flagged)
- Throughput >= 2000 lines/sec (Bandit baseline)
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

import pytest

# Ensure project root on path
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "owasp"

# ---------------------------------------------------------------------------
# Import scanner classes + config models
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.InputValidation.services.input_validation_scanner import (
    InputValidationScanner,
)
from Asgard.Heimdall.Security.InputValidation.models.input_validation_models import (
    InputValidationScanConfig,
)
from Asgard.Heimdall.Security.PathTraversal.services.path_traversal_scanner import (
    PathTraversalScanner,
)
from Asgard.Heimdall.Security.PathTraversal.models.path_traversal_models import (
    PathTraversalScanConfig,
)
from Asgard.Heimdall.Security.SensitiveData.services.sensitive_data_scanner import (
    SensitiveDataScanner,
)
from Asgard.Heimdall.Security.SensitiveData.models.sensitive_data_models import (
    SensitiveDataScanConfig,
)
from Asgard.Heimdall.Security.Deserialization.services.deserialization_scanner import (
    DeserializationScanner,
)
from Asgard.Heimdall.Security.Deserialization.models.deserialization_models import (
    DeserializationScanConfig,
)
from Asgard.Heimdall.Security.ReDoS.services.redos_scanner import ReDoSScanner
from Asgard.Heimdall.Security.ReDoS.models.redos_models import ReDoSScanConfig
from Asgard.Heimdall.Security.services.cryptographic_validation_service import (
    CryptographicValidationService,
)
from Asgard.Heimdall.Security.models.security_models import SecurityScanConfig

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
TPR_THRESHOLD = 0.70
FPR_THRESHOLD = 0.30
THROUGHPUT_MIN = 2000  # lines per second


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _copy_fixtures(src_dir: Path, tmp_path: Path) -> list[Path]:
    """Copy fixture files into tmp_path, return list of copied paths."""
    copied = []
    for src in src_dir.iterdir():
        if src.is_file():
            dst = tmp_path / src.name
            shutil.copy2(src, dst)
            copied.append(dst)
    return copied


def _run_input_validation(scan_dir: Path) -> int:
    scanner = InputValidationScanner()
    config = InputValidationScanConfig(scan_path=scan_dir)
    report = scanner.scan(config)
    return report.total_findings


def _run_path_traversal(scan_dir: Path) -> int:
    scanner = PathTraversalScanner()
    config = PathTraversalScanConfig(scan_path=scan_dir)
    report = scanner.scan(config)
    return report.total_findings


def _run_sensitive_data(scan_dir: Path) -> int:
    scanner = SensitiveDataScanner()
    config = SensitiveDataScanConfig(scan_path=scan_dir)
    report = scanner.scan(config)
    return report.total_findings


def _run_deserialization(scan_dir: Path) -> int:
    scanner = DeserializationScanner()
    config = DeserializationScanConfig(scan_path=scan_dir)
    report = scanner.scan(config)
    return report.total_findings


def _run_redos(scan_dir: Path) -> int:
    scanner = ReDoSScanner()
    config = ReDoSScanConfig(scan_path=scan_dir)
    report = scanner.scan(config)
    return report.total_findings


def _run_crypto(scan_dir: Path) -> int:
    # CryptographicValidationService has default exclude_patterns that include
    # 'test_*' (applied via fnmatch on every path segment).  pytest names
    # tmp_path directories after the test function (e.g. test_tpr_...), so
    # those paths are silently excluded.  Use a neutral tempdir name instead.
    with tempfile.TemporaryDirectory(prefix="heimdall_crypto_") as neutral_dir:
        neutral = Path(neutral_dir)
        for f in scan_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, neutral / f.name)
        svc = CryptographicValidationService(
            config=SecurityScanConfig(scan_path=neutral)
        )
        report = svc.scan(neutral)
        return len(report.findings)


# ===========================================================================
# CWE-89: SQL Injection  (InputValidationScanner — database_queries category)
# ===========================================================================

class TestCWE89SQLi:
    FIXTURE = _FIXTURES_ROOT / "CWE89_SQLi"

    def test_tpr_exceeds_70pct(self, tmp_path):
        bad_dir = self.FIXTURE / "bad"
        copied = _copy_fixtures(bad_dir, tmp_path)
        assert copied, "No bad fixtures found"
        findings = _run_input_validation(tmp_path)
        tpr = findings / len(copied)
        assert tpr >= TPR_THRESHOLD, (
            f"CWE-89 SQLi TPR {tpr:.2%} < {TPR_THRESHOLD:.0%} "
            f"(findings={findings}, files={len(copied)})"
        )

    def test_fpr_below_30pct(self, tmp_path):
        safe_dir = self.FIXTURE / "safe"
        copied = _copy_fixtures(safe_dir, tmp_path)
        assert copied, "No safe fixtures found"
        findings = _run_input_validation(tmp_path)
        fpr = findings / len(copied)
        assert fpr <= FPR_THRESHOLD, (
            f"CWE-89 SQLi FPR {fpr:.2%} > {FPR_THRESHOLD:.0%} "
            f"(false_positives={findings}, files={len(copied)})"
        )


# ===========================================================================
# CWE-22: Path Traversal  (PathTraversalScanner)
# ===========================================================================

class TestCWE22PathTraversal:
    FIXTURE = _FIXTURES_ROOT / "CWE22_PathTraversal"

    def test_tpr_exceeds_70pct(self, tmp_path):
        bad_dir = self.FIXTURE / "bad"
        copied = _copy_fixtures(bad_dir, tmp_path)
        assert copied, "No bad fixtures found"
        findings = _run_path_traversal(tmp_path)
        tpr = findings / len(copied)
        assert tpr >= TPR_THRESHOLD, (
            f"CWE-22 PathTraversal TPR {tpr:.2%} < {TPR_THRESHOLD:.0%} "
            f"(findings={findings}, files={len(copied)})"
        )

    def test_fpr_below_30pct(self, tmp_path):
        safe_dir = self.FIXTURE / "safe"
        copied = _copy_fixtures(safe_dir, tmp_path)
        assert copied, "No safe fixtures found"
        findings = _run_path_traversal(tmp_path)
        fpr = findings / len(copied)
        assert fpr <= FPR_THRESHOLD, (
            f"CWE-22 PathTraversal FPR {fpr:.2%} > {FPR_THRESHOLD:.0%} "
            f"(false_positives={findings}, files={len(copied)})"
        )


# ===========================================================================
# CWE-79: XSS / SSTI  (InputValidationScanner — template_injection category)
# ===========================================================================

class TestCWE79XSS:
    FIXTURE = _FIXTURES_ROOT / "CWE79_XSS"

    def test_tpr_exceeds_70pct(self, tmp_path):
        bad_dir = self.FIXTURE / "bad"
        copied = _copy_fixtures(bad_dir, tmp_path)
        assert copied, "No bad fixtures found"
        findings = _run_input_validation(tmp_path)
        tpr = findings / len(copied)
        assert tpr >= TPR_THRESHOLD, (
            f"CWE-79 XSS/SSTI TPR {tpr:.2%} < {TPR_THRESHOLD:.0%} "
            f"(findings={findings}, files={len(copied)})"
        )

    def test_fpr_below_30pct(self, tmp_path):
        safe_dir = self.FIXTURE / "safe"
        copied = _copy_fixtures(safe_dir, tmp_path)
        assert copied, "No safe fixtures found"
        findings = _run_input_validation(tmp_path)
        fpr = findings / len(copied)
        assert fpr <= FPR_THRESHOLD, (
            f"CWE-79 XSS/SSTI FPR {fpr:.2%} > {FPR_THRESHOLD:.0%} "
            f"(false_positives={findings}, files={len(copied)})"
        )


# ===========================================================================
# CWE-611: XXE / SSRF  (InputValidationScanner — url_operations category)
# ===========================================================================

class TestCWE611XXE:
    FIXTURE = _FIXTURES_ROOT / "CWE611_XXE"

    def test_tpr_exceeds_70pct(self, tmp_path):
        bad_dir = self.FIXTURE / "bad"
        copied = _copy_fixtures(bad_dir, tmp_path)
        assert copied, "No bad fixtures found"
        findings = _run_input_validation(tmp_path)
        tpr = findings / len(copied)
        assert tpr >= TPR_THRESHOLD, (
            f"CWE-611 SSRF TPR {tpr:.2%} < {TPR_THRESHOLD:.0%} "
            f"(findings={findings}, files={len(copied)})"
        )

    def test_fpr_below_30pct(self, tmp_path):
        safe_dir = self.FIXTURE / "safe"
        copied = _copy_fixtures(safe_dir, tmp_path)
        assert copied, "No safe fixtures found"
        findings = _run_input_validation(tmp_path)
        fpr = findings / len(copied)
        assert fpr <= FPR_THRESHOLD, (
            f"CWE-611 SSRF FPR {fpr:.2%} > {FPR_THRESHOLD:.0%} "
            f"(false_positives={findings}, files={len(copied)})"
        )


# ===========================================================================
# CWE-327: Weak Cryptography  (CryptographicValidationService)
# ===========================================================================

class TestCWE327WeakCrypto:
    FIXTURE = _FIXTURES_ROOT / "CWE327_WeakCrypto"

    def test_tpr_exceeds_70pct(self, tmp_path):
        bad_dir = self.FIXTURE / "bad"
        copied = _copy_fixtures(bad_dir, tmp_path)
        assert copied, "No bad fixtures found"
        findings = _run_crypto(tmp_path)
        tpr = findings / len(copied)
        assert tpr >= TPR_THRESHOLD, (
            f"CWE-327 WeakCrypto TPR {tpr:.2%} < {TPR_THRESHOLD:.0%} "
            f"(findings={findings}, files={len(copied)})"
        )

    def test_fpr_below_30pct(self, tmp_path):
        safe_dir = self.FIXTURE / "safe"
        copied = _copy_fixtures(safe_dir, tmp_path)
        assert copied, "No safe fixtures found"
        findings = _run_crypto(tmp_path)
        fpr = findings / len(copied)
        assert fpr <= FPR_THRESHOLD, (
            f"CWE-327 WeakCrypto FPR {fpr:.2%} > {FPR_THRESHOLD:.0%} "
            f"(false_positives={findings}, files={len(copied)})"
        )


# ===========================================================================
# CWE-798: Hardcoded Credentials  (SensitiveDataScanner)
# ===========================================================================

class TestCWE798HardcodedCreds:
    FIXTURE = _FIXTURES_ROOT / "CWE798_HardcodedCreds"

    def test_tpr_exceeds_70pct(self, tmp_path):
        bad_dir = self.FIXTURE / "bad"
        copied = _copy_fixtures(bad_dir, tmp_path)
        assert copied, "No bad fixtures found"
        findings = _run_sensitive_data(tmp_path)
        tpr = findings / len(copied)
        assert tpr >= TPR_THRESHOLD, (
            f"CWE-798 HardcodedCreds TPR {tpr:.2%} < {TPR_THRESHOLD:.0%} "
            f"(findings={findings}, files={len(copied)})"
        )

    def test_fpr_below_30pct(self, tmp_path):
        safe_dir = self.FIXTURE / "safe"
        copied = _copy_fixtures(safe_dir, tmp_path)
        assert copied, "No safe fixtures found"
        findings = _run_sensitive_data(tmp_path)
        fpr = findings / len(copied)
        assert fpr <= FPR_THRESHOLD, (
            f"CWE-798 HardcodedCreds FPR {fpr:.2%} > {FPR_THRESHOLD:.0%} "
            f"(false_positives={findings}, files={len(copied)})"
        )


# ===========================================================================
# CWE-502: Insecure Deserialization  (DeserializationScanner)
# ===========================================================================

class TestCWE502Deserialization:
    FIXTURE = _FIXTURES_ROOT / "CWE502_Deserialization"

    def test_tpr_exceeds_70pct(self, tmp_path):
        bad_dir = self.FIXTURE / "bad"
        copied = _copy_fixtures(bad_dir, tmp_path)
        assert copied, "No bad fixtures found"
        findings = _run_deserialization(tmp_path)
        tpr = findings / len(copied)
        assert tpr >= TPR_THRESHOLD, (
            f"CWE-502 Deserialization TPR {tpr:.2%} < {TPR_THRESHOLD:.0%} "
            f"(findings={findings}, files={len(copied)})"
        )

    def test_fpr_below_30pct(self, tmp_path):
        safe_dir = self.FIXTURE / "safe"
        copied = _copy_fixtures(safe_dir, tmp_path)
        assert copied, "No safe fixtures found"
        findings = _run_deserialization(tmp_path)
        fpr = findings / len(copied)
        assert fpr <= FPR_THRESHOLD, (
            f"CWE-502 Deserialization FPR {fpr:.2%} > {FPR_THRESHOLD:.0%} "
            f"(false_positives={findings}, files={len(copied)})"
        )


# ===========================================================================
# CWE-400: ReDoS  (ReDoSScanner)
# ===========================================================================

class TestCWE400ReDoS:
    FIXTURE = _FIXTURES_ROOT / "CWE400_ReDoS"

    def test_tpr_exceeds_70pct(self, tmp_path):
        bad_dir = self.FIXTURE / "bad"
        copied = _copy_fixtures(bad_dir, tmp_path)
        assert copied, "No bad fixtures found"
        findings = _run_redos(tmp_path)
        tpr = findings / len(copied)
        assert tpr >= TPR_THRESHOLD, (
            f"CWE-400 ReDoS TPR {tpr:.2%} < {TPR_THRESHOLD:.0%} "
            f"(findings={findings}, files={len(copied)})"
        )

    def test_fpr_below_30pct(self, tmp_path):
        safe_dir = self.FIXTURE / "safe"
        copied = _copy_fixtures(safe_dir, tmp_path)
        assert copied, "No safe fixtures found"
        findings = _run_redos(tmp_path)
        fpr = findings / len(copied)
        assert fpr <= FPR_THRESHOLD, (
            f"CWE-400 ReDoS FPR {fpr:.2%} > {FPR_THRESHOLD:.0%} "
            f"(false_positives={findings}, files={len(copied)})"
        )


# ===========================================================================
# Throughput benchmarks — each scanner >= 2000 lines/sec
# ===========================================================================

def _make_synthetic_py(tmp_path: Path, lines: int = 10_000) -> Path:
    """Generate a large .py file with benign code."""
    out = tmp_path / "synthetic_bench.py"
    block = [
        "def func_{i}(x, y):",
        "    result = x + y",
        "    data = list(range(100))",
        "    return result",
        "",
    ]
    content_lines = []
    idx = 0
    while len(content_lines) < lines:
        for ln in block:
            content_lines.append(ln.replace("{i}", str(idx)))
        idx += 1
    out.write_text("\n".join(content_lines[:lines]))
    return out


def _make_synthetic_js(tmp_path: Path, lines: int = 10_000) -> Path:
    out = tmp_path / "synthetic_bench.js"
    block = [
        "function func_{i}(x, y) {{",
        "    const result = x + y;",
        "    const data = Array.from({{length: 100}}, (_, i) => i);",
        "    return result;",
        "}}",
        "",
    ]
    content_lines = []
    idx = 0
    while len(content_lines) < lines:
        for ln in block:
            content_lines.append(ln.replace("{i}", str(idx)))
        idx += 1
    out.write_text("\n".join(content_lines[:lines]))
    return out


class TestThroughput:

    def test_input_validation_throughput(self, tmp_path):
        f = _make_synthetic_py(tmp_path)
        line_count = len(f.read_text().splitlines())
        scanner = InputValidationScanner()
        config = InputValidationScanConfig(scan_path=tmp_path)
        t0 = time.perf_counter()
        scanner.scan(config)
        elapsed = time.perf_counter() - t0
        lps = line_count / elapsed
        assert lps >= THROUGHPUT_MIN, (
            f"InputValidationScanner throughput {lps:.0f} lines/sec < {THROUGHPUT_MIN}"
        )

    def test_path_traversal_throughput(self, tmp_path):
        f = _make_synthetic_py(tmp_path)
        line_count = len(f.read_text().splitlines())
        scanner = PathTraversalScanner()
        config = PathTraversalScanConfig(scan_path=tmp_path)
        t0 = time.perf_counter()
        scanner.scan(config)
        elapsed = time.perf_counter() - t0
        lps = line_count / elapsed
        assert lps >= THROUGHPUT_MIN, (
            f"PathTraversalScanner throughput {lps:.0f} lines/sec < {THROUGHPUT_MIN}"
        )

    def test_sensitive_data_throughput(self, tmp_path):
        f = _make_synthetic_py(tmp_path)
        line_count = len(f.read_text().splitlines())
        scanner = SensitiveDataScanner()
        config = SensitiveDataScanConfig(scan_path=tmp_path)
        t0 = time.perf_counter()
        scanner.scan(config)
        elapsed = time.perf_counter() - t0
        lps = line_count / elapsed
        assert lps >= THROUGHPUT_MIN, (
            f"SensitiveDataScanner throughput {lps:.0f} lines/sec < {THROUGHPUT_MIN}"
        )

    def test_deserialization_throughput(self, tmp_path):
        f = _make_synthetic_py(tmp_path)
        line_count = len(f.read_text().splitlines())
        scanner = DeserializationScanner()
        config = DeserializationScanConfig(scan_path=tmp_path)
        t0 = time.perf_counter()
        scanner.scan(config)
        elapsed = time.perf_counter() - t0
        lps = line_count / elapsed
        assert lps >= THROUGHPUT_MIN, (
            f"DeserializationScanner throughput {lps:.0f} lines/sec < {THROUGHPUT_MIN}"
        )

    def test_redos_throughput(self, tmp_path):
        f = _make_synthetic_py(tmp_path)
        line_count = len(f.read_text().splitlines())
        scanner = ReDoSScanner()
        config = ReDoSScanConfig(scan_path=tmp_path)
        t0 = time.perf_counter()
        scanner.scan(config)
        elapsed = time.perf_counter() - t0
        lps = line_count / elapsed
        assert lps >= THROUGHPUT_MIN, (
            f"ReDoSScanner throughput {lps:.0f} lines/sec < {THROUGHPUT_MIN}"
        )

    def test_crypto_throughput(self, tmp_path):
        # Use a neutral tempdir to avoid the 'test_*' exclude pattern.
        with tempfile.TemporaryDirectory(prefix="heimdall_crypto_bench_") as neutral_dir:
            scan_dir = Path(neutral_dir)
            f = _make_synthetic_py(scan_dir)
            line_count = len(f.read_text().splitlines())
            svc = CryptographicValidationService(
                config=SecurityScanConfig(scan_path=scan_dir)
            )
            t0 = time.perf_counter()
            svc.scan(scan_dir)
            elapsed = time.perf_counter() - t0
            lps = line_count / elapsed
            assert lps >= THROUGHPUT_MIN, (
                f"CryptographicValidationService throughput {lps:.0f} lines/sec < {THROUGHPUT_MIN}"
            )
