"""
Volundr GitOps / Kustomize tests (plan 05 remainder).

Covers Kustomize v5 semantics (labels+includeSelectors, replacements not
vars, components), ArgoCD safe defaults (pinned revisions, non-default
project, repoURL/destination allowlists, ServerSideDiff, prune guard,
AppProject generation), Flux health-check encouragement, and the
render->validate pipeline (external tools skip-if-unavailable).
"""

import shutil

import pytest
import yaml

from Asgard.Volundr.GitOps import (
    ArgoApplication,
    ArgoAppProject,
    ArgoDestination,
    ArgoSource,
    ArgoCDGenerator,
    GitOpsPolicy,
)
from Asgard.Volundr.GitOps.models.gitops_models import (
    ArgoSourceHelm,
    FluxKustomization,
)
from Asgard.Volundr.GitOps.services.argocd_generator_helpers import (
    ignore_differences_preset,
)
from Asgard.Volundr.GitOps.services.flux_generator_helpers import (
    validate_kustomization,
)
from Asgard.Volundr.Kustomize import (
    BaseGenerator,
    ComponentGenerator,
    KustomizeBase,
    KustomizeComponent,
    KustomizeConfig,
    KustomizeOverlay,
    OverlayGenerator,
    Replacement,
    ReplacementSource,
    ReplacementTarget,
    ReplacementTargetSelect,
)
from Asgard.Volundr.Validation import render_and_validate, render_kustomize


def make_app(**kwargs):
    source = kwargs.pop("source", None) or ArgoSource(
        repo_url="https://git.example.com/org/repo.git",
        target_revision="v1.2.3",
        path="deploy",
    )
    return ArgoApplication(
        name=kwargs.pop("name", "myapp"),
        project=kwargs.pop("project", "platform"),
        source=source,
        destination=ArgoDestination(namespace="prod"),
        **kwargs,
    )


class TestArgoSafeDefaults:
    def test_head_revision_flagged(self):
        app = make_app(source=ArgoSource(
            repo_url="https://git.example.com/org/repo.git",
            target_revision="HEAD",
        ))
        result = ArgoCDGenerator().generate(app)
        assert any("VOL-GITOPS-0001" in r for r in result.validation_results)

    def test_default_project_flagged_and_caps_score(self):
        result = ArgoCDGenerator().generate(make_app(project="default"))
        assert any("VOL-GITOPS-0002" in r for r in result.validation_results)
        # HIGH security finding -> composite capped at 70 (plan 07 veto).
        assert result.best_practice_score <= 70

    def test_server_side_diff_annotation_default(self):
        result = ArgoCDGenerator().generate(make_app())
        manifest = yaml.safe_load(result.files["myapp-application.yaml"])
        assert manifest["metadata"]["annotations"][
            "argocd.argoproj.io/compare-options"
        ] == "ServerSideDiff=true"

    def test_explicit_compare_options_not_overwritten(self):
        app = make_app(annotations={
            "argocd.argoproj.io/compare-options": "IncludeMutationWebhook=true",
        })
        result = ArgoCDGenerator().generate(app)
        manifest = yaml.safe_load(result.files["myapp-application.yaml"])
        assert manifest["metadata"]["annotations"][
            "argocd.argoproj.io/compare-options"
        ] == "IncludeMutationWebhook=true"

    def test_helm_chart_range_flagged(self):
        app = make_app(source=ArgoSource(
            repo_url="https://charts.example.com",
            target_revision="v1",
            helm=ArgoSourceHelm(
                chart="redis", repo_url="https://charts.example.com",
            ),  # target_revision defaults to "*" — an unpinned range
        ))
        result = ArgoCDGenerator().generate(app)
        assert any("VOL-GITOPS-0005" in r for r in result.validation_results)

    def test_prune_blast_radius_documented(self):
        result = ArgoCDGenerator().generate(make_app())
        assert any("VOL-GITOPS-0006" in r for r in result.validation_results)

    def test_ignore_differences_presets(self):
        preset = ignore_differences_preset("hpa-replicas")
        assert preset["jsonPointers"] == ["/spec/replicas"]
        with pytest.raises(KeyError):
            ignore_differences_preset("nonsense")


