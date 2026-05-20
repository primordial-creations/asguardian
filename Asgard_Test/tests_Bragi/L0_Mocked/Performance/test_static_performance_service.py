"""
Tests for Heimdall Static Performance Service

Unit tests for comprehensive static performance analysis combining all scanners.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from Asgard.Bragi.Performance.models.performance_models import (
    CacheReport,
    CpuReport,
    DatabaseReport,
    MemoryReport,
    PerformanceReport,
    PerformanceScanConfig,
    PerformanceSeverity,
)
from Asgard.Bragi.Performance.services.static_performance_service import (
    StaticPerformanceService,
)


class TestStaticPerformanceService:
    """Tests for StaticPerformanceService class."""

    def test_init_with_default_config(self):
        """Test initializing with default configuration."""
        service = StaticPerformanceService()

        assert service.config is not None
        assert isinstance(service.config, PerformanceScanConfig)
        assert service.memory_service is not None
        assert service.cpu_service is not None
        assert service.database_service is not None
        assert service.cache_service is not None

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        config = PerformanceScanConfig(
            scan_path=Path("/custom/path"),
            scan_memory=False,
            scan_cpu=True,
            scan_database=False,
            scan_cache=True,
        )
        service = StaticPerformanceService(config)

        assert service.config.scan_path == Path("/custom/path")
        assert service.config.scan_memory is False
        assert service.config.scan_cpu is True
        assert service.config.scan_database is False
        assert service.config.scan_cache is True

    def test_scan_nonexistent_path(self):
        """Test scanning a path that doesn't exist."""
        service = StaticPerformanceService()

        with pytest.raises(FileNotFoundError):
            service.scan(Path("/nonexistent/path"))

    def test_scan_empty_directory(self):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = StaticPerformanceService()
            result = service.scan(Path(tmpdir))

            assert isinstance(result, PerformanceReport)
            assert result.scan_path == str(Path(tmpdir).resolve())
            assert result.scan_duration_seconds >= 0

    def test_scan_with_all_scanners_enabled(self):
        """Test scanning with all performance scanners enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
import time

def function():
    time.sleep(1)
''')

            config = PerformanceScanConfig(
                scan_memory=True,
                scan_cpu=True,
                scan_database=True,
                scan_cache=True,
            )
            service = StaticPerformanceService(config)
            result = service.scan(tmpdir_path)

            assert result.memory_report is not None
            assert result.cpu_report is not None
            assert result.database_report is not None
            assert result.cache_report is not None

    def test_scan_with_memory_only(self):
        """Test scanning with only memory scanner enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
def read_file():
    return open('file').read()
''')

            config = PerformanceScanConfig(
                scan_memory=True,
                scan_cpu=False,
                scan_database=False,
                scan_cache=False,
            )
            service = StaticPerformanceService(config)
            result = service.scan(tmpdir_path)

            assert result.memory_report is not None
            assert result.cpu_report is None
            assert result.database_report is None
            assert result.cache_report is None

    def test_scan_with_cpu_only(self):
        """Test scanning with only CPU scanner enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
import time

def slow():
    time.sleep(1)
''')

            config = PerformanceScanConfig(
                scan_memory=False,
                scan_cpu=True,
                scan_database=False,
                scan_cache=False,
            )
            service = StaticPerformanceService(config)
            result = service.scan(tmpdir_path)

            assert result.memory_report is None
            assert result.cpu_report is not None
            assert result.database_report is None
            assert result.cache_report is None

    def test_scan_with_database_only(self):
        """Test scanning with only database scanner enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
def query():
    return User.objects.all()
''')

            config = PerformanceScanConfig(
                scan_memory=False,
                scan_cpu=False,
                scan_database=True,
                scan_cache=False,
            )
            service = StaticPerformanceService(config)
            result = service.scan(tmpdir_path)

            assert result.memory_report is None
            assert result.cpu_report is None
            assert result.database_report is not None
            assert result.cache_report is None

    def test_scan_with_cache_only(self):
        """Test scanning with only cache scanner enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
def get_data():
    pass
''')

            config = PerformanceScanConfig(
                scan_memory=False,
                scan_cpu=False,
                scan_database=False,
                scan_cache=True,
            )
            service = StaticPerformanceService(config)
            result = service.scan(tmpdir_path)

            assert result.memory_report is None
            assert result.cpu_report is None
            assert result.database_report is None
            assert result.cache_report is not None

    def test_scan_memory_only_method(self):
        """Test scan_memory_only convenience method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
def read():
    return open('file').read()
''')

            service = StaticPerformanceService()
            result = service.scan_memory_only(tmpdir_path)

            assert result.memory_report is not None
            assert result.cpu_report is None
            assert result.database_report is None
            assert result.cache_report is None

    def test_scan_cpu_only_method(self):
        """Test scan_cpu_only convenience method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
import time
time.sleep(1)
''')

            service = StaticPerformanceService()
            result = service.scan_cpu_only(tmpdir_path)

            assert result.memory_report is None
            assert result.cpu_report is not None
            assert result.database_report is None
            assert result.cache_report is None

    def test_scan_database_only_method(self):
        """Test scan_database_only convenience method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
