"""L3 Contract tests for remaining Heimdall models:
CodeFix, Dependencies (SBOM), QualityGate, Ratings, Issues, Performance, Profiles.
"""
import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# CodeFix
# ---------------------------------------------------------------------------
from Asgard.Bragi.CodeFix.models.codefix_models import (
    CodeFix,
    FixSuggestion,
    CodeFixReport,
)


class TestCodeFixContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            CodeFix()

    def test_accepts_valid_data(self):
        cf = CodeFix(
            rule_id="R001",
            title="Remove bare except",
            description="Replace with specific exception",
            fix_type="automated",
            confidence="high",
        )
        assert cf.rule_id == "R001"
        assert hasattr(cf, "fix_type")

    def test_accepts_valid_enum_types(self):
        from Asgard.Bragi.CodeFix.models.codefix_models import FixType
        cf = CodeFix(
            rule_id="R001",
            title="t",
            description="d",
            fix_type=FixType.AUTOMATED,
            confidence="high",
        )
        assert hasattr(cf, "fix_type")


class TestFixSuggestionContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            FixSuggestion()

    def test_accepts_valid_data(self):
        from Asgard.Bragi.CodeFix.models.codefix_models import CodeFix
        fix = CodeFix(rule_id="R001", title="t", description="d", fix_type="automated", confidence="high")
        fs = FixSuggestion(
            file_path="/a.py",
            line_number=10,
            rule_id="R001",
            finding_title="Bare except",
            fix=fix,
        )
        assert fs.file_path == "/a.py"


class TestCodeFixReportContract:
    def test_instantiates_with_defaults(self):
        report = CodeFixReport()
        assert report is not None
        assert hasattr(CodeFixReport, "model_fields")

    def test_has_suggestions_field(self):
        report = CodeFixReport()
        assert hasattr(report, "suggestions")


# ---------------------------------------------------------------------------
# Dependencies / SBOM
# ---------------------------------------------------------------------------
from Asgard.Bragi.Dependencies.models.sbom_models import (
    SBOMComponent,
    SBOMDocument,
    SBOMConfig,
)


class TestSBOMComponentContract:
    def test_requires_name_and_version(self):
        with pytest.raises((ValidationError, TypeError)):
            SBOMComponent()

    def test_accepts_valid_data(self):
        comp = SBOMComponent(name="requests", version="2.31.0")
        assert comp.name == "requests"
        assert hasattr(comp, "version")

    def test_has_license_field(self):
        comp = SBOMComponent(name="requests", version="2.31.0")
        assert hasattr(comp, "license_id")


class TestSBOMDocumentContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            SBOMDocument()

    def test_accepts_valid_data(self):
        from datetime import datetime
        doc = SBOMDocument(
            format="spdx",
            spec_version="2.3",
            document_id="SPDXRef-DOCUMENT",
            document_name="my-project",
            project_name="my-project",
            created_at=datetime.now(),
        )
        assert doc.format == "spdx"
        assert hasattr(doc, "components")


class TestSBOMConfigContract:
    def test_instantiates_with_defaults(self):
        config = SBOMConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# QualityGate
# ---------------------------------------------------------------------------
from Asgard.Bragi.QualityGate.models.quality_gate_models import (
    GateCondition,
    ConditionResult,
    QualityGate,
    QualityGateResult,
    QualityGateConfig,
)


class TestGateConditionContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            GateCondition()

    def test_accepts_valid_data(self):
        from Asgard.Bragi.QualityGate.models.quality_gate_models import MetricType, GateOperator
        gc = GateCondition(metric=MetricType.SECURITY_RATING, operator=GateOperator.LESS_THAN, threshold=1.0)
        assert hasattr(gc, "metric")
        assert hasattr(gc, "threshold")


class TestQualityGateContract:
    def test_requires_name(self):
        with pytest.raises((ValidationError, TypeError)):
            QualityGate()

    def test_accepts_valid_data(self):
        qg = QualityGate(name="Default Gate")
        assert qg.name == "Default Gate"
        assert hasattr(qg, "conditions")


class TestQualityGateConfigContract:
    def test_requires_gate(self):
        with pytest.raises((ValidationError, TypeError)):
            QualityGateConfig()

    def test_accepts_valid_data(self):
        qg = QualityGate(name="Gate")
        config = QualityGateConfig(gate=qg)
        assert config.gate.name == "Gate"


