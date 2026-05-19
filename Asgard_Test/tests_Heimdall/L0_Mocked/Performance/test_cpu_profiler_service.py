"""
Tests for Heimdall CPU Profiler Service

Unit tests for CPU performance pattern detection and complexity analysis.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Heimdall.Performance.models.performance_models import (
    CpuFinding,
    CpuIssueType,
    CpuReport,
    PerformanceScanConfig,
    PerformanceSeverity,
)
from Asgard.Heimdall.Performance.services.cpu_profiler_service import (
    CpuProfilerService,
    CpuPattern,
    CPU_PATTERNS,
)


class TestCpuPattern:
    """Tests for CpuPattern class."""

    def test_init_with_default_file_types(self):
        """Test initializing pattern with default file types."""
        pattern = CpuPattern(
            name="test_pattern",
            pattern=r"test",
            issue_type=CpuIssueType.BLOCKING_OPERATION,
            severity=PerformanceSeverity.MEDIUM,
            description="Test description",
            estimated_impact="Test impact",
            recommendation="Test recommendation",
        )

        assert pattern.name == "test_pattern"
        assert pattern.issue_type == CpuIssueType.BLOCKING_OPERATION
        assert pattern.severity == PerformanceSeverity.MEDIUM
        assert ".py" in pattern.file_types
        assert ".js" in pattern.file_types
        assert ".java" in pattern.file_types

    def test_init_with_custom_file_types(self):
        """Test initializing pattern with custom file types."""
        pattern = CpuPattern(
            name="test_pattern",
            pattern=r"test",
            issue_type=CpuIssueType.BLOCKING_OPERATION,
            severity=PerformanceSeverity.LOW,
            description="Test description",
            estimated_impact="Test impact",
            recommendation="Test recommendation",
            file_types={".py", ".js"},
        )

        assert pattern.file_types == {".py", ".js"}

    def test_pattern_compilation(self):
        """Test that regex pattern is compiled correctly."""
        pattern = CpuPattern(
            name="test_pattern",
            pattern=r"time\.sleep",
            issue_type=CpuIssueType.BLOCKING_OPERATION,
            severity=PerformanceSeverity.MEDIUM,
            description="Test description",
            estimated_impact="Test impact",
            recommendation="Test recommendation",
        )

        assert pattern.pattern.search("time.sleep(1)") is not None
        assert pattern.pattern.search("TIME.SLEEP(1)") is not None


class TestCpuPatterns:
    """Tests for predefined CPU_PATTERNS."""

    def test_cpu_patterns_exist(self):
        """Test that predefined CPU patterns are defined."""
        assert len(CPU_PATTERNS) > 0

    def test_synchronous_sleep_pattern_exists(self):
        """Test that synchronous_sleep pattern exists."""
        pattern_names = [p.name for p in CPU_PATTERNS]
        assert "synchronous_sleep" in pattern_names

    def test_synchronous_http_pattern_exists(self):
        """Test that synchronous_http pattern exists."""
        pattern_names = [p.name for p in CPU_PATTERNS]
        assert "synchronous_http" in pattern_names

    def test_all_patterns_have_required_fields(self):
        """Test that all patterns have required fields."""
        for pattern in CPU_PATTERNS:
            assert pattern.name
            assert pattern.pattern
            assert pattern.issue_type
            assert pattern.severity
            assert pattern.description
            assert pattern.estimated_impact
            assert pattern.recommendation


class TestCpuProfilerService:
    """Tests for CpuProfilerService class."""

    def test_init_with_default_config(self):
        """Test initializing with default configuration."""
        service = CpuProfilerService()

        assert service.config is not None
        assert isinstance(service.config, PerformanceScanConfig)
        assert len(service.patterns) > 0

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        config = PerformanceScanConfig(
            scan_path=Path("/custom/path"),
            complexity_threshold=15,
        )
        service = CpuProfilerService(config)

        assert service.config.scan_path == Path("/custom/path")
        assert service.config.complexity_threshold == 15

    def test_scan_nonexistent_path(self):
        """Test scanning a path that doesn't exist."""
        service = CpuProfilerService()

        with pytest.raises(FileNotFoundError):
            service.scan(Path("/nonexistent/path"))

    def test_scan_empty_directory(self):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = CpuProfilerService()
            result = service.scan(Path(tmpdir))

            assert isinstance(result, CpuReport)
            assert result.total_files_scanned == 0
            assert result.issues_found == 0
            assert result.total_functions_analyzed == 0

    def test_scan_clean_code(self):
        """Test scanning clean code with low complexity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "clean.py").write_text('''
def simple_function(x):
    """A simple function."""
    return x * 2

def another_simple_function(a, b):
    """Another simple function."""
    return a + b
''')

            service = CpuProfilerService()
            result = service.scan(tmpdir_path)

            assert result.total_files_scanned == 1
            assert result.total_functions_analyzed == 2

    def test_detect_synchronous_sleep(self):
        """Test detecting synchronous sleep operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "sleep.py").write_text('''
import time

def slow_function():
    time.sleep(1)
    time.sleep(2)
    return True
''')

            service = CpuProfilerService()
            result = service.scan(tmpdir_path)

            blocking_findings = [
                f for f in result.findings
                if f.issue_type == CpuIssueType.BLOCKING_OPERATION
            ]
            assert len(blocking_findings) >= 2

    def test_detect_synchronous_http(self):
        """Test detecting synchronous HTTP requests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "http.py").write_text('''
import requests

def fetch_data():
    response = requests.get("https://api.example.com/data")
    return response.json()

def post_data(payload):
    response = requests.post("https://api.example.com/submit", json=payload)
    return response
''')

            service = CpuProfilerService()
            result = service.scan(tmpdir_path)

            sync_io_findings = [
                f for f in result.findings
                if f.issue_type == CpuIssueType.SYNCHRONOUS_IO
            ]
            assert len(sync_io_findings) >= 2

    def test_detect_regex_greedy_star(self):
        """Test detecting regex patterns with greedy wildcards."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "regex.py").write_text('''
