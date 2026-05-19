"""L3 Contract tests for Heimdall Security scanner models.

Verifies the public API surface — field names, types, required fields —
so breaking model changes are caught immediately.
"""

import pytest
from pydantic import ValidationError
from pathlib import Path


# ---------------------------------------------------------------------------
# ReDoS
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.ReDoS.models.redos_models import (
    ReDoSScanConfig,
    ReDoSScanReport,
    ReDoSFinding,
    ReDoSSeverity,
)


class TestReDoSScanConfigContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            ReDoSScanConfig()

    def test_accepts_valid_scan_path(self, tmp_path):
        config = ReDoSScanConfig(scan_path=tmp_path)
        assert hasattr(config, "scan_path")

    def test_has_recursive_field(self, tmp_path):
        config = ReDoSScanConfig(scan_path=tmp_path)
        assert hasattr(config, "recursive")

    def test_has_skip_dirs_field(self, tmp_path):
        config = ReDoSScanConfig(scan_path=tmp_path)
        assert hasattr(config, "skip_dirs")


class TestReDoSScanReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            ReDoSScanReport()

    def test_instantiates_with_scan_path(self):
        report = ReDoSScanReport(scan_path="/some/path")
        assert hasattr(report, "scan_path")

    def test_has_findings_field(self):
        report = ReDoSScanReport(scan_path="/some/path")
        assert hasattr(report, "findings")
        assert isinstance(report.findings, list)

    def test_has_total_findings_field(self):
        report = ReDoSScanReport(scan_path="/some/path")
        assert hasattr(report, "total_findings")


class TestReDoSFindingContract:
    def test_requires_all_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ReDoSFinding()

    def test_instantiates_with_required_fields(self):
        finding = ReDoSFinding(
            file_path="foo.py",
            line_number=1,
            severity=ReDoSSeverity.HIGH,
            pattern_type="exponential_backtracking",
            description="Vulnerable regex",
            recommendation="Use atomic groups",
        )
        assert finding.file_path == "foo.py"
        assert finding.severity == ReDoSSeverity.HIGH


# ---------------------------------------------------------------------------
# API Security
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.API.models.api_models import APIScanConfig, APIScanReport


class TestAPIScanConfigContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            APIScanConfig()

    def test_accepts_valid_scan_path(self, tmp_path):
        config = APIScanConfig(scan_path=tmp_path)
        assert hasattr(config, "scan_path")


class TestAPIScanReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            APIScanReport()

    def test_has_findings_field(self):
        report = APIScanReport(scan_path="/path")
        assert hasattr(report, "findings")


# ---------------------------------------------------------------------------
# Backdoor
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Backdoor.models.backdoor_models import (
    BackdoorScanConfig,
    BackdoorScanReport,
)


class TestBackdoorScanConfigContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            BackdoorScanConfig()

    def test_accepts_valid_scan_path(self, tmp_path):
        config = BackdoorScanConfig(scan_path=tmp_path)
        assert hasattr(config, "scan_path")


class TestBackdoorScanReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            BackdoorScanReport()

    def test_has_findings_field(self):
        report = BackdoorScanReport(scan_path="/path")
        assert hasattr(report, "findings")


# ---------------------------------------------------------------------------
# Deserialization
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Deserialization.models.deserialization_models import (
    DeserializationScanConfig,
    DeserializationScanReport,
)


class TestDeserializationScanConfigContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            DeserializationScanConfig()

    def test_accepts_valid_scan_path(self, tmp_path):
        config = DeserializationScanConfig(scan_path=tmp_path)
        assert hasattr(config, "scan_path")


class TestDeserializationScanReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            DeserializationScanReport()

    def test_has_findings_field(self):
        report = DeserializationScanReport(scan_path="/path")
        assert hasattr(report, "findings")


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Frontend.models.frontend_models import (
    FrontendScanConfig,
    FrontendScanReport,
)


class TestFrontendScanConfigContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            FrontendScanConfig()

    def test_accepts_valid_scan_path(self, tmp_path):
        config = FrontendScanConfig(scan_path=tmp_path)
        assert hasattr(config, "scan_path")


class TestFrontendScanReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            FrontendScanReport()

    def test_has_findings_field(self):
        report = FrontendScanReport(scan_path="/path")
        assert hasattr(report, "findings")


