"""
Tests for Heimdall Performance Models

Unit tests for Pydantic models used in performance analysis.
"""

import pytest
from datetime import datetime
from pathlib import Path

from Asgard.Bragi.Performance.models.performance_models import (
    CacheFinding,
    CacheIssueType,
    CacheReport,
    CpuFinding,
    CpuIssueType,
    CpuReport,
    DatabaseFinding,
    DatabaseIssueType,
    DatabaseReport,
    MemoryFinding,
    MemoryIssueType,
    MemoryReport,
    PerformanceReport,
    PerformanceScanConfig,
    PerformanceSeverity,
)


class TestPerformanceSeverity:
    """Tests for PerformanceSeverity enum."""

    def test_severity_values(self):
        """Test that severity enum has correct values."""
        assert PerformanceSeverity.INFO.value == "info"
        assert PerformanceSeverity.LOW.value == "low"
        assert PerformanceSeverity.MEDIUM.value == "medium"
        assert PerformanceSeverity.HIGH.value == "high"
        assert PerformanceSeverity.CRITICAL.value == "critical"

    def test_severity_is_string_enum(self):
        """Test that PerformanceSeverity is a string enum."""
        assert isinstance(PerformanceSeverity.LOW.value, str)


class TestMemoryIssueType:
    """Tests for MemoryIssueType enum."""

    def test_issue_type_values(self):
        """Test that memory issue types have correct values."""
        assert MemoryIssueType.MEMORY_LEAK.value == "memory_leak"
        assert MemoryIssueType.HIGH_ALLOCATION.value == "high_allocation"
        assert MemoryIssueType.CIRCULAR_REFERENCE.value == "circular_reference"
        assert MemoryIssueType.LARGE_OBJECT.value == "large_object"
        assert MemoryIssueType.UNBOUNDED_GROWTH.value == "unbounded_growth"
        assert MemoryIssueType.INEFFICIENT_STRUCTURE.value == "inefficient_structure"


class TestCpuIssueType:
    """Tests for CpuIssueType enum."""

    def test_issue_type_values(self):
        """Test that CPU issue types have correct values."""
        assert CpuIssueType.HIGH_COMPLEXITY.value == "high_complexity"
        assert CpuIssueType.INEFFICIENT_LOOP.value == "inefficient_loop"
        assert CpuIssueType.BLOCKING_OPERATION.value == "blocking_operation"
        assert CpuIssueType.EXCESSIVE_RECURSION.value == "excessive_recursion"
        assert CpuIssueType.REDUNDANT_COMPUTATION.value == "redundant_computation"
        assert CpuIssueType.SYNCHRONOUS_IO.value == "synchronous_io"


class TestDatabaseIssueType:
    """Tests for DatabaseIssueType enum."""

    def test_issue_type_values(self):
        """Test that database issue types have correct values."""
        assert DatabaseIssueType.N_PLUS_ONE.value == "n_plus_one"
        assert DatabaseIssueType.MISSING_INDEX.value == "missing_index"
        assert DatabaseIssueType.FULL_TABLE_SCAN.value == "full_table_scan"
        assert DatabaseIssueType.EXCESSIVE_QUERIES.value == "excessive_queries"
        assert DatabaseIssueType.UNOPTIMIZED_JOIN.value == "unoptimized_join"
        assert DatabaseIssueType.NO_PAGINATION.value == "no_pagination"
        assert DatabaseIssueType.EAGER_LOADING.value == "eager_loading"


class TestCacheIssueType:
    """Tests for CacheIssueType enum."""

    def test_issue_type_values(self):
        """Test that cache issue types have correct values."""
        assert CacheIssueType.MISSING_CACHE.value == "missing_cache"
        assert CacheIssueType.CACHE_MISS.value == "cache_miss"
        assert CacheIssueType.STALE_CACHE.value == "stale_cache"
        assert CacheIssueType.INEFFICIENT_KEY.value == "inefficient_key"
        assert CacheIssueType.CACHE_STAMPEDE.value == "cache_stampede"
        assert CacheIssueType.OVER_CACHING.value == "over_caching"


