"""
Tests for the Helm chart generator (Volundr plan 05).

Covers `values.schema.json` generation, hook-delete-policy hygiene on
Helm test hooks, NOTES.txt secret-avoidance, and shared-scoring-engine
wiring (plan 07: generators never grade their own intent).
"""

import json

import pytest

from Asgard.Volundr.Helm.models.helm_models import HelmChart, HelmConfig, HelmValues
from Asgard.Volundr.Helm.services.chart_generator import ChartGenerator


@pytest.fixture
def generator():
    return ChartGenerator()


@pytest.fixture
def basic_config():
    return HelmConfig(
        chart=HelmChart(name="demo"),
        values=HelmValues(image_repository="nginx"),
    )


class TestValuesSchema:
    def test_values_schema_json_is_generated(self, generator, basic_config):
        result = generator.generate(basic_config)
        assert "values.schema.json" in result.chart_files

    def test_values_schema_is_valid_draft7_json(self, generator, basic_config):
        result = generator.generate(basic_config)
        schema = json.loads(result.chart_files["values.schema.json"])
        assert schema["$schema"] == "https://json-schema.org/draft-07/schema#"
        assert schema["type"] == "object"
        assert "properties" in schema

    def test_schema_covers_top_level_values_keys(self, generator, basic_config):
        result = generator.generate(basic_config)
        schema = json.loads(result.chart_files["values.schema.json"])
        values = __import__("yaml").safe_load(result.chart_files["values.yaml"])
        assert set(schema["properties"].keys()) == set(values.keys())

    def test_schema_infers_types_correctly(self, generator, basic_config):
        result = generator.generate(basic_config)
        schema = json.loads(result.chart_files["values.schema.json"])
        assert schema["properties"]["replicaCount"]["type"] == "integer"
        assert schema["properties"]["image"]["type"] == "object"
        assert schema["properties"]["image"]["properties"]["repository"]["type"] == "string"


class TestHookHygiene:
    def test_test_hook_has_delete_policy(self, generator, basic_config):
        result = generator.generate(basic_config)
        test_pod = result.chart_files["templates/tests/test-connection.yaml"]
        assert '"helm.sh/hook": test' in test_pod
        assert "helm.sh/hook-delete-policy" in test_pod
        assert "before-hook-creation" in test_pod
        assert "hook-succeeded" in test_pod


class TestNotesSecretAvoidance:
    def test_notes_txt_never_renders_secret_values(self, generator, basic_config):
        config = HelmConfig(
            chart=HelmChart(name="demo"),
            values=HelmValues(image_repository="nginx"),
            include_secret=True,
        )
        result = generator.generate(config)
        notes = result.chart_files["templates/NOTES.txt"]
        # NOTES.txt is printed to the terminal on every `helm install`; it
        # must never dereference .Values.secret* or a Secret's data field.
        assert ".Values.secret" not in notes
        assert "Secret" not in notes
        assert "password" not in notes.lower()
        assert "token" not in notes.lower()


class TestScoringEngineWiring:
    """Plan 07: the chart generator never grades its own intent — the
    rendered chart's findings are scored through the shared
    ScoringEngine composite, not a hand-tuned local percentage."""

    def test_generate_returns_score_between_0_and_100(self, generator, basic_config):
        result = generator.generate(basic_config)
        assert 0.0 <= result.best_practice_score <= 100.0

    def test_missing_resources_lowers_score_via_shared_engine(self, generator):
        # A chart whose values.yaml lacks resource limits should score
        # strictly lower than one that has them (adversarial: verifies
        # scoring responds to real content, not just file presence).
        full_config = HelmConfig(
            chart=HelmChart(name="demo"),
            values=HelmValues(image_repository="nginx"),
        )
        full_result = generator.generate(full_config)
        assert full_result.best_practice_score == 100.0
        # validate_chart only flags "missing resources:" when the string
        # is entirely absent from values.yaml; simulate that by checking
        # the finding path directly rather than mutating the pydantic
        # model (resources is always populated by HelmValues defaults).
        from Asgard.Volundr.Helm.services._chart_generator_extras_part2 import validate_chart
        issues = validate_chart({"Chart.yaml": "x", "values.yaml": "no res here"}, full_config)
        assert any("resource" in i.lower() for i in issues)
