"""
Volundr Kubernetes secure-by-default tests (plan 01).

Covers:
- the full NSA/CISA + CIS 5.x static control matrix over all five workload kinds
- always-on companion resources (ServiceAccount, NetworkPolicy, PDB, headless Service)
- auto emptyDir injection for writable paths under a read-only root filesystem
- digest pinning and AppArmor version-aware shape
- SecurityProfile-as-suppression-preset with machine-readable receipts
- warning-annihilation round trip and adversarial anti-gaming properties
- golden-file snapshots per (workload kind x suppression set)
- kubeconform external contract check (skip-if-unavailable)
"""

import os
import shutil
import subprocess
from datetime import date, timedelta

import pytest
import yaml

from Asgard.Volundr.Kubernetes import (
    EnvironmentType,
    ManifestConfig,
    ManifestGenerator,
    SecurityProfile,
    WorkloadType,
)
from Asgard.Volundr.Kubernetes.models.kubernetes_models import SecurityContext
from Asgard.Volundr.Kubernetes.services.manifest_generator import (
    PROFILE_PRESET_RULES,
    preset_suppressions,
)
from Asgard.Volundr.Validation.models.suppression_models import Suppression

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden", "kubernetes")

ALL_KINDS = [
    WorkloadType.DEPLOYMENT,
    WorkloadType.STATEFULSET,
    WorkloadType.DAEMONSET,
    WorkloadType.JOB,
    WorkloadType.CRONJOB,
]

POD_SPEC_PATH = {
    WorkloadType.DEPLOYMENT: ("spec", "template", "spec"),
    WorkloadType.STATEFULSET: ("spec", "template", "spec"),
    WorkloadType.DAEMONSET: ("spec", "template", "spec"),
    WorkloadType.JOB: ("spec", "template", "spec"),
    WorkloadType.CRONJOB: ("spec", "jobTemplate", "spec", "template", "spec"),
}


def _config(kind: WorkloadType, **kwargs) -> ManifestConfig:
    defaults = dict(
        name="hardened-app",
        image="registry.example.com/app:1.2.3",
        workload_type=kind,
        replicas=3,
        environment=EnvironmentType.PRODUCTION,
    )
    if kind == WorkloadType.CRONJOB:
        defaults["cron_schedule"] = "0 3 * * *"
    defaults.update(kwargs)
    return ManifestConfig(**defaults)


def _pod_spec(result, kind: WorkloadType) -> dict:
    workload = result.manifests[kind.value.lower()]
    node = workload
    for key in POD_SPEC_PATH[kind]:
        node = node[key]
    return node


# ---------------------------------------------------------------------------
# Full control matrix, uniform across all five workload kinds
# ---------------------------------------------------------------------------

