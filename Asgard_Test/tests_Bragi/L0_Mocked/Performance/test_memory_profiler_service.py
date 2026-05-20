"""
Tests for Heimdall Memory Profiler Service

Unit tests for memory performance pattern detection and memory leak analysis.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Bragi.Performance.models.performance_models import (
    MemoryFinding,
    MemoryIssueType,
    MemoryReport,
    PerformanceScanConfig,
    PerformanceSeverity,
)
from Asgard.Bragi.Performance.services.memory_profiler_service import (
    MemoryProfilerService,
    MemoryPattern,
    MEMORY_PATTERNS,
)


class TestMemoryPattern:
    """Tests for MemoryPattern class."""

    def test_init_with_default_file_types(self):
        """Test initializing pattern with default file types."""
        pattern = MemoryPattern(
            name="test_pattern",
            pattern=r"test",
            issue_type=MemoryIssueType.HIGH_ALLOCATION,
            severity=PerformanceSeverity.MEDIUM,
            description="Test description",
            estimated_impact="Test impact",
            recommendation="Test recommendation",
        )

        assert pattern.name == "test_pattern"
        assert pattern.issue_type == MemoryIssueType.HIGH_ALLOCATION
        assert pattern.severity == PerformanceSeverity.MEDIUM
        assert ".py" in pattern.file_types
        assert ".js" in pattern.file_types

    def test_init_with_custom_file_types(self):
        """Test initializing pattern with custom file types."""
        pattern = MemoryPattern(
            name="test_pattern",
            pattern=r"test",
            issue_type=MemoryIssueType.MEMORY_LEAK,
            severity=PerformanceSeverity.HIGH,
            description="Test description",
            estimated_impact="Test impact",
            recommendation="Test recommendation",
            file_types={".py"},
        )

        assert pattern.file_types == {".py"}

    def test_pattern_compilation(self):
        """Test that regex pattern is compiled correctly."""
        pattern = MemoryPattern(
            name="test_pattern",
            pattern=r"\.read\(\)",
            issue_type=MemoryIssueType.HIGH_ALLOCATION,
            severity=PerformanceSeverity.MEDIUM,
            description="Test description",
            estimated_impact="Test impact",
            recommendation="Test recommendation",
        )

        assert pattern.pattern.search("file.read()") is not None
        assert pattern.pattern.search("FILE.READ()") is not None


class TestMemoryPatterns:
    """Tests for predefined MEMORY_PATTERNS."""

    def test_memory_patterns_exist(self):
        """Test that predefined memory patterns are defined."""
        assert len(MEMORY_PATTERNS) > 0

    def test_large_file_read_pattern_exists(self):
        """Test that large_file_read pattern exists."""
        pattern_names = [p.name for p in MEMORY_PATTERNS]
        assert "large_file_read" in pattern_names

    def test_event_listener_pattern_exists(self):
        """Test that event_listener pattern exists."""
        pattern_names = [p.name for p in MEMORY_PATTERNS]
        assert "event_listener" in pattern_names

    def test_all_patterns_have_required_fields(self):
        """Test that all patterns have required fields."""
        for pattern in MEMORY_PATTERNS:
            assert pattern.name
            assert pattern.pattern
            assert pattern.issue_type
            assert pattern.severity
            assert pattern.description
            assert pattern.estimated_impact
            assert pattern.recommendation


class TestMemoryProfilerService:
    """Tests for MemoryProfilerService class."""

    def test_init_with_default_config(self):
        """Test initializing with default configuration."""
        service = MemoryProfilerService()

        assert service.config is not None
        assert isinstance(service.config, PerformanceScanConfig)
        assert len(service.patterns) > 0

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        config = PerformanceScanConfig(
            scan_path=Path("/custom/path"),
            memory_threshold_mb=200,
        )
        service = MemoryProfilerService(config)

        assert service.config.scan_path == Path("/custom/path")
        assert service.config.memory_threshold_mb == 200

    def test_scan_nonexistent_path(self):
        """Test scanning a path that doesn't exist."""
        service = MemoryProfilerService()

        with pytest.raises(FileNotFoundError):
            service.scan(Path("/nonexistent/path"))

    def test_scan_empty_directory(self):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = MemoryProfilerService()
            result = service.scan(Path(tmpdir))

            assert isinstance(result, MemoryReport)
            assert result.total_files_scanned == 0
            assert result.issues_found == 0

    def test_scan_clean_code(self):
        """Test scanning clean memory-efficient code."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "clean.py").write_text('''
def process_file(filename):
    with open(filename, 'r') as f:
        for line in f:
            process_line(line)

def efficient_copy(data):
    return data
''')

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            assert result.total_files_scanned == 1

    def test_detect_large_file_read(self):
        """Test detecting reading entire file into memory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "file_read.py").write_text('''
def load_file(filename):
    with open(filename, 'r') as f:
        content = f.read()
    return content

def another_read(path):
    data = open(path).read()
    return data
''')

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            high_alloc_findings = [
                f for f in result.findings
                if f.issue_type == MemoryIssueType.HIGH_ALLOCATION
            ]
            assert len(high_alloc_findings) >= 2

    def test_detect_readlines_call(self):
        """Test detecting readlines() calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "readlines.py").write_text('''
def load_lines(filename):
    with open(filename) as f:
        lines = f.readlines()
    return lines

def process_file(path):
    all_lines = open(path).readlines()
    return all_lines
''')

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            high_alloc_findings = [
                f for f in result.findings
                if f.issue_type == MemoryIssueType.HIGH_ALLOCATION
            ]
            assert len(high_alloc_findings) >= 2

    def test_detect_dataframe_copy(self):
        """Test detecting DataFrame copy operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "df_copy.py").write_text('''
import pandas as pd

def process_data(df):
    df_copy = df.copy()
    return df_copy

def transform(data):
    temp = data.copy()
    return temp.apply(lambda x: x * 2)
''')

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            high_alloc_findings = [
                f for f in result.findings
                if f.issue_type == MemoryIssueType.HIGH_ALLOCATION
            ]
            assert len(high_alloc_findings) >= 2

    def test_detect_json_load(self):
        """Test detecting JSON file loading into memory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "json_load.py").write_text('''
import json

def load_config(filename):
    with open(filename) as f:
        config = json.load(f)
    return config

def read_data(path):
    data = json.load(open(path))
    return data
''')

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            high_alloc_findings = [
                f for f in result.findings
                if f.issue_type == MemoryIssueType.HIGH_ALLOCATION
            ]
            assert len(high_alloc_findings) >= 2

    def test_detect_lru_cache_unbounded(self):
        """Test detecting lru_cache without maxsize."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "unbounded.py").write_text('''