class TestMemoryFinding:
    """Tests for MemoryFinding model."""

    def test_create_memory_finding(self):
        """Test creating a memory finding."""
        finding = MemoryFinding(
            file_path="test.py",
            line_number=10,
            issue_type=MemoryIssueType.HIGH_ALLOCATION,
            severity=PerformanceSeverity.MEDIUM,
            description="Test issue",
            code_pattern="test_pattern",
            estimated_impact="High memory usage",
            recommendation="Use streaming",
            code_snippet="code here",
        )

        assert finding.file_path == "test.py"
        assert finding.line_number == 10
        assert finding.issue_type == "high_allocation"
        assert finding.severity == "medium"
        assert finding.description == "Test issue"
        assert finding.code_pattern == "test_pattern"
        assert finding.estimated_impact == "High memory usage"
        assert finding.recommendation == "Use streaming"
        assert finding.code_snippet == "code here"

    def test_memory_finding_with_defaults(self):
        """Test creating memory finding with default values."""
        finding = MemoryFinding(
            file_path="test.py",
            line_number=10,
            issue_type=MemoryIssueType.MEMORY_LEAK,
            severity=PerformanceSeverity.HIGH,
            description="Test",
            recommendation="Fix it",
        )

        assert finding.code_pattern == ""
        assert finding.estimated_impact == ""
        assert finding.code_snippet == ""


class TestCpuFinding:
    """Tests for CpuFinding model."""

    def test_create_cpu_finding(self):
        """Test creating a CPU finding."""
        finding = CpuFinding(
            file_path="test.py",
            line_number=20,
            function_name="complex_func",
            issue_type=CpuIssueType.HIGH_COMPLEXITY,
            severity=PerformanceSeverity.HIGH,
            description="Complex function",
            complexity_score=15.5,
            estimated_impact="Hard to maintain",
            recommendation="Simplify logic",
            code_snippet="def complex_func():",
        )

        assert finding.file_path == "test.py"
        assert finding.line_number == 20
        assert finding.function_name == "complex_func"
        assert finding.issue_type == "high_complexity"
        assert finding.severity == "high"
        assert finding.complexity_score == 15.5
        assert finding.recommendation == "Simplify logic"

    def test_cpu_finding_without_complexity(self):
        """Test creating CPU finding without complexity score."""
        finding = CpuFinding(
            file_path="test.py",
            line_number=20,
            issue_type=CpuIssueType.BLOCKING_OPERATION,
            severity=PerformanceSeverity.MEDIUM,
            description="Blocking call",
            recommendation="Use async",
        )

        assert finding.complexity_score is None
        assert finding.function_name == ""


class TestDatabaseFinding:
    """Tests for DatabaseFinding model."""

    def test_create_database_finding(self):
        """Test creating a database finding."""
        finding = DatabaseFinding(
            file_path="models.py",
            line_number=30,
            issue_type=DatabaseIssueType.N_PLUS_ONE,
            severity=PerformanceSeverity.HIGH,
            description="N+1 query detected",
            query_pattern="objects.all",
            estimated_impact="Multiple queries",
            recommendation="Use select_related",
            code_snippet="User.objects.all()",
        )

        assert finding.file_path == "models.py"
        assert finding.line_number == 30
        assert finding.issue_type == "n_plus_one"
        assert finding.severity == "high"
        assert finding.query_pattern == "objects.all"

    def test_database_finding_with_defaults(self):
        """Test creating database finding with defaults."""
        finding = DatabaseFinding(
            file_path="test.py",
            line_number=10,
            issue_type=DatabaseIssueType.FULL_TABLE_SCAN,
            severity=PerformanceSeverity.MEDIUM,
            description="Full scan",
            recommendation="Add filter",
        )

        assert finding.query_pattern == ""
        assert finding.estimated_impact == ""


class TestCacheFinding:
    """Tests for CacheFinding model."""

    def test_create_cache_finding(self):
        """Test creating a cache finding."""
        finding = CacheFinding(
            file_path="views.py",
            line_number=40,
            issue_type=CacheIssueType.MISSING_CACHE,
            severity=PerformanceSeverity.LOW,
            description="No caching",
            cache_pattern="get_method",
            estimated_impact="Repeated calculations",
            recommendation="Add caching",
            code_snippet="def get_data():",
        )

        assert finding.file_path == "views.py"
        assert finding.line_number == 40
        assert finding.issue_type == "missing_cache"
        assert finding.severity == "low"
        assert finding.cache_pattern == "get_method"