class TestControlMatrixAllKinds:
    generator = ManifestGenerator()

    @pytest.mark.parametrize("kind", ALL_KINDS)
    def test_pod_level_controls(self, kind):
        result = self.generator.generate(_config(kind))
        pod = _pod_spec(result, kind)
        assert pod["automountServiceAccountToken"] is False  # CIS 5.1.6
        assert pod["serviceAccountName"] == "hardened-app"  # CIS 5.1.5
        sc = pod["securityContext"]
        assert sc["runAsNonRoot"] is True
        assert sc["fsGroup"] == 2000
        assert sc["fsGroupChangePolicy"] == "OnRootMismatch"
        assert sc["seccompProfile"] == {"type": "RuntimeDefault"}
        assert sc["appArmorProfile"] == {"type": "RuntimeDefault"}  # K8s >= 1.30

    @pytest.mark.parametrize("kind", ALL_KINDS)
    def test_container_level_controls(self, kind):
        result = self.generator.generate(_config(kind))
        container = _pod_spec(result, kind)["containers"][0]
        assert container["imagePullPolicy"] == "Always"  # NSA/CISA supply chain
        sc = container["securityContext"]
        assert sc["runAsNonRoot"] is True  # CIS 5.2.6
        assert sc["allowPrivilegeEscalation"] is False  # CIS 5.2.5
        assert sc["privileged"] is False  # CIS 5.2.1
        assert sc["readOnlyRootFilesystem"] is True
        assert sc["capabilities"]["drop"] == ["ALL"]  # CIS 5.2.9
        assert sc["seccompProfile"] == {"type": "RuntimeDefault"}  # container-level
        assert sc["runAsUser"] == 1000
        assert sc["runAsGroup"] == 3000
        resources = container["resources"]
        assert resources["limits"] and resources["requests"]

    @pytest.mark.parametrize("kind", ALL_KINDS)
    def test_auto_emptydir_for_tmp_with_ro_rootfs(self, kind):
        result = self.generator.generate(_config(kind))
        pod = _pod_spec(result, kind)
        mounts = pod["containers"][0]["volumeMounts"]
        assert any(m["mountPath"] == "/tmp" for m in mounts)
        vol = next(v for v in pod["volumes"] if v["name"] == "volundr-writable-tmp")
        assert vol["emptyDir"] == {}

    @pytest.mark.parametrize("kind", ALL_KINDS)
    def test_profiles_render_identical_hardening(self, kind):
        """Profiles are suppression presets, never alternate templates."""
        specs = [
            _pod_spec(self.generator.generate(_config(kind, security_profile=p)), kind)
            for p in SecurityProfile
        ]
        assert all(s == specs[0] for s in specs)

    def test_no_host_namespaces_emitted(self):
        result = self.generator.generate(_config(WorkloadType.DEPLOYMENT))
        pod = _pod_spec(result, WorkloadType.DEPLOYMENT)
        for field in ("hostNetwork", "hostPID", "hostIPC"):
            assert field not in pod


class TestCompanionResources:
    generator = ManifestGenerator()

    @pytest.mark.parametrize("kind", ALL_KINDS)
    def test_service_account_always_generated(self, kind):
        result = self.generator.generate(_config(kind))
        sa = result.manifests["serviceaccount"]
        assert sa["kind"] == "ServiceAccount"
        assert sa["automountServiceAccountToken"] is False

    def test_existing_service_account_not_regenerated(self):
        result = self.generator.generate(
            _config(WorkloadType.DEPLOYMENT, service_account="existing-sa")
        )
        assert "serviceaccount" not in result.manifests
        pod = _pod_spec(result, WorkloadType.DEPLOYMENT)
        assert pod["serviceAccountName"] == "existing-sa"

    @pytest.mark.parametrize("kind", ALL_KINDS)
    def test_network_policy_always_generated(self, kind):
        """NetPol regardless of profile or environment (CIS 5.3.2)."""
        result = self.generator.generate(
            _config(kind, security_profile=SecurityProfile.BASIC,
                    environment=EnvironmentType.DEVELOPMENT)
        )
        netpol = result.manifests["networkpolicy"]
        spec = netpol["spec"]
        assert set(spec["policyTypes"]) == {"Ingress", "Egress"}
        # DNS egress carve-out
        dns = spec["egress"][0]["ports"]
        assert {"protocol": "TCP", "port": 53} in dns
        assert {"protocol": "UDP", "port": 53} in dns
        # ingress allows only declared ports
        assert spec["ingress"][0]["ports"] == [{"protocol": "TCP", "port": 8080}]

    def test_network_policy_declared_egress_rules(self):
        from Asgard.Volundr.Kubernetes import EgressRule
        result = self.generator.generate(_config(
            WorkloadType.DEPLOYMENT,
            egress_rules=[EgressRule(cidr="10.0.0.0/8", ports=[5432])],
        ))
        egress = result.manifests["networkpolicy"]["spec"]["egress"]
        assert {"to": [{"ipBlock": {"cidr": "10.0.0.0/8"}}],
                "ports": [{"protocol": "TCP", "port": 5432}]} in egress

    def test_pdb_generated_in_any_environment_when_replicas_gt_1(self):
        result = self.generator.generate(_config(
            WorkloadType.DEPLOYMENT, environment=EnvironmentType.DEVELOPMENT, replicas=2,
        ))
        assert result.manifests["poddisruptionbudget"]["spec"]["minAvailable"] == 1

    def test_pdb_not_generated_for_single_replica(self):
        result = self.generator.generate(_config(WorkloadType.DEPLOYMENT, replicas=1))
        assert "poddisruptionbudget" not in result.manifests

    def test_statefulset_headless_service_emitted(self):
        """Regression: serviceName referenced a Service that was never rendered."""
        result = self.generator.generate(_config(WorkloadType.STATEFULSET))
        sts = result.manifests["statefulset"]
        headless = result.manifests["service-headless"]
        assert sts["spec"]["serviceName"] == headless["metadata"]["name"]
        assert headless["spec"]["clusterIP"] == "None"

    def test_configmap_uses_real_data_not_stub(self):
        result = self.generator.generate(_config(
            WorkloadType.DEPLOYMENT,
            config_maps=["app-config"],
            configmap_data={"app-config": {"LOG_LEVEL": "info"}},
        ))
        assert result.manifests["configmap-app-config"]["data"] == {"LOG_LEVEL": "info"}

    def test_empty_secret_yields_completeness_finding_not_fake_data(self):
        result = self.generator.generate(_config(
            WorkloadType.DEPLOYMENT,
            security_profile=SecurityProfile.ZERO_TRUST,
            secrets=["db-creds"],
        ))
        secret = result.manifests["secret-db-creds"]
        assert secret["stringData"] == {}
        assert any("VOL-K8S-0014" in issue for issue in result.validation_results)


