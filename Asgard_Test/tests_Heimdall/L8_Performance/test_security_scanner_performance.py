"""
L8 Performance Tests — Security Scanner Benchmarks (extended).

Covers security modules not already included in test_scanner_performance.py:
DataExfil, Deserialization, FileIntegrity, Frontend, InfoDisclosure,
InputValidation, PathTraversal, RaceCondition, TaintAnalysis,
Access, Auth, Container, Headers, Hotspots, Infrastructure, TLS,
Compliance (report generation), LogAnalysis, Git (scan on tmp dir).
"""

from pathlib import Path
from textwrap import dedent

import pytest

# ---------------------------------------------------------------------------
# DataExfil
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.DataExfil.services.data_exfil_detector import DataExfiltrationDetector
from Asgard.Heimdall.Security.DataExfil.models.data_exfil_models import ExfilScanConfig

# ---------------------------------------------------------------------------
# Deserialization
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Deserialization.services.deserialization_scanner import DeserializationScanner
from Asgard.Heimdall.Security.Deserialization.models.deserialization_models import DeserializationScanConfig

# ---------------------------------------------------------------------------
# FileIntegrity
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.FileIntegrity.services.file_integrity_checker import FileIntegrityChecker

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Frontend.services.frontend_scanner import FrontendSecurityScanner
from Asgard.Heimdall.Security.Frontend.models.frontend_models import FrontendScanConfig

# ---------------------------------------------------------------------------
# InfoDisclosure
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.InfoDisclosure.services.info_disclosure_scanner import InfoDisclosureScanner
from Asgard.Heimdall.Security.InfoDisclosure.models.info_disclosure_models import InfoDisclosureScanConfig

# ---------------------------------------------------------------------------
# InputValidation
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.InputValidation.services.input_validation_scanner import InputValidationScanner
from Asgard.Heimdall.Security.InputValidation.models.input_validation_models import InputValidationScanConfig

# ---------------------------------------------------------------------------
# PathTraversal
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.PathTraversal.services.path_traversal_scanner import PathTraversalScanner
from Asgard.Heimdall.Security.PathTraversal.models.path_traversal_models import PathTraversalScanConfig

# ---------------------------------------------------------------------------
# RaceCondition
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.RaceCondition.services.race_condition_detector import RaceConditionDetector
from Asgard.Heimdall.Security.RaceCondition.models.race_condition_models import RaceConditionScanConfig

# ---------------------------------------------------------------------------
# TaintAnalysis
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.TaintAnalysis.services.taint_analyzer import TaintAnalyzer
from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import TaintConfig

# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Access.services.access_analyzer import AccessAnalyzer
from Asgard.Heimdall.Security.Access.models.access_models import AccessConfig

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Auth.services.auth_analyzer import AuthAnalyzer
from Asgard.Heimdall.Security.Auth.models.auth_models import AuthConfig

# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Container.services.container_analyzer import ContainerAnalyzer
from Asgard.Heimdall.Security.Container.models.container_models import ContainerConfig

# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Headers.services.headers_analyzer import HeadersAnalyzer
from Asgard.Heimdall.Security.Headers.models.header_models import HeaderConfig

# ---------------------------------------------------------------------------
# Hotspots
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Hotspots.services.hotspot_detector import HotspotDetector
from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import HotspotConfig

# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Infrastructure.services.infra_analyzer import InfraAnalyzer
from Asgard.Heimdall.Security.Infrastructure.models.infra_models import InfraConfig

# ---------------------------------------------------------------------------
# TLS
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.TLS.services.tls_analyzer import TLSAnalyzer
from Asgard.Heimdall.Security.TLS.models.tls_models import TLSConfig

# ---------------------------------------------------------------------------
# LogAnalysis
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.LogAnalysis.services.log_analyzer import LogAnalyzer

# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Git.services.git_scanner import GitSecurityScanner

# ---------------------------------------------------------------------------
# Shared synthetic payloads
# ---------------------------------------------------------------------------
_PYTHON_PAYLOAD = (
    "import os\nimport re\n"
    "def process(user_input):\n"
    "    x = 1\n"
    "    result = re.match(r'hello', str(user_input))\n"
    "    return result\n"
) * 100

_JS_PAYLOAD = (
    "const x = 1;\n"
    "function foo(req) { return req.params; }\n"
) * 200

_LOG_PAYLOAD = (
    "2024-01-01 12:00:00 INFO user logged in\n"
    "2024-01-01 12:00:01 ERROR failed to connect to database\n"
    "2024-01-01 12:00:02 WARNING possible SQL injection attempt detected\n"
) * 100


# ===========================================================================
# DataExfiltration
# ===========================================================================
class TestDataExfiltrationDetectorPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = ExfilScanConfig(scan_path=target)
        scanner = DataExfiltrationDetector()
        result = benchmark(scanner.scan, config)
        assert result is not None


# ===========================================================================
# Deserialization
# ===========================================================================
class TestDeserializationScannerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = DeserializationScanConfig(scan_path=target)
        scanner = DeserializationScanner()
        result = benchmark(scanner.scan, config)
        assert result is not None


# ===========================================================================
# FileIntegrity
# ===========================================================================
class TestFileIntegrityCheckerPerformance:
    def test_verify_integrity_benchmark(self, benchmark, tmp_path: Path) -> None:
        # Create some synthetic files
        for i in range(5):
            (tmp_path / f"module_{i}.py").write_text(_PYTHON_PAYLOAD)
        checker = FileIntegrityChecker(baseline_file=str(tmp_path / ".baseline.json"))
        checker.create_baseline(tmp_path)
        result = benchmark(checker.verify_integrity, tmp_path)
        assert result is not None


