"""
L8 Performance Tests — OOP Analyzers and Cross-Cutting Service Benchmarks.

Covers:
- OOPAnalyzer and sub-analyzers (Coupling, Inheritance, Cohesion, RFC)
- Architecture: LayerAnalyzer, PatternDetector
- Dependencies: DependencyAnalyzer
- Coverage: CoverageAnalyzer
- Performance: StaticPerformanceService
- Profiles: ProfileManager.list_profiles()
- CodeFix: CodeFixService.get_fix()
- QualityGate: QualityGateEvaluator.get_default_gate() + evaluate()
- Ratings: RatingsCalculator.calculate_from_reports()
"""

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# OOP
# ---------------------------------------------------------------------------
from Asgard.Heimdall.OOP.services.oop_analyzer import OOPAnalyzer
from Asgard.Heimdall.OOP.services.coupling_analyzer import CouplingAnalyzer
from Asgard.Heimdall.OOP.services.inheritance_analyzer import InheritanceAnalyzer
from Asgard.Heimdall.OOP.services.cohesion_analyzer import CohesionAnalyzer
from Asgard.Heimdall.OOP.models.oop_models import OOPConfig

# ---------------------------------------------------------------------------
# Architecture extras
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Architecture.services.layer_analyzer import LayerAnalyzer
from Asgard.Heimdall.Architecture.services.pattern_detector import PatternDetector
from Asgard.Heimdall.Architecture.models.architecture_models import ArchitectureConfig

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Dependencies.services.dependency_analyzer import DependencyAnalyzer
from Asgard.Heimdall.Dependencies.models.dependency_models import DependencyConfig

# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Coverage.services.coverage_analyzer import CoverageAnalyzer
from Asgard.Heimdall.Coverage.models.coverage_models import CoverageConfig

# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Performance.services.static_performance_service import StaticPerformanceService
from Asgard.Heimdall.Performance.models._performance_reports import PerformanceScanConfig

# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Profiles.services.profile_manager import ProfileManager

# ---------------------------------------------------------------------------
# CodeFix
# ---------------------------------------------------------------------------
from Asgard.Heimdall.CodeFix.services.codefix_service import CodeFixService

# ---------------------------------------------------------------------------
# QualityGate
# ---------------------------------------------------------------------------
from Asgard.Heimdall.QualityGate.services.quality_gate_evaluator import QualityGateEvaluator
from Asgard.Heimdall.QualityGate.models.quality_gate_models import MetricType

# ---------------------------------------------------------------------------
# Ratings
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Ratings.services.ratings_calculator import RatingsCalculator

# ---------------------------------------------------------------------------
# Shared synthetic payload and project builder
# ---------------------------------------------------------------------------
_PYTHON_PAYLOAD = (
    "import os\n"
    "import re\n\n"
    "def process_data(user_input: str) -> str:\n"
    "    result = re.match(r'hello', user_input)\n"
    "    return str(result)\n\n"
    "class DataProcessor:\n"
    "    def __init__(self) -> None:\n"
    "        self.value: int = 0\n\n"
    "    def run(self, x: int) -> int:\n"
    "        return x + self.value\n\n"
    "    def reset(self) -> None:\n"
    "        self.value = 0\n\n"
) * 40


def _make_project(tmp_path: Path, n_files: int = 5) -> Path:
    for i in range(n_files):
        (tmp_path / f"module_{i}.py").write_text(_PYTHON_PAYLOAD)
    return tmp_path


# ===========================================================================
# OOPAnalyzer
# ===========================================================================
class TestOOPAnalyzerPerformance:
    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        _make_project(tmp_path)
        config = OOPConfig(scan_path=tmp_path)
        analyzer = OOPAnalyzer(config=config)
        result = benchmark(analyzer.analyze, tmp_path)
        assert result is not None


# ===========================================================================
# CouplingAnalyzer
# ===========================================================================
class TestCouplingAnalyzerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        analyzer = CouplingAnalyzer()
        result = benchmark(analyzer.analyze_file, target)
        assert result is not None


# ===========================================================================
# InheritanceAnalyzer
# ===========================================================================
class TestInheritanceAnalyzerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        analyzer = InheritanceAnalyzer()
        result = benchmark(analyzer.analyze_file, target)
        assert result is not None


