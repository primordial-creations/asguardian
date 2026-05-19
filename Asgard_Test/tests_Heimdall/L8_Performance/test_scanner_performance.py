"""
L8 Performance Tests — Scanner Throughput Benchmarks.

Uses pytest-benchmark to measure per-scanner execution time on a synthetic
code file.  Tests are not expected to meet any specific time threshold; they
simply must execute without error.
"""

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# ReDoS
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.ReDoS.services.redos_scanner import ReDoSScanner
from Asgard.Heimdall.Security.ReDoS.models.redos_models import ReDoSScanConfig

# ---------------------------------------------------------------------------
# API Security
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.API.services.api_scanner import APISecurityScanner
from Asgard.Heimdall.Security.API.models.api_models import APIScanConfig

# ---------------------------------------------------------------------------
# Backdoor
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Backdoor.services.backdoor_detector import BackdoorDetector
from Asgard.Heimdall.Security.Backdoor.models.backdoor_models import BackdoorScanConfig

# ---------------------------------------------------------------------------
# Malware
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Malware.services.malware_scanner import MalwareScanner
from Asgard.Heimdall.Security.Malware.models.malware_models import MalwareScanConfig

# ---------------------------------------------------------------------------
# Security Misconfiguration
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Misconfig.services.misconfig_scanner import SecurityMisconfigScanner
from Asgard.Heimdall.Security.Misconfig.models.misconfig_models import MisconfigScanConfig

# ---------------------------------------------------------------------------
# Sensitive Data
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.SensitiveData.services.sensitive_data_scanner import SensitiveDataScanner
from Asgard.Heimdall.Security.SensitiveData.models.sensitive_data_models import SensitiveDataScanConfig

# ---------------------------------------------------------------------------
# SSRF / XXE
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.SSRF.services.ssrf_scanner import SSRFXXEScanner
from Asgard.Heimdall.Security.SSRF.models.ssrf_models import SSRFScanConfig

# ---------------------------------------------------------------------------
# Shared synthetic payload (200 repetitions of benign Python code)
# ---------------------------------------------------------------------------
_PYTHON_PAYLOAD = ("import re\nx = 1\nresult = re.match(r'hello', x)\n" * 200)
_JS_PAYLOAD = ("const x = 1;\nfunction foo(req) { return req.params; }\n" * 200)


# ===========================================================================
# ReDoS
# ===========================================================================
class TestReDoSScannerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = ReDoSScanConfig(scan_path=target)
        scanner = ReDoSScanner()
        result = benchmark(scanner.scan, config)
        assert result is not None


# ===========================================================================
# API Security
# ===========================================================================
class TestAPISecurityScannerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "api_handler.js"
        target.write_text(_JS_PAYLOAD)
        config = APIScanConfig(scan_path=target)
        scanner = APISecurityScanner()
        result = benchmark(scanner.scan, config)
        assert result is not None


# ===========================================================================
# Backdoor Detector
# ===========================================================================
class TestBackdoorDetectorPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = BackdoorScanConfig(scan_path=target)
        scanner = BackdoorDetector()
        result = benchmark(scanner.scan, config)
        assert result is not None


# ===========================================================================
# Malware
# ===========================================================================
class TestMalwareScannerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = MalwareScanConfig(scan_path=target)
        scanner = MalwareScanner()
        result = benchmark(scanner.scan, config)
        assert result is not None


# ===========================================================================
# Security Misconfiguration
# ===========================================================================
class TestSecurityMisconfigScannerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "settings.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = MisconfigScanConfig(scan_path=target)
        scanner = SecurityMisconfigScanner()
        result = benchmark(scanner.scan, config)
        assert result is not None


# ===========================================================================
# Sensitive Data
# ===========================================================================
class TestSensitiveDataScannerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "config.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = SensitiveDataScanConfig(scan_path=target)
        scanner = SensitiveDataScanner()
        result = benchmark(scanner.scan, config)
        assert result is not None


# ===========================================================================
# SSRF / XXE
# ===========================================================================
class TestSSRFXXEScannerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "proxy.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = SSRFScanConfig(scan_path=target)
        scanner = SSRFXXEScanner()
        result = benchmark(scanner.scan, config)
        assert result is not None
