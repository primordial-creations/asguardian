"""Four-tier validation engine tests: schema binding, skew downgrade,
canonical normalization, default-deny policies, SARIF/JUnit emission,
and adversarial score-gaming resistance."""

import warnings
import xml.etree.ElementTree as ET

import pytest
import yaml

from Asgard.Volundr.Validation import (
    COMPUTED,
    TAINTED,
    ValidationContext,
    ValidationEngine,
    default_registry,
    is_computed,
    is_tainted,
    to_junit_xml,
    to_sarif,
)
from Asgard.Volundr.Validation.models.canonical_models import CanonicalContainer
from Asgard.Volundr.Validation.models.rule_registry import RuleSeverity
from Asgard.Volundr.Validation.models.validation_models import ValidationSeverity
from Asgard.Volundr.Validation.services.normalizers import (
    POD_SPEC_PATHS,
    normalize_manifest,
)
from Asgard.Volundr.Validation.services.schema_binder import SchemaBinder
from Asgard.Volundr.Validation.services.semantic_policies import PolicyEngine


HARDENED_CONTAINER = {
    "name": "app",
    "image": "registry.example.com/app@sha256:" + "a" * 64,
    "resources": {
        "limits": {"cpu": "100m", "memory": "128Mi"},
        "requests": {"cpu": "100m", "memory": "128Mi"},
    },
    "securityContext": {
        "runAsNonRoot": True,
        "allowPrivilegeEscalation": False,
        "readOnlyRootFilesystem": True,
        "privileged": False,
        "capabilities": {"drop": ["ALL"]},
        "seccompProfile": {"type": "RuntimeDefault"},
    },
}


def make_workload(kind: str, container=None) -> dict:
    """Build a manifest of any workload kind with the correct nested PodSpec."""
    import copy
    pod_spec = {
        "automountServiceAccountToken": False,
        "containers": [copy.deepcopy(container or HARDENED_CONTAINER)],
    }
    metadata = {"name": "app", "labels": {"app": "app"}}
    if kind == "Pod":
        return {"apiVersion": "v1", "kind": "Pod", "metadata": metadata,
                "spec": pod_spec}
    template = {"metadata": metadata, "spec": pod_spec}
    if kind == "CronJob":
        return {
            "apiVersion": "batch/v1", "kind": "CronJob", "metadata": metadata,
            "spec": {"schedule": "0 0 * * *",
                     "jobTemplate": {"spec": {"template": template}}},
        }
    if kind == "Job":
        return {"apiVersion": "batch/v1", "kind": "Job", "metadata": metadata,
                "spec": {"template": template}}
    return {
        "apiVersion": "apps/v1", "kind": kind, "metadata": metadata,
        "spec": {"selector": {"matchLabels": {"app": "app"}},
                 "template": template,
                 **({"serviceName": "app"} if kind == "StatefulSet" else {})},
    }


class TestSentinels:
    def test_sentinels_are_falsy_and_typed(self):
        assert not COMPUTED and not TAINTED
        assert is_computed(COMPUTED) and not is_computed(TAINTED)
        assert is_tainted(TAINTED) and not is_tainted(COMPUTED)
        assert repr(COMPUTED) == "<computed>"
        assert repr(TAINTED) == "<tainted>"


class TestNormalizerPathMatrix:
    """Same rule must fire identically across all workload kinds."""

    @pytest.mark.parametrize("kind", sorted(POD_SPEC_PATHS))
    def test_pod_spec_path_normalization(self, kind):
        workload = normalize_manifest(make_workload(kind))
        assert workload is not None
        assert workload.kind == kind
        assert len(workload.containers) == 1
        assert workload.containers[0].run_as_non_root is True
        assert workload.pod_spec_path == POD_SPEC_PATHS[kind]

    @pytest.mark.parametrize("kind", sorted(POD_SPEC_PATHS))
    def test_run_as_non_root_rule_fires_identically(self, kind):
        bad = dict(HARDENED_CONTAINER)
        bad["securityContext"] = dict(bad["securityContext"])
        del bad["securityContext"]["runAsNonRoot"]
        manifest = make_workload(kind, bad)
        results = PolicyEngine().check_workload(normalize_manifest(manifest))
        assert any(r.rule_id == "VOL-K8S-0001" for r in results), kind

    @pytest.mark.parametrize("kind", sorted(POD_SPEC_PATHS))
    def test_hardened_workload_has_no_security_findings(self, kind):
        results = PolicyEngine().check_workload(
            normalize_manifest(make_workload(kind))
        )
        assert results == [], [r.rule_id for r in results]


