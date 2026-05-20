"""
Tests for Heimdall OOP Analyzer Service

Unit tests for object-oriented metrics analysis.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Bragi.OOP.models.oop_models import OOPConfig
from Asgard.Bragi.OOP.services.oop_analyzer import OOPAnalyzer


class TestOOPAnalyzer:
    """Tests for OOPAnalyzer class."""

    def test_init_with_default_config(self):
        """Test initializing with default configuration."""
        analyzer = OOPAnalyzer()
        assert analyzer.config is not None
        assert analyzer.config.cbo_threshold == 10

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        config = OOPConfig(cbo_threshold=10, lcom_threshold=0.5)
        analyzer = OOPAnalyzer(config)
        assert analyzer.config.cbo_threshold == 10
        assert analyzer.config.lcom_threshold == 0.5

    def test_analyze_nonexistent_path(self):
        """Test analyzing a path that doesn't exist."""
        analyzer = OOPAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.analyze(Path("/nonexistent/path"))

    def test_analyze_empty_directory(self):
        """Test analyzing an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = OOPAnalyzer()
            result = analyzer.analyze(Path(tmpdir))

            assert result.total_classes_analyzed == 0
            assert result.class_metrics == []

    def test_analyze_simple_class(self):
        """Test analyzing a simple class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''
class SimpleClass:
    def __init__(self):
        self.value = 0

    def get_value(self):
        return self.value

    def set_value(self, value):
        self.value = value
'''
            (tmpdir_path / "simple.py").write_text(code)

            analyzer = OOPAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            assert result.total_classes_analyzed == 1
            assert len(result.class_metrics) == 1
            assert result.class_metrics[0].class_name == "SimpleClass"

    def test_analyze_class_with_inheritance(self):
        """Test analyzing a class with inheritance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''
class BaseClass:
    def base_method(self):
        pass

class ChildClass(BaseClass):
    def child_method(self):
        pass

class GrandchildClass(ChildClass):
    def grandchild_method(self):
        pass
'''
            (tmpdir_path / "hierarchy.py").write_text(code)

            analyzer = OOPAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            assert result.total_classes_analyzed == 3

            # Find grandchild class
            grandchild = next(
                (m for m in result.class_metrics if m.class_name == "GrandchildClass"),
                None
            )
            assert grandchild is not None
            # DIT should be at least 1 (ChildClass parent)
            assert grandchild.dit >= 1

    def test_analyze_class_with_coupling(self):
        """Test analyzing classes with coupling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''
class ServiceA:
    def do_work(self):
        return "work done"

class ServiceB:
    def __init__(self, service_a: ServiceA):
        self.service_a = service_a

    def use_service(self):
        return self.service_a.do_work()
'''
            (tmpdir_path / "coupled.py").write_text(code)

            analyzer = OOPAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            assert result.total_classes_analyzed == 2

            # ServiceB should have coupling to ServiceA
            service_b = next(
                (m for m in result.class_metrics if m.class_name == "ServiceB"),
                None
            )
            assert service_b is not None
            assert service_b.efferent_coupling >= 1

    def test_generate_text_report(self):
        """Test generating text format report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''
class TestClass:
    def method(self):
        pass
'''
            (tmpdir_path / "test.py").write_text(code)

            analyzer = OOPAnalyzer()
            result = analyzer.analyze(tmpdir_path)
            report = analyzer.generate_report(result, "text")

            assert "OOP" in report or "METRICS" in report
            assert "Classes Analyzed" in report or "TestClass" in report

    def test_generate_json_report(self):
        """Test generating JSON format report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''
class TestClass:
    def method(self):
        pass
'''
            (tmpdir_path / "test.py").write_text(code)

            analyzer = OOPAnalyzer()
            result = analyzer.analyze(tmpdir_path)
            report = analyzer.generate_report(result, "json")

            import json
            data = json.loads(report)
            assert "classes" in data
            assert len(data["classes"]) == 1

    def test_get_god_classes_returns_list(self):
        """Test get_god_classes returns a list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "test.py").write_text(
                "class TestClass:\n    def method(self):\n        pass\n"
            )

            analyzer = OOPAnalyzer()
            god_classes = analyzer.get_god_classes(tmpdir_path)
            assert isinstance(god_classes, list)
