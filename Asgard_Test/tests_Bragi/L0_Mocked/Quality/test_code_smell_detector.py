"""
Tests for Heimdall Code Smell Detector Service

Unit tests for code smell detection and analysis.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Bragi.Quality.models.smell_models import (
    CodeSmell,
    SmellCategory,
    SmellConfig,
    SmellReport,
    SmellSeverity,
    SmellThresholds,
)
from Asgard.Bragi.Quality.services.code_smell_detector import CodeSmellDetector


class TestCodeSmellDetector:
    """Tests for CodeSmellDetector class."""

    def test_init_with_default_config(self):
        """Test initializing with default configuration."""
        detector = CodeSmellDetector()
        assert detector.config is not None
        assert detector.config.thresholds.long_method_lines == 50
        assert detector.config.thresholds.large_class_methods == 20

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        thresholds = SmellThresholds(
            long_method_lines=30,
            large_class_methods=15,
        )
        config = SmellConfig(thresholds=thresholds)
        detector = CodeSmellDetector(config)
        assert detector.config.thresholds.long_method_lines == 30
        assert detector.config.thresholds.large_class_methods == 15

    def test_analyze_nonexistent_path(self):
        """Test analyzing a path that doesn't exist."""
        detector = CodeSmellDetector()
        with pytest.raises(FileNotFoundError):
            detector.analyze(Path("/nonexistent/path"))

    def test_analyze_empty_directory(self):
        """Test analyzing an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = CodeSmellDetector()
            result = detector.analyze(Path(tmpdir))

            assert result.total_smells == 0
            assert result.has_smells is False

    def test_analyze_clean_code(self):
        """Test analyzing well-structured code with no smells."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "clean.py").write_text('''
def calculate_sum(a, b):
    """Add two numbers."""
    return a + b

def calculate_product(a, b):
    """Multiply two numbers."""
    return a * b

class Calculator:
    """Simple calculator class."""

    def add(self, a, b):
        """Add two numbers."""
        return a + b

    def subtract(self, a, b):
        """Subtract b from a."""
        return a - b
''')

            detector = CodeSmellDetector()
            result = detector.analyze(tmpdir_path)

            assert result.has_smells is False

    def test_detect_long_method(self):
        """Test detecting long method smell."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a method with 60 lines (exceeds default 50)
            long_method_code = '''
def very_long_method():
    """This method is too long."""
    x = 1
    y = 2
    z = 3
''' + '    result = x + y + z\n' * 60 + '''    return result
'''
            (tmpdir_path / "long_method.py").write_text(long_method_code)

            config = SmellConfig(
                thresholds=SmellThresholds(long_method_lines=50),
            )
            detector = CodeSmellDetector(config)
            result = detector.analyze(tmpdir_path)

            # Should detect Long Method smell
            long_method_smells = [s for s in result.detected_smells if s.name == "Long Method"]
            assert len(long_method_smells) >= 1

    def test_detect_long_parameter_list(self):
        """Test detecting long parameter list smell."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "long_params.py").write_text('''
def function_with_too_many_params(a, b, c, d, e, f, g, h, i):
    """This function has too many parameters."""
    return a + b + c + d + e + f + g + h + i
''')

            config = SmellConfig(
                thresholds=SmellThresholds(long_parameter_list=6),
            )
            detector = CodeSmellDetector(config)
            result = detector.analyze(tmpdir_path)

            # Should detect Long Parameter List smell
            param_smells = [s for s in result.detected_smells if s.name == "Long Parameter List"]
            assert len(param_smells) >= 1

    def test_detect_large_class(self):
        """Test detecting large class smell."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a class with many methods
            methods = "\n".join([f'''
    def method_{i}(self):
        """Method {i}."""
        return {i}
''' for i in range(25)])

            (tmpdir_path / "large_class.py").write_text(f'''
class VeryLargeClass:
    """This class has too many methods."""
{methods}
''')

            config = SmellConfig(
                thresholds=SmellThresholds(large_class_methods=20),
            )
            detector = CodeSmellDetector(config)
            result = detector.analyze(tmpdir_path)

            # Should detect Large Class smell
            large_class_smells = [s for s in result.detected_smells if s.name == "Large Class"]
            assert len(large_class_smells) >= 1

    def test_detect_dead_code(self):
        """Test detecting dead code (pass-only methods)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "dead_code.py").write_text('''
