"""
Tests for Heimdall Cache Analyzer Service

Unit tests for cache pattern detection and analysis.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Heimdall.Performance.models.performance_models import (
    CacheFinding,
    CacheIssueType,
    CacheReport,
    PerformanceScanConfig,
    PerformanceSeverity,
)
from Asgard.Heimdall.Performance.services.cache_analyzer_service import (
    CacheAnalyzerService,
    CachePattern,
    CACHE_PATTERNS,
)


class TestCachePattern:
    """Tests for CachePattern class."""

    def test_init_with_default_file_types(self):
        """Test initializing pattern with default file types."""
        pattern = CachePattern(
            name="test_pattern",
            pattern=r"test",
            issue_type=CacheIssueType.MISSING_CACHE,
            severity=PerformanceSeverity.LOW,
            description="Test description",
            estimated_impact="Test impact",
            recommendation="Test recommendation",
        )

        assert pattern.name == "test_pattern"
        assert pattern.issue_type == CacheIssueType.MISSING_CACHE
        assert pattern.severity == PerformanceSeverity.LOW
        assert ".py" in pattern.file_types
        assert ".js" in pattern.file_types
        assert ".ts" in pattern.file_types

    def test_init_with_custom_file_types(self):
        """Test initializing pattern with custom file types."""
        pattern = CachePattern(
            name="test_pattern",
            pattern=r"test",
            issue_type=CacheIssueType.MISSING_CACHE,
            severity=PerformanceSeverity.LOW,
            description="Test description",
            estimated_impact="Test impact",
            recommendation="Test recommendation",
            file_types={".py"},
        )

        assert pattern.file_types == {".py"}

    def test_pattern_compilation(self):
        """Test that regex pattern is compiled correctly."""
        pattern = CachePattern(
            name="test_pattern",
            pattern=r"cache\.get",
            issue_type=CacheIssueType.MISSING_CACHE,
            severity=PerformanceSeverity.LOW,
            description="Test description",
            estimated_impact="Test impact",
            recommendation="Test recommendation",
        )

        assert pattern.pattern.search("cache.get('key')") is not None
        assert pattern.pattern.search("CACHE.GET('key')") is not None


class TestCachePatterns:
    """Tests for predefined CACHE_PATTERNS."""

    def test_cache_patterns_exist(self):
        """Test that predefined cache patterns are defined."""
        assert len(CACHE_PATTERNS) > 0

    def test_no_cache_decorator_pattern_exists(self):
        """Test that no_cache_decorator pattern exists."""
        pattern_names = [p.name for p in CACHE_PATTERNS]
        assert "no_cache_decorator" in pattern_names

    def test_cache_no_ttl_pattern_exists(self):
        """Test that cache_no_ttl pattern exists."""
        pattern_names = [p.name for p in CACHE_PATTERNS]
        assert "cache_no_ttl" in pattern_names

    def test_all_patterns_have_required_fields(self):
        """Test that all patterns have required fields."""
        for pattern in CACHE_PATTERNS:
            assert pattern.name
            assert pattern.pattern
            assert pattern.issue_type
            assert pattern.severity
            assert pattern.description
            assert pattern.estimated_impact
            assert pattern.recommendation


class TestCacheAnalyzerService:
    """Tests for CacheAnalyzerService class."""

    def test_init_with_default_config(self):
        """Test initializing with default configuration."""
        service = CacheAnalyzerService()

        assert service.config is not None
        assert isinstance(service.config, PerformanceScanConfig)
        assert len(service.patterns) > 0

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        config = PerformanceScanConfig(
            scan_path=Path("/custom/path"),
            min_severity=PerformanceSeverity.HIGH,
        )
        service = CacheAnalyzerService(config)

        assert service.config.scan_path == Path("/custom/path")
        assert service.config.min_severity == PerformanceSeverity.HIGH

    def test_scan_nonexistent_path(self):
        """Test scanning a path that doesn't exist."""
        service = CacheAnalyzerService()

        with pytest.raises(FileNotFoundError):
            service.scan(Path("/nonexistent/path"))

    def test_scan_empty_directory(self):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = CacheAnalyzerService()
            result = service.scan(Path(tmpdir))

            assert isinstance(result, CacheReport)
            assert result.total_files_scanned == 0
            assert result.issues_found == 0
            assert result.scan_path == str(Path(tmpdir).resolve())

    def test_scan_directory_with_clean_code(self):
        """Test scanning directory with clean caching patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "clean.py").write_text('''
import redis
from functools import lru_cache

@lru_cache(maxsize=128)
def compute_value(x):
    return x * 2

def store_value(key, value, ttl=3600):
    redis.set(key, value, ex=ttl)
''')

            service = CacheAnalyzerService()
            result = service.scan(tmpdir_path)

            assert result.total_files_scanned == 1

    def test_detect_missing_cache_decorator(self):
        """Test detecting functions that could benefit from caching."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "no_cache.py").write_text('''
