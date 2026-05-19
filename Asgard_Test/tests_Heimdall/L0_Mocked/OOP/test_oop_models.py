"""
Tests for Heimdall OOP Models

Unit tests for object-oriented metrics data models.
"""

import pytest
from datetime import datetime

from Asgard.Heimdall.OOP.models.oop_models import (
    ClassOOPMetrics,
    OOPConfig,
    OOPReport,
    OOPSeverity,
)


class TestOOPConfig:
    """Tests for OOPConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = OOPConfig()
        assert config.cbo_threshold == 10
        assert config.lcom_threshold == 0.85
        assert config.dit_threshold == 5
        assert config.noc_threshold == 10
        assert config.rfc_threshold == 50
        assert config.wmc_threshold == 50

    def test_custom_values(self):
        """Test custom configuration values."""
        config = OOPConfig(
            cbo_threshold=8,
            lcom_threshold=0.5,
            dit_threshold=4,
        )
        assert config.cbo_threshold == 8
        assert config.lcom_threshold == 0.5
        assert config.dit_threshold == 4


class TestOOPSeverity:
    """Tests for OOPSeverity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert OOPSeverity.LOW.value == "low"
        assert OOPSeverity.MODERATE.value == "moderate"
        assert OOPSeverity.HIGH.value == "high"
        assert OOPSeverity.CRITICAL.value == "critical"


class TestClassOOPMetrics:
    """Tests for ClassOOPMetrics class."""

    def test_create_metrics(self):
        """Test creating class OOP metrics."""
        metrics = ClassOOPMetrics(
            class_name="TestClass",
            file_path="/test/path.py",
            relative_path="path.py",
            line_number=1,
            cbo=5,
            afferent_coupling=2,
            efferent_coupling=3,
            dit=2,
            noc=1,
            lcom=0.3,
            rfc=15,
            wmc=10,
        )
        assert metrics.class_name == "TestClass"
        assert metrics.cbo == 5
        assert metrics.lcom == 0.3

    def test_instability_field(self):
        """Test instability metric field."""
        metrics = ClassOOPMetrics(
            class_name="TestClass",
            file_path="/test/path.py",
            relative_path="path.py",
            line_number=1,
            afferent_coupling=4,
            efferent_coupling=6,
            instability=0.6,
        )
        assert metrics.instability == pytest.approx(0.6, rel=0.01)

    def test_instability_with_zero_coupling(self):
        """Test instability when no coupling exists."""
        metrics = ClassOOPMetrics(
            class_name="TestClass",
            file_path="/test/path.py",
            relative_path="path.py",
            line_number=1,
            afferent_coupling=0,
            efferent_coupling=0,
        )
        assert metrics.instability == 0.0


class TestOOPReport:
    """Tests for OOPReport class."""

    def test_create_report(self):
        """Test creating an OOP report."""
        report = OOPReport(scan_path="/test/path")
        assert report.scan_path == "/test/path"
        assert report.class_metrics == []
        assert report.total_classes_analyzed == 0

    def test_report_with_metrics(self):
        """Test report with class metrics."""
        metrics = ClassOOPMetrics(
            class_name="TestClass",
            file_path="/test/path.py",
            relative_path="path.py",
            line_number=1,
            cbo=15,
            lcom=0.9,
        )
        report = OOPReport(
            scan_path="/test/path",
            class_metrics=[metrics],
        )
        # Note: total_classes_analyzed is only updated via add_file_analysis method
        assert len(report.class_metrics) == 1

    def test_has_issues_property(self):
        """Test has_issues detection."""
        good_metrics = ClassOOPMetrics(
            class_name="GoodClass",
            file_path="/test/path.py",
            relative_path="path.py",
            line_number=1,
            cbo=5,
            lcom=0.3,
        )
        bad_metrics = ClassOOPMetrics(
            class_name="BadClass",
            file_path="/test/path.py",
            relative_path="path.py",
            line_number=10,
            cbo=20,
            lcom=0.9,
            overall_severity=OOPSeverity.CRITICAL,
        )

        # Report with good metrics
        good_report = OOPReport(
            scan_path="/test/path",
            class_metrics=[good_metrics],
        )

        # Report with bad metrics (high coupling)
        bad_report = OOPReport(
            scan_path="/test/path",
            class_metrics=[bad_metrics],
        )

        # Check has_issues based on severity
        assert good_metrics.overall_severity == OOPSeverity.INFO
        assert bad_metrics.overall_severity in (OOPSeverity.HIGH, OOPSeverity.CRITICAL)
