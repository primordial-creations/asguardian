"""Golden-style tests for the reporter adapters over one shared finding set (plan 08)."""

import json

import pytest

from Asgard.Forseti.Reporting.models.finding_models import (
    Coordinates,
    Finding,
    Remediation,
    ReportSummary,
)
from Asgard.Forseti.Reporting.services.reporter_service import (
    ExplainReporter,
    GithubReporter,
    JsonReporter,
    MarkdownReporter,
    SarifReporter,
    TextReporter,
    select_reporter,
)
from Asgard.Forseti.Rules.models._rule_base_models import RuleCategory, SchemaFormat, Severity


@pytest.fixture
def findings() -> list[Finding]:
    return [
        Finding(
            rule_id="oas.structure.required-field",
            severity=Severity.ERROR,
            message="Missing required field: info",
            coordinates=Coordinates(file="api.yaml", json_path="/", line=1, column=1),
            rationale="Required fields keep the document usable.",
            remediation=Remediation(description="Add an info object."),
            category=RuleCategory.STRUCTURE,
            format=SchemaFormat.OPENAPI,
        ),
        Finding(
            rule_id="oas.docs.description-required",
            severity=Severity.WARNING,
            message="Operation has no description",
            coordinates=Coordinates(file="api.yaml", json_path="/paths/~1u/get",
                                    line=12, column=5),
            category=RuleCategory.DOCS,
            format=SchemaFormat.OPENAPI,
        ),
        Finding(
            rule_id="oas.lifecycle.deprecated-operation",
            severity=Severity.INFO,
            message="Operation GET /old is deprecated",
            coordinates=Coordinates(file="api.yaml", json_path="/paths/~1old/get",
                                    line=30, column=5),
            category=RuleCategory.LIFECYCLE,
            format=SchemaFormat.OPENAPI,
        ),
        Finding(
            rule_id="oas.style.kebab-case-paths",
            severity=Severity.WARNING,
            message="Path is not kebab-case",
            coordinates=Coordinates(file="api.yaml", json_path="/paths/~1BadPath",
                                    line=44, column=3),
            suppressed=True,
            suppression_reason="legacy path",
            category=RuleCategory.STYLE,
            format=SchemaFormat.OPENAPI,
        ),
    ]


class TestTextReporter:
    def test_greppable_lines_and_summary(self, findings):
        output = TextReporter().render(findings)
        assert "api.yaml:1:1 ERR [oas.structure.required-field] Missing required field: info" in output
        assert output.strip().endswith("1 error(s), 1 warning(s), 1 info, 0 hint(s), 1 suppressed")

    def test_quiet_shows_errors_only(self, findings):
        output = TextReporter(quiet=True).render(findings)
        assert "ERR" in output and "WARN" not in output

    def test_suppressed_findings_hidden_from_text(self, findings):
        assert "kebab" not in TextReporter().render(findings)


class TestExplainReporter:
    def test_includes_rationale_and_fix(self, findings):
        output = ExplainReporter().render(findings)
        assert "why: Required fields keep the document usable." in output
        assert "fix: Add an info object." in output


class TestJsonReporter:
    def test_stable_envelope_and_round_trip(self, findings):
        output = JsonReporter().render(findings, ruleset_version="1.0.0")
        data = json.loads(output)
        assert data["tool"] == "forseti"
        assert data["ruleset_version"] == "1.0.0"
        assert data["summary"] == {"errors": 1, "warnings": 1, "info": 1,
                                   "hints": 0, "suppressed": 1}
        # suppressed findings stay in the machine envelope (suppression velocity)
        assert len(data["findings"]) == 4
        envelope = JsonReporter.parse(output)
        assert envelope.summary.errors == 1


class TestMarkdownReporter:
    def test_grouped_by_severity(self, findings):
        output = MarkdownReporter().render(findings)
        assert "# Forseti Report" in output
        assert "## Errors" in output and "## Warnings" in output
        assert "| `api.yaml:1` | oas.structure.required-field |" in output


class TestGithubReporter:
    def test_workflow_commands(self, findings):
        output = GithubReporter().render(findings)
        assert "::error file=api.yaml,line=1,col=1::[oas.structure.required-field]" in output
        assert "::notice" in output
        assert "kebab" not in output  # suppressed


class TestSarifReporter:
    def test_sarif_structure(self, findings):
        data = json.loads(SarifReporter().render(findings, ruleset_version="1.0.0"))
        assert data["version"] == "2.1.0"
        run = data["runs"][0]
        assert run["tool"]["driver"]["name"] == "Forseti"
        rule_ids = [r["id"] for r in run["tool"]["driver"]["rules"]]
        assert rule_ids == sorted(rule_ids)
        result = run["results"][0]
        assert result["ruleId"] in rule_ids
        assert result["locations"][0]["physicalLocation"]["region"]["startLine"] >= 1
        suppressed = [r for r in run["results"] if "suppressions" in r]
        assert len(suppressed) == 1
        assert suppressed[0]["suppressions"][0]["justification"] == "legacy path"

    def test_sarif_validates_against_own_jsonschema_engine(self, findings):
        """Dogfooding: validate SARIF output with Forseti's JSONSchema validator."""
        from Asgard.Forseti.JSONSchema import SchemaValidatorService

        schema = {
            "type": "object",
            "required": ["version", "runs"],
            "properties": {
                "version": {"type": "string", "enum": ["2.1.0"]},
                "runs": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["tool", "results"],
                        "properties": {
                            "tool": {
                                "type": "object",
                                "required": ["driver"],
                                "properties": {
                                    "driver": {
                                        "type": "object",
                                        "required": ["name", "rules"],
                                    },
                                },
                            },
                            "results": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["ruleId", "level", "message"],
                                    "properties": {
                                        "level": {"enum": ["error", "warning",
                                                            "note", "none"]},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }
        sarif = json.loads(SarifReporter().render(findings))
        result = SchemaValidatorService().validate(sarif, schema)
        assert result.is_valid, result.errors


class TestSelectReporter:
    def test_selection_matrix(self):
        assert isinstance(select_reporter("sarif"), SarifReporter)
        assert isinstance(select_reporter("github"), GithubReporter)
        assert isinstance(select_reporter("text", explain=True), ExplainReporter)
        assert select_reporter("text", quiet=True).quiet is True


class TestSummary:
    def test_summary_counts(self, findings):
        summary = ReportSummary.from_findings(findings)
        assert (summary.errors, summary.warnings, summary.info,
                summary.hints, summary.suppressed) == (1, 1, 1, 0, 1)