# ===========================================================================
# CohesionAnalyzer
# ===========================================================================
class TestCohesionAnalyzerPerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        analyzer = CohesionAnalyzer()
        result = benchmark(analyzer.analyze_file, target)
        assert result is not None


# ===========================================================================
# LayerAnalyzer (Architecture)
# ===========================================================================
class TestLayerAnalyzerPerformance:
    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        _make_project(tmp_path)
        analyzer = LayerAnalyzer()
        result = benchmark(analyzer.analyze, tmp_path)
        assert result is not None


# ===========================================================================
# PatternDetector (Architecture)
# ===========================================================================
class TestPatternDetectorPerformance:
    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        _make_project(tmp_path)
        detector = PatternDetector()
        result = benchmark(detector.detect, tmp_path)
        assert result is not None


# ===========================================================================
# DependencyAnalyzer
# ===========================================================================
class TestDependencyAnalyzerPerformance:
    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        _make_project(tmp_path)
        config = DependencyConfig(scan_path=tmp_path)
        analyzer = DependencyAnalyzer(config=config)
        result = benchmark(analyzer.analyze, tmp_path)
        assert result is not None


# ===========================================================================
# CoverageAnalyzer
# ===========================================================================
class TestCoverageAnalyzerPerformance:
    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        _make_project(tmp_path)
        config = CoverageConfig(scan_path=tmp_path)
        analyzer = CoverageAnalyzer(config=config)
        result = benchmark(analyzer.analyze, tmp_path)
        assert result is not None


# ===========================================================================
# StaticPerformanceService
# ===========================================================================
class TestStaticPerformanceServicePerformance:
    def test_single_file_benchmark(self, benchmark, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text(_PYTHON_PAYLOAD)
        config = PerformanceScanConfig(scan_path=target)
        service = StaticPerformanceService(config=config)
        result = benchmark(service.scan, target)
        assert result is not None

    def test_directory_benchmark(self, benchmark, tmp_path: Path) -> None:
        _make_project(tmp_path)
        config = PerformanceScanConfig(scan_path=tmp_path)
        service = StaticPerformanceService(config=config)
        result = benchmark(service.scan, tmp_path)
        assert result is not None


# ===========================================================================
# ProfileManager
# ===========================================================================
class TestProfileManagerPerformance:
    def test_list_profiles_benchmark(self, benchmark) -> None:
        manager = ProfileManager()
        result = benchmark(manager.list_profiles)
        assert result is not None


# ===========================================================================
# CodeFixService
# ===========================================================================
class TestCodeFixServicePerformance:
    def test_get_fix_benchmark(self, benchmark) -> None:
        service = CodeFixService()
        result = benchmark(service.get_fix, "quality.lazy_imports", "import os\n")
        # get_fix may return None for unknown rules — that's acceptable
        _ = result  # no assertion on value, just ensure no exception


# ===========================================================================
# QualityGateEvaluator
# ===========================================================================
class TestQualityGateEvaluatorPerformance:
    def test_get_default_gate_benchmark(self, benchmark) -> None:
        evaluator = QualityGateEvaluator()
        result = benchmark(evaluator.get_default_gate)
        assert result is not None

    def test_evaluate_benchmark(self, benchmark) -> None:
        evaluator = QualityGateEvaluator()
        gate = evaluator.get_default_gate()
        metrics = {
            MetricType.SECURITY_RATING: 1.0,
            MetricType.RELIABILITY_RATING: 1.0,
            MetricType.MAINTAINABILITY_RATING: 1.0,
            MetricType.DUPLICATION_PERCENTAGE: 3.0,
            MetricType.CRITICAL_VULNERABILITIES: 0.0,
        }
        result = benchmark(evaluator.evaluate, gate, metrics)
        assert result is not None


# ===========================================================================
# RatingsCalculator
# ===========================================================================
class TestRatingsCalculatorPerformance:
    def test_calculate_from_empty_reports_benchmark(self, benchmark) -> None:
        calculator = RatingsCalculator()
        result = benchmark(calculator.calculate_from_reports, ".")
        assert result is not None
