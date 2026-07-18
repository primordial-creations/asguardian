"""L3 contract tests: external-tool bridge (skip-if-unavailable)."""

import shutil

import pytest
import yaml

from Asgard.Volundr.Validation.services import external_tools


HARDENED_DEPLOYMENT = {
    "apiVersion": "apps/v1",
    "kind": "Deployment",
    "metadata": {"name": "app", "labels": {"app": "app"}},
    "spec": {
        "selector": {"matchLabels": {"app": "app"}},
        "template": {
            "metadata": {"labels": {"app": "app"}},
            "spec": {
                "containers": [{
                    "name": "app",
                    "image": "nginx:1.25",
                }],
            },
        },
    },
}


class TestBridgeAvailability:
    def test_available_tools_is_subset_of_supported(self):
        available = external_tools.available_tools()
        assert set(available) <= set(external_tools.SUPPORTED_TOOLS)

    def test_unavailable_tool_returns_empty_not_error(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        assert external_tools.run_kubeconform("apiVersion: v1") == []
        assert external_tools.run_hadolint("FROM scratch") == []
        assert external_tools.run_actionlint("jobs: {}") == []


@pytest.mark.skipif(
    not external_tools.is_available("kubeconform"),
    reason="kubeconform not on PATH",
)
class TestKubeconformContract:
    def test_valid_manifest_yields_no_findings(self):
        results = external_tools.run_kubeconform(yaml.dump(HARDENED_DEPLOYMENT))
        assert results == []

    def test_bogus_field_detected(self):
        bad = dict(HARDENED_DEPLOYMENT)
        bad["spec"] = {**bad["spec"], "frobnicate": True}
        results = external_tools.run_kubeconform(yaml.dump(bad))
        assert results, "kubeconform -strict should flag unknown fields"


@pytest.mark.skipif(
    not external_tools.is_available("hadolint"),
    reason="hadolint not on PATH",
)
class TestHadolintContract:
    def test_latest_tag_flagged(self):
        results = external_tools.run_hadolint("FROM ubuntu:latest\n")
        assert any(r.rule_id == "DL3007" for r in results)


@pytest.mark.skipif(
    not external_tools.is_available("actionlint"),
    reason="actionlint not on PATH",
)
class TestActionlintContract:
    def test_invalid_workflow_flagged(self):
        results = external_tools.run_actionlint(
            "on: push\njobs:\n  build:\n    steps: []\n"
        )
        assert results  # missing runs-on is an actionlint error
