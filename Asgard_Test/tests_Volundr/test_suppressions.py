"""Suppression contract tests (warning-annihilation, receipts, hygiene)."""

from datetime import date, timedelta

import pytest
import yaml
from pydantic import ValidationError

from Asgard.Volundr.Validation import (
    Suppression,
    SuppressionEngine,
    SuppressionSet,
    ValidationEngine,
    annotate_k8s_manifest,
    append_comment_receipts,
    k8s_receipt_annotations,
)
from Asgard.Volundr.Validation.models.validation_models import (
    ValidationCategory,
    ValidationResult,
    ValidationSeverity,
)


def finding(rule_id="VOL-K8S-0001", target="app", severity=ValidationSeverity.ERROR):
    return ValidationResult(
        rule_id=rule_id,
        message="test finding",
        severity=severity,
        category=ValidationCategory.SECURITY,
        resource_name=target,
        context={"target": target},
    )


BAD_DEPLOYMENT = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: legacy-backend
  labels: {app: legacy-backend}
spec:
  selector: {matchLabels: {app: legacy-backend}}
  template:
    spec:
      containers:
        - name: legacy-backend
          image: vendor/legacy:1.2.3
          resources:
            limits: {cpu: 100m, memory: 128Mi}
            requests: {cpu: 100m, memory: 128Mi}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: {drop: [ALL]}
            seccompProfile: {type: RuntimeDefault}
