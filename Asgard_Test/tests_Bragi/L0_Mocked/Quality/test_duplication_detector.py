"""
Tests for Heimdall Duplication Detector Service

Unit tests for code duplication detection and analysis.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Bragi.Quality.models.duplication_models import (
    CloneFamily,
    CodeBlock,
    DuplicationConfig,
    DuplicationSeverity,
    DuplicationType,
)
from Asgard.Bragi.Quality.services.duplication_detector import DuplicationDetector


class TestDuplicationDetector:
    """Tests for DuplicationDetector class."""

    def test_init_with_default_config(self):
        """Test initializing with default configuration."""
        detector = DuplicationDetector()
        assert detector.config is not None
        assert detector.config.min_block_size == 6
        assert detector.config.similarity_threshold == 0.85

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        config = DuplicationConfig(min_block_size=4, similarity_threshold=0.9)
        detector = DuplicationDetector(config)
        assert detector.config.min_block_size == 4
        assert detector.config.similarity_threshold == 0.9

    def test_analyze_nonexistent_path(self):
        """Test analyzing a path that doesn't exist."""
        detector = DuplicationDetector()
        with pytest.raises(FileNotFoundError):
            detector.analyze(Path("/nonexistent/path"))

    def test_analyze_empty_directory(self):
        """Test analyzing an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = DuplicationDetector()
            result = detector.analyze(Path(tmpdir))

            assert result.total_files_scanned == 0
            assert result.total_clone_families == 0
            assert result.has_duplicates is False

    def test_analyze_no_duplicates(self):
        """Test analyzing unique code with no duplicates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create files with unique code
            (tmpdir_path / "file1.py").write_text('''
def function_one():
    x = 1
    y = 2
    z = 3
    return x + y + z

def function_two():
    a = 10
    b = 20
    return a * b
''')

            config = DuplicationConfig(min_block_size=4)
            detector = DuplicationDetector(config)
            result = detector.analyze(tmpdir_path)

            assert result.total_files_scanned == 1
            assert result.has_duplicates is False

    def test_analyze_exact_duplicates(self):
        """Test detecting exact duplicate code blocks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a file with exact duplicates
            (tmpdir_path / "duplicates.py").write_text('''
def function_a():
    x = 1
    y = 2
    z = 3
    w = 4
    v = 5
    return x + y + z + w + v

def function_b():
    x = 1
    y = 2
    z = 3
    w = 4
    v = 5
    return x + y + z + w + v
''')

            config = DuplicationConfig(min_block_size=4, similarity_threshold=0.8)
            detector = DuplicationDetector(config)
            result = detector.analyze(tmpdir_path)

            assert result.total_files_scanned == 1
            # Should find the duplicated block

    def test_analyze_similar_code(self):
        """Test detecting similar (not exact) code blocks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create files with similar code
            (tmpdir_path / "similar.py").write_text('''
def calculate_total(items):
    total = 0
    for item in items:
        total += item.price
    return total

def calculate_sum(products):
    sum_value = 0
    for product in products:
        sum_value += product.cost
    return sum_value
''')

            config = DuplicationConfig(min_block_size=4, similarity_threshold=0.7)
            detector = DuplicationDetector(config)
            result = detector.analyze(tmpdir_path)

            assert result.total_files_scanned == 1

    def test_analyze_cross_file_duplicates(self):
        """Test detecting duplicates across multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            duplicate_code = '''
def duplicate_function():
    x = 1
    y = 2
    z = 3
    w = 4
    v = 5
    return x + y + z + w + v
'''
            (tmpdir_path / "file1.py").write_text(duplicate_code)
            (tmpdir_path / "file2.py").write_text(duplicate_code)

            config = DuplicationConfig(min_block_size=4)
            detector = DuplicationDetector(config)
            result = detector.analyze(tmpdir_path)

            assert result.total_files_scanned == 2

    def test_analyze_single_file(self):
        """Test analyzing a single file directly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "single.py").write_text('''
def func():
    x = 1
    y = 2
    z = 3
    return x + y + z
''')
            file_path = tmpdir_path / "single.py"

            detector = DuplicationDetector()
            result = detector.analyze_single_file(file_path)

            assert result.total_files_scanned == 1


class TestCloneFamily:
    """Tests for CloneFamily model."""

    def test_calculate_severity_low(self):
        """Test severity calculation for low (2 blocks)."""
        assert CloneFamily.calculate_severity(2) == DuplicationSeverity.LOW

    def test_calculate_severity_moderate(self):
        """Test severity calculation for moderate (3-4 blocks)."""
        assert CloneFamily.calculate_severity(3) == DuplicationSeverity.MODERATE
        assert CloneFamily.calculate_severity(4) == DuplicationSeverity.MODERATE

    def test_calculate_severity_high(self):
        """Test severity calculation for high (5-7 blocks)."""
        assert CloneFamily.calculate_severity(5) == DuplicationSeverity.HIGH
        assert CloneFamily.calculate_severity(7) == DuplicationSeverity.HIGH

    def test_calculate_severity_critical(self):
        """Test severity calculation for critical (8+ blocks)."""
        assert CloneFamily.calculate_severity(8) == DuplicationSeverity.CRITICAL
        assert CloneFamily.calculate_severity(15) == DuplicationSeverity.CRITICAL

    def test_add_block(self):
        """Test adding blocks to a clone family."""
        family = CloneFamily(
            match_type=DuplicationType.EXACT,
            severity=DuplicationSeverity.LOW,
        )

        block = CodeBlock(
            file_path="/test/file.py",
            relative_path="file.py",
            start_line=1,
            end_line=10,
            content="test content",
            hash_value="abc123",
            line_count=10,
        )

        family.add_block(block)

        assert family.block_count == 1
        assert family.total_duplicated_lines == 10
        assert family.representative == block


class TestCodeBlock:
    """Tests for CodeBlock model."""

    def test_location_property(self):
        """Test the location property."""
        block = CodeBlock(
            file_path="/full/path/file.py",
            relative_path="path/file.py",
            start_line=10,
            end_line=20,
            content="content",
            hash_value="hash123",
            line_count=11,
        )

        assert block.location == "path/file.py:10-20"