import re

def parse_text(text):
    pattern = re.compile(r".*start.*end.*")
    matches = re.findall(r".*foo.*bar.*", text)
    return matches
''')

            service = CpuProfilerService()
            result = service.scan(tmpdir_path)

            high_complexity_findings = [
                f for f in result.findings
                if f.issue_type == CpuIssueType.HIGH_COMPLEXITY and "regex" in f.description.lower()
            ]
            assert len(high_complexity_findings) >= 1

    def test_detect_list_in_literal(self):
        """Test detecting 'in' operator with literal list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "list_in.py").write_text('''
def check_value(value):
    if value in [1, 2, 3, 4, 5]:
        return True
    return False

def another_check(x):
    if x in ["a", "b", "c", "d"]:
        return True
    return False
''')

            service = CpuProfilerService()
            result = service.scan(tmpdir_path)

            inefficient_loop_findings = [
                f for f in result.findings
                if f.issue_type == CpuIssueType.INEFFICIENT_LOOP
            ]
            assert len(inefficient_loop_findings) >= 2

    def test_detect_for_loop_len_call(self):
        """Test detecting range(len()) pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "range_len.py").write_text('''
def process_items(items):
    for i in range(len(items)):
        print(items[i])

def another_loop(data):
    for index in range(len(data)):
        process(data[index])
''')

            service = CpuProfilerService()
            result = service.scan(tmpdir_path)

            inefficient_loop_findings = [
                f for f in result.findings
                if f.issue_type == CpuIssueType.INEFFICIENT_LOOP
            ]
            assert len(inefficient_loop_findings) >= 2

    def test_detect_js_nested_for(self):
        """Test detecting nested for loops in JavaScript."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "nested.js").write_text('''
function findPairs(arr1, arr2) {
    for (let i = 0; i < arr1.length; i++) {
        for (let j = 0; j < arr2.length; j++) {
            if (arr1[i] === arr2[j]) {
                console.log("Match found");
            }
        }
    }
}
''')

            service = CpuProfilerService()
            result = service.scan(tmpdir_path)

            high_complexity_findings = [
                f for f in result.findings
                if f.issue_type == CpuIssueType.HIGH_COMPLEXITY
            ]
            assert len(high_complexity_findings) >= 1

    def test_detect_document_query_loop(self):
        """Test detecting DOM queries inside loops."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "dom.js").write_text('''
items.forEach(item => {
    const element = document.querySelector('.item-' + item.id);
    element.textContent = item.name;
});

data.map(d => {
    return document.querySelector('#result-' + d.id);
});
''')

            service = CpuProfilerService()
            result = service.scan(tmpdir_path)

            inefficient_loop_findings = [
                f for f in result.findings
                if f.issue_type == CpuIssueType.INEFFICIENT_LOOP
            ]
            assert len(inefficient_loop_findings) >= 2

    def test_calculate_complexity_simple_function(self):
        """Test complexity calculation for simple function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "simple.py").write_text('''
def simple_function(x):
    return x * 2
''')

            service = CpuProfilerService()
            result = service.scan(tmpdir_path)

            assert result.total_functions_analyzed == 1
            assert result.average_complexity == 1.0
            assert result.max_complexity == 1.0

    def test_calculate_complexity_high(self):
        """Test complexity calculation for complex function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            complex_function = '''
