"""
Tests for Heimdall Performance Utilities

Unit tests for performance analysis utility functions.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Heimdall.Performance.utilities.performance_utils import (
    PERFORMANCE_SCAN_EXTENSIONS,
    DEFAULT_EXCLUDE_DIRS,
    is_excluded_path,
    scan_directory_for_performance,
    calculate_complexity,
    extract_function_info,
    find_loops,
    find_line_column,
    extract_code_snippet,
)


class TestConstants:
    """Tests for module constants."""

    def test_performance_scan_extensions_defined(self):
        """Test that performance scan extensions are defined."""
        assert len(PERFORMANCE_SCAN_EXTENSIONS) > 0
        assert ".py" in PERFORMANCE_SCAN_EXTENSIONS
        assert ".js" in PERFORMANCE_SCAN_EXTENSIONS
        assert ".ts" in PERFORMANCE_SCAN_EXTENSIONS

    def test_default_exclude_dirs_defined(self):
        """Test that default exclude directories are defined."""
        assert len(DEFAULT_EXCLUDE_DIRS) > 0
        assert "__pycache__" in DEFAULT_EXCLUDE_DIRS
        assert "node_modules" in DEFAULT_EXCLUDE_DIRS
        assert ".git" in DEFAULT_EXCLUDE_DIRS


class TestIsExcludedPath:
    """Tests for is_excluded_path function."""

    def test_exclude_dotfile(self):
        """Test that dotfiles are excluded."""
        path = Path(".hidden_file")
        assert is_excluded_path(path, [])

    def test_exclude_dotdir(self):
        """Test that directories starting with dot are excluded."""
        path = Path(".git")
        assert is_excluded_path(path, [])

    def test_exclude_by_pattern(self):
        """Test excluding by glob pattern."""
        path = Path("test_file.py")
        assert is_excluded_path(path, ["test_*.py"])

    def test_exclude_by_directory_name(self):
        """Test excluding by directory name pattern."""
        path = Path("node_modules")
        assert is_excluded_path(path, ["node_modules"])

    def test_exclude_nested_path(self):
        """Test excluding nested paths."""
        path = Path("src/node_modules/package.json")
        assert is_excluded_path(path, ["node_modules"])

    def test_not_excluded(self):
        """Test that normal files are not excluded."""
        path = Path("normal_file.py")
        assert not is_excluded_path(path, [])

    def test_exclude_custom_pattern(self):
        """Test custom exclude pattern."""
        path = Path("temporary.tmp")
        assert is_excluded_path(path, ["*.tmp"])

    def test_pycache_excluded(self):
        """Test that __pycache__ is excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            pycache = tmpdir_path / "__pycache__"
            pycache.mkdir()
            assert is_excluded_path(pycache, [])