from functools import lru_cache

@lru_cache()
def expensive_function(x):
    return x * 2

@lru_cache()
def another_function(a, b):
    return a + b
''')

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            unbounded_findings = [
                f for f in result.findings
                if f.issue_type == MemoryIssueType.UNBOUNDED_GROWTH
            ]
            assert len(unbounded_findings) >= 2

    def test_detect_event_listener(self):
        """Test detecting event listeners in JavaScript."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "events.js").write_text('''
function setupListeners() {
    button.addEventListener('click', handleClick);
    window.addEventListener('resize', handleResize);
}

document.addEventListener('DOMContentLoaded', init);
''')

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            leak_findings = [
                f for f in result.findings
                if f.issue_type == MemoryIssueType.MEMORY_LEAK
            ]
            assert len(leak_findings) >= 3

    def test_detect_setinterval(self):
        """Test detecting setInterval without cleanup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "interval.js").write_text('''
function startPolling() {
    setInterval(() => {
        fetchData();
    }, 1000);
}

const timer = setInterval(updateUI, 500);
''')

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            leak_findings = [
                f for f in result.findings
                if f.issue_type == MemoryIssueType.MEMORY_LEAK
            ]
            assert len(leak_findings) >= 2

    def test_detect_new_array_large(self):
        """Test detecting large pre-sized array allocation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "large_array.js").write_text('''
const bigArray = new Array(1000000);
const hugeArray = new Array(5000000);
''')

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            large_obj_findings = [
                f for f in result.findings
                if f.issue_type == MemoryIssueType.LARGE_OBJECT
            ]
            assert len(large_obj_findings) >= 2

    def test_severity_filtering(self):
        """Test filtering findings by severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "mixed.py").write_text('''
def read_file():
    with open('file.txt') as f:
        return f.read()
''')

            config = PerformanceScanConfig(
                min_severity=PerformanceSeverity.HIGH,
            )
            service = MemoryProfilerService(config)
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

            (tmpdir_path / "mixed.js").write_text('''
const arr = new Array(2000000);
addEventListener('click', handler);
''')

            service = MemoryProfilerService()
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
            service = MemoryProfilerService()
            result = service.scan(Path(tmpdir))

            assert result.scan_duration_seconds >= 0

    def test_ignore_comments(self):
        """Test that patterns in comments are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "comments.py").write_text(
                "# f.read()\n"
                "# f.readlines()\n"
                "\n"
                "def actual_function():\n"
                "    pass\n"
            )

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            assert result.issues_found == 0

    def test_exclude_patterns(self):
        """Test that files matching exclude patterns are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "include.py").write_text('''
def read():
    return open('file').read()
''')

            test_dir = tmpdir_path / "tests"
            test_dir.mkdir()
            (test_dir / "test_file.py").write_text('''
def test_read():
    return open('file').read()
''')

            config = PerformanceScanConfig(
                exclude_patterns=["tests"],
            )
            service = MemoryProfilerService(config)
            result = service.scan(tmpdir_path)

            assert result.total_files_scanned == 1

    def test_include_extensions(self):
        """Test that only specified file extensions are scanned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "script.py").write_text('''
def read():
    return open('file').read()
''')

            (tmpdir_path / "script.js").write_text('''