def get_user_data(user_id):
    """Fetch user data from database."""
    return expensive_query(user_id)

def fetch_config():
    """Load configuration."""
    return read_config_file()

def compute_result(x, y):
    """Calculate expensive result."""
    return expensive_calculation(x, y)
''')

            service = CacheAnalyzerService()
            result = service.scan(tmpdir_path)

            missing_cache_findings = [
                f for f in result.findings
                if f.issue_type == CacheIssueType.MISSING_CACHE
            ]
            assert len(missing_cache_findings) >= 1

    def test_detect_cache_no_ttl(self):
        """Test detecting cache operations without TTL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "no_ttl.py").write_text('''
import redis

r = redis.Redis()

def store_data(key, value):
    r.set(key, value)
    cache.set(key, value)
''')

            service = CacheAnalyzerService()
            result = service.scan(tmpdir_path)

            stale_cache_findings = [
                f for f in result.findings
                if f.issue_type == CacheIssueType.STALE_CACHE
            ]
            assert len(stale_cache_findings) >= 1

    def test_detect_inefficient_cache_key(self):
        """Test detecting simple cache keys without versioning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "simple_key.py").write_text('''
import redis

r = redis.Redis()

def get_data():
    value = cache.get("mykey")
    value = redis.get("data")
''')

            service = CacheAnalyzerService()
            result = service.scan(tmpdir_path)

            inefficient_key_findings = [
                f for f in result.findings
                if f.issue_type == CacheIssueType.INEFFICIENT_KEY
            ]
            assert len(inefficient_key_findings) >= 1

    def test_detect_query_in_template(self):
        """Test detecting database queries in templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "template.html").write_text('''
<div>
    {% for user in User.objects.all() %}
        <p>{{ user.name }}</p>
    {% endfor %}
</div>
''')

            config = PerformanceScanConfig(include_extensions=[".html"])
            service = CacheAnalyzerService(config)
            result = service.scan(tmpdir_path)

            template_query_findings = [
                f for f in result.findings
                if "template" in f.description.lower()
            ]
            assert len(template_query_findings) >= 1

    def test_detect_lru_cache_no_maxsize(self):
        """Test detecting lru_cache without maxsize."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "unbounded.py").write_text('''
from functools import lru_cache

@lru_cache()
def compute_value(x):
    return x * 2

@lru_cache()
def another_function(a, b):
    return a + b
''')

            service = CacheAnalyzerService()
            result = service.scan(tmpdir_path)

            over_caching_findings = [
                f for f in result.findings
                if f.issue_type == CacheIssueType.OVER_CACHING
            ]
            assert len(over_caching_findings) >= 2

    def test_detect_localstorage_sync(self):
        """Test detecting synchronous localStorage usage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "storage.js").write_text('''
function saveData(key, value) {
    localStorage.setItem(key, value);
}

function loadData(key) {
    return localStorage.getItem(key);
}
''')

            service = CacheAnalyzerService()
            result = service.scan(tmpdir_path)

            assert result.issues_found >= 2

    def test_detect_cache_systems(self):
        """Test detection of caching systems in use."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "systems.py").write_text('''