class TestImageAndAppArmor:
    generator = ManifestGenerator()

    def test_digest_pinning(self):
        digest = "sha256:" + "a" * 64
        result = self.generator.generate(_config(WorkloadType.DEPLOYMENT, image_digest=digest))
        container = _pod_spec(result, WorkloadType.DEPLOYMENT)["containers"][0]
        assert container["image"] == f"registry.example.com/app@{digest}"

    def test_no_digest_yields_completeness_finding_under_zero_trust(self):
        result = self.generator.generate(_config(
            WorkloadType.DEPLOYMENT, security_profile=SecurityProfile.ZERO_TRUST,
        ))
        assert any("VOL-K8S-0013" in issue for issue in result.validation_results)

    def test_apparmor_annotation_fallback_pre_130(self):
        result = self.generator.generate(_config(
            WorkloadType.DEPLOYMENT, target_k8s_version="1.28",
        ))
        workload = result.manifests["deployment"]
        annotations = workload["spec"]["template"]["metadata"]["annotations"]
        key = "container.apparmor.security.beta.kubernetes.io/hardened-app"
        assert annotations[key] == "runtime/default"
        pod_sc = workload["spec"]["template"]["spec"]["securityContext"]
        assert "appArmorProfile" not in pod_sc


# ---------------------------------------------------------------------------
# Profile presets + reified suppressions + receipts
# ---------------------------------------------------------------------------

