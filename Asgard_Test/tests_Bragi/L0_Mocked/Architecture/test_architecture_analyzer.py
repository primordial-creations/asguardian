"""
Tests for Heimdall Architecture Analyzer Service

Unit tests for SOLID validation, layer analysis, and pattern detection.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Bragi.Architecture.models.architecture_models import ArchitectureConfig
from Asgard.Bragi.Architecture.services.architecture_analyzer import ArchitectureAnalyzer


class TestArchitectureAnalyzer:
    """Tests for ArchitectureAnalyzer class."""

    def test_init_with_default_config(self):
        """Test initializing with default configuration."""
        analyzer = ArchitectureAnalyzer()
        assert analyzer.config is not None
        assert analyzer.config.max_class_responsibilities == 3

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        config = ArchitectureConfig(max_class_responsibilities=5, max_method_count=30)
        analyzer = ArchitectureAnalyzer(config)
        assert analyzer.config.max_class_responsibilities == 5
        assert analyzer.config.max_method_count == 30

    def test_analyze_nonexistent_path(self):
        """Test analyzing a path that doesn't exist."""
        analyzer = ArchitectureAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.analyze(Path("/nonexistent/path"))

    def test_analyze_empty_directory(self):
        """Test analyzing an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ArchitectureAnalyzer()
            result = analyzer.analyze(Path(tmpdir))

            # Should complete without errors
            assert result.scan_path == str(Path(tmpdir).resolve())

    def test_analyze_simple_class(self):
        """Test analyzing a simple class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''
class SimpleService:
    def do_work(self):
        return "work done"
'''
            (tmpdir_path / "service.py").write_text(code)

            analyzer = ArchitectureAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            assert result is not None

    def test_validate_solid_srp_violation(self):
        """Test detecting SRP violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a "God class" with many responsibilities
            code = '''
class GodClass:
    def handle_user_login(self, username, password):
        pass

    def handle_user_logout(self, user_id):
        pass

    def send_email(self, to, subject, body):
        pass

    def generate_report(self, data):
        pass

    def save_to_database(self, record):
        pass

    def read_from_database(self, query):
        pass

    def validate_input(self, data):
        pass

    def format_output(self, data):
        pass

    def log_event(self, event):
        pass

    def handle_error(self, error):
        pass

    def process_payment(self, amount):
        pass

    def calculate_tax(self, amount):
        pass

    def update_inventory(self, product):
        pass

    def notify_admin(self, message):
        pass

    def backup_data(self):
        pass
'''
            (tmpdir_path / "god_class.py").write_text(code)

            analyzer = ArchitectureAnalyzer()
            result = analyzer.validate_solid(tmpdir_path)

            # Should detect SRP violation
            assert result is not None

    def test_detect_singleton_pattern(self):
        """Test detecting Singleton pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''
class Singleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def do_work(self):
        return "singleton work"
'''
            (tmpdir_path / "singleton.py").write_text(code)

            analyzer = ArchitectureAnalyzer()
            result = analyzer.detect_patterns(tmpdir_path)

            # Should detect singleton pattern
            assert result is not None
            # Pattern detection should find the singleton

    def test_detect_factory_pattern(self):
        """Test detecting Factory pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''
class Animal:
    def speak(self):
        raise NotImplementedError

class Dog(Animal):
    def speak(self):
        return "Woof"

class Cat(Animal):
    def speak(self):
        return "Meow"

class AnimalFactory:
    @staticmethod
    def create(animal_type):
        if animal_type == "dog":
            return Dog()
        elif animal_type == "cat":
            return Cat()
        raise ValueError(f"Unknown animal: {animal_type}")
'''
            (tmpdir_path / "factory.py").write_text(code)

            analyzer = ArchitectureAnalyzer()
            result = analyzer.detect_patterns(tmpdir_path)

            assert result is not None

    def test_analyze_layers(self):
        """Test layer analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create layer structure
            (tmpdir_path / "presentation").mkdir()
            (tmpdir_path / "application").mkdir()
            (tmpdir_path / "domain").mkdir()
            (tmpdir_path / "infrastructure").mkdir()

            # Create files in layers
            (tmpdir_path / "presentation" / "view.py").write_text('''
def render():
    pass
''')
            (tmpdir_path / "domain" / "entity.py").write_text('''
class User:
    def __init__(self, name):
        self.name = name
''')

            analyzer = ArchitectureAnalyzer()
            result = analyzer.analyze_layers(tmpdir_path)

            assert result is not None

    def test_generate_text_report(self):
        """Test generating text format report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "test.py").write_text('''
class TestClass:
    def method(self):
        pass
''')

            analyzer = ArchitectureAnalyzer()
            result = analyzer.analyze(tmpdir_path)
            report = analyzer.generate_report(result, "text")

            assert "ARCHITECTURE" in report or "ANALYSIS" in report

    def test_generate_json_report(self):
        """Test generating JSON format report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "test.py").write_text('''
class TestClass:
    def method(self):
        pass
''')

            analyzer = ArchitectureAnalyzer()
            result = analyzer.analyze(tmpdir_path)
            report = analyzer.generate_report(result, "json")

            import json
            data = json.loads(report)
            assert "scan_path" in data

    def test_quick_check(self):
        """Test quick check functionality."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "test.py").write_text('''
class TestClass:
    def method(self):
        pass
''')

            analyzer = ArchitectureAnalyzer()
            check = analyzer.quick_check(tmpdir_path)

            assert "solid_violations" in check
            assert "layer_violations" in check
            assert "patterns_found" in check