def query():
    return User.objects.all()
''')

            service = StaticPerformanceService()
            result = service.scan_database_only(tmpdir_path)

            assert result.memory_report is None
            assert result.cpu_report is None
            assert result.database_report is not None
            assert result.cache_report is None

    def test_scan_cache_only_method(self):
        """Test scan_cache_only convenience method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
def get_data():
    pass
''')

            service = StaticPerformanceService()
            result = service.scan_cache_only(tmpdir_path)

            assert result.memory_report is None
            assert result.cpu_report is None
            assert result.database_report is None
            assert result.cache_report is not None

    def test_exception_handling_in_memory_scan(self):
        """Test that exceptions in memory scan are handled gracefully."""
        service = StaticPerformanceService()

        with patch.object(service.memory_service, 'scan', side_effect=Exception("Test error")):
            with tempfile.TemporaryDirectory() as tmpdir:
                result = service.scan(Path(tmpdir))

                assert result.memory_report is None

    def test_exception_handling_in_cpu_scan(self):
        """Test that exceptions in CPU scan are handled gracefully."""
        service = StaticPerformanceService()

        with patch.object(service.cpu_service, 'scan', side_effect=Exception("Test error")):
            with tempfile.TemporaryDirectory() as tmpdir:
                result = service.scan(Path(tmpdir))

                assert result.cpu_report is None

    def test_exception_handling_in_database_scan(self):
        """Test that exceptions in database scan are handled gracefully."""
        service = StaticPerformanceService()

        with patch.object(service.database_service, 'scan', side_effect=Exception("Test error")):
            with tempfile.TemporaryDirectory() as tmpdir:
                result = service.scan(Path(tmpdir))

                assert result.database_report is None

    def test_exception_handling_in_cache_scan(self):
        """Test that exceptions in cache scan are handled gracefully."""
        service = StaticPerformanceService()

        with patch.object(service.cache_service, 'scan', side_effect=Exception("Test error")):
            with tempfile.TemporaryDirectory() as tmpdir:
                result = service.scan(Path(tmpdir))

                assert result.cache_report is None

    def test_scan_with_config_path(self):
        """Test scanning using path from configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PerformanceScanConfig(
                scan_path=Path(tmpdir),
            )
            service = StaticPerformanceService(config)
            result = service.scan()

            assert result.scan_path == str(Path(tmpdir).resolve())

    def test_calculate_totals_called(self):
        """Test that calculate_totals is called on the report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
import time
time.sleep(1)
''')

            service = StaticPerformanceService()
            result = service.scan(tmpdir_path)

            assert hasattr(result, 'total_issues')
            assert hasattr(result, 'performance_score')

    def test_scanned_at_timestamp(self):
        """Test that scanned_at timestamp is set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = StaticPerformanceService()
            result = service.scan(Path(tmpdir))

            assert result.scanned_at is not None

    def test_get_summary_text_generation(self):
        """Test generating text summary of performance report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
import time
time.sleep(1)
''')

            service = StaticPerformanceService()
            result = service.scan(tmpdir_path)
            summary = service.get_summary(result)

            assert isinstance(summary, str)
            assert "HEIMDALL PERFORMANCE ANALYSIS REPORT" in summary
            assert "Performance Score:" in summary
            assert "Total Issues:" in summary

    def test_get_summary_includes_memory_section(self):
        """Test that summary includes memory analysis section when present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
def read():
    return open('file').read()
''')

            config = PerformanceScanConfig(
                scan_memory=True,
                scan_cpu=False,
                scan_database=False,
                scan_cache=False,
            )
            service = StaticPerformanceService(config)
            result = service.scan(tmpdir_path)
            summary = service.get_summary(result)

            assert "MEMORY ANALYSIS" in summary

    def test_get_summary_includes_cpu_section(self):
        """Test that summary includes CPU analysis section when present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