class TestPerformanceScanConfig:
    """Tests for PerformanceScanConfig model."""

    def test_create_default_config(self):
        """Test creating config with default values."""
        config = PerformanceScanConfig()

        assert config.scan_path == Path(".")
        assert config.scan_memory is True
        assert config.scan_cpu is True
        assert config.scan_database is True
        assert config.scan_cache is True
        assert config.min_severity == PerformanceSeverity.LOW
        assert config.complexity_threshold == 10
        assert config.memory_threshold_mb == 100

    def test_create_custom_config(self):
        """Test creating config with custom values."""
        config = PerformanceScanConfig(
            scan_path=Path("/custom"),
            scan_memory=False,
            scan_cpu=True,
            min_severity=PerformanceSeverity.HIGH,
            complexity_threshold=20,
        )

        assert config.scan_path == Path("/custom")
        assert config.scan_memory is False
        assert config.scan_cpu is True
        assert config.min_severity == "high"
        assert config.complexity_threshold == 20

    def test_default_exclude_patterns(self):
        """Test default exclude patterns."""
        config = PerformanceScanConfig()

        assert "__pycache__" in config.exclude_patterns
        assert "node_modules" in config.exclude_patterns
        assert ".git" in config.exclude_patterns
        assert "tests" in config.exclude_patterns

    def test_custom_exclude_patterns(self):
        """Test custom exclude patterns."""
        config = PerformanceScanConfig(
            exclude_patterns=["custom", "pattern"],
        )

        assert "custom" in config.exclude_patterns
        assert "pattern" in config.exclude_patterns

    def test_include_extensions_none(self):
        """Test include_extensions set to None."""
        config = PerformanceScanConfig()

        assert config.include_extensions is None

    def test_custom_include_extensions(self):
        """Test custom include extensions."""
        config = PerformanceScanConfig(
            include_extensions=[".py", ".js"],
        )

        assert ".py" in config.include_extensions
        assert ".js" in config.include_extensions


class TestMemoryReport:
    """Tests for MemoryReport model."""

    def test_create_memory_report(self):
        """Test creating a memory report."""
        report = MemoryReport(
            scan_path="/test/path",
        )

        assert report.scan_path == "/test/path"
        assert report.total_files_scanned == 0
        assert report.issues_found == 0
        assert len(report.findings) == 0
        assert report.scan_duration_seconds == 0.0

    def test_add_finding(self):
        """Test adding a finding to the report."""
        report = MemoryReport(scan_path="/test")

        finding = MemoryFinding(
            file_path="test.py",
            line_number=10,
            issue_type=MemoryIssueType.HIGH_ALLOCATION,
            severity=PerformanceSeverity.MEDIUM,
            description="Test",
            recommendation="Fix",
        )

        report.add_finding(finding)

        assert report.issues_found == 1
        assert len(report.findings) == 1
        assert report.findings[0] == finding

    def test_has_findings_property(self):
        """Test has_findings property."""
        report = MemoryReport(scan_path="/test")

        assert report.has_findings is False

        finding = MemoryFinding(
            file_path="test.py",
            line_number=10,
            issue_type=MemoryIssueType.MEMORY_LEAK,
            severity=PerformanceSeverity.HIGH,
            description="Test",
            recommendation="Fix",
        )
        report.add_finding(finding)

        assert report.has_findings is True

    def test_get_findings_by_severity(self):
        """Test grouping findings by severity."""
        report = MemoryReport(scan_path="/test")

        high_finding = MemoryFinding(
            file_path="test1.py",
            line_number=10,
            issue_type=MemoryIssueType.MEMORY_LEAK,
            severity=PerformanceSeverity.HIGH,
            description="High",
            recommendation="Fix",
        )
        low_finding = MemoryFinding(
            file_path="test2.py",
            line_number=20,
            issue_type=MemoryIssueType.HIGH_ALLOCATION,
            severity=PerformanceSeverity.LOW,
            description="Low",
            recommendation="Fix",
        )

        report.add_finding(high_finding)
        report.add_finding(low_finding)

        by_severity = report.get_findings_by_severity()

        assert len(by_severity["high"]) == 1
        assert len(by_severity["low"]) == 1
        assert len(by_severity["critical"]) == 0


class TestCpuReport:
    """Tests for CpuReport model."""

    def test_create_cpu_report(self):
        """Test creating a CPU report."""
        report = CpuReport(
            scan_path="/test/path",
        )

        assert report.scan_path == "/test/path"
        assert report.total_files_scanned == 0
        assert report.total_functions_analyzed == 0
        assert report.issues_found == 0
        assert report.average_complexity == 0.0
        assert report.max_complexity == 0.0

    def test_add_finding(self):
        """Test adding a finding to CPU report."""
        report = CpuReport(scan_path="/test")

        finding = CpuFinding(
            file_path="test.py",
            line_number=10,
            issue_type=CpuIssueType.HIGH_COMPLEXITY,
            severity=PerformanceSeverity.HIGH,
            description="Complex",
            recommendation="Simplify",
        )

        report.add_finding(finding)

        assert report.issues_found == 1
        assert len(report.findings) == 1

    def test_has_findings_property(self):
        """Test has_findings property for CPU report."""
        report = CpuReport(scan_path="/test")

        assert report.has_findings is False

        finding = CpuFinding(
            file_path="test.py",
            line_number=10,
            issue_type=CpuIssueType.BLOCKING_OPERATION,
            severity=PerformanceSeverity.MEDIUM,
            description="Blocking",
            recommendation="Make async",
        )
        report.add_finding(finding)

        assert report.has_findings is True


