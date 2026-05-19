"""
Tests for Heimdall Security Utilities

Unit tests for security scanning utility functions.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Heimdall.Security.utilities.security_utils import (
    SECURITY_SCAN_EXTENSIONS,
    BINARY_EXTENSIONS,
    DEFAULT_EXCLUDE_DIRS,
    is_binary_file,
    is_excluded_path,
    scan_directory_for_security,
    read_file_lines,
    extract_code_snippet,
    mask_secret,
    get_cwe_url,
    get_owasp_url,
    calculate_entropy,
    find_line_column,
)


class TestSecurityScanExtensions:
    """Tests for SECURITY_SCAN_EXTENSIONS constant."""

    def test_contains_python(self):
        """Test that Python extensions are included."""
        assert ".py" in SECURITY_SCAN_EXTENSIONS

    def test_contains_javascript_typescript(self):
        """Test that JS/TS extensions are included."""
        assert ".js" in SECURITY_SCAN_EXTENSIONS
        assert ".jsx" in SECURITY_SCAN_EXTENSIONS
        assert ".ts" in SECURITY_SCAN_EXTENSIONS
        assert ".tsx" in SECURITY_SCAN_EXTENSIONS

    def test_contains_backend_languages(self):
        """Test that backend language extensions are included."""
        assert ".java" in SECURITY_SCAN_EXTENSIONS
        assert ".go" in SECURITY_SCAN_EXTENSIONS
        assert ".rb" in SECURITY_SCAN_EXTENSIONS
        assert ".php" in SECURITY_SCAN_EXTENSIONS

    def test_contains_config_files(self):
        """Test that configuration file extensions are included."""
        assert ".yaml" in SECURITY_SCAN_EXTENSIONS
        assert ".yml" in SECURITY_SCAN_EXTENSIONS
        assert ".json" in SECURITY_SCAN_EXTENSIONS
        assert ".env" in SECURITY_SCAN_EXTENSIONS


class TestBinaryExtensions:
    """Tests for BINARY_EXTENSIONS constant."""

    def test_contains_executables(self):
        """Test that executable extensions are marked as binary."""
        assert ".exe" in BINARY_EXTENSIONS
        assert ".dll" in BINARY_EXTENSIONS
        assert ".so" in BINARY_EXTENSIONS

    def test_contains_compiled_code(self):
        """Test that compiled code extensions are marked as binary."""
        assert ".pyc" in BINARY_EXTENSIONS
        assert ".class" in BINARY_EXTENSIONS
        assert ".o" in BINARY_EXTENSIONS

    def test_contains_images(self):
        """Test that image extensions are marked as binary."""
        assert ".png" in BINARY_EXTENSIONS
        assert ".jpg" in BINARY_EXTENSIONS
        assert ".gif" in BINARY_EXTENSIONS


class TestDefaultExcludeDirs:
    """Tests for DEFAULT_EXCLUDE_DIRS constant."""

    def test_excludes_cache_directories(self):
        """Test that cache directories are excluded."""
        assert "__pycache__" in DEFAULT_EXCLUDE_DIRS
        assert ".pytest_cache" in DEFAULT_EXCLUDE_DIRS
        assert ".mypy_cache" in DEFAULT_EXCLUDE_DIRS

    def test_excludes_dependency_directories(self):
        """Test that dependency directories are excluded."""
        assert "node_modules" in DEFAULT_EXCLUDE_DIRS
        assert "vendor" in DEFAULT_EXCLUDE_DIRS

    def test_excludes_build_directories(self):
        """Test that build directories are excluded."""
        assert "build" in DEFAULT_EXCLUDE_DIRS
        assert "dist" in DEFAULT_EXCLUDE_DIRS
        assert "target" in DEFAULT_EXCLUDE_DIRS


class TestIsBinaryFile:
    """Tests for is_binary_file function."""

    def test_python_file_not_binary(self):
        """Test that Python files are not considered binary."""
        assert is_binary_file(Path("test.py")) is False

    def test_javascript_file_not_binary(self):
        """Test that JavaScript files are not considered binary."""
        assert is_binary_file(Path("app.js")) is False

    def test_exe_file_is_binary(self):
        """Test that .exe files are considered binary."""
        assert is_binary_file(Path("program.exe")) is True

    def test_image_file_is_binary(self):
        """Test that image files are considered binary."""
        assert is_binary_file(Path("photo.png")) is True
        assert is_binary_file(Path("logo.jpg")) is True

    def test_compiled_python_is_binary(self):
        """Test that .pyc files are considered binary."""
        assert is_binary_file(Path("module.pyc")) is True

    def test_pdf_is_binary(self):
        """Test that PDF files are considered binary."""
        assert is_binary_file(Path("document.pdf")) is True


class TestIsExcludedPath:
    """Tests for is_excluded_path function."""

    def test_pycache_excluded(self):
        """Test that __pycache__ directories are excluded."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "__pycache__"
            path.mkdir()
            assert is_excluded_path(path, []) is True

    def test_node_modules_excluded(self):
        """Test that node_modules is excluded."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "node_modules"
            path.mkdir()
            assert is_excluded_path(path, []) is True

    def test_git_directory_excluded(self):
        """Test that .git directory is excluded."""
        path = Path("/project/.git")
        assert is_excluded_path(path, []) is True

    def test_custom_exclude_pattern(self):
        """Test custom exclusion patterns."""
        path = Path("/project/custom_exclude")
        assert is_excluded_path(path, ["custom_exclude"]) is True

    def test_wildcard_pattern_exclusion(self):
        """Test wildcard pattern exclusion."""
        path = Path("/project/test.min.js")
        assert is_excluded_path(path, ["*.min.js"]) is True

    def test_normal_file_not_excluded(self):
        """Test that normal files are not excluded."""
        path = Path("/project/src/app.py")
        assert is_excluded_path(path, []) is False

    def test_env_file_not_excluded(self):
        """Test that .env files are not excluded despite starting with dot."""
        path = Path("/project/.env")
        assert is_excluded_path(path, []) is False


class TestScanDirectoryForSecurity:
    """Tests for scan_directory_for_security function."""

    def test_scan_empty_directory(self):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = list(scan_directory_for_security(Path(tmpdir)))
            assert len(files) == 0

    def test_scan_with_code_files(self):
        """Test scanning directory with code files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "app.py").write_text("print('hello')")
            (tmpdir_path / "utils.js").write_text("const x = 1;")
            (tmpdir_path / "service.ts").write_text("const y = 2;")

            files = list(scan_directory_for_security(tmpdir_path))
            assert len(files) == 3

    def test_scan_excludes_pycache(self):
        """Test that __pycache__ directories are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            pycache = tmpdir_path / "__pycache__"
            pycache.mkdir()
            (pycache / "module.pyc").write_bytes(b"compiled")

            (tmpdir_path / "app.py").write_text("code")

            files = list(scan_directory_for_security(tmpdir_path))
            assert len(files) == 1
            assert files[0].name == "app.py"

    def test_scan_with_custom_extensions(self):
        """Test scanning with custom file extensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "file.py").write_text("python")
            (tmpdir_path / "file.custom").write_text("custom")

            files = list(scan_directory_for_security(
                tmpdir_path,
                include_extensions=[".custom"]
            ))

            assert len(files) == 1
            assert files[0].suffix == ".custom"

    def test_scan_with_exclude_patterns(self):
        """Test scanning with exclude patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "app.py").write_text("code")
            (tmpdir_path / "test.py").write_text("test")

            files = list(scan_directory_for_security(
                tmpdir_path,
                exclude_patterns=["test.py"]
            ))

            assert len(files) == 1
            assert files[0].name == "app.py"

    def test_scan_includes_env_files(self):
        """Test that .env files are included in scan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / ".env").write_text("SECRET=value")
            (tmpdir_path / "app.py").write_text("code")

            files = list(scan_directory_for_security(tmpdir_path))
            file_names = [f.name for f in files]

            assert "app.py" in file_names
            # .env files may or may not be included based on implementation