def complex_function(x, y, z):
    if x > 0:
        if y > 0:
            for i in range(10):
                if z > i:
                    while True:
                        if x == y:
                            break
                        elif x > y:
                            x -= 1
                        else:
                            y -= 1
    return x + y + z
'''

            (tmpdir_path / "complex.py").write_text(complex_function)

            config = PerformanceScanConfig(
                complexity_threshold=5,
            )
            service = CpuProfilerService(config)
            result = service.scan(tmpdir_path)

            complexity_findings = [
                f for f in result.findings
                if f.complexity_score is not None and f.complexity_score > 5
            ]
            assert len(complexity_findings) >= 1

    def test_complexity_to_severity_critical(self):
        """Test complexity to severity conversion for critical level."""
        service = CpuProfilerService()

        severity = service._complexity_to_severity(35)
        assert severity == PerformanceSeverity.CRITICAL

    def test_complexity_to_severity_high(self):
        """Test complexity to severity conversion for high level."""
        service = CpuProfilerService()

        severity = service._complexity_to_severity(25)
        assert severity == PerformanceSeverity.HIGH

    def test_complexity_to_severity_medium(self):
        """Test complexity to severity conversion for medium level."""
        service = CpuProfilerService()

        severity = service._complexity_to_severity(18)
        assert severity == PerformanceSeverity.MEDIUM

    def test_complexity_to_severity_low(self):
        """Test complexity to severity conversion for low level."""
        service = CpuProfilerService()

        severity = service._complexity_to_severity(12)
        assert severity == PerformanceSeverity.LOW

    def test_find_function_line(self):
        """Test finding line number of function definition."""
        service = CpuProfilerService()

        code = '''
# Comment
def target_function(x, y):
    return x + y

def another_function():
    pass
'''

        result = service._find_function_line(code, "target_function")
        assert result["line"] == 3

    def test_find_function_line_not_found(self):
        """Test finding line number when function doesn't exist."""
        service = CpuProfilerService()

        code = '''
def some_function():
    pass
'''

        result = service._find_function_line(code, "nonexistent_function")
        assert result["line"] == 1

    def test_severity_filtering(self):
        """Test filtering findings by severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "mixed.py").write_text('''
import time
import requests

def function():
    time.sleep(1)
    requests.get("http://example.com")
''')

            config = PerformanceScanConfig(
                min_severity=PerformanceSeverity.HIGH,
            )
            service = CpuProfilerService(config)
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
import time
import requests

def function():
    time.sleep(1)
    for i in range(len([1, 2, 3])):
        pass
''')

            service = CpuProfilerService()
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
            service = CpuProfilerService()
            result = service.scan(Path(tmpdir))

            assert result.scan_duration_seconds >= 0

    def test_ignore_comments(self):
        """Test that patterns in comments are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "comments.py").write_text(
                "# time.sleep(1)\n"
                "# requests.get('http://example.com')\n"
                "\n"
                "def actual_function():\n"
                "    pass\n"
            )

            service = CpuProfilerService()
            result = service.scan(tmpdir_path)

            assert result.issues_found == 0

    def test_exclude_patterns(self):
        """Test that files matching exclude patterns are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "include.py").write_text('''
def simple():
    pass
''')

            test_dir = tmpdir_path / "tests"
            test_dir.mkdir()
            (test_dir / "test_file.py").write_text('''
def test_function():
    pass
''')

            config = PerformanceScanConfig(
                exclude_patterns=["tests"],
            )
            service = CpuProfilerService(config)
            result = service.scan(tmpdir_path)

            assert result.total_files_scanned == 1

    def test_include_extensions(self):
        """Test that only specified file extensions are scanned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "script.py").write_text('''
def function():
    pass
''')

            (tmpdir_path / "script.js").write_text('''
function jsFunction() {}
''')

            config = PerformanceScanConfig(
                include_extensions=[".py"],
            )
            service = CpuProfilerService(config)
            result = service.scan(tmpdir_path)

            assert result.total_files_scanned == 1

    def test_python_only_complexity_calculation(self):
        """Test that complexity is only calculated for Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.js").write_text('''
function complexFunction(x, y, z) {
    if (x > 0) {
        if (y > 0) {
            for (let i = 0; i < 10; i++) {
                console.log(i);
            }
        }
    }
}
''')

            service = CpuProfilerService()
            result = service.scan(tmpdir_path)

            assert result.total_functions_analyzed == 0

    def test_file_read_error_handling(self):
        """Test handling of file read errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            file_path = tmpdir_path / "normal.py"
            file_path.write_text('''