import redis
from functools import lru_cache
from django.core.cache import cache

r = redis.Redis()

@lru_cache(maxsize=128)
def cached_func():
    pass
''')

            service = CacheAnalyzerService()
            result = service.scan(tmpdir_path)

            assert "Redis" in result.cache_systems_detected
            assert "Python functools cache" in result.cache_systems_detected
            assert "Django Cache" in result.cache_systems_detected

    def test_detect_multiple_cache_systems(self):
        """Test detecting multiple caching systems."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "multi.js").write_text('''
// Using browser storage
localStorage.setItem("key", "value");
sessionStorage.setItem("key", "value");

// Using IndexedDB
const db = indexedDB.open("mydb");
''')

            service = CacheAnalyzerService()
            result = service.scan(tmpdir_path)

            assert "Browser Storage" in result.cache_systems_detected
            assert "IndexedDB" in result.cache_systems_detected

    def test_severity_filtering(self):
        """Test filtering findings by severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "mixed.py").write_text('''
def get_data():
    pass

def fetch_user(id):
    pass
''')

            config = PerformanceScanConfig(
                min_severity=PerformanceSeverity.HIGH,
            )
            service = CacheAnalyzerService(config)
            result = service.scan(tmpdir_path)

            for finding in result.findings:
                assert finding.severity in [
                    PerformanceSeverity.HIGH.value,
                    PerformanceSeverity.CRITICAL.value,
                ]

    def test_findings_sorted_by_severity(self):
        """Test that findings are sorted by severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "mixed.py").write_text('''
import redis

def get_user(id):
    pass

redis.set("key", "value")
''')

            service = CacheAnalyzerService()
            result = service.scan(tmpdir_path)

            if len(result.findings) > 1:
                severity_order = {
                    PerformanceSeverity.CRITICAL.value: 0,
                    PerformanceSeverity.HIGH.value: 1,
                    PerformanceSeverity.MEDIUM.value: 2,
                    PerformanceSeverity.LOW.value: 3,
                    PerformanceSeverity.INFO.value: 4,
                }

                for i in range(len(result.findings) - 1):
                    current_order = severity_order.get(result.findings[i].severity, 5)
                    next_order = severity_order.get(result.findings[i + 1].severity, 5)
                    assert current_order <= next_order

    def test_scan_duration_recorded(self):
        """Test that scan duration is recorded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = CacheAnalyzerService()
            result = service.scan(Path(tmpdir))

            assert result.scan_duration_seconds >= 0

    def test_ignore_comments(self):
        """Test that patterns in comments are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "comments.py").write_text(
                "# def get_user_data(id):\n"
                "#     pass\n"
                "\n"
                "# redis.set('key', 'value')\n"
                "\n"
                "def actual_function():\n"
                "    pass\n"
            )

            service = CacheAnalyzerService()
            result = service.scan(tmpdir_path)

            assert result.issues_found == 0

    def test_exclude_patterns(self):
        """Test that files matching exclude patterns are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "include.py").write_text('''
def get_data():
    pass
''')

            test_dir = tmpdir_path / "tests"
            test_dir.mkdir()
            (test_dir / "test_file.py").write_text('''
def get_test_data():
    pass
''')

            config = PerformanceScanConfig(
                exclude_patterns=["tests"],
            )
            service = CacheAnalyzerService(config)
            result = service.scan(tmpdir_path)

            assert result.total_files_scanned == 1

    def test_include_extensions(self):
        """Test that only specified file extensions are scanned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "script.py").write_text('''
def get_data():
    pass
''')

            (tmpdir_path / "script.js").write_text('''
function getData() {}
''')

            config = PerformanceScanConfig(
                include_extensions=[".py"],
            )
            service = CacheAnalyzerService(config)
            result = service.scan(tmpdir_path)

            assert result.total_files_scanned == 1

    def test_file_read_error_handling(self):
        """Test handling of file read errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            file_path = tmpdir_path / "normal.py"
            file_path.write_text('''