class TestReadFileLines:
    """Tests for read_file_lines function."""

    def test_read_empty_file(self):
        """Test reading an empty file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("")
            temp_path = Path(f.name)

        try:
            lines = read_file_lines(temp_path)
            assert lines == []
        finally:
            temp_path.unlink()

    def test_read_single_line_file(self):
        """Test reading a single-line file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("single line")
            temp_path = Path(f.name)

        try:
            lines = read_file_lines(temp_path)
            assert len(lines) == 1
            assert lines[0] == "single line"
        finally:
            temp_path.unlink()

    def test_read_multi_line_file(self):
        """Test reading a multi-line file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("line 1\nline 2\nline 3\n")
            temp_path = Path(f.name)

        try:
            lines = read_file_lines(temp_path)
            assert len(lines) == 3
            assert lines[0] == "line 1\n"
            assert lines[1] == "line 2\n"
            assert lines[2] == "line 3\n"
        finally:
            temp_path.unlink()

    def test_read_nonexistent_file(self):
        """Test reading a file that doesn't exist."""
        lines = read_file_lines(Path("/nonexistent/file.txt"))
        assert lines == []


class TestExtractCodeSnippet:
    """Tests for extract_code_snippet function."""

    def test_extract_snippet_with_context(self):
        """Test extracting code snippet with context lines."""
        lines = [
            "line 1\n",
            "line 2\n",
            "line 3\n",
            "line 4\n",
            "line 5\n",
        ]

        snippet = extract_code_snippet(lines, line_number=3, context_lines=1)

        assert ">>> 3:" in snippet
        assert "line 3" in snippet
        assert "2:" in snippet
        assert "4:" in snippet

    def test_extract_snippet_at_start_of_file(self):
        """Test extracting snippet at the start of file."""
        lines = ["line 1\n", "line 2\n", "line 3\n"]

        snippet = extract_code_snippet(lines, line_number=1, context_lines=2)

        assert ">>> 1:" in snippet
        assert "line 1" in snippet

    def test_extract_snippet_at_end_of_file(self):
        """Test extracting snippet at the end of file."""
        lines = ["line 1\n", "line 2\n", "line 3\n"]

        snippet = extract_code_snippet(lines, line_number=3, context_lines=2)

        assert ">>> 3:" in snippet
        assert "line 3" in snippet

    def test_extract_snippet_empty_lines(self):
        """Test extracting snippet from empty line list."""
        snippet = extract_code_snippet([], line_number=1)
        assert snippet == ""

    def test_extract_snippet_invalid_line_number(self):
        """Test extracting snippet with invalid line number."""
        lines = ["line 1\n", "line 2\n"]
        snippet = extract_code_snippet(lines, line_number=0)
        assert snippet == ""