class TestGitOpsPolicyAllowlists:
    def test_repo_not_in_allowlist_flagged(self):
        policy = GitOpsPolicy(
            allowed_repo_patterns=["https://git.corp.example.com/*"],
        )
        result = ArgoCDGenerator().generate(make_app(), policy=policy)
        assert any("VOL-GITOPS-0003" in r for r in result.validation_results)

    def test_repo_in_allowlist_not_flagged(self):
        policy = GitOpsPolicy(
            allowed_repo_patterns=["https://git.example.com/*"],
        )
        result = ArgoCDGenerator().generate(make_app(), policy=policy)
        assert not any("VOL-GITOPS-0003" in r for r in result.validation_results)

    def test_destination_allowlist(self):
        policy = GitOpsPolicy(
            allowed_destination_servers=["https://prod.k8s.example.com"],
        )
        result = ArgoCDGenerator().generate(make_app(), policy=policy)
        assert any("VOL-GITOPS-0004" in r for r in result.validation_results)

    def test_empty_policy_flags_nothing(self):
        result = ArgoCDGenerator().generate(make_app(), policy=GitOpsPolicy())
        assert not any(
            "VOL-GITOPS-0003" in r or "VOL-GITOPS-0004" in r
            for r in result.validation_results
        )


class TestAppProject:
    def test_generate_app_project_manifest(self):
        project = ArgoAppProject(
            name="platform",
            source_repos=["https://git.example.com/org/*"],
            destinations=[{"server": "https://kubernetes.default.svc",
                           "namespace": "prod"}],
        )
        result = ArgoCDGenerator().generate_app_project(project)
        manifest = yaml.safe_load(result.files["platform-appproject.yaml"])
        assert manifest["kind"] == "AppProject"
        assert manifest["spec"]["sourceRepos"] == ["https://git.example.com/org/*"]
        assert manifest["spec"]["destinations"][0]["namespace"] == "prod"

    def test_default_named_app_project_flagged(self):
        project = ArgoAppProject(name="default")
        result = ArgoCDGenerator().generate_app_project(project)
        assert any("VOL-GITOPS-0002" in r for r in result.validation_results)


class TestFluxHealthChecks:
    def test_missing_health_checks_flagged(self):
        ks = FluxKustomization(name="apps", source_ref_name="repo")
        assert any("VOL-GITOPS-0007" in i for i in validate_kustomization(ks))

    def test_present_health_checks_not_flagged(self):
        ks = FluxKustomization(
            name="apps", source_ref_name="repo",
            health_checks=[{"apiVersion": "apps/v1", "kind": "Deployment",
                            "name": "web", "namespace": "prod"}],
        )
        assert not any("VOL-GITOPS-0007" in i for i in validate_kustomization(ks))


class TestKustomizeV5:
    def config(self, **base_kwargs):
        base = KustomizeBase(
            name="web",
            common_labels={"team": "platform"},
            **base_kwargs,
        )
        return KustomizeConfig(base=base, image="web:1.0")

    def test_no_commonlabels_anywhere(self):
        result = BaseGenerator().generate(self.config())
        for path, content in result.files.items():
            assert "commonLabels" not in content, path
            assert "vars:" not in content, path

    def test_labels_transformer_with_include_selectors_false(self):
        result = BaseGenerator().generate(self.config())
        kustomization = yaml.safe_load(result.files["base/kustomization.yaml"])
        assert kustomization["labels"] == [
            {"pairs": {"team": "platform"}, "includeSelectors": False}
        ]

    def test_overlay_labels_transformer(self):
        overlay = KustomizeOverlay(
            name="production", common_labels={"env": "prod"},
        )
        result = OverlayGenerator().generate(overlay)
        content = result.files["overlays/production/kustomization.yaml"]
        assert "commonLabels" not in content
        parsed = yaml.safe_load(content)
        assert parsed["labels"][0]["includeSelectors"] is False

    def test_replacements_emitted_never_vars(self):
        replacement = Replacement(
            source=ReplacementSource(kind="Service", name="web",
                                     field_path="metadata.name"),
            targets=[ReplacementTarget(
                select=ReplacementTargetSelect(kind="Deployment", name="web"),
                field_paths=["spec.template.spec.containers.[name=web].env.[name=SVC].value"],
            )],
        )
        base = KustomizeBase(name="web", replacements=[replacement])
        result = BaseGenerator().generate(
            KustomizeConfig(base=base, image="web:1.0")
        )
        parsed = yaml.safe_load(result.files["base/kustomization.yaml"])
        assert parsed["replacements"][0]["source"]["kind"] == "Service"
        assert "[name=web]" in parsed["replacements"][0]["targets"][0]["fieldPaths"][0]
        assert "vars" not in parsed

    def test_openapi_passthrough(self):
        base = KustomizeBase(name="web", openapi_path="schemas/crds.json")
        result = BaseGenerator().generate(
            KustomizeConfig(base=base, image="web:1.0")
        )
        parsed = yaml.safe_load(result.files["base/kustomization.yaml"])
        assert parsed["openapi"] == {"path": "schemas/crds.json"}

    def test_component_generation(self):
        component = KustomizeComponent(
            name="monitoring", resources=["servicemonitor.yaml"],
        )
        result = ComponentGenerator().generate(component)
        parsed = yaml.safe_load(
            result.files["components/monitoring/kustomization.yaml"]
        )
        assert parsed["kind"] == "Component"
        assert parsed["apiVersion"] == "kustomize.config.k8s.io/v1alpha1"

    def test_remote_base_flagged(self):
        overlay = KustomizeOverlay(
            name="staging",
            bases=["https://github.com/org/repo//base?ref=main"],
        )
        result = OverlayGenerator().generate(overlay)
        assert any(
            "VOL-KUST-REMOTE-BASE" in r for r in result.validation_results
        )