class TestScanDirectoryForPerformance:
    """Tests for scan_directory_for_performance function."""

    def test_scan_empty_directory(self):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = list(scan_directory_for_performance(Path(tmpdir)))
            assert len(files) == 0

    def test_scan_directory_with_python_files(self):
        """Test scanning directory with Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "file1.py").write_text("print('hello')")
            (tmpdir_path / "file2.py").write_text("print('world')")

            files = list(scan_directory_for_performance(tmpdir_path))
            assert len(files) == 2

    def test_scan_directory_excludes_pycache(self):
        """Test that __pycache__ is excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "file.py").write_text("print('hello')")

            pycache = tmpdir_path / "__pycache__"
            pycache.mkdir()
            (pycache / "cache.pyc").write_text("compiled")

            files = list(scan_directory_for_performance(tmpdir_path))
            assert len(files) == 1
            assert files[0].name == "file.py"

    def test_scan_directory_with_custom_exclude(self):
        """Test scanning with custom exclude patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "include.py").write_text("code")
            (tmpdir_path / "exclude.py").write_text("code")

            files = list(scan_directory_for_performance(
                tmpdir_path,
                exclude_patterns=["exclude.py"]
            ))
            assert len(files) == 1
            assert files[0].name == "include.py"

    def test_scan_directory_with_include_extensions(self):
        """Test scanning with specific file extensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "script.py").write_text("code")
            (tmpdir_path / "script.js").write_text("code")
            (tmpdir_path / "script.txt").write_text("text")

            files = list(scan_directory_for_performance(
                tmpdir_path,
                include_extensions=[".py"]
            ))
            assert len(files) == 1
            assert files[0].suffix == ".py"

    def test_scan_nested_directories(self):
        """Test scanning nested directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            subdir1 = tmpdir_path / "subdir1"
            subdir1.mkdir()
            (subdir1 / "file1.py").write_text("code")

            subdir2 = tmpdir_path / "subdir2"
            subdir2.mkdir()
            (subdir2 / "file2.py").write_text("code")

            files = list(scan_directory_for_performance(tmpdir_path))
            assert len(files) == 2

    def test_scan_excludes_git_directory(self):
        """Test that .git directory is excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "file.py").write_text("code")

            git_dir = tmpdir_path / ".git"
            git_dir.mkdir()
            (git_dir / "config").write_text("git config")

            files = list(scan_directory_for_performance(tmpdir_path))
            assert len(files) == 1
            assert files[0].name == "file.py"

    def test_scan_multiple_file_types(self):
        """Test scanning with multiple file types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "code.py").write_text("python")
            (tmpdir_path / "code.js").write_text("javascript")
            (tmpdir_path / "code.ts").write_text("typescript")

            files = list(scan_directory_for_performance(tmpdir_path))
            assert len(files) == 3


class TestCalculateComplexity:
    """Tests for calculate_complexity function."""

    def test_simple_function(self):
        """Test complexity of simple function."""
        code = '''
def simple_function():
    return 42
'''
        complexity = calculate_complexity(code)
        assert "simple_function" in complexity
        assert complexity["simple_function"] == 1

    def test_function_with_if(self):
        """Test complexity of function with if statement."""
        code = '''
def function_with_if(x):
    if x > 0:
        return x
    return 0
'''
        complexity = calculate_complexity(code)
        assert complexity["function_with_if"] == 2

    def test_function_with_nested_if(self):
        """Test complexity of function with nested if."""
        code = '''
def nested_if(x, y):
    if x > 0:
        if y > 0:
            return x + y
    return 0
'''
        complexity = calculate_complexity(code)
        assert complexity["nested_if"] == 3

    def test_function_with_for_loop(self):
        """Test complexity of function with for loop."""
        code = '''
def with_loop(items):
    for item in items:
        print(item)
'''
        complexity = calculate_complexity(code)
        assert complexity["with_loop"] == 2

    def test_function_with_while_loop(self):
        """Test complexity of function with while loop."""
        code = '''
def with_while(x):
    while x > 0:
        x -= 1
    return x
'''
        complexity = calculate_complexity(code)
        assert complexity["with_while"] == 2

    def test_function_with_exception_handling(self):
        """Test complexity with exception handling."""
        code = '''
def with_exception():
    try:
        risky_operation()
    except ValueError:
        handle_error()
    except TypeError:
        handle_type_error()
'''
        complexity = calculate_complexity(code)
        assert complexity["with_exception"] >= 3

    def test_function_with_boolean_operators(self):
        """Test complexity with boolean operators."""
        code = '''
def with_bool_ops(a, b, c):
    if a and b or c:
        return True
    return False
'''
        complexity = calculate_complexity(code)
        assert complexity["with_bool_ops"] >= 2

    def test_async_function(self):
        """Test complexity of async function."""
        code = '''
async def async_function():
    if True:
        await something()
'''
        complexity = calculate_complexity(code)
        assert "async_function" in complexity
        assert complexity["async_function"] == 2

    def test_invalid_syntax(self):
        """Test handling of invalid syntax."""
        code = "def broken( syntax"
        complexity = calculate_complexity(code)
        assert len(complexity) == 0

    def test_multiple_functions(self):
        """Test calculating complexity for multiple functions."""
        code = '''
def func1():
    return 1

def func2(x):
    if x > 0:
        return x
    return 0
'''
        complexity = calculate_complexity(code)
        assert len(complexity) == 2
        assert "func1" in complexity
        assert "func2" in complexity


class TestExtractFunctionInfo:
    """Tests for extract_function_info function."""

    def test_extract_simple_function(self):
        """Test extracting info from simple function."""
        code = '''
def simple():
    return 42
'''
        functions = extract_function_info(code)
        assert len(functions) == 1
        assert functions[0]["name"] == "simple"
        assert functions[0]["is_async"] is False

    def test_extract_async_function(self):
        """Test extracting async function info."""
        code = '''
async def async_func():
    await something()
'''
        functions = extract_function_info(code)
        assert len(functions) == 1
        assert functions[0]["name"] == "async_func"
        assert functions[0]["is_async"] is True

    def test_extract_function_with_args(self):
        """Test extracting function with arguments."""
        code = '''
def with_args(a, b, c):
    return a + b + c
'''
        functions = extract_function_info(code)
        assert functions[0]["num_args"] == 3

    def test_extract_function_with_return(self):
        """Test extracting function with return statement."""
        code = '''
def with_return():
    return 42
'''
        functions = extract_function_info(code)
        assert functions[0]["has_return"] is True

    def test_extract_function_without_return(self):
        """Test extracting function without return statement."""
        code = '''
def no_return():
    print("hello")
'''
        functions = extract_function_info(code)
        assert functions[0]["has_return"] is False

    def test_extract_function_with_decorators(self):
        """Test extracting function with decorators."""
        code = '''
@decorator1
@decorator2
def decorated():
    pass
'''
        functions = extract_function_info(code)
        assert "decorator1" in functions[0]["decorators"]
        assert "decorator2" in functions[0]["decorators"]

    def test_extract_multiple_functions(self):
        """Test extracting multiple functions."""
        code = '''
def func1():
    pass

def func2():
    pass

async def func3():
    pass
'''
        functions = extract_function_info(code)
        assert len(functions) == 3

    def test_extract_invalid_syntax(self):
        """Test handling invalid syntax."""
        code = "def broken( syntax"
        functions = extract_function_info(code)
        assert len(functions) == 0


class TestFindLoops:
    """Tests for find_loops function."""

    def test_find_for_loop(self):
        """Test finding for loop."""
        code = '''
for i in range(10):
    print(i)
'''
        loops = find_loops(code)
        assert len(loops) == 1
        assert loops[0]["type"] == "for"

    def test_find_while_loop(self):
        """Test finding while loop."""
        code = '''
while True:
    break
'''
        loops = find_loops(code)
        assert len(loops) == 1
        assert loops[0]["type"] == "while"

    def test_find_list_comprehension(self):
        """Test finding list comprehension."""
        code = '''
result = [x * 2 for x in range(10)]
'''
        loops = find_loops(code)
        assert len(loops) == 1
        assert loops[0]["type"] == "comprehension"

    def test_find_nested_loops(self):
        """Test finding nested loops."""
        code = '''
for i in range(10):
    for j in range(10):
        print(i, j)
'''
        loops = find_loops(code)
        outer_loop = [loop for loop in loops if not loop.get("is_nested")]
        nested_loop = [loop for loop in loops if loop.get("is_nested")]
        assert len(nested_loop) >= 1

    def test_find_loop_with_break(self):
        """Test finding loop with break statement."""
        code = '''
for i in range(10):
    if i == 5:
        break
'''
        loops = find_loops(code)
        assert loops[0]["has_break"] is True

    def test_find_loop_with_continue(self):
        """Test finding loop with continue statement."""
        code = '''
for i in range(10):
    if i % 2 == 0:
        continue
    print(i)
'''
        loops = find_loops(code)
        assert loops[0]["has_continue"] is True

    def test_find_multiple_comprehensions(self):
        """Test finding comprehension with multiple generators (nested)."""
        code = '''
result = [x * y for x in range(5) for y in range(5)]
'''
        loops = find_loops(code)
        nested = [loop for loop in loops if loop.get("is_nested")]
        assert len(nested) >= 1

    def test_invalid_syntax(self):
        """Test handling invalid syntax."""
        code = "for i in broken syntax"
        loops = find_loops(code)
        assert len(loops) == 0


class TestFindLineColumn:
    """Tests for find_line_column function."""

    def test_find_at_start(self):
        """Test finding position at start of content."""
        content = "Hello world"
        line, col = find_line_column(content, 0)
        assert line == 1
        assert col == 1

    def test_find_in_middle(self):
        """Test finding position in middle of line."""
        content = "Hello world"
        line, col = find_line_column(content, 6)
        assert line == 1
        assert col == 7

    def test_find_on_second_line(self):
        """Test finding position on second line."""
        content = "Line 1\nLine 2"
        line, col = find_line_column(content, 7)
        assert line == 2

    def test_find_multiline(self):
        """Test finding position in multiline content."""
        content = "Line 1\nLine 2\nLine 3"
        line, col = find_line_column(content, 14)
        assert line == 3

    def test_find_at_newline(self):
        """Test finding position at newline character."""
        content = "Line 1\nLine 2"
        line, col = find_line_column(content, 6)
        assert line == 1


class TestExtractCodeSnippet:
    """Tests for extract_code_snippet function."""

    def test_extract_single_line(self):
        """Test extracting snippet for single line."""
        lines = ["line 1", "line 2", "line 3"]
        snippet = extract_code_snippet(lines, 2)

        assert "line 2" in snippet
        assert ">>>" in snippet

    def test_extract_with_context(self):
        """Test extracting snippet with context lines."""
        lines = ["line 1", "line 2", "line 3", "line 4", "line 5"]
        snippet = extract_code_snippet(lines, 3, context_lines=2)

        assert "line 1" in snippet
        assert "line 2" in snippet
        assert "line 3" in snippet
        assert "line 4" in snippet
        assert "line 5" in snippet

    def test_extract_at_start(self):
        """Test extracting snippet at start of file."""
        lines = ["line 1", "line 2", "line 3"]
        snippet = extract_code_snippet(lines, 1, context_lines=2)

        assert "line 1" in snippet
        assert ">>>" in snippet

    def test_extract_at_end(self):
        """Test extracting snippet at end of file."""
        lines = ["line 1", "line 2", "line 3"]
        snippet = extract_code_snippet(lines, 3, context_lines=2)

        assert "line 3" in snippet
        assert ">>>" in snippet

    def test_extract_empty_lines(self):
        """Test extracting from empty line list."""
        lines = []
        snippet = extract_code_snippet(lines, 1)

        assert snippet == ""

    def test_extract_invalid_line_number(self):
        """Test extracting with invalid line number."""
        lines = ["line 1", "line 2"]
        snippet = extract_code_snippet(lines, 0)

        assert snippet == ""

    def test_extract_shows_line_numbers(self):
        """Test that snippet shows line numbers."""
        lines = ["code 1", "code 2", "code 3"]
        snippet = extract_code_snippet(lines, 2)

        assert "1:" in snippet or "2:" in snippet or "3:" in snippet

    def test_extract_marks_target_line(self):
        """Test that target line is marked with >>>."""
        lines = ["code 1", "code 2", "code 3"]
        snippet = extract_code_snippet(lines, 2)

        assert ">>>" in snippet
        snippet_lines = snippet.split("\n")
        marked_lines = [line for line in snippet_lines if ">>>" in line]
        assert len(marked_lines) == 1

    def test_extract_custom_context(self):
        """Test extracting with custom context size."""
        lines = ["line " + str(i) for i in range(1, 11)]
        snippet = extract_code_snippet(lines, 5, context_lines=1)

        snippet_lines = snippet.split("\n")
        assert len(snippet_lines) == 3

    def test_extract_preserves_indentation(self):
        """Test that indentation is preserved."""
        lines = [
            "def func():",
            "    if True:",
            "        return 42",
        ]
        snippet = extract_code_snippet(lines, 2)

        assert "    if True:" in snippet