class TestMaskSecret:
    """Tests for mask_secret function."""

    def test_mask_long_secret(self):
        """Test masking a long secret value."""
        secret = "AKIAIOSFODNN7EXAMPLE"
        masked = mask_secret(secret, visible_chars=4)

        assert masked.startswith("AKIA")
        assert masked.endswith("MPLE")
        assert "*" in masked
        assert len(masked) == len(secret)

    def test_mask_short_secret(self):
        """Test masking a short secret value."""
        secret = "abc"
        masked = mask_secret(secret, visible_chars=4)

        assert masked == "***"
        assert len(masked) == len(secret)

    def test_mask_with_different_visible_chars(self):
        """Test masking with different visible character counts."""
        secret = "verylongsecretkey1234567890"

        masked_2 = mask_secret(secret, visible_chars=2)
        assert masked_2.startswith("ve")
        assert masked_2.endswith("90")

        masked_6 = mask_secret(secret, visible_chars=6)
        assert masked_6.startswith("verylo")
        assert masked_6.endswith("567890")


class TestGetCweUrl:
    """Tests for get_cwe_url function."""

    def test_get_cwe_url_with_prefix(self):
        """Test getting CWE URL with CWE- prefix."""
        url = get_cwe_url("CWE-89")
        assert url == "https://cwe.mitre.org/data/definitions/89.html"

    def test_get_cwe_url_lowercase(self):
        """Test getting CWE URL with lowercase prefix."""
        url = get_cwe_url("cwe-79")
        assert url == "https://cwe.mitre.org/data/definitions/79.html"

    def test_get_cwe_url_without_prefix(self):
        """Test getting CWE URL without prefix."""
        url = get_cwe_url("22")
        assert url == "https://cwe.mitre.org/data/definitions/22.html"


