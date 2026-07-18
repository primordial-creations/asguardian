"""Tests for the central severity normalization engine (plan 06 B/C)."""

from Asgard.Heimdall.Security.normalization.equivalency import (
    EQUIVALENCY_MATRIX,
    finding_classes_for,
    severity_of_class,
)
from Asgard.Heimdall.Security.normalization.impact_matrix import (
    MECHANISMS,
    normalize_finding,
)
from Asgard.Heimdall.Security.normalization.priority import (
    confidence_bucket,
    priority,
)


class TestConfidenceBuckets:
    def test_bucket_boundaries(self):
        assert confidence_bucket(0.86) == "certain"
        assert confidence_bucket(0.85) == "probable"   # certain is strictly > 0.85
        assert confidence_bucket(0.50) == "probable"
        assert confidence_bucket(0.49) == "possible"
        assert confidence_bucket(0.25) == "possible"
        assert confidence_bucket(0.24) == "unlikely"
        assert confidence_bucket(0.0) == "unlikely"

    def test_buckets_are_qualitative_names(self):
        for value in (0.0, 0.3, 0.6, 0.9, 1.0):
            assert confidence_bucket(value) in (
                "certain", "probable", "possible", "unlikely")


class TestImpactMatrix:
    def test_cia_criteria_severities(self):
        assert MECHANISMS["rce.unauthenticated"].severity == "critical"
        assert MECHANISMS["auth.total_bypass"].severity == "critical"
        assert MECHANISMS["secret.cloud_admin.validated"].severity == "critical"
        assert MECHANISMS["injection.sql.authenticated"].severity == "high"
        assert MECHANISMS["xss.stored"].severity == "high"
        assert MECHANISMS["path_traversal.read"].severity == "high"
        assert MECHANISMS["container.root_privileged"].severity == "high"
        assert MECHANISMS["xss.reflected"].severity == "medium"
        assert MECHANISMS["secret.internal_test"].severity == "medium"
        assert MECHANISMS["secret.dummy"].severity == "low"
        assert MECHANISMS["fingerprinting"].severity == "low"

    def test_severity_confidence_orthogonal(self):
        """A low-confidence RCE stays CRITICAL; it is routed to review via
        its bucket, never downgraded."""
        result = normalize_finding("rce.unauthenticated", confidence=0.1)
        assert result.severity == "critical"
        assert result.confidence_bucket == "unlikely"
        assert result.normalized is True

    def test_unknown_mechanism_passthrough(self):
        result = normalize_finding(
            "not.a.known.mechanism", 0.9, fallback_severity="high")
        assert result.severity == "high"
        assert result.normalized is False

    def test_browser_only_downgraded_in_api_context(self):
        web = normalize_finding("header.missing_csp", 0.9)
        api = normalize_finding(
            "header.missing_csp", 0.9, context_tags=("api_context",))
        assert web.severity == "medium"
        assert api.severity == "low"

    def test_context_modifier_scales_priority_only(self):
        full = normalize_finding("xss.stored", 0.9, context_modifier=1.0)
        internal = normalize_finding("xss.stored", 0.9, context_modifier=0.5)
        assert internal.severity == full.severity
        assert internal.priority == full.priority / 2


class TestPriorityOrdering:
    def test_twilio_vs_rce_regression(self):
        """DEEPTHINK_11 worked example: a validated third-party key (HIGH,
        confidence 1.0 -> P=80) outranks a tentative RCE (CRITICAL,
        confidence 0.4 -> P=40)."""
        validated_key = normalize_finding(
            "secret.third_party.scoped_live", confidence=1.0)
        tentative_rce = normalize_finding(
            "rce.unauthenticated", confidence=0.4)
        assert validated_key.priority == 80.0
        assert tentative_rce.priority == 40.0
        assert validated_key.priority > tentative_rce.priority
        # ... while severity ordering is the opposite (orthogonality)
        assert tentative_rce.severity == "critical"
        assert validated_key.severity == "high"

    def test_priority_formula(self):
        assert priority("critical", 1.0) == 100.0
        assert priority("high", 0.5) == 40.0
        assert priority("medium", 1.0, context_modifier=0.5) == 25.0
        assert priority("low", 1.0) == 20.0


class TestEquivalencyMatrix:
    def test_all_families_define_all_four_severities(self):
        for family, row in EQUIVALENCY_MATRIX.items():
            for severity in ("critical", "high", "medium", "low"):
                assert row.get(severity), (
                    f"{family} missing {severity} equivalency class")

    def test_class_maps_to_exactly_one_severity(self):
        for family, row in EQUIVALENCY_MATRIX.items():
            seen = {}
            for severity, classes in row.items():
                for cls in classes:
                    assert cls not in seen, (
                        f"{family}: '{cls}' in both {seen.get(cls)} and {severity}")
                    seen[cls] = severity

    def test_cross_module_blast_radius_equivalences(self):
        """A 'HIGH' means the same blast radius everywhere."""
        assert severity_of_class(
            "secrets", "scoped live third-party token") == "high"
        assert severity_of_class(
            "sast", "authenticated SQL injection") == "high"
        assert severity_of_class(
            "container_iac", "container root + privileged mode") == "high"
        assert severity_of_class(
            "secrets", "validated cloud-admin credential") == "critical"
        assert severity_of_class("sast", "unauthenticated RCE") == "critical"

    def test_lookup_helpers(self):
        assert "dummy/placeholder key" in finding_classes_for("secrets", "low")
        assert severity_of_class("secrets", "nonexistent") is None