class TestSuppressionsAndPresets:
    generator = ManifestGenerator()

    def test_zero_trust_is_empty_preset(self):
        assert preset_suppressions(SecurityProfile.ZERO_TRUST) == []
        assert PROFILE_PRESET_RULES[SecurityProfile.ZERO_TRUST] == []

    def test_preset_reasons_are_marked(self):
        for s in preset_suppressions(SecurityProfile.BASIC):
            assert s.reason.startswith("preset:basic")

    def test_basic_preset_annihilates_digest_finding_with_receipt(self):
        result = self.generator.generate(_config(WorkloadType.DEPLOYMENT))
        assert not any("VOL-K8S-0013" in issue for issue in result.validation_results)
        assert "VOL-K8S-0013" in result.applied_suppressions
        annotations = result.manifests["deployment"]["metadata"]["annotations"]
        assert annotations["volundr.asgard/suppress-VOL-K8S-0013"] == "true"
        assert "preset:basic" in annotations["volundr.asgard/rationale"]
        # receipt is present in the rendered YAML, not just the dict
        assert "volundr.asgard/suppress-VOL-K8S-0013" in result.yaml_content

    def test_warning_annihilation_round_trip(self):
        """Relax a control via config; without a suppression it warns, with a
        justified suppression it emits ZERO warnings plus a receipt."""
        relaxed = dict(
            security_context=SecurityContext(read_only_root_filesystem=False),
            security_profile=SecurityProfile.ZERO_TRUST,
            image_digest="sha256:" + "b" * 64,
            replicas=1,  # no PDB -> no VOL-K8S-0015 completeness hint
        )
        without = self.generator.generate(_config(WorkloadType.DEPLOYMENT, **relaxed))
        assert any("VOL-K8S-0004" in issue for issue in without.validation_results)

        with_suppression = self.generator.generate(_config(
            WorkloadType.DEPLOYMENT,
            suppressions=[Suppression(
                rule="VOL-K8S-0004", target="hardened-app",
                reason="JIRA-123: legacy app writes to /var/lib at runtime",
            )],
            **relaxed,
        ))
        assert with_suppression.validation_results == []
        assert with_suppression.best_practice_score == 100.0
        annotations = with_suppression.manifests["deployment"]["metadata"]["annotations"]
        assert annotations["volundr.asgard/suppress-VOL-K8S-0004"] == "true"
        assert "JIRA-123" in annotations["volundr.asgard/rationale"]

    def test_suppression_requires_reason(self):
        with pytest.raises(Exception):
            Suppression(rule="VOL-K8S-0004", target="*", reason="   ")

    def test_unknown_rule_suppression_is_hard_error(self):
        result = self.generator.generate(_config(
            WorkloadType.DEPLOYMENT,
            suppressions=[Suppression(rule="VOL-NOPE-9999", target="*", reason="x")],
        ))
        assert any("VOL-SUPPRESS-UNKNOWN-RULE" in i for i in result.validation_results)
        assert result.best_practice_score < 100.0

    def test_expired_suppression_is_hard_error(self):
        result = self.generator.generate(_config(
            WorkloadType.DEPLOYMENT,
            suppressions=[Suppression(
                rule="VOL-K8S-0013", target="*", reason="old",
                expires=date.today() - timedelta(days=1),
            )],
        ))
        assert any("VOL-SUPPRESS-EXPIRED" in i for i in result.validation_results)

    def test_stale_user_suppression_warns(self):
        result = self.generator.generate(_config(
            WorkloadType.DEPLOYMENT,
            image_digest="sha256:" + "c" * 64,
            suppressions=[Suppression(
                rule="VOL-K8S-0004", target="hardened-app", reason="never fires",
            )],
        ))
        assert any("VOL-SUPPRESS-STALE" in i for i in result.validation_results)


# ---------------------------------------------------------------------------
# Adversarial anti-gaming
# ---------------------------------------------------------------------------

class TestAdversarialAntiGaming:
    generator = ManifestGenerator()

    def _score(self, **kwargs) -> float:
        return self.generator.generate(_config(WorkloadType.DEPLOYMENT, **kwargs)).best_practice_score

    def test_resource_dilution_does_not_improve_score(self):
        """Adding clean companion resources must not wash out a finding."""
        base = self._score(security_profile=SecurityProfile.ZERO_TRUST)
        diluted = self._score(
            security_profile=SecurityProfile.ZERO_TRUST,
            config_maps=[f"cm-{i}" for i in range(10)],
            configmap_data={f"cm-{i}": {"k": "v"} for i in range(10)},
        )
        assert diluted <= base

    def test_relaxed_controls_lower_score(self):
        hardened = self._score(security_profile=SecurityProfile.ZERO_TRUST,
                               image_digest="sha256:" + "d" * 64)
        relaxed = self._score(
            security_profile=SecurityProfile.ZERO_TRUST,
            image_digest="sha256:" + "d" * 64,
            security_context=SecurityContext(
                run_as_non_root=False,
                read_only_root_filesystem=False,
                allow_privilege_escalation=True,
            ),
        )
        assert hardened == 100.0
        assert relaxed < hardened

    def test_suppressing_via_bogus_rule_id_does_not_help(self):
        relaxed_ctx = SecurityContext(read_only_root_filesystem=False)
        honest = self._score(security_profile=SecurityProfile.ZERO_TRUST,
                             image_digest="sha256:" + "e" * 64,
                             security_context=relaxed_ctx)
        gamed = self._score(
            security_profile=SecurityProfile.ZERO_TRUST,
            image_digest="sha256:" + "e" * 64,
            security_context=relaxed_ctx,
            suppressions=[Suppression(rule="TOTALLY-FAKE", target="*", reason="lol")],
        )
        assert gamed <= honest

    def test_generator_does_not_grade_its_own_intent(self):
        """The score must come from the rendered YAML via the Validation
        engine — mutating rendered output must change the verdict."""
        result = self.generator.generate(_config(
            WorkloadType.DEPLOYMENT,
            security_profile=SecurityProfile.ZERO_TRUST,
            image_digest="sha256:" + "f" * 64,
        ))
        assert result.validation_report is not None
        assert result.validation_report.validator == "ValidationEngine"
        from Asgard.Volundr.Validation.services.validation_engine import ValidationEngine
        tampered = result.yaml_content.replace(
            "readOnlyRootFilesystem: true", "readOnlyRootFilesystem: false"
        )
        report = ValidationEngine().validate_kubernetes(tampered)
        assert any(r.rule_id == "VOL-K8S-0004" for r in report.results)