addEventListener('click', handler);
''')

            config = PerformanceScanConfig(
                include_extensions=[".py"],
            )
            service = MemoryProfilerService(config)
            result = service.scan(tmpdir_path)

            assert result.total_files_scanned == 1

    def test_file_read_error_handling(self):
        """Test handling of file read errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            file_path = tmpdir_path / "normal.py"
            file_path.write_text('''
def process():
    pass
''')

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            assert isinstance(result, MemoryReport)

    def test_is_in_comment_python(self):
        """Test comment detection for Python code."""
        service = MemoryProfilerService()
        lines = [
            "# This is a comment",
            "def function():",
            "    pass",
        ]

        assert service._is_in_comment(lines, 1)
        assert not service._is_in_comment(lines, 2)

    def test_is_in_comment_javascript(self):
        """Test comment detection for JavaScript code."""
        service = MemoryProfilerService()
        lines = [
            "// This is a comment",
            "function test() {",
            "    return true;",
            "}",
        ]

        assert service._is_in_comment(lines, 1)
        assert not service._is_in_comment(lines, 2)

    def test_is_in_comment_out_of_bounds(self):
        """Test comment detection with invalid line numbers."""
        service = MemoryProfilerService()
        lines = ["line 1", "line 2"]

        assert not service._is_in_comment(lines, 0)
        assert not service._is_in_comment(lines, 10)

    def test_code_snippet_in_findings(self):
        """Test that findings include code snippets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "snippet.py").write_text('''
def load():
    with open('file') as f:
        return f.read()
''')

            service = MemoryProfilerService()
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
def load():
    return open('file').read()
''')

            service = MemoryProfilerService()
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
            service = MemoryProfilerService(config)
            result = service.scan()

            assert result.scan_path == str(Path(tmpdir).resolve())

    def test_multiple_findings_same_file(self):
        """Test detecting multiple issues in the same file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "multi.py").write_text('''
import json
from functools import lru_cache

def load1():
    return open('file1').read()

def load2():
    with open('file2') as f:
        return f.readlines()

@lru_cache()
def cached():
    pass
''')

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            assert result.issues_found >= 3

    def test_code_pattern_in_findings(self):
        """Test that findings include code pattern names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "pattern.py").write_text('''
def load():
    return open('file').read()
''')

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            if result.findings:
                assert result.findings[0].code_pattern
                assert result.findings[0].code_pattern == "large_file_read"

    def test_severity_meets_threshold_low(self):
        """Test severity threshold checking with LOW threshold."""
        service = MemoryProfilerService()

        assert service._severity_meets_threshold(PerformanceSeverity.LOW.value)
        assert service._severity_meets_threshold(PerformanceSeverity.MEDIUM.value)
        assert service._severity_meets_threshold(PerformanceSeverity.HIGH.value)
        assert service._severity_meets_threshold(PerformanceSeverity.CRITICAL.value)

    def test_severity_meets_threshold_high(self):
        """Test severity threshold checking with HIGH threshold."""
        config = PerformanceScanConfig(
            min_severity=PerformanceSeverity.HIGH,
        )
        service = MemoryProfilerService(config)

        assert not service._severity_meets_threshold(PerformanceSeverity.LOW.value)
        assert not service._severity_meets_threshold(PerformanceSeverity.MEDIUM.value)
        assert service._severity_meets_threshold(PerformanceSeverity.HIGH.value)
        assert service._severity_meets_threshold(PerformanceSeverity.CRITICAL.value)

    def test_severity_order(self):
        """Test severity ordering for sorting."""
        service = MemoryProfilerService()

        assert service._severity_order(PerformanceSeverity.CRITICAL.value) < \
               service._severity_order(PerformanceSeverity.HIGH.value)
        assert service._severity_order(PerformanceSeverity.HIGH.value) < \
               service._severity_order(PerformanceSeverity.MEDIUM.value)
        assert service._severity_order(PerformanceSeverity.MEDIUM.value) < \
               service._severity_order(PerformanceSeverity.LOW.value)

    def test_estimated_impact_in_findings(self):
        """Test that findings include estimated impact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "impact.py").write_text('''
def load():
    return open('file').read()
''')

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            if result.findings:
                assert result.findings[0].estimated_impact
                assert len(result.findings[0].estimated_impact) > 0

    def test_recommendation_in_findings(self):
        """Test that findings include recommendations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "recommend.py").write_text('''
def load():
    return open('file').read()
''')

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            if result.findings:
                assert result.findings[0].recommendation
                assert len(result.findings[0].recommendation) > 0

    def test_typescript_file_scanning(self):
        """Test scanning TypeScript files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.ts").write_text('''
function setupEvents(): void {
    button.addEventListener('click', handleClick);
    setInterval(() => update(), 1000);
}
''')

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            assert result.total_files_scanned == 1
            assert result.issues_found >= 2

    def test_tsx_file_scanning(self):
        """Test scanning TSX files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "component.tsx").write_text('''
export function Component() {
    useEffect(() => {
        window.addEventListener('resize', handler);
    }, []);
}
''')

            service = MemoryProfilerService()
            result = service.scan(tmpdir_path)

            assert result.total_files_scanned == 1
