"""
L8 Performance Tests — Quality Analyzer Benchmarks.

Covers Quality service modules:
ComplexityAnalyzer, DuplicationDetector, NamingConventionScanner,
MaintainabilityAnalyzer, TypingScanner, CodeSmellDetector,
TechnicalDebtAnalyzer, and several specialty quality scanners.
"""

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Complexity
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.services.complexity_analyzer import ComplexityAnalyzer
from Asgard.Heimdall.Quality.models.complexity_models import ComplexityConfig

# ---------------------------------------------------------------------------
# Duplication
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.services.duplication_detector import DuplicationDetector
from Asgard.Heimdall.Quality.models.duplication_models import DuplicationConfig

# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.services.naming_convention_scanner import NamingConventionScanner
from Asgard.Heimdall.Quality.models.naming_models import NamingConfig

# ---------------------------------------------------------------------------
# Maintainability
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.services.maintainability_analyzer import MaintainabilityAnalyzer
from Asgard.Heimdall.Quality.models.maintainability_models import MaintainabilityConfig

# ---------------------------------------------------------------------------
# Typing coverage
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.services.typing_scanner import TypingScanner
from Asgard.Heimdall.Quality.models.typing_models import TypingConfig

# ---------------------------------------------------------------------------
# Code smell
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.services.code_smell_detector import CodeSmellDetector
from Asgard.Heimdall.Quality.models.smell_models import SmellConfig

# ---------------------------------------------------------------------------
# Technical debt
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.services.technical_debt_analyzer import TechnicalDebtAnalyzer
from Asgard.Heimdall.Quality.models.debt_models import DebtConfig

# ---------------------------------------------------------------------------
# Shared synthetic payload
# ---------------------------------------------------------------------------
_PYTHON_PAYLOAD = (
    "import os\n"
    "import re\n\n"
    "def process_data(user_input: str) -> str:\n"
    "    result = re.match(r'hello', user_input)\n"
    "    return str(result)\n\n"
    "class DataProcessor:\n"
    "    def __init__(self) -> None:\n"
    "        self.value = 0\n\n"
    "    def run(self, x: int) -> int:\n"
    "        return x + self.value\n\n"
) * 50


def _make_project(tmp_path: Path, n_files: int = 5) -> Path:
    """Create a small synthetic Python project."""
    for i in range(n_files):
        (tmp_path / f"module_{i}.py").write_text(_PYTHON_PAYLOAD)
    return tmp_path


# ===========================================================================
# ComplexityAnalyzer
# ===========================================================================
class TestComplexityAnalyzerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = ComplexityConfig(scan_path=target)
        analyzer = ComplexityAnalyzer(config=config)
        result = benchmark(analyzer.analyze, target)
        assert result is not None

    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        _make_project(tmp_path)
        config = ComplexityConfig(scan_path=tmp_path)
        analyzer = ComplexityAnalyzer(config=config)
        result = benchmark(analyzer.analyze, tmp_path)
        assert result is not None


# ===========================================================================
# DuplicationDetector
# ===========================================================================
class TestDuplicationDetectorPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = DuplicationConfig(scan_path=target)
        detector = DuplicationDetector(config=config)
        result = benchmark(detector.analyze, target)
        assert result is not None

    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        _make_project(tmp_path)
        config = DuplicationConfig(scan_path=tmp_path)
        detector = DuplicationDetector(config=config)
        result = benchmark(detector.analyze, tmp_path)
        assert result is not None


# ===========================================================================
# NamingConventionScanner
# ===========================================================================
class TestNamingConventionScannerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = NamingConfig(scan_path=target)
        scanner = NamingConventionScanner(config=config)
        result = benchmark(scanner.scan, target)
        assert result is not None

    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        _make_project(tmp_path)
        config = NamingConfig(scan_path=tmp_path)
        scanner = NamingConventionScanner(config=config)
        result = benchmark(scanner.scan, tmp_path)
        assert result is not None


# ===========================================================================
# MaintainabilityAnalyzer
# ===========================================================================
class TestMaintainabilityAnalyzerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = MaintainabilityConfig(scan_path=target)
        analyzer = MaintainabilityAnalyzer(config=config)
        result = benchmark(analyzer.analyze, target)
        assert result is not None

    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        _make_project(tmp_path)
        config = MaintainabilityConfig(scan_path=tmp_path)
        analyzer = MaintainabilityAnalyzer(config=config)
        result = benchmark(analyzer.analyze, tmp_path)
        assert result is not None


# ===========================================================================
# TypingScanner (TypingCoverageAnalyzer)
# ===========================================================================
class TestTypingScannerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = TypingConfig(scan_path=target)
        scanner = TypingScanner(config=config)
        result = benchmark(scanner.analyze, target)
        assert result is not None

    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        _make_project(tmp_path)
        config = TypingConfig(scan_path=tmp_path)
        scanner = TypingScanner(config=config)
        result = benchmark(scanner.analyze, tmp_path)
        assert result is not None


# ===========================================================================
# CodeSmellDetector
# ===========================================================================
class TestCodeSmellDetectorPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = SmellConfig(scan_path=target)
        detector = CodeSmellDetector(config=config)
        result = benchmark(detector.analyze, target)
        assert result is not None

    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        _make_project(tmp_path)
        config = SmellConfig(scan_path=tmp_path)
        detector = CodeSmellDetector(config=config)
        result = benchmark(detector.analyze, tmp_path)
        assert result is not None


# ===========================================================================
# TechnicalDebtAnalyzer
# ===========================================================================
class TestTechnicalDebtAnalyzerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = DebtConfig(scan_path=target)
        analyzer = TechnicalDebtAnalyzer(config=config)
        result = benchmark(analyzer.analyze, target)
        assert result is not None

    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        _make_project(tmp_path)
        config = DebtConfig(scan_path=tmp_path)
        analyzer = TechnicalDebtAnalyzer(config=config)
        result = benchmark(analyzer.analyze, tmp_path)
        assert result is not None