# ---------------------------------------------------------------------------
# Golden files: workload kind x suppression set
# ---------------------------------------------------------------------------

GOLDEN_SETS = {
    "zero-trust": dict(security_profile=SecurityProfile.ZERO_TRUST),
    "basic-preset": dict(security_profile=SecurityProfile.BASIC),
    "suppressed-ro-rootfs": dict(
        security_profile=SecurityProfile.ZERO_TRUST,
        image_digest="sha256:" + "0" * 64,
        security_context=SecurityContext(read_only_root_filesystem=False),
        suppressions=[Suppression(
            rule="VOL-K8S-0004", target="hardened-app",
            reason="GOLDEN-1: fixture app requires writable rootfs",
        )],
    ),
}


class TestGoldenFiles:
    generator = ManifestGenerator()

    @pytest.mark.parametrize("kind", ALL_KINDS)
    @pytest.mark.parametrize("set_name", sorted(GOLDEN_SETS))
    def test_golden(self, kind, set_name):
        result = self.generator.generate(_config(kind, **GOLDEN_SETS[set_name]))
        path = os.path.join(GOLDEN_DIR, f"{kind.value.lower()}_{set_name}.yaml")
        assert os.path.exists(path), (
            f"Missing golden file {path} — regenerate deliberately with "
            "Asgard_Test/tests_Volundr/golden/kubernetes/regenerate.py and review the diff"
        )
        with open(path, "r", encoding="utf-8") as f:
            expected = f.read()
        assert result.yaml_content == expected, (
            f"Rendered output for {kind.value}/{set_name} diverged from golden file "
            f"{path}; review like code and regenerate if intended"
        )


# ---------------------------------------------------------------------------
# External contract: kubeconform (skip-if-unavailable)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(shutil.which("kubeconform") is None, reason="kubeconform not installed")
class TestKubeconformContract:
    generator = ManifestGenerator()

    @pytest.mark.parametrize("kind", ALL_KINDS)
    def test_kubeconform_strict(self, kind, tmp_path):
        result = self.generator.generate(_config(kind))
        path = tmp_path / "manifest.yaml"
        path.write_text(result.yaml_content, encoding="utf-8")
        proc = subprocess.run(
            ["kubeconform", "-strict", "-summary", str(path)],
            capture_output=True, text=True, timeout=120,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr


# ---------------------------------------------------------------------------
# YAML sanity for the full document set
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ALL_KINDS)
def test_all_documents_parse_and_have_core_fields(kind):
    result = ManifestGenerator().generate(_config(kind))
    docs = [d for d in yaml.safe_load_all(result.yaml_content) if d]
    assert len(docs) == len(result.manifests)
    for doc in docs:
        for field in ("apiVersion", "kind", "metadata"):
            assert field in doc