def get_data():
    pass
''')

            service = CacheAnalyzerService()
            result = service.scan(tmpdir_path)

            assert isinstance(result, CacheReport)

    def test_severity_meets_threshold_low(self):
        """Test severity threshold checking with LOW threshold."""
        service = CacheAnalyzerService()

        assert service._severity_meets_threshold(PerformanceSeverity.LOW.value)
        assert service._severity_meets_threshold(PerformanceSeverity.MEDIUM.value)
        assert service._severity_meets_threshold(PerformanceSeverity.HIGH.value)
        assert service._severity_meets_threshold(PerformanceSeverity.CRITICAL.value)

    def test_severity_meets_threshold_high(self):
        """Test severity threshold checking with HIGH threshold."""
        config = PerformanceScanConfig(
            min_severity=PerformanceSeverity.HIGH,
        )
        service = CacheAnalyzerService(config)

        assert not service._severity_meets_threshold(PerformanceSeverity.LOW.value)
        assert not service._severity_meets_threshold(PerformanceSeverity.MEDIUM.value)
        assert service._severity_meets_threshold(PerformanceSeverity.HIGH.value)
        assert service._severity_meets_threshold(PerformanceSeverity.CRITICAL.value)

    def test_severity_order(self):
        """Test severity ordering for sorting."""
        service = CacheAnalyzerService()

        assert service._severity_order(PerformanceSeverity.CRITICAL.value) < \
               service._severity_order(PerformanceSeverity.HIGH.value)
        assert service._severity_order(PerformanceSeverity.HIGH.value) < \
               service._severity_order(PerformanceSeverity.MEDIUM.value)
        assert service._severity_order(PerformanceSeverity.MEDIUM.value) < \
               service._severity_order(PerformanceSeverity.LOW.value)
        assert service._severity_order(PerformanceSeverity.LOW.value) < \
               service._severity_order(PerformanceSeverity.INFO.value)

    def test_is_in_comment_python(self):
        """Test comment detection for Python code."""
        service = CacheAnalyzerService()
        lines = [
            "# This is a comment",
            "def function():",
            "    pass  # inline comment",
        ]

        assert service._is_in_comment(lines, 1)
        assert not service._is_in_comment(lines, 2)

    def test_is_in_comment_out_of_bounds(self):
        """Test comment detection with invalid line numbers."""
        service = CacheAnalyzerService()
        lines = ["line 1", "line 2"]

        assert not service._is_in_comment(lines, 0)
        assert not service._is_in_comment(lines, 10)

    def test_code_snippet_in_findings(self):
        """Test that findings include code snippets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "snippet.py").write_text('''
import redis

r = redis.Redis()
r.set("key", "value")
''')

            service = CacheAnalyzerService()
            result = service.scan(tmpdir_path)

            if result.findings:
                assert result.findings[0].code_snippet
                assert ">>>" in result.findings[0].code_snippet

    def test_relative_file_paths_in_findings(self):
        """Test that findings contain relative file paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            subdir = tmpdir_path / "subdir"
            subdir.mkdir()
            (subdir / "code.py").write_text('''
def get_data():
    pass
''')

            service = CacheAnalyzerService()
            result = service.scan(tmpdir_path)

            if result.findings:
                assert not result.findings[0].file_path.startswith("/")
                assert "subdir" in result.findings[0].file_path

    def test_scan_with_config_path(self):
        """Test scanning using path from configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PerformanceScanConfig(
                scan_path=Path(tmpdir),
            )
            service = CacheAnalyzerService(config)
            result = service.scan()

            assert result.scan_path == str(Path(tmpdir).resolve())

    def test_multiple_findings_same_file(self):
        """Test detecting multiple issues in the same file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "multi.py").write_text('''
from functools import lru_cache

@lru_cache()
def get_user(id):
    pass

@lru_cache()
def get_post(id):
    pass

def fetch_data():
    pass
''')

            service = CacheAnalyzerService()
            result = service.scan(tmpdir_path)

            assert result.issues_found >= 2