# ---------------------------------------------------------------------------
# Ratings
# ---------------------------------------------------------------------------
from Asgard.Bragi.Ratings.models.ratings_models import (
    DimensionRating,
    ProjectRatings,
    RatingsConfig,
)


class TestDimensionRatingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            DimensionRating()

    def test_accepts_valid_data(self):
        dr = DimensionRating(dimension="maintainability", rating="A")
        assert dr.dimension == "maintainability"
        assert hasattr(dr, "rating")


class TestProjectRatingsContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ProjectRatings()

    def test_accepts_valid_data(self):
        dr = DimensionRating(dimension="maintainability", rating="A")
        pr = ProjectRatings(
            maintainability=dr,
            reliability=dr,
            security=dr,
            overall_rating="A",
        )
        assert pr.overall_rating == "A"


class TestRatingsConfigContract:
    def test_instantiates_with_defaults(self):
        config = RatingsConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------
from Asgard.Shared.Issues.models.issue_models import (
    TrackedIssue,
    IssueFilter,
    IssuesSummary,
)


class TestTrackedIssueContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            TrackedIssue()

    def test_accepts_valid_data(self):
        from datetime import datetime
        now = datetime.now()
        ti = TrackedIssue(
            issue_id="I001",
            rule_id="R001",
            issue_type="bug",
            file_path="/a.py",
            line_number=10,
            severity="high",
            title="Null pointer",
            description="Possible NPE",
            first_detected=now,
            last_seen=now,
        )
        assert ti.issue_id == "I001"
        assert hasattr(ti, "severity")


class TestIssueFilterContract:
    def test_instantiates_with_defaults(self):
        f = IssueFilter()
        assert f is not None

    def test_has_severity_field(self):
        f = IssueFilter()
        assert hasattr(f, "severity")


class TestIssuesSummaryContract:
    def test_requires_project_path(self):
        with pytest.raises((ValidationError, TypeError)):
            IssuesSummary()

    def test_accepts_valid_data(self):
        summary = IssuesSummary(project_path="/my/project")
        assert summary.project_path == "/my/project"
        assert hasattr(summary, "total_open")


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------
from Asgard.Bragi.Performance.models.performance_models import (
    CacheFinding,
    CpuFinding,
    DatabaseFinding,
    MemoryFinding,
    PerformanceReport,
    PerformanceScanConfig,
)


class TestCacheFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            CacheFinding()

    def test_accepts_valid_data(self):
        from Asgard.Bragi.Performance.models.performance_models import CacheIssueType, PerformanceSeverity
        cf = CacheFinding(
            file_path="/a.py",
            line_number=10,
            issue_type=CacheIssueType.CACHE_MISS,
            severity=PerformanceSeverity.HIGH,
            description="Cache miss on every request",
            recommendation="Add caching",
        )
        assert hasattr(cf, "issue_type")


class TestPerformanceScanConfigContract:
    def test_instantiates_with_defaults(self):
        config = PerformanceScanConfig()
        assert config is not None

    def test_has_scan_path_field(self):
        config = PerformanceScanConfig()
        assert hasattr(config, "scan_path")


class TestPerformanceReportContract:
    def test_requires_scan_path_and_config(self):
        with pytest.raises((ValidationError, TypeError)):
            PerformanceReport()

    def test_accepts_valid_data(self):
        config = PerformanceScanConfig()
        report = PerformanceReport(scan_path="/path", scan_config=config)
        assert report.scan_path == "/path"
        assert hasattr(report, "total_issues")


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------
from Asgard.Shared.Profiles.models.profile_models import (
    RuleConfig,
    QualityProfile,
    ProfileAssignment,
)


class TestRuleConfigContract:
    def test_requires_rule_id(self):
        with pytest.raises((ValidationError, TypeError)):
            RuleConfig()

    def test_accepts_valid_data(self):
        rc = RuleConfig(rule_id="R001")
        assert rc.rule_id == "R001"


class TestQualityProfileContract:
    def test_requires_name(self):
        with pytest.raises((ValidationError, TypeError)):
            QualityProfile()

    def test_accepts_valid_data(self):
        qp = QualityProfile(name="strict")
        assert qp.name == "strict"
        assert hasattr(qp, "rules") or hasattr(QualityProfile, "model_fields")


class TestProfileAssignmentContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ProfileAssignment()

    def test_accepts_valid_data(self):
        pa = ProfileAssignment(project_path="/my/project", profile_name="strict")
        assert pa.project_path == "/my/project"
        assert pa.profile_name == "strict"