class TestDefaultDenyPolicies:
    """Policies assert presence of safety, never absence of danger."""

    def test_absent_security_context_fails_closed(self):
        container = {"name": "app", "image": "app:1.0",
                     "resources": HARDENED_CONTAINER["resources"]}
        results = PolicyEngine().check_workload(
            normalize_manifest(make_workload("Deployment", container))
        )
        rule_ids = {r.rule_id for r in results}
        # Absence of every safety assertion fails, not just explicit danger.
        assert {"VOL-K8S-0001", "VOL-K8S-0002", "VOL-K8S-0003",
                "VOL-K8S-0004", "VOL-K8S-0007"} <= rule_ids

    def test_run_as_non_root_false_fails(self):
        bad = dict(HARDENED_CONTAINER)
        bad["securityContext"] = {**bad["securityContext"], "runAsNonRoot": False}
        results = PolicyEngine().check_workload(
            normalize_manifest(make_workload("Deployment", bad))
        )
        assert any(r.rule_id == "VOL-K8S-0001" for r in results)

    def test_computed_value_does_not_fail_open(self):
        container = CanonicalContainer(
            name="app", image="app:1.0",
            run_as_non_root=COMPUTED,
            allow_privilege_escalation=False,
            read_only_root_filesystem=True,
            capabilities_drop=["ALL"],
            seccomp_profile_type="RuntimeDefault",
            has_resource_limits=True, has_resource_requests=True,
        )
        registry = default_registry()
        engine = PolicyEngine(registry)
        finding = engine._finding(
            "VOL-K8S-0001", "unknown", target="app",
            value=container.run_as_non_root,
        )
        # Default-deny: computed value still yields a (softened) finding.
        assert finding is not None
        assert finding.severity == ValidationSeverity.WARNING


class TestSchemaBindingAndSkew:
    def test_unknown_field_is_error_within_known_versions(self):
        manifest = make_workload("Deployment")
        manifest["spec"]["frobnicate"] = True
        binder = SchemaBinder(ValidationContext(kubernetes_version="1.29"))
        outcome = binder.bind(manifest)
        unknown = [r for r in outcome.results if r.rule_id == "VOL-K8S-0011"]
        assert len(unknown) == 1
        assert unknown[0].severity == ValidationSeverity.ERROR
        assert outcome.tainted is False

    def test_version_skew_downgrades_to_warn_and_taints(self):
        manifest = make_workload("Deployment")
        manifest["spec"]["frobnicate"] = True
        binder = SchemaBinder(ValidationContext(kubernetes_version="1.99"))
        outcome = binder.bind(manifest)
        unknown = [r for r in outcome.results if r.rule_id == "VOL-K8S-0011"]
        assert len(unknown) == 1
        assert unknown[0].severity == ValidationSeverity.WARNING
        assert outcome.tainted is True

    def test_tainted_node_does_not_fail_open(self):
        """A policy on a tainted node still emits a finding (default-deny)."""
        manifest = make_workload("Deployment")
        # Remove the safety assertion AND introduce skew taint.
        del manifest["spec"]["template"]["spec"]["containers"][0][
            "securityContext"]["runAsNonRoot"]
        manifest["spec"]["futureField"] = True
        engine = ValidationEngine(ValidationContext(kubernetes_version="1.99"))
        report = engine.validate_kubernetes(yaml.dump(manifest))
        assert any(r.rule_id == "VOL-K8S-0001" for r in report.results)

    def test_deprecated_api_version_flagged(self):
        manifest = make_workload("CronJob")
        manifest["apiVersion"] = "batch/v1beta1"
        outcome = SchemaBinder().bind(manifest)
        assert any(
            r.rule_id == "VOL-K8S-0012"
            and r.severity == ValidationSeverity.ERROR
            for r in outcome.results
        )