"""


class TestSuppressionSchema:
    def test_missing_reason_refuses_to_compile(self):
        with pytest.raises(ValidationError):
            Suppression(rule="VOL-K8S-0001", target="app", reason="")

    def test_whitespace_reason_refuses_to_compile(self):
        with pytest.raises(ValidationError):
            Suppression(rule="VOL-K8S-0001", target="app", reason="   ")

    def test_missing_target_refuses_to_compile(self):
        with pytest.raises(ValidationError):
            Suppression(rule="VOL-K8S-0001", target="", reason="JIRA-1: x")

    def test_missing_rule_refuses_to_compile(self):
        with pytest.raises(ValidationError):
            SuppressionSet.from_yaml(
                "suppressions:\n  - target: app\n    reason: because\n"
            )

    def test_valid_yaml_parses(self):
        ss = SuppressionSet.from_yaml(
            "suppressions:\n"
            "  - rule: VOL-K8S-0001\n"
            "    target: legacy-backend\n"
            "    reason: 'JIRA-4092: vendor image hardcoded to root'\n"
            "    expires: 2099-12-31\n"
        )
        assert len(ss) == 1
        assert ss.suppressions[0].expires == date(2099, 12, 31)

    def test_bare_list_yaml_parses(self):
        ss = SuppressionSet.from_yaml(
            "- rule: VOL-K8S-0001\n  target: app\n  reason: why\n"
        )
        assert len(ss) == 1


class TestWarningAnnihilation:
    def test_violation_without_suppression_fails(self):
        outcome = SuppressionEngine(SuppressionSet()).apply([finding()])
        assert len(outcome.results) == 1
        assert outcome.results[0].severity == ValidationSeverity.ERROR

    def test_suppressed_rule_emits_zero_warnings(self):
        ss = SuppressionSet(suppressions=[
            Suppression(rule="VOL-K8S-0001", target="app", reason="JIRA-1: ok"),
        ])
        outcome = SuppressionEngine(ss).apply([finding()])
        assert outcome.results == []
        assert outcome.hygiene == []
        assert len(outcome.applied) == 1

    def test_glob_target_matches(self):
        ss = SuppressionSet(suppressions=[
            Suppression(rule="VOL-K8S-0001", target="legacy-*", reason="JIRA-2: x"),
        ])
        outcome = SuppressionEngine(ss).apply([finding(target="legacy-backend")])
        assert outcome.results == []
        assert len(outcome.applied) == 1

    def test_suppression_scoped_to_target(self):
        ss = SuppressionSet(suppressions=[
            Suppression(rule="VOL-K8S-0001", target="other", reason="JIRA-3: x"),
        ])
        outcome = SuppressionEngine(ss).apply([finding(target="app")])
        # Finding survives; suppression is stale.
        assert len(outcome.results) == 1
        assert any(r.rule_id == "VOL-SUPPRESS-STALE" for r in outcome.hygiene)

    def test_expired_suppression_is_hard_error(self):
        ss = SuppressionSet(suppressions=[
            Suppression(
                rule="VOL-K8S-0001", target="app", reason="JIRA-4: x",
                expires=date.today() - timedelta(days=1),
            ),
        ])
        outcome = SuppressionEngine(ss).apply([finding()])
        # Finding NOT annihilated and an expiry error emitted.
        assert len(outcome.results) == 1
        expired = [r for r in outcome.hygiene if r.rule_id == "VOL-SUPPRESS-EXPIRED"]
        assert len(expired) == 1
        assert expired[0].severity == ValidationSeverity.ERROR

    def test_stale_suppression_warns(self):
        ss = SuppressionSet(suppressions=[
            Suppression(rule="VOL-K8S-0002", target="app", reason="JIRA-5: x"),
        ])
        outcome = SuppressionEngine(ss).apply([])
        stale = [r for r in outcome.hygiene if r.rule_id == "VOL-SUPPRESS-STALE"]
        assert len(stale) == 1
        assert stale[0].severity == ValidationSeverity.WARNING

    def test_unknown_rule_suppression_is_error(self):
        ss = SuppressionSet(suppressions=[
            Suppression(rule="VOL-NOPE-9999", target="*", reason="gaming attempt"),
        ])
        outcome = SuppressionEngine(ss).apply([finding()])
        assert len(outcome.results) == 1  # nothing annihilated
        assert any(
            r.rule_id == "VOL-SUPPRESS-UNKNOWN-RULE"
            and r.severity == ValidationSeverity.ERROR
            for r in outcome.hygiene
        )


class TestReceipts:
    def test_k8s_annotation_receipts(self):
        s = Suppression(rule="VOL-K8S-0001", target="app", reason="JIRA-9: legacy")
        annotations = k8s_receipt_annotations([s])
        assert annotations["volundr.asgard/suppress-VOL-K8S-0001"] == "true"
        assert "JIRA-9: legacy" in annotations["volundr.asgard/rationale"]

    def test_annotate_manifest_inserts_receipts(self):
        manifest = yaml.safe_load(BAD_DEPLOYMENT)
        s = Suppression(rule="VOL-K8S-0001", target="legacy-backend", reason="JIRA-9: x")
        annotate_k8s_manifest(manifest, [s])
        rendered = yaml.dump(manifest)
        assert "volundr.asgard/suppress-VOL-K8S-0001" in rendered
        assert "volundr.asgard/rationale" in rendered

    def test_comment_receipt_format(self):
        s = Suppression(rule="DL3007", target="Dockerfile", reason="pinning later")
        assert s.receipt_comment() == "# volundr:suppress=DL3007 pinning later"

    def test_append_comment_receipts(self):
        s = Suppression(rule="VOL-CICD-0002", target="build", reason="trusted fork")
        out = append_comment_receipts("jobs: {}\n", [s])
        assert out.endswith("# volundr:suppress=VOL-CICD-0002 trusted fork\n")


class TestEndToEndSuppression:
    def test_engine_annihilates_suppressed_rule_only(self):
        ss = SuppressionSet(suppressions=[
            Suppression(
                rule="VOL-K8S-0001", target="legacy-backend",
                reason="JIRA-4092: vendor image hardcoded to root, migration Q4",
            ),
        ])
        engine = ValidationEngine(suppressions=ss)
        report = engine.validate_kubernetes(BAD_DEPLOYMENT, "deploy.yaml")
        rule_ids = {r.rule_id for r in report.results}
        assert "VOL-K8S-0001" not in rule_ids  # annihilated, zero warnings
        # Other findings unaffected (e.g. automount token).
        assert "VOL-K8S-0008" in rule_ids

    def test_without_suppression_rule_fires(self):
        report = ValidationEngine().validate_kubernetes(BAD_DEPLOYMENT, "deploy.yaml")
        assert any(r.rule_id == "VOL-K8S-0001" for r in report.results)
        assert not report.passed