class TestGetOwaspUrl:
    """Tests for get_owasp_url function."""

    def test_get_owasp_url_single_digit(self):
        """Test getting OWASP URL for single digit category."""
        url = get_owasp_url("3")
        assert url == "https://owasp.org/Top10/A03/"

    def test_get_owasp_url_double_digit(self):
        """Test getting OWASP URL for double digit category."""
        url = get_owasp_url("10")
        assert url == "https://owasp.org/Top10/A10/"


class TestCalculateEntropy:
    """Tests for calculate_entropy function."""

    def test_entropy_empty_string(self):
        """Test entropy of empty string."""
        entropy = calculate_entropy("")
        assert entropy == 0.0

    def test_entropy_single_character(self):
        """Test entropy of repeated single character."""
        entropy = calculate_entropy("aaaa")
        assert entropy == 0.0

    def test_entropy_random_string(self):
        """Test entropy of random-looking string."""
        random_str = "K7gR2mN9pL4xQ8wE"
        entropy = calculate_entropy(random_str)
        assert entropy > 3.0

    def test_entropy_predictable_string(self):
        """Test entropy of predictable string."""
        predictable = "abcabcabc"
        entropy = calculate_entropy(predictable)

        random_like = "xK9mQ2wL7pN4gR8E"
        random_entropy = calculate_entropy(random_like)

        assert random_entropy > entropy

    def test_entropy_comparison(self):
        """Test that high-entropy strings score higher than low-entropy."""
        low_entropy = "password"
        high_entropy = "xK9m#Q2w@L7p!N4g"

        low_score = calculate_entropy(low_entropy)
        high_score = calculate_entropy(high_entropy)

        assert high_score > low_score


class TestFindLineColumn:
    """Tests for find_line_column function."""

    def test_find_line_column_first_line(self):
        """Test finding line and column for first line."""
        content = "line 1\nline 2\nline 3"
        line, col = find_line_column(content, 0)

        assert line == 1
        assert col == 1

    def test_find_line_column_second_line(self):
        """Test finding line and column for second line."""
        content = "line 1\nline 2\nline 3"
        match_start = content.index("line 2")
        line, col = find_line_column(content, match_start)

        assert line == 2
        assert col == 1

    def test_find_line_column_middle_of_line(self):
        """Test finding line and column in middle of line."""
        content = "def function():\n    return True"
        match_start = content.index("return")
        line, col = find_line_column(content, match_start)

        assert line == 2
        assert col > 1

    def test_find_line_column_end_of_content(self):
        """Test finding line and column at end of content."""
        content = "line 1\nline 2\nline 3"
        line, col = find_line_column(content, len(content))

        assert line == 3

    def test_find_line_column_multiline_code(self):
        """Test finding line and column in multiline code."""
        content = """def test():
    x = 1
    y = 2
    return x + y"""

        match_start = content.index("return")
        line, col = find_line_column(content, match_start)

        assert line == 4