class TestDatabaseReport:
    """Tests for DatabaseReport model."""

    def test_create_database_report(self):
        """Test creating a database report."""
        report = DatabaseReport(
            scan_path="/test/path",
        )

        assert report.scan_path == "/test/path"
        assert report.total_files_scanned == 0
        assert report.issues_found == 0
        assert report.orm_detected is None

    def test_add_finding(self):
        """Test adding a finding to database report."""
        report = DatabaseReport(scan_path="/test")

        finding = DatabaseFinding(
            file_path="models.py",
            line_number=30,
            issue_type=DatabaseIssueType.N_PLUS_ONE,
            severity=PerformanceSeverity.HIGH,
            description="N+1",
            recommendation="Use select_related",
        )

        report.add_finding(finding)

        assert report.issues_found == 1
        assert len(report.findings) == 1

    def test_has_findings_property(self):
        """Test has_findings property for database report."""
        report = DatabaseReport(scan_path="/test")

        assert report.has_findings is False

        finding = DatabaseFinding(
            file_path="test.py",
            line_number=10,
            issue_type=DatabaseIssueType.FULL_TABLE_SCAN,
            severity=PerformanceSeverity.MEDIUM,
            description="Full scan",
            recommendation="Add filter",
        )
        report.add_finding(finding)

        assert report.has_findings is True

    def test_orm_detected_field(self):
        """Test ORM detection field."""
        report = DatabaseReport(scan_path="/test")
        report.orm_detected = "Django ORM"

        assert report.orm_detected == "Django ORM"


class TestCacheReport:
    """Tests for CacheReport model."""

    def test_create_cache_report(self):
        """Test creating a cache report."""
        report = CacheReport(
            scan_path="/test/path",
        )

        assert report.scan_path == "/test/path"
        assert report.total_files_scanned == 0
        assert report.issues_found == 0
        assert len(report.cache_systems_detected) == 0

    def test_add_finding(self):
        """Test adding a finding to cache report."""
        report = CacheReport(scan_path="/test")

        finding = CacheFinding(
            file_path="views.py",
            line_number=40,
            issue_type=CacheIssueType.MISSING_CACHE,
            severity=PerformanceSeverity.LOW,
            description="No cache",
            recommendation="Add caching",
        )

        report.add_finding(finding)

        assert report.issues_found == 1
        assert len(report.findings) == 1

    def test_has_findings_property(self):
        """Test has_findings property for cache report."""
        report = CacheReport(scan_path="/test")

        assert report.has_findings is False

        finding = CacheFinding(
            file_path="test.py",
            line_number=10,
            issue_type=CacheIssueType.STALE_CACHE,
            severity=PerformanceSeverity.MEDIUM,
            description="Stale",
            recommendation="Add TTL",
        )
        report.add_finding(finding)

        assert report.has_findings is True

    def test_cache_systems_detected(self):
        """Test cache systems detected field."""
        report = CacheReport(scan_path="/test")
        report.cache_systems_detected = ["Redis", "Memcached"]

        assert "Redis" in report.cache_systems_detected
        assert "Memcached" in report.cache_systems_detected