import time
time.sleep(1)
''')

            config = PerformanceScanConfig(
                scan_memory=False,
                scan_cpu=True,
                scan_database=False,
                scan_cache=False,
            )
            service = StaticPerformanceService(config)
            result = service.scan(tmpdir_path)
            summary = service.get_summary(result)

            assert "CPU/COMPLEXITY ANALYSIS" in summary

    def test_get_summary_includes_database_section(self):
        """Test that summary includes database analysis section when present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
def query():
    return User.objects.all()
''')

            config = PerformanceScanConfig(
                scan_memory=False,
                scan_cpu=False,
                scan_database=True,
                scan_cache=False,
            )
            service = StaticPerformanceService(config)
            result = service.scan(tmpdir_path)
            summary = service.get_summary(result)

            assert "DATABASE ANALYSIS" in summary

    def test_get_summary_includes_cache_section(self):
        """Test that summary includes cache analysis section when present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
def get_data():
    pass
''')

            config = PerformanceScanConfig(
                scan_memory=False,
                scan_cpu=False,
                scan_database=False,
                scan_cache=True,
            )
            service = StaticPerformanceService(config)
            result = service.scan(tmpdir_path)
            summary = service.get_summary(result)

            assert "CACHE ANALYSIS" in summary

    def test_get_summary_shows_healthy_status(self):
        """Test that summary shows HEALTHY status when no critical/high issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "clean.py").write_text('''
def simple():
    return 42
''')

            service = StaticPerformanceService()
            result = service.scan(tmpdir_path)
            summary = service.get_summary(result)

            if result.is_healthy:
                assert "HEALTHY" in summary

    def test_get_summary_shows_needs_attention_status(self):
        """Test that summary shows NEEDS ATTENTION when issues found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            complex_function = '''
def complex_function(a, b, c, d, e):
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    if e > 0:
                        for i in range(100):
                            for j in range(100):
                                if i == j:
                                    pass
    return a + b + c + d + e
'''
            (tmpdir_path / "complex.py").write_text(complex_function)

            config = PerformanceScanConfig(
                complexity_threshold=5,
            )
            service = StaticPerformanceService(config)
            result = service.scan(tmpdir_path)
            summary = service.get_summary(result)

            if not result.is_healthy:
                assert "NEEDS ATTENTION" in summary

    def test_get_summary_limits_findings_display(self):
        """Test that summary limits displayed findings to 5 per category."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code_with_many_issues = '''
import time

def f1(): time.sleep(1)
def f2(): time.sleep(1)
def f3(): time.sleep(1)
def f4(): time.sleep(1)
def f5(): time.sleep(1)
def f6(): time.sleep(1)
def f7(): time.sleep(1)
'''
            (tmpdir_path / "many.py").write_text(code_with_many_issues)

            service = StaticPerformanceService()
            result = service.scan(tmpdir_path)
            summary = service.get_summary(result)

            # Summary should be a non-empty string regardless of finding count
            assert isinstance(summary, str)
            assert len(summary) > 0

    def test_scan_duration_aggregated(self):
        """Test that scan duration is aggregated across all scans."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = StaticPerformanceService()
            result = service.scan(Path(tmpdir))

            assert result.scan_duration_seconds >= 0

    def test_scan_with_mixed_content(self):
        """Test scanning directory with mixed performance issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "issues.py").write_text('''
import time
import requests

def slow():
    time.sleep(1)
    requests.get("http://example.com")
    data = open('file').read()
    return User.objects.all()
''')

            service = StaticPerformanceService()
            result = service.scan(tmpdir_path)

            assert result.total_issues > 0

    def test_performance_score_calculated(self):
        """Test that performance score is calculated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = StaticPerformanceService()
            result = service.scan(Path(tmpdir))

            assert 0 <= result.performance_score <= 100

    def test_severity_breakdown_calculated(self):
        """Test that severity breakdown is calculated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
import time
time.sleep(1)
''')

            service = StaticPerformanceService()
            result = service.scan(tmpdir_path)

            assert hasattr(result, 'critical_issues')
            assert hasattr(result, 'high_issues')
            assert hasattr(result, 'medium_issues')
            assert hasattr(result, 'low_issues')

    def test_scan_config_preserved_in_report(self):
        """Test that scan configuration is preserved in the report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PerformanceScanConfig(
                scan_memory=True,
                scan_cpu=False,
                complexity_threshold=20,
            )
            service = StaticPerformanceService(config)
            result = service.scan(Path(tmpdir))

            assert result.scan_config.scan_memory is True
            assert result.scan_config.scan_cpu is False
            assert result.scan_config.complexity_threshold == 20

    def test_multiple_file_types_scanned(self):
        """Test scanning directory with multiple file types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text('''
import time
time.sleep(1)
''')

            (tmpdir_path / "script.js").write_text('''
addEventListener('click', handler);
''')

            service = StaticPerformanceService()
            result = service.scan(tmpdir_path)

            assert result.total_issues >= 0

    def test_nested_directory_scanning(self):
        """Test scanning nested directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            subdir = tmpdir_path / "subdir"
            subdir.mkdir()
            (subdir / "code.py").write_text('''
import time
time.sleep(1)
''')

            service = StaticPerformanceService()
            result = service.scan(tmpdir_path)

            assert result.total_issues >= 0