class TestEngineEndToEnd:
    def test_hardened_manifest_passes(self):
        report = ValidationEngine().validate_kubernetes(
            yaml.dump(make_workload("Deployment")), "deploy.yaml"
        )
        assert report.passed, [r.message for r in report.error_results]
        assert report.results == []

    def test_line_numbers_populated(self):
        bad = dict(HARDENED_CONTAINER)
        bad["securityContext"] = dict(bad["securityContext"])
        del bad["securityContext"]["runAsNonRoot"]
        report = ValidationEngine().validate_kubernetes(
            yaml.dump(make_workload("Deployment", bad)), "deploy.yaml"
        )
        finding = next(r for r in report.results if r.rule_id == "VOL-K8S-0001")
        assert finding.line_number is not None and finding.line_number > 0

    def test_compose_obsolete_version_key_flagged(self):
        report = ValidationEngine().validate_compose(
            "version: '3.8'\nservices:\n  web:\n    image: nginx:1.25\n"
        )
        assert any(r.rule_id == "VOL-COMPOSE-0001" for r in report.results)

    def test_compose_privileged_and_unpinned(self):
        report = ValidationEngine().validate_compose(
            "services:\n  web:\n    image: nginx:latest\n"
            "    privileged: true\n    ports: ['0.0.0.0:80:80']\n"
        )
        rule_ids = {r.rule_id for r in report.results}
        assert {"VOL-COMPOSE-0002", "VOL-COMPOSE-0004", "VOL-COMPOSE-0005"} <= rule_ids

    def test_pipeline_zero_trust_rules(self):
        workflow = (
            "name: ci\n'on': push\njobs:\n  build:\n"
            "    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: actions/checkout@v4\n"
        )
        report = ValidationEngine().validate_pipeline(workflow)
        rule_ids = {r.rule_id for r in report.results}
        assert {"VOL-CICD-0001", "VOL-CICD-0002", "VOL-CICD-0003"} <= rule_ids

    def test_pipeline_sha_pinned_passes_pin_rule(self):
        workflow = (
            "name: ci\n'on': push\npermissions: {}\njobs:\n  build:\n"
            "    runs-on: ubuntu-latest\n    timeout-minutes: 15\n    steps:\n"
            f"      - uses: actions/checkout@{'a' * 40}\n"
        )
        report = ValidationEngine().validate_pipeline(workflow)
        assert not any(r.rule_id == "VOL-CICD-0002" for r in report.results)
        assert not any(r.rule_id == "VOL-CICD-0001" for r in report.results)

    def test_ignore_rules_deprecation_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ValidationEngine(ValidationContext(ignore_rules=["VOL-K8S-0001"]))
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)


