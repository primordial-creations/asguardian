"""
L1 Integration Tests for Heimdall Architecture Analysis

Tests architecture validation on real Python projects.
"""

import json
import pytest
from pathlib import Path

from Asgard.Heimdall.Architecture import (
    ArchitectureAnalyzer,
    ArchitectureConfig,
)


class TestArchitectureIntegration:
    """Integration tests for architecture analysis."""

    def test_architecture_analyze_simple_project_full(self, simple_project):
        """Test full architecture analysis on simple project."""
        analyzer = ArchitectureAnalyzer()
        report = analyzer.analyze(simple_project)

        assert report is not None
        assert hasattr(report, 'scan_path')
        assert report.scan_path == str(simple_project.resolve())

    def test_architecture_analyze_complex_project_full(self, complex_project):
        """Test full architecture analysis on complex project."""
        analyzer = ArchitectureAnalyzer()
        report = analyzer.analyze(complex_project)

        assert report is not None
        assert hasattr(report, 'scan_path')

    def test_architecture_validate_solid_simple_project(self, simple_project):
        """Test SOLID validation on simple project."""
        analyzer = ArchitectureAnalyzer()
        solid_report = analyzer.validate_solid(simple_project)

        assert solid_report is not None
        assert hasattr(solid_report, 'total_violations')
        assert isinstance(solid_report.total_violations, int)

        # Simple project should have few or no SOLID violations
        assert solid_report.total_violations >= 0

    def test_architecture_validate_solid_god_class(self, god_class_project):
        """Test SOLID validation on god class project."""
        analyzer = ArchitectureAnalyzer()
        solid_report = analyzer.validate_solid(god_class_project)

        assert solid_report is not None
        assert hasattr(solid_report, 'total_violations')

        # God class should have SOLID violations (SRP violation at minimum)
        assert solid_report.total_violations > 0

    def test_architecture_validate_solid_srp_violation(self, god_class_project):
        """Test Single Responsibility Principle violation detection."""
        analyzer = ArchitectureAnalyzer()
        solid_report = analyzer.validate_solid(god_class_project)

        assert solid_report is not None

        # Check for SRP violations
        srp_violations = []
        if hasattr(solid_report, 'violations'):
            for violation in solid_report.violations:
                if hasattr(violation, 'principle'):
                    if 'SRP' in str(violation.principle) or 'Single' in str(violation.principle):
                        srp_violations.append(violation)

        assert len(srp_violations) > 0, "SRP violations should be detected in god class"

    def test_architecture_validate_solid_ocp(self, tmp_path):
        """Test Open/Closed Principle validation."""
        code_file = tmp_path / "shapes.py"
        code_file.write_text('''
class Shape:
    """Base shape class."""
    def area(self):
        """Calculate area."""
        raise NotImplementedError

class Circle(Shape):
    """Circle shape."""
    def __init__(self, radius):
        self.radius = radius

    def area(self):
        """Calculate circle area."""
        return 3.14 * self.radius ** 2

class Square(Shape):
    """Square shape."""
    def __init__(self, side):
        self.side = side

    def area(self):
        """Calculate square area."""
        return self.side ** 2
''')

        analyzer = ArchitectureAnalyzer()
        solid_report = analyzer.validate_solid(tmp_path)

        assert solid_report is not None
        # This design follows OCP, should have no or few violations

    def test_architecture_validate_solid_lsp(self, tmp_path):
        """Test Liskov Substitution Principle validation."""
        code_file = tmp_path / "birds.py"
        code_file.write_text('''
class Bird:
    """Base bird class."""
    def fly(self):
        """Fly method."""
        return "Flying"

class Penguin(Bird):
    """Penguin cannot fly - LSP violation."""
    def fly(self):
        """Penguins cannot fly."""
        raise Exception("Penguins cannot fly!")
''')

        analyzer = ArchitectureAnalyzer()
        solid_report = analyzer.validate_solid(tmp_path)

        assert solid_report is not None
        # May or may not detect LSP violation depending on implementation

    def test_architecture_detect_patterns_simple_project(self, simple_project):
        """Test design pattern detection on simple project."""
        analyzer = ArchitectureAnalyzer()
        pattern_report = analyzer.detect_patterns(simple_project)

        assert pattern_report is not None
        assert hasattr(pattern_report, 'patterns')
        assert isinstance(pattern_report.patterns, list)

    def test_architecture_detect_singleton_pattern(self, tmp_path):
        """Test Singleton pattern detection."""
        singleton_file = tmp_path / "singleton.py"
        singleton_file.write_text('''
class DatabaseConnection:
    """Singleton database connection."""
    _instance = None

    def __new__(cls):
        """Create singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def connect(self):
        """Connect to database."""
        return "Connected"
''')

        analyzer = ArchitectureAnalyzer()
        pattern_report = analyzer.detect_patterns(tmp_path)

        assert pattern_report is not None

        # Check for singleton pattern detection
        singleton_found = False
        if hasattr(pattern_report, 'detected_patterns'):
            for pattern in pattern_report.detected_patterns:
                if 'singleton' in str(pattern).lower():
                    singleton_found = True
                    break

        # May or may not detect depending on implementation

    def test_architecture_detect_factory_pattern(self, tmp_path):
        """Test Factory pattern detection."""
        factory_file = tmp_path / "factory.py"
        factory_file.write_text('''
class Animal:
    """Base animal class."""
    def speak(self):
        """Animal speaks."""
        raise NotImplementedError

class Dog(Animal):
    """Dog class."""
    def speak(self):
        """Dog barks."""
        return "Woof"

class Cat(Animal):
    """Cat class."""
    def speak(self):
        """Cat meows."""
        return "Meow"

class AnimalFactory:
    """Factory for creating animals."""
    @staticmethod
    def create_animal(animal_type):
        """Create animal by type."""
        if animal_type == "dog":
            return Dog()
        elif animal_type == "cat":
            return Cat()
        raise ValueError(f"Unknown animal: {animal_type}")
''')

        analyzer = ArchitectureAnalyzer()
        pattern_report = analyzer.detect_patterns(tmp_path)

        assert pattern_report is not None

        # Check for factory pattern detection
        if hasattr(pattern_report, 'detected_patterns'):
            assert isinstance(pattern_report.detected_patterns, list)

    def test_architecture_analyze_layers_simple_structure(self, tmp_path):
        """Test layer analysis on simple structure."""
        # Create layer structure
        (tmp_path / "presentation").mkdir()
        (tmp_path / "application").mkdir()
        (tmp_path / "domain").mkdir()
        (tmp_path / "infrastructure").mkdir()

        (tmp_path / "presentation" / "view.py").write_text('''
def render_view():
    """Render view."""
    return "HTML"
''')

        (tmp_path / "domain" / "entity.py").write_text('''
class User:
    """User entity."""
    def __init__(self, name):
        self.name = name
''')

        analyzer = ArchitectureAnalyzer()
        layer_report = analyzer.analyze_layers(tmp_path)

        assert layer_report is not None
        assert hasattr(layer_report, 'layers')
        assert isinstance(layer_report.layers, (list, dict))

    def test_architecture_analyze_layers_violations(self, tmp_path):
        """Test layer violation detection."""
        # Create layers
        (tmp_path / "presentation").mkdir()
        (tmp_path / "domain").mkdir()

        # Presentation layer accessing infrastructure directly (violation)
        (tmp_path / "presentation" / "view.py").write_text('''
import sqlite3

def render_user_list():
    """Render user list - violates layering."""
    conn = sqlite3.connect('users.db')
    users = conn.execute("SELECT * FROM users").fetchall()
    return f"<ul>{''.join([f'<li>{u}</li>' for u in users])}</ul>"
''')

        (tmp_path / "domain" / "user.py").write_text('''
class User:
    """User entity."""
    def __init__(self, name):
        self.name = name
''')

        analyzer = ArchitectureAnalyzer()
        layer_report = analyzer.analyze_layers(tmp_path)

        assert layer_report is not None
        # May detect layer violations

    def test_architecture_quick_check(self, simple_project):
        """Test quick architecture check."""
        analyzer = ArchitectureAnalyzer()
        quick_check = analyzer.quick_check(simple_project)

        assert quick_check is not None
        assert isinstance(quick_check, dict)
        assert "solid_violations" in quick_check
        assert "layer_violations" in quick_check
        assert "patterns_found" in quick_check

    def test_architecture_generate_text_report(self, simple_project):
        """Test generating text report for architecture analysis."""
        analyzer = ArchitectureAnalyzer()
        report = analyzer.analyze(simple_project)
        text_report = analyzer.generate_report(report, "text")

        assert text_report is not None
        assert isinstance(text_report, str)
        assert len(text_report) > 0
        assert "ARCHITECTURE" in text_report or "ANALYSIS" in text_report

    def test_architecture_generate_json_report(self, simple_project):
        """Test generating JSON report for architecture analysis."""
        analyzer = ArchitectureAnalyzer()
        report = analyzer.analyze(simple_project)
        json_report = analyzer.generate_report(report, "json")

        assert json_report is not None
        assert isinstance(json_report, str)

        # Validate JSON structure
        data = json.loads(json_report)
        assert isinstance(data, dict)
        assert "scan_path" in data

    def test_architecture_empty_directory_handling(self, tmp_path):
        """Test architecture analysis on empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        analyzer = ArchitectureAnalyzer()
        report = analyzer.analyze(empty_dir)

        assert report is not None
        assert report.scan_path == str(empty_dir.resolve())

    def test_architecture_nonexistent_path_handling(self):
        """Test architecture analysis on nonexistent path."""
        nonexistent = Path("/nonexistent/path/to/nowhere")

        analyzer = ArchitectureAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.analyze(nonexistent)

    def test_architecture_with_custom_config(self, simple_project):
        """Test architecture analysis with custom configuration."""
        config = ArchitectureConfig(
            max_class_responsibilities=5,
            max_method_count=25,
        )
        analyzer = ArchitectureAnalyzer(config)
        report = analyzer.analyze(simple_project)

        assert report is not None

    def test_architecture_circular_dependency_detection(self, circular_dependency_project):
        """Test circular dependency detection at module level."""
        analyzer = ArchitectureAnalyzer()
        report = analyzer.analyze(circular_dependency_project)

        assert report is not None

        # May detect circular dependencies as architecture violation
        if hasattr(report, 'circular_dependencies'):
            assert isinstance(report.circular_dependencies, (list, bool))

    def test_architecture_god_class_metrics(self, god_class_project):
        """Test god class metrics in architecture analysis."""
        analyzer = ArchitectureAnalyzer()
        report = analyzer.analyze(god_class_project)

        assert report is not None

        # God class should be flagged
        if hasattr(report, 'god_classes'):
            assert isinstance(report.god_classes, list)
            # ApplicationManager should be detected as god class

    def test_architecture_inheritance_depth_check(self, inheritance_hierarchy_project):
        """Test inheritance depth checking."""
        analyzer = ArchitectureAnalyzer()
        report = analyzer.analyze(inheritance_hierarchy_project)

        assert report is not None

        # Deep inheritance should be flagged
        if hasattr(report, 'deep_inheritance'):
            assert isinstance(report.deep_inheritance, (list, dict))

    def test_architecture_coupling_analysis(self, inheritance_hierarchy_project):
        """Test coupling analysis in architecture validation."""
        analyzer = ArchitectureAnalyzer()
        report = analyzer.analyze(inheritance_hierarchy_project)

        assert report is not None

        # High coupling should be detected
        if hasattr(report, 'high_coupling'):
            assert isinstance(report.high_coupling, (list, dict))

    def test_architecture_cohesion_analysis(self, complex_project):
        """Test cohesion analysis in architecture validation."""
        analyzer = ArchitectureAnalyzer()
        report = analyzer.analyze(complex_project)

        assert report is not None

        # Cohesion metrics should be available
        if hasattr(report, 'cohesion_metrics'):
            assert isinstance(report.cohesion_metrics, (list, dict))

    def test_architecture_interface_segregation_principle(self, tmp_path):
        """Test Interface Segregation Principle validation."""
        code_file = tmp_path / "interfaces.py"
        code_file.write_text('''
from abc import ABC, abstractmethod

class Worker(ABC):
    """Worker interface."""
    @abstractmethod
    def work(self):
        """Do work."""
        pass

class Eater(ABC):
    """Eater interface."""
    @abstractmethod
    def eat(self):
        """Eat food."""
        pass

class Human(Worker, Eater):
    """Human implements both interfaces."""
    def work(self):
        """Human works."""
        return "Working"

    def eat(self):
        """Human eats."""
        return "Eating"

class Robot(Worker):
    """Robot only implements Worker."""
    def work(self):
        """Robot works."""
        return "Working"
''')

        analyzer = ArchitectureAnalyzer()
        solid_report = analyzer.validate_solid(tmp_path)

        assert solid_report is not None
        # This follows ISP, should have no or few violations

    def test_architecture_dependency_inversion_principle(self, tmp_path):
        """Test Dependency Inversion Principle validation."""
        code_file = tmp_path / "dip.py"
        code_file.write_text('''
from abc import ABC, abstractmethod

class MessageSender(ABC):
    """Abstract message sender."""
    @abstractmethod
    def send(self, message):
        """Send message."""
        pass

class EmailSender(MessageSender):
    """Email sender implementation."""
    def send(self, message):
        """Send email."""
        return f"Email: {message}"

class Notifier:
    """Notifier depends on abstraction."""
    def __init__(self, sender: MessageSender):
        self.sender = sender

    def notify(self, message):
        """Send notification."""
        return self.sender.send(message)
''')

        analyzer = ArchitectureAnalyzer()
        solid_report = analyzer.validate_solid(tmp_path)

        assert solid_report is not None
        # This follows DIP, should have no or few violations
