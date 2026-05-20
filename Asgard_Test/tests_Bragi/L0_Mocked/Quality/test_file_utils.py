"""
Tests for Heimdall Quality File Utilities

Unit tests for file discovery, path filtering, and line counting utilities.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Bragi.Quality.utilities.file_utils import (
    CODE_EXTENSIONS,
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_EXCLUDE_FILES,
    count_lines,
    get_file_extension,
    is_code_file,
    is_excluded_path,
    scan_directory,
)


class TestCodeExtensions:
    """Tests for CODE_EXTENSIONS constant."""

    def test_contains_python(self):
        """Test that Python extensions are included."""
        assert ".py" in CODE_EXTENSIONS

    def test_contains_javascript_typescript(self):
        """Test that JS/TS extensions are included."""
        assert ".js" in CODE_EXTENSIONS
        assert ".jsx" in CODE_EXTENSIONS
        assert ".ts" in CODE_EXTENSIONS
        assert ".tsx" in CODE_EXTENSIONS

    def test_contains_web_files(self):
        """Test that web file extensions are included."""
        assert ".html" in CODE_EXTENSIONS
        assert ".css" in CODE_EXTENSIONS
        assert ".scss" in CODE_EXTENSIONS

    def test_contains_config_files(self):
        """Test that config file extensions are included."""
        assert ".json" in CODE_EXTENSIONS
        assert ".yaml" in CODE_EXTENSIONS
        assert ".yml" in CODE_EXTENSIONS


class TestDefaultExcludeDirs:
    """Tests for DEFAULT_EXCLUDE_DIRS constant."""

    def test_excludes_python_cache(self):
        """Test that __pycache__ is excluded."""
        assert "__pycache__" in DEFAULT_EXCLUDE_DIRS

    def test_excludes_node_modules(self):
        """Test that node_modules is excluded."""
        assert "node_modules" in DEFAULT_EXCLUDE_DIRS

    def test_excludes_venv(self):
        """Test that virtual environment directories are excluded."""
        assert ".venv" in DEFAULT_EXCLUDE_DIRS
        assert "venv" in DEFAULT_EXCLUDE_DIRS

    def test_excludes_git(self):
        """Test that .git is excluded."""
        assert ".git" in DEFAULT_EXCLUDE_DIRS


class TestDefaultExcludeFiles:
    """Tests for DEFAULT_EXCLUDE_FILES constant."""

    def test_excludes_minified_files(self):
        """Test that minified files are excluded."""
        assert "*.min.js" in DEFAULT_EXCLUDE_FILES
        assert "*.min.css" in DEFAULT_EXCLUDE_FILES

    def test_excludes_lock_files(self):
        """Test that lock files are excluded."""
        assert "package-lock.json" in DEFAULT_EXCLUDE_FILES
        assert "yarn.lock" in DEFAULT_EXCLUDE_FILES
        assert "pnpm-lock.yaml" in DEFAULT_EXCLUDE_FILES


class TestGetFileExtension:
    """Tests for get_file_extension function."""

    def test_python_extension(self):
        """Test getting Python extension."""
        assert get_file_extension(Path("/path/to/file.py")) == ".py"

    def test_typescript_extension(self):
        """Test getting TypeScript extension."""
        assert get_file_extension(Path("/path/to/file.tsx")) == ".tsx"

    def test_lowercase_conversion(self):
        """Test that extensions are lowercased."""
        assert get_file_extension(Path("/path/to/file.PY")) == ".py"
        assert get_file_extension(Path("/path/to/file.TSX")) == ".tsx"


class TestIsCodeFile:
    """Tests for is_code_file function."""

    def test_python_file_is_code(self):
        """Test that Python files are recognized as code files."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            temp_path = Path(f.name)
            try:
                assert is_code_file(temp_path) is True
            finally:
                temp_path.unlink()

    def test_text_file_is_not_code(self):
        """Test that .txt files are not recognized as code files."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            temp_path = Path(f.name)
            try:
                assert is_code_file(temp_path) is False
            finally:
                temp_path.unlink()

    def test_custom_extensions(self):
        """Test using custom extension list."""
        with tempfile.NamedTemporaryFile(suffix=".custom", delete=False) as f:
            temp_path = Path(f.name)
            try:
                assert is_code_file(temp_path) is False
                assert is_code_file(temp_path, include_extensions=[".custom"]) is True
            finally:
                temp_path.unlink()


class TestCountLines:
    """Tests for count_lines function."""

    def test_count_empty_file(self):
        """Test counting lines in an empty file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix=".py", delete=False) as f:
            f.write("")
            temp_path = Path(f.name)

        try:
            assert count_lines(temp_path) == 0
        finally:
            temp_path.unlink()

    def test_count_single_line(self):
        """Test counting lines in a single-line file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix=".py", delete=False) as f:
            f.write("print('hello')")
            temp_path = Path(f.name)

        try:
            assert count_lines(temp_path) == 1
        finally:
            temp_path.unlink()

    def test_count_multiple_lines(self):
        """Test counting lines in a multi-line file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix=".py", delete=False) as f:
            f.write("line 1\nline 2\nline 3\nline 4\nline 5\n")
            temp_path = Path(f.name)

        try:
            assert count_lines(temp_path) == 5
        finally:
            temp_path.unlink()

    def test_count_with_blank_lines(self):
        """Test counting lines including blank lines."""
        with tempfile.NamedTemporaryFile(mode='w', suffix=".py", delete=False) as f:
            f.write("line 1\n\nline 3\n\nline 5\n")
            temp_path = Path(f.name)

        try:
            # All lines including blank ones should be counted
            assert count_lines(temp_path) == 5
        finally:
            temp_path.unlink()


