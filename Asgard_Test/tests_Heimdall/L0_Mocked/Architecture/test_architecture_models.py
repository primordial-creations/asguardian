"""
Tests for Heimdall Architecture Models

Unit tests for architecture analysis data models.
"""

import pytest
from datetime import datetime

from Asgard.Heimdall.Architecture.models.architecture_models import (
    ArchitectureConfig,
    SOLIDPrinciple,
    ViolationSeverity,
    PatternType,
    SOLIDViolation,
    SOLIDReport,
    LayerDefinition,
    LayerViolation,
    LayerReport,
    PatternMatch,
    PatternReport,
    ArchitectureReport,
)


class TestArchitectureConfig:
    """Tests for ArchitectureConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ArchitectureConfig()
        assert config.max_class_responsibilities == 3
        assert config.max_method_count == 20
        assert config.detect_patterns == []
        assert config.layers == {}

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ArchitectureConfig(
            max_class_responsibilities=5,
            max_method_count=15,
            detect_patterns=[PatternType.SINGLETON],
        )
        assert config.max_class_responsibilities == 5
        assert config.max_method_count == 15
        assert config.detect_patterns == [PatternType.SINGLETON]


class TestSOLIDPrinciple:
    """Tests for SOLIDPrinciple enum."""

    def test_principle_values(self):
        """Test SOLID principle enum values."""
        assert SOLIDPrinciple.SRP.value == "single_responsibility"
        assert SOLIDPrinciple.OCP.value == "open_closed"
        assert SOLIDPrinciple.LSP.value == "liskov_substitution"
        assert SOLIDPrinciple.ISP.value == "interface_segregation"
        assert SOLIDPrinciple.DIP.value == "dependency_inversion"


class TestViolationSeverity:
    """Tests for ViolationSeverity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert ViolationSeverity.LOW.value == "low"
        assert ViolationSeverity.MODERATE.value == "moderate"
        assert ViolationSeverity.HIGH.value == "high"
        assert ViolationSeverity.CRITICAL.value == "critical"


class TestPatternType:
    """Tests for PatternType enum."""

    def test_pattern_type_values(self):
        """Test pattern type enum values."""
        assert PatternType.SINGLETON.value == "singleton"
        assert PatternType.FACTORY.value == "factory"
        assert PatternType.STRATEGY.value == "strategy"


class TestSOLIDViolation:
    """Tests for SOLIDViolation class."""

    def test_create_violation(self):
        """Test creating a SOLID violation."""
        violation = SOLIDViolation(
            principle=SOLIDPrinciple.SRP,
            class_name="GodClass",
            file_path="/test/god_class.py",
            line_number=1,
            severity=ViolationSeverity.HIGH,
            message="Class has too many responsibilities",
            suggestion="Split into smaller focused classes",
        )
        assert violation.principle == SOLIDPrinciple.SRP
        assert violation.class_name == "GodClass"
        assert violation.severity == ViolationSeverity.HIGH


class TestSOLIDReport:
    """Tests for SOLIDReport class."""

    def test_create_report(self):
        """Test creating a SOLID report."""
        report = SOLIDReport(scan_path="/test/path")
        assert report.scan_path == "/test/path"
        assert report.violations == []
        assert report.has_violations is False

    def test_report_with_violations(self):
        """Test report with violations."""
        violation = SOLIDViolation(
            principle=SOLIDPrinciple.SRP,
            class_name="TestClass",
            file_path="/test/path.py",
            line_number=1,
            severity=ViolationSeverity.HIGH,
            message="Test violation",
        )
        report = SOLIDReport(
            scan_path="/test/path",
            violations=[violation],
        )
        assert report.has_violations is True
        assert report.total_violations == 1

    def test_violations_by_principle(self):
        """Test grouping violations by principle."""
        srp_violation = SOLIDViolation(
            principle=SOLIDPrinciple.SRP,
            class_name="TestClass",
            file_path="/test/path.py",
            line_number=1,
            severity=ViolationSeverity.HIGH,
            message="SRP violation",
        )
        dip_violation = SOLIDViolation(
            principle=SOLIDPrinciple.DIP,
            class_name="TestClass2",
            file_path="/test/path2.py",
            line_number=1,
            severity=ViolationSeverity.MODERATE,
            message="DIP violation",
        )
        report = SOLIDReport(
            scan_path="/test/path",
            violations=[srp_violation, dip_violation],
        )
        by_principle = report.violations_by_principle
        assert SOLIDPrinciple.SRP in by_principle
        assert SOLIDPrinciple.DIP in by_principle


class TestLayerDefinition:
    """Tests for LayerDefinition class."""

    def test_create_layer(self):
        """Test creating a layer definition."""
        layer = LayerDefinition(
            name="presentation",
            patterns=["**/views/**", "**/controllers/**"],
            allowed_dependencies=["application", "domain"],
        )
        assert layer.name == "presentation"
        assert len(layer.patterns) == 2


class TestLayerViolation:
    """Tests for LayerViolation class."""

    def test_create_layer_violation(self):
        """Test creating a layer violation."""
        violation = LayerViolation(
            source_module="app.views",
            source_layer="presentation",
            target_module="app.database",
            target_layer="infrastructure",
            file_path="/test/view.py",
            line_number=10,
            message="Presentation layer should not depend on infrastructure",
            severity=ViolationSeverity.HIGH,
        )
        assert violation.source_layer == "presentation"
        assert violation.target_layer == "infrastructure"


class TestLayerReport:
    """Tests for LayerReport class."""

    def test_create_report(self):
        """Test creating a layer report."""
        report = LayerReport(scan_path="/test/path")
        assert report.is_valid is True
        assert report.violations == []


class TestPatternMatch:
    """Tests for PatternMatch class."""

    def test_create_match(self):
        """Test creating a pattern match."""
        match = PatternMatch(
            pattern_type=PatternType.SINGLETON,
            class_name="DatabaseConnection",
            file_path="/test/db.py",
            line_number=1,
            confidence=0.9,
            participants=["__new__ method", "_instance attribute"],
        )
        assert match.pattern_type == PatternType.SINGLETON
        assert match.confidence == 0.9


class TestPatternReport:
    """Tests for PatternReport class."""

    def test_create_report(self):
        """Test creating a pattern report."""
        report = PatternReport(scan_path="/test/path")
        assert report.patterns == []
        assert report.total_patterns == 0


class TestArchitectureReport:
    """Tests for ArchitectureReport class."""

    def test_create_report(self):
        """Test creating an architecture report."""
        report = ArchitectureReport(scan_path="/test/path")
        assert report.scan_path == "/test/path"

    def test_is_healthy(self):
        """Test is_healthy property."""
        report = ArchitectureReport(scan_path="/test/path")
        assert report.is_healthy is True

        # Add a violation
        violation = SOLIDViolation(
            principle=SOLIDPrinciple.SRP,
            class_name="TestClass",
            file_path="/test/path.py",
            line_number=1,
            severity=ViolationSeverity.CRITICAL,
            message="Test violation",
        )
        report.solid_report = SOLIDReport(
            scan_path="/test/path",
            violations=[violation],
        )
        # is_healthy depends on implementation