class TestRenderValidatePipeline:
    def test_render_kustomize_none_when_unavailable(self, monkeypatch):
        import Asgard.Volundr.Validation.services.render_pipeline as rp
        monkeypatch.setattr(rp, "is_available", lambda tool: False)
        assert rp.render_kustomize("/nonexistent") is None

    def test_pipeline_reports_skip_when_no_renderer(self, monkeypatch, tmp_path):
        import Asgard.Volundr.Validation.services.render_pipeline as rp
        monkeypatch.setattr(rp, "is_available", lambda tool: False)
        report = rp.render_and_validate(str(tmp_path), kind="kustomize")
        assert any(
            r.rule_id == "VOL-EXTERNAL-TOOL-SKIPPED" for r in report.results
        )

    def test_pluto_skip_notice_when_unavailable(self, monkeypatch):
        import Asgard.Volundr.Validation.services.render_pipeline as rp
        monkeypatch.setattr(rp, "is_available", lambda tool: False)
        results = rp.run_pluto("kind: Deployment")
        assert results[0].rule_id == "VOL-EXTERNAL-TOOL-SKIPPED"

    @pytest.mark.skipif(
        shutil.which("kustomize") is None and shutil.which("kubectl") is None,
        reason="kustomize/kubectl not installed",
    )
    def test_kustomize_build_contract_gate(self, tmp_path):
        """L3_Contract gate: generated base+overlay trees build cleanly."""
        base = KustomizeBase(name="web", common_labels={"team": "platform"})
        config = KustomizeConfig(base=base, image="web:1.0")
        result = BaseGenerator().generate(config)
        BaseGenerator(output_dir=str(tmp_path)).save_to_directory(
            result, str(tmp_path)
        )
        rendered = render_kustomize(str(tmp_path / "base"))
        assert rendered is not None
        docs = list(yaml.safe_load_all(rendered))
        deployment = next(d for d in docs if d["kind"] == "Deployment")
        # includeSelectors: false — selector must stay untouched.
        assert deployment["spec"]["selector"]["matchLabels"] == {"app": "web"}
        assert deployment["metadata"]["labels"]["team"] == "platform"

    @pytest.mark.skipif(
        shutil.which("kustomize") is None and shutil.which("kubectl") is None,
        reason="kustomize/kubectl not installed",
    )
    def test_render_and_validate_end_to_end(self, tmp_path):
        base = KustomizeBase(name="web")
        config = KustomizeConfig(base=base, image="web:1.0")
        result = BaseGenerator().generate(config)
        BaseGenerator(output_dir=str(tmp_path)).save_to_directory(
            result, str(tmp_path)
        )
        report = render_and_validate(str(tmp_path / "base"), kind="kustomize")
        assert report.total_files == 1
        assert report.results is not None