def unused_function():
    pass

class SomeClass:
    def dead_method(self):
        pass
''')

            detector = CodeSmellDetector()
            result = detector.analyze(tmpdir_path)

            # Should detect Dead Code smell
            dead_code_smells = [s for s in result.detected_smells if s.name == "Dead Code"]
            assert len(dead_code_smells) >= 1

    def test_detect_complex_conditional(self):
        """Test detecting complex conditional smell."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "complex_conditional.py").write_text('''
def check_conditions(a, b, c, d, e, f):
    if a > 0 and b > 0 and c > 0 and d > 0 and e > 0 and f > 0:
        return True
    return False
''')

            config = SmellConfig(
                thresholds=SmellThresholds(complex_conditional_operators=3),
            )
            detector = CodeSmellDetector(config)
            result = detector.analyze(tmpdir_path)

            # Should detect Complex Conditional smell
            complex_cond_smells = [s for s in result.detected_smells if s.name == "Complex Conditional"]
            assert len(complex_cond_smells) >= 1

    def test_severity_filtering(self):
        """Test filtering smells by severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create code with smells
            (tmpdir_path / "smells.py").write_text('''
def pass_only():
    pass
''')

            # Filter for only HIGH and above
            config = SmellConfig(
                severity_filter=SmellSeverity.HIGH,
            )
            detector = CodeSmellDetector(config)
            result = detector.analyze(tmpdir_path)

            # Dead code is LOW severity, should be filtered out
            for smell in result.detected_smells:
                sev = smell.severity if isinstance(smell.severity, str) else smell.severity.value
                assert sev in [SmellSeverity.HIGH.value, SmellSeverity.CRITICAL.value]

    def test_category_filtering(self):
        """Test filtering smells by category."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "smells.py").write_text('''
def pass_only():
    pass

def too_many_params(a, b, c, d, e, f, g, h):
    return a + b + c + d + e + f + g + h
''')

            # Only check bloaters category
            config = SmellConfig(
                smell_categories=["bloaters"],
            )
            detector = CodeSmellDetector(config)
            result = detector.analyze(tmpdir_path)

            # Should only have bloater smells (no dispensables like dead code)
            for smell in result.detected_smells:
                cat = smell.category if isinstance(smell.category, str) else smell.category.value
                assert cat == SmellCategory.BLOATERS.value

    def test_analyze_single_file(self):
        """Test analyzing a single file directly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "single.py").write_text('''
def simple_function():
    return 42