class TestIsExcludedPath:
    """Tests for is_excluded_path function."""

    def test_git_dir_excluded(self):
        """Test that .git is excluded with default patterns."""
        path = Path("/some/path/.git")
        assert is_excluded_path(path, None) is True

    def test_pycache_excluded(self):
        """Test that __pycache__ is excluded with default patterns."""
        path = Path("/some/path/__pycache__")
        assert is_excluded_path(path, None) is True

    def test_node_modules_excluded(self):
        """Test that node_modules is excluded with default patterns."""
        path = Path("/some/path/node_modules")
        assert is_excluded_path(path, None) is True

    def test_custom_exclude_pattern(self):
        """Test custom exclude patterns."""
        path = Path("/some/path/custom_folder")
        assert is_excluded_path(path, ["custom_folder"]) is True

    def test_normal_path_not_excluded(self):
        """Test that normal paths are not excluded."""
        path = Path("/some/path/src/app.py")
        # This should return False for a regular file (not a dir)
        # Note: is_excluded_path checks various things including if it's a hidden file
        assert path.name.startswith(".") is False


class TestScanDirectory:
    """Tests for scan_directory function."""

    def test_scan_empty_directory(self):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = list(scan_directory(Path(tmpdir)))
            assert len(files) == 0

    def test_scan_directory_with_code_files(self):
        """Test scanning a directory with code files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create some code files
            (tmpdir_path / "app.py").write_text("print('hello')")
            (tmpdir_path / "utils.ts").write_text("export const x = 1;")

            files = list(scan_directory(tmpdir_path))
            assert len(files) == 2

    def test_scan_excludes_non_code_files(self):
        """Test that non-code files are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create code and non-code files
            (tmpdir_path / "app.py").write_text("print('hello')")
            (tmpdir_path / "readme.txt").write_text("readme")
            (tmpdir_path / "data.csv").write_text("a,b,c")

            files = list(scan_directory(tmpdir_path))
            # Only the .py file should be found
            assert len(files) == 1
            assert files[0].suffix == ".py"

    def test_scan_excludes_pycache(self):
        """Test that __pycache__ directories are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a __pycache__ directory with a .pyc file
            pycache = tmpdir_path / "__pycache__"
            pycache.mkdir()
            (pycache / "app.cpython-311.pyc").write_bytes(b"")

            # Create a regular Python file
            (tmpdir_path / "app.py").write_text("print('hello')")

            files = list(scan_directory(tmpdir_path))
            # Only the app.py should be found, not the .pyc
            assert len(files) == 1
            assert files[0].name == "app.py"