# ---------------------------------------------------------------------------
# Malware
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Malware.models.malware_models import (
    MalwareScanConfig,
    MalwareScanReport,
)


class TestMalwareScanConfigContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            MalwareScanConfig()

    def test_accepts_valid_scan_path(self, tmp_path):
        config = MalwareScanConfig(scan_path=tmp_path)
        assert hasattr(config, "scan_path")


class TestMalwareScanReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            MalwareScanReport()

    def test_has_findings_field(self):
        report = MalwareScanReport(scan_path="/path")
        assert hasattr(report, "findings")


# ---------------------------------------------------------------------------
# Misconfig
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Misconfig.models.misconfig_models import (
    MisconfigScanConfig,
    MisconfigScanReport,
)


class TestMisconfigScanConfigContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            MisconfigScanConfig()

    def test_accepts_valid_scan_path(self, tmp_path):
        config = MisconfigScanConfig(scan_path=tmp_path)
        assert hasattr(config, "scan_path")


class TestMisconfigScanReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            MisconfigScanReport()

    def test_has_findings_field(self):
        report = MisconfigScanReport(scan_path="/path")
        assert hasattr(report, "findings")


# ---------------------------------------------------------------------------
# PathTraversal
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.PathTraversal.models.path_traversal_models import (
    PathTraversalScanConfig,
    PathTraversalScanReport,
)


class TestPathTraversalScanConfigContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            PathTraversalScanConfig()

    def test_accepts_valid_scan_path(self, tmp_path):
        config = PathTraversalScanConfig(scan_path=tmp_path)
        assert hasattr(config, "scan_path")


class TestPathTraversalScanReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            PathTraversalScanReport()

    def test_has_findings_field(self):
        report = PathTraversalScanReport(scan_path="/path")
        assert hasattr(report, "findings")


# ---------------------------------------------------------------------------
# RaceCondition
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.RaceCondition.models.race_condition_models import (
    RaceConditionScanConfig,
    RaceConditionScanReport,
)


class TestRaceConditionScanConfigContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            RaceConditionScanConfig()

    def test_accepts_valid_scan_path(self, tmp_path):
        config = RaceConditionScanConfig(scan_path=tmp_path)
        assert hasattr(config, "scan_path")


class TestRaceConditionScanReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            RaceConditionScanReport()

    def test_has_findings_field(self):
        report = RaceConditionScanReport(scan_path="/path")
        assert hasattr(report, "findings")


# ---------------------------------------------------------------------------
# SensitiveData
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.SensitiveData.models.sensitive_data_models import (
    SensitiveDataScanConfig,
    SensitiveDataScanReport,
)


class TestSensitiveDataScanConfigContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            SensitiveDataScanConfig()

    def test_accepts_valid_scan_path(self, tmp_path):
        config = SensitiveDataScanConfig(scan_path=tmp_path)
        assert hasattr(config, "scan_path")


class TestSensitiveDataScanReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            SensitiveDataScanReport()

    def test_has_findings_field(self):
        report = SensitiveDataScanReport(scan_path="/path")
        assert hasattr(report, "findings")


# ---------------------------------------------------------------------------
# SSRF
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.SSRF.models.ssrf_models import (
    SSRFScanConfig,
    SSRFScanReport,
)


class TestSSRFScanConfigContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            SSRFScanConfig()

    def test_accepts_valid_scan_path(self, tmp_path):
        config = SSRFScanConfig(scan_path=tmp_path)
        assert hasattr(config, "scan_path")


class TestSSRFScanReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            SSRFScanReport()

    def test_has_findings_field(self):
        report = SSRFScanReport(scan_path="/path")
        assert hasattr(report, "findings")


# ---------------------------------------------------------------------------
# InputValidation
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.InputValidation.models.input_validation_models import (
    InputValidationScanConfig,
    InputValidationScanReport,
)


class TestInputValidationScanConfigContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            InputValidationScanConfig()

    def test_accepts_valid_scan_path(self, tmp_path):
        config = InputValidationScanConfig(scan_path=tmp_path)
        assert hasattr(config, "scan_path")


class TestInputValidationScanReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            InputValidationScanReport()

    def test_has_findings_field(self):
        report = InputValidationScanReport(scan_path="/path")
        assert hasattr(report, "findings")