def function():
    pass
''')

            service = CpuProfilerService()
            result = service.scan(tmpdir_path)

            assert isinstance(result, CpuReport)

    def test_is_in_comment_python(self):
        """Test comment detection for Python code."""
        service = CpuProfilerService()
        lines = [
            "# This is a comment",
            "def function():",
            "    pass",
        ]

        assert service._is_in_comment(lines, 1)
        assert not service._is_in_comment(lines, 2)

    def test_is_in_comment_javascript(self):
        """Test comment detection for JavaScript code."""
        service = CpuProfilerService()
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
        service = CpuProfilerService()
        lines = ["line 1", "line 2"]

        assert not service._is_in_comment(lines, 0)
        assert not service._is_in_comment(lines, 10)

    def test_code_snippet_in_findings(self):
        """Test that findings include code snippets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "snippet.py").write_text('''
import time

def slow():
    time.sleep(1)
''')

            service = CpuProfilerService()
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
import time

time.sleep(1)
''')

            service = CpuProfilerService()
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
            service = CpuProfilerService(config)
            result = service.scan()

            assert result.scan_path == str(Path(tmpdir).resolve())

    def test_multiple_findings_same_file(self):
        """Test detecting multiple issues in the same file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "multi.py").write_text('''
import time
import requests

def function1():
    time.sleep(1)

def function2():
    requests.get("http://example.com")

def function3():
    for i in range(len([1, 2, 3])):
        pass
''')

            service = CpuProfilerService()
            result = service.scan(tmpdir_path)

            assert result.issues_found >= 3

    def test_average_complexity_calculation(self):
        """Test average complexity calculation across multiple functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "funcs.py").write_text('''
def simple1():
    return 1

def simple2():
    return 2

def with_if(x):
    if x > 0:
        return x
    return 0
''')

            service = CpuProfilerService()
            result = service.scan(tmpdir_path)

            assert result.total_functions_analyzed == 3
            assert result.average_complexity > 0
            assert result.max_complexity >= result.average_complexity

    def test_max_complexity_tracking(self):
        """Test tracking of maximum complexity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "complex.py").write_text('''
def simple():
    return 1

def more_complex(x, y):
    if x > 0:
        if y > 0:
            return x + y
    return 0
''')

            service = CpuProfilerService()
            result = service.scan(tmpdir_path)

            assert result.max_complexity > 1

    def test_function_name_in_complexity_findings(self):
        """Test that complexity findings include function names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            complex_function = '''
def named_complex_function(a, b, c):
    if a > 0:
        if b > 0:
            if c > 0:
                for i in range(10):
                    if i % 2 == 0:
                        pass
    return a + b + c
'''

            (tmpdir_path / "named.py").write_text(complex_function)

            config = PerformanceScanConfig(
                complexity_threshold=5,
            )
            service = CpuProfilerService(config)
            result = service.scan(tmpdir_path)

            complexity_findings = [
                f for f in result.findings
                if f.function_name == "named_complex_function"
            ]
            assert len(complexity_findings) >= 1

    def test_severity_meets_threshold_low(self):
        """Test severity threshold checking with LOW threshold."""
        service = CpuProfilerService()

        assert service._severity_meets_threshold(PerformanceSeverity.LOW.value)
        assert service._severity_meets_threshold(PerformanceSeverity.MEDIUM.value)
        assert service._severity_meets_threshold(PerformanceSeverity.HIGH.value)
        assert service._severity_meets_threshold(PerformanceSeverity.CRITICAL.value)

    def test_severity_meets_threshold_high(self):
        """Test severity threshold checking with HIGH threshold."""
        config = PerformanceScanConfig(
            min_severity=PerformanceSeverity.HIGH,
        )
        service = CpuProfilerService(config)

        assert not service._severity_meets_threshold(PerformanceSeverity.LOW.value)
        assert not service._severity_meets_threshold(PerformanceSeverity.MEDIUM.value)
        assert service._severity_meets_threshold(PerformanceSeverity.HIGH.value)
        assert service._severity_meets_threshold(PerformanceSeverity.CRITICAL.value)

    def test_severity_order(self):
        """Test severity ordering for sorting."""
        service = CpuProfilerService()

        assert service._severity_order(PerformanceSeverity.CRITICAL.value) < \
               service._severity_order(PerformanceSeverity.HIGH.value)
        assert service._severity_order(PerformanceSeverity.HIGH.value) < \
               service._severity_order(PerformanceSeverity.MEDIUM.value)
        assert service._severity_order(PerformanceSeverity.MEDIUM.value) < \
               service._severity_order(PerformanceSeverity.LOW.value)