# ===========================================================================
# Frontend
# ===========================================================================
class TestFrontendSecurityScannerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "app.js"
        target.write_text(_JS_PAYLOAD)
        config = FrontendScanConfig(scan_path=target)
        scanner = FrontendSecurityScanner()
        result = benchmark(scanner.scan, config)
        assert result is not None


# ===========================================================================
# InfoDisclosure
# ===========================================================================
class TestInfoDisclosureScannerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = InfoDisclosureScanConfig(scan_path=target)
        scanner = InfoDisclosureScanner()
        result = benchmark(scanner.scan, config)
        assert result is not None


# ===========================================================================
# InputValidation
# ===========================================================================
class TestInputValidationScannerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = InputValidationScanConfig(scan_path=target)
        scanner = InputValidationScanner()
        result = benchmark(scanner.scan, config)
        assert result is not None


# ===========================================================================
# PathTraversal
# ===========================================================================
class TestPathTraversalScannerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = PathTraversalScanConfig(scan_path=target)
        scanner = PathTraversalScanner()
        result = benchmark(scanner.scan, config)
        assert result is not None


# ===========================================================================
# RaceCondition
# ===========================================================================
class TestRaceConditionDetectorPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = RaceConditionScanConfig(scan_path=target)
        scanner = RaceConditionDetector()
        result = benchmark(scanner.scan, config)
        assert result is not None


# ===========================================================================
# TaintAnalysis
# ===========================================================================
class TestTaintAnalyzerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = TaintConfig(scan_path=target)
        scanner = TaintAnalyzer(config=config)
        result = benchmark(scanner.scan, target)
        assert result is not None


# ===========================================================================
# Access
# ===========================================================================
class TestAccessAnalyzerPerformance:
    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        (tmp_path / "code.py").write_text(_PYTHON_PAYLOAD)
        config = AccessConfig(scan_path=tmp_path)
        analyzer = AccessAnalyzer(config=config)
        result = benchmark(analyzer.scan, tmp_path)
        assert result is not None


# ===========================================================================
# Auth
# ===========================================================================
class TestAuthAnalyzerPerformance:
    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        (tmp_path / "code.py").write_text(_PYTHON_PAYLOAD)
        config = AuthConfig(scan_path=tmp_path)
        analyzer = AuthAnalyzer(config=config)
        result = benchmark(analyzer.scan, tmp_path)
        assert result is not None


# ===========================================================================
# Container
# ===========================================================================
class TestContainerAnalyzerPerformance:
    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(
            "FROM python:3.11-slim\n"
            "RUN pip install flask\n"
            "COPY . /app\n"
            "CMD [\"python\", \"app.py\"]\n"
        )
        config = ContainerConfig(scan_path=tmp_path)
        analyzer = ContainerAnalyzer(config=config)
        result = benchmark(analyzer.scan, tmp_path)
        assert result is not None


# ===========================================================================
# Headers
# ===========================================================================
class TestHeadersAnalyzerPerformance:
    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text(_PYTHON_PAYLOAD)
        config = HeaderConfig(scan_path=tmp_path)
        analyzer = HeadersAnalyzer(config=config)
        result = benchmark(analyzer.scan, tmp_path)
        assert result is not None


# ===========================================================================
# Hotspots
# ===========================================================================
class TestHotspotDetectorPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = HotspotConfig(scan_path=target)
        detector = HotspotDetector(config=config)
        result = benchmark(detector.scan, target)
        assert result is not None


# ===========================================================================
# Infrastructure
# ===========================================================================
class TestInfraAnalyzerPerformance:
    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        (tmp_path / "config.yaml").write_text(
            "server:\n  host: 0.0.0.0\n  port: 8080\n"
        )
        config = InfraConfig(scan_path=tmp_path)
        analyzer = InfraAnalyzer(config=config)
        result = benchmark(analyzer.scan, tmp_path)
        assert result is not None


# ===========================================================================
# TLS
# ===========================================================================
class TestTLSAnalyzerPerformance:
    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        (tmp_path / "tls_config.py").write_text(_PYTHON_PAYLOAD)
        config = TLSConfig(scan_path=tmp_path)
        analyzer = TLSAnalyzer(config=config)
        result = benchmark(analyzer.scan, tmp_path)
        assert result is not None


# ===========================================================================
# LogAnalysis
# ===========================================================================
class TestLogAnalyzerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "app.log"
        target.write_text(_LOG_PAYLOAD)
        analyzer = LogAnalyzer()
        result = benchmark(analyzer.analyze_file, target)
        assert result is not None

    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        for i in range(5):
            (tmp_path / f"app_{i}.log").write_text(_LOG_PAYLOAD)
        analyzer = LogAnalyzer()
        result = benchmark(analyzer.analyze_directory, tmp_path)
        assert result is not None


# ===========================================================================
# Git Security (scan on a non-git tmp dir — returns empty report gracefully)
# ===========================================================================
class TestGitSecurityScannerPerformance:
    def test_scan_benchmark(self, benchmark, tmp_path: Path) -> None:
        (tmp_path / "secret.py").write_text(_PYTHON_PAYLOAD)
        scanner = GitSecurityScanner()
        result = benchmark(scanner.scan, tmp_path)
        assert result is not None