class TestPerformanceReport:
    """Tests for PerformanceReport model."""

    def test_create_performance_report(self):
        """Test creating a performance report."""
        config = PerformanceScanConfig()
        report = PerformanceReport(
            scan_path="/test/path",
            scan_config=config,
        )

        assert report.scan_path == "/test/path"
        assert report.scan_config == config
        assert report.total_issues == 0
        assert report.performance_score == 100.0

    def test_calculate_totals_empty(self):
        """Test calculating totals with no findings."""
        config = PerformanceScanConfig()
        report = PerformanceReport(
            scan_path="/test",
            scan_config=config,
        )

        report.calculate_totals()

        assert report.total_issues == 0
        assert report.critical_issues == 0
        assert report.high_issues == 0
        assert report.medium_issues == 0
        assert report.low_issues == 0
        assert report.performance_score == 100.0

    def test_calculate_totals_with_findings(self):
        """Test calculating totals with various findings."""
        config = PerformanceScanConfig()
        report = PerformanceReport(
            scan_path="/test",
            scan_config=config,
        )

        memory_report = MemoryReport(scan_path="/test")
        memory_report.add_finding(MemoryFinding(
            file_path="test.py",
            line_number=10,
            issue_type=MemoryIssueType.MEMORY_LEAK,
            severity=PerformanceSeverity.CRITICAL,
            description="Leak",
            recommendation="Fix",
        ))

        cpu_report = CpuReport(scan_path="/test")
        cpu_report.add_finding(CpuFinding(
            file_path="test.py",
            line_number=20,
            issue_type=CpuIssueType.HIGH_COMPLEXITY,
            severity=PerformanceSeverity.HIGH,
            description="Complex",
            recommendation="Simplify",
        ))

        report.memory_report = memory_report
        report.cpu_report = cpu_report

        report.calculate_totals()

        assert report.total_issues == 2
        assert report.critical_issues == 1
        assert report.high_issues == 1

    def test_performance_score_calculation(self):
        """Test performance score calculation."""
        config = PerformanceScanConfig()
        report = PerformanceReport(
            scan_path="/test",
            scan_config=config,
        )

        memory_report = MemoryReport(scan_path="/test")
        memory_report.add_finding(MemoryFinding(
            file_path="test.py",
            line_number=10,
            issue_type=MemoryIssueType.MEMORY_LEAK,
            severity=PerformanceSeverity.CRITICAL,
            description="Leak",
            recommendation="Fix",
        ))

        report.memory_report = memory_report
        report.calculate_totals()

        assert report.performance_score == 80.0

    def test_performance_score_minimum_zero(self):
        """Test that performance score doesn't go below zero."""
        config = PerformanceScanConfig()
        report = PerformanceReport(
            scan_path="/test",
            scan_config=config,
        )

        memory_report = MemoryReport(scan_path="/test")
        for i in range(10):
            memory_report.add_finding(MemoryFinding(
                file_path=f"test{i}.py",
                line_number=10,
                issue_type=MemoryIssueType.MEMORY_LEAK,
                severity=PerformanceSeverity.CRITICAL,
                description="Leak",
                recommendation="Fix",
            ))

        report.memory_report = memory_report
        report.calculate_totals()

        assert report.performance_score >= 0.0

    def test_has_issues_property(self):
        """Test has_issues property."""
        config = PerformanceScanConfig()
        report = PerformanceReport(
            scan_path="/test",
            scan_config=config,
        )

        assert report.has_issues is False

        memory_report = MemoryReport(scan_path="/test")
        memory_report.add_finding(MemoryFinding(
            file_path="test.py",
            line_number=10,
            issue_type=MemoryIssueType.HIGH_ALLOCATION,
            severity=PerformanceSeverity.LOW,
            description="Alloc",
            recommendation="Fix",
        ))

        report.memory_report = memory_report
        report.calculate_totals()

        assert report.has_issues is True

    def test_is_healthy_property(self):
        """Test is_healthy property."""
        config = PerformanceScanConfig()
        report = PerformanceReport(
            scan_path="/test",
            scan_config=config,
        )

        report.calculate_totals()
        assert report.is_healthy is True

        memory_report = MemoryReport(scan_path="/test")
        memory_report.add_finding(MemoryFinding(
            file_path="test.py",
            line_number=10,
            issue_type=MemoryIssueType.MEMORY_LEAK,
            severity=PerformanceSeverity.HIGH,
            description="Leak",
            recommendation="Fix",
        ))

        report.memory_report = memory_report
        report.calculate_totals()

        assert report.is_healthy is False

    def test_is_healthy_with_low_severity(self):
        """Test is_healthy property with only low severity issues."""
        config = PerformanceScanConfig()
        report = PerformanceReport(
            scan_path="/test",
            scan_config=config,
        )

        memory_report = MemoryReport(scan_path="/test")
        memory_report.add_finding(MemoryFinding(
            file_path="test.py",
            line_number=10,
            issue_type=MemoryIssueType.HIGH_ALLOCATION,
            severity=PerformanceSeverity.LOW,
            description="Alloc",
            recommendation="Fix",
        ))

        report.memory_report = memory_report
        report.calculate_totals()

        assert report.is_healthy is True

    def test_scanned_at_timestamp(self):
        """Test scanned_at timestamp."""
        config = PerformanceScanConfig()
        report = PerformanceReport(
            scan_path="/test",
            scan_config=config,
        )

        assert isinstance(report.scanned_at, datetime)