''')
            file_path = tmpdir_path / "single.py"

            detector = CodeSmellDetector()
            result = detector.analyze_single_file(file_path)

            assert result is not None

    def test_generate_text_report(self):
        """Test generating text report."""
        detector = CodeSmellDetector()
        report = SmellReport(
            scan_path="/test/path",
            total_smells=1,
        )

        text = detector.generate_report(report, "text")
        assert "CODE SMELLS REPORT" in text
        assert "/test/path" in text

    def test_generate_json_report(self):
        """Test generating JSON report."""
        import json

        detector = CodeSmellDetector()
        report = SmellReport(
            scan_path="/test/path",
            total_smells=0,
        )

        json_str = detector.generate_report(report, "json")
        data = json.loads(json_str)
        assert data["scan_info"]["scan_path"] == "/test/path"
        assert data["summary"]["total_smells"] == 0

    def test_generate_markdown_report(self):
        """Test generating Markdown report."""
        detector = CodeSmellDetector()
        report = SmellReport(
            scan_path="/test/path",
            total_smells=0,
        )

        md = detector.generate_report(report, "markdown")
        assert "# Code Smells Report" in md
        assert "/test/path" in md

    def test_generate_html_report(self):
        """Test generating HTML report."""
        detector = CodeSmellDetector()
        report = SmellReport(
            scan_path="/test/path",
            total_smells=0,
        )

        html = detector.generate_report(report, "html")
        assert "<!DOCTYPE html>" in html
        assert "/test/path" in html


class TestSmellReport:
    """Tests for SmellReport model."""

    def test_add_smell(self):
        """Test adding a smell to the report."""
        report = SmellReport(scan_path="/test")
        smell = CodeSmell(
            name="Test Smell",
            category=SmellCategory.BLOATERS,
            severity=SmellSeverity.MEDIUM,
            file_path="/test/file.py",
            line_number=10,
            description="Test description",
            evidence="Test evidence",
            remediation="Test remediation",
            confidence=0.9,
        )

        report.add_smell(smell)

        assert report.total_smells == 1
        assert report.smells_by_severity.get("medium", 0) == 1
        assert report.smells_by_category.get("bloaters", 0) == 1

    def test_has_smells(self):
        """Test has_smells property."""
        report = SmellReport(scan_path="/test")
        assert report.has_smells is False

        smell = CodeSmell(
            name="Test",
            category=SmellCategory.BLOATERS,
            severity=SmellSeverity.LOW,
            file_path="/test/file.py",
            line_number=1,
            description="Test",
            evidence="Test",
            remediation="Test",
        )
        report.add_smell(smell)
        assert report.has_smells is True

    def test_critical_count(self):
        """Test critical_count property."""
        report = SmellReport(scan_path="/test")
        assert report.critical_count == 0

        smell = CodeSmell(
            name="Critical Smell",
            category=SmellCategory.BLOATERS,
            severity=SmellSeverity.CRITICAL,
            file_path="/test/file.py",
            line_number=1,
            description="Test",
            evidence="Test",
            remediation="Test",
        )
        report.add_smell(smell)
        assert report.critical_count == 1

    def test_get_smells_by_severity(self):
        """Test get_smells_by_severity method."""
        report = SmellReport(scan_path="/test")

        smell1 = CodeSmell(
            name="High1",
            category=SmellCategory.BLOATERS,
            severity=SmellSeverity.HIGH,
            file_path="/test/file.py",
            line_number=1,
            description="Test",
            evidence="Test",
            remediation="Test",
        )
        smell2 = CodeSmell(
            name="Low1",
            category=SmellCategory.BLOATERS,
            severity=SmellSeverity.LOW,
            file_path="/test/file.py",
            line_number=2,
            description="Test",
            evidence="Test",
            remediation="Test",
        )

        report.add_smell(smell1)
        report.add_smell(smell2)

        high_smells = report.get_smells_by_severity(SmellSeverity.HIGH)
        assert len(high_smells) == 1
        assert high_smells[0].name == "High1"


class TestCodeSmell:
    """Tests for CodeSmell model."""

    def test_location_property(self):
        """Test the location property."""
        smell = CodeSmell(
            name="Test",
            category=SmellCategory.BLOATERS,
            severity=SmellSeverity.LOW,
            file_path="/full/path/to/file.py",
            line_number=42,
            description="Test",
            evidence="Test",
            remediation="Test",
        )

        assert smell.location == "file.py:42"


class TestSmellThresholds:
    """Tests for SmellThresholds model."""

    def test_default_values(self):
        """Test default threshold values."""
        thresholds = SmellThresholds()
        assert thresholds.long_method_lines == 50
        assert thresholds.long_method_statements == 30
        assert thresholds.large_class_methods == 20
        assert thresholds.large_class_lines == 500
        assert thresholds.long_parameter_list == 6

    def test_custom_values(self):
        """Test custom threshold values."""
        thresholds = SmellThresholds(
            long_method_lines=100,
            large_class_methods=10,
        )
        assert thresholds.long_method_lines == 100
        assert thresholds.large_class_methods == 10


class TestSmellConfig:
    """Tests for SmellConfig model."""

    def test_default_config(self):
        """Test default configuration."""
        config = SmellConfig()
        assert config.thresholds is not None
        assert config.severity_filter == SmellSeverity.LOW
        assert config.smell_categories is None
        assert config.include_tests is False

    def test_get_enabled_categories_all(self):
        """Test getting all categories when none specified."""
        config = SmellConfig()
        categories = config.get_enabled_categories()
        assert len(categories) == 5
        assert SmellCategory.BLOATERS.value in categories
        assert SmellCategory.DISPENSABLES.value in categories

    def test_get_enabled_categories_specific(self):
        """Test getting specific categories."""
        config = SmellConfig(smell_categories=["bloaters", "couplers"])
        categories = config.get_enabled_categories()
        assert categories == ["bloaters", "couplers"]