class TestAdversarialScoreGaming:
    """Attempts to game the score must not improve it."""

    def test_dilution_with_compliant_docs_does_not_pass_report(self):
        bad = dict(HARDENED_CONTAINER)
        bad["securityContext"] = {**bad["securityContext"], "privileged": True}
        bad_doc = yaml.dump(make_workload("Deployment", bad))
        good_doc = yaml.dump(make_workload("Deployment"))
        engine = ValidationEngine()

        lone = engine.validate_kubernetes(bad_doc)
        diluted = engine.validate_kubernetes(
            "---\n".join([bad_doc] + [good_doc] * 20)
        )
        assert not lone.passed
        assert not diluted.passed
        assert diluted.total_errors >= lone.total_errors
        assert diluted.score <= lone.score  # padding must not raise the score

    def test_wildcard_suppression_of_unknown_rule_rejected(self):
        from Asgard.Volundr.Validation import Suppression, SuppressionSet
        ss = SuppressionSet(suppressions=[
            Suppression(rule="VOL-*", target="*", reason="suppress everything"),
        ])
        bad = dict(HARDENED_CONTAINER)
        bad["securityContext"] = {**bad["securityContext"], "privileged": True}
        report = ValidationEngine(suppressions=ss).validate_kubernetes(
            yaml.dump(make_workload("Deployment", bad))
        )
        # Rule globs are not honored: the violation survives and the bogus
        # suppression is itself an error.
        assert any(r.rule_id == "VOL-K8S-0009" for r in report.results)
        assert any(r.rule_id == "VOL-SUPPRESS-UNKNOWN-RULE" for r in report.results)
        assert not report.passed

    def test_generator_intent_is_not_graded(self):
        """The engine only sees rendered YAML — a 'trust me' annotation
        claiming hardening must not affect findings."""
        manifest = make_workload("Deployment", {
            "name": "app", "image": "app:1.0",
            "resources": HARDENED_CONTAINER["resources"],
        })
        manifest["metadata"]["annotations"] = {
            "volundr.asgard/security-profile": "ZERO_TRUST",
        }
        report = ValidationEngine().validate_kubernetes(yaml.dump(manifest))
        assert any(r.rule_id == "VOL-K8S-0001" for r in report.results)


class TestSeverityTaxonomy:
    def test_five_levels_map_to_legacy(self):
        assert RuleSeverity.CRITICAL.to_validation_severity() == ValidationSeverity.ERROR
        assert RuleSeverity.HIGH.to_validation_severity() == ValidationSeverity.ERROR
        assert RuleSeverity.MEDIUM.to_validation_severity() == ValidationSeverity.WARNING
        assert RuleSeverity.LOW.to_validation_severity() == ValidationSeverity.INFO
        assert RuleSeverity.INFO.to_validation_severity() == ValidationSeverity.HINT

    def test_round_trip_from_legacy(self):
        for legacy in ValidationSeverity:
            assert RuleSeverity.from_validation_severity(legacy).to_validation_severity() == legacy


class TestReportEmitters:
    def _bad_report(self):
        bad = dict(HARDENED_CONTAINER)
        bad["securityContext"] = {**bad["securityContext"], "privileged": True}
        return ValidationEngine().validate_kubernetes(
            yaml.dump(make_workload("Deployment", bad)), "deploy.yaml"
        )

    def test_sarif_structure_and_help_markdown(self):
        report = self._bad_report()
        sarif = to_sarif(report)
        assert sarif["version"] == "2.1.0"
        assert "$schema" in sarif
        run = sarif["runs"][0]
        rules = run["tool"]["driver"]["rules"]
        assert rules, "rules[] must be populated from the registry"
        for rule in rules:
            assert rule["help"]["markdown"], rule["id"]
        result_rule_ids = {r["ruleId"] for r in run["results"]}
        assert result_rule_ids <= {r["id"] for r in rules}
        levels = {r["level"] for r in run["results"]}
        assert levels <= {"error", "warning", "note", "none"}

    def test_sarif_locations_carry_lines(self):
        sarif = to_sarif(self._bad_report())
        located = [
            r for r in sarif["runs"][0]["results"]
            if "locations" in r
            and "region" in r["locations"][0]["physicalLocation"]
        ]
        assert located

    def test_junit_xml_well_formed(self):
        xml_text = to_junit_xml(self._bad_report())
        suite = ET.fromstring(xml_text)
        assert suite.tag == "testsuite"
        assert int(suite.get("errors")) >= 1

    def test_junit_clean_report_emits_passing_case(self):
        report = ValidationEngine().validate_kubernetes(
            yaml.dump(make_workload("Deployment")), "deploy.yaml"
        )
        suite = ET.fromstring(to_junit_xml(report))
        assert suite.get("errors") == "0"
        assert len(list(suite)) >= 1
