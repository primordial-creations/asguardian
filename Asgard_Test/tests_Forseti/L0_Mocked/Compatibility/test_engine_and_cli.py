"""Engine orchestration: detection, transitive modes, telemetry, findings, CLI."""

import json

import pytest

from Asgard.Forseti.cli import main as cli_main
from Asgard.Forseti.Compatibility import (
    CompatEngineService,
    CompatMode,
    CompatStatus,
    JsonFileTelemetrySource,
)
from Asgard.Forseti.Compatibility.utilities.compat_utils import detect_format
from Asgard.Forseti.Rules.models._rule_base_models import SchemaFormat, Severity


def write(tmp_path, name, data):
    path = tmp_path / name
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def openapi(props, required=None):
    return {
        "openapi": "3.0.0",
        "info": {"title": "t", "version": "1.0.0"},
        "paths": {"/x": {"get": {"responses": {"200": {"content": {
            "application/json": {"schema": {
                "type": "object", "properties": props,
                **({"required": required} if required else {}),
            }}}}}}}},
    }


def avro(fields):
    return {"type": "record", "name": "R", "fields": fields}


class TestFormatDetection:
    def test_detects_each_format(self, tmp_path):
        assert detect_format(write(tmp_path, "a.json", openapi({}))) == \
            SchemaFormat.OPENAPI
        assert detect_format(write(tmp_path, "b.json", {"asyncapi": "2.0.0"})) == \
            SchemaFormat.ASYNCAPI
        assert detect_format(write(tmp_path, "c.avsc", avro([]))) == SchemaFormat.AVRO
        assert detect_format(write(tmp_path, "d.json", avro([]))) == SchemaFormat.AVRO
        assert detect_format(write(tmp_path, "e.proto", "syntax")) == \
            SchemaFormat.PROTOBUF
        assert detect_format(write(tmp_path, "f.graphql", "type Q { a: Int }")) == \
            SchemaFormat.GRAPHQL
        assert detect_format(write(tmp_path, "g.json",
                                   {"$schema": "x", "properties": {}})) == \
            SchemaFormat.JSONSCHEMA

    def test_unknown_format_reports_input_error(self, tmp_path):
        path = write(tmp_path, "u.json", [1, 2, 3])
        report = CompatEngineService().check(path, path)
        assert report.status == CompatStatus.FAILED
        assert report.changes[0].rule_id == "COMPAT-PARSE-ERROR"
        assert report.score == 0


class TestEngine:
    def test_openapi_end_to_end_score_and_receipt(self, tmp_path):
        old = write(tmp_path, "old.json",
                    openapi({"a": {"type": "string"}, "b": {"type": "string"}}))
        new = write(tmp_path, "new.json", openapi({"a": {"type": "string"}}))
        report = CompatEngineService().check(old, new)
        assert report.status == CompatStatus.FAILED
        assert report.score == 85
        assert report.structural_breaks == 1
        assert len(report.score_receipt) == 1
        assert report.is_compatible is False

    def test_forward_mode_swaps_direction(self, tmp_path):
        old = write(tmp_path, "old.json", openapi({"a": {"type": "string"}}))
        new = write(tmp_path, "new.json",
                    openapi({"a": {"type": "string"}, "b": {"type": "string"}}))
        backward = CompatEngineService().check(old, new, mode=CompatMode.BACKWARD)
        assert backward.status == CompatStatus.PASSED
        forward = CompatEngineService().check(old, new, mode=CompatMode.FORWARD)
        assert forward.status == CompatStatus.FAILED

    def test_avro_full_mode(self, tmp_path):
        old = write(tmp_path, "old.avsc", avro([{"name": "a", "type": "int"}]))
        new = write(tmp_path, "new.avsc", avro([{"name": "a", "type": "long"}]))
        report = CompatEngineService().check(old, new, mode=CompatMode.FULL)
        assert report.status == CompatStatus.FAILED  # forward leg fails

    def test_to_findings_uses_registry_ids_and_severities(self, tmp_path):
        old = write(tmp_path, "old.json",
                    openapi({"a": {"type": "string"}, "b": {"type": "string"}}))
        new = write(tmp_path, "new.json", openapi({"a": {"type": "string"}}))
        engine = CompatEngineService()
        report = engine.check(old, new)
        findings = engine.to_findings(report)
        assert len(findings) == 1
        assert findings[0].rule_id == "oas.compat.res-field-removed"
        assert findings[0].severity == Severity.ERROR
        assert "output_covariance_violation" in findings[0].rationale


class TestTransitive:
    def make_history(self, tmp_path):
        v1 = write(tmp_path, "v1.avsc", avro([
            {"name": "a", "type": "string"},
            {"name": "b", "type": "int", "default": 0}]))
        v2 = write(tmp_path, "v2.avsc", avro([{"name": "a", "type": "string"}]))
        v3 = write(tmp_path, "v3.avsc", avro([
            {"name": "a", "type": "string"},
            {"name": "b", "type": "int"}]))  # no default: breaks vs v1 data
        return [v1, v2, v3]

    def test_non_transitive_checks_last_pair_only(self, tmp_path):
        history = self.make_history(tmp_path)
        engine = CompatEngineService()
        report = engine.check_history(history, mode=CompatMode.BACKWARD)
        # v2 -> v3 adds field b without default => FAIL either way,
        # but must not contain the v1-specific removed-field hazard.
        assert not any("AVRO-FIELD-REMOVED" == c.rule_id for c in report.changes)

    def test_transitive_checks_all_prior_versions(self, tmp_path):
        history = self.make_history(tmp_path)
        engine = CompatEngineService()
        report = engine.check_history(history, mode=CompatMode.BACKWARD_TRANSITIVE)
        assert report.mode == CompatMode.BACKWARD_TRANSITIVE
        assert report.status == CompatStatus.FAILED
        assert any(c.rule_id == "AVRO-FIELD-ADDED-NO-DEFAULT" for c in report.changes)

    def test_history_requires_two_versions(self):
        with pytest.raises(ValueError):
            CompatEngineService().check_history(["only.avsc"])


class TestTelemetry:
    def test_unused_element_downgrades_to_conditional(self, tmp_path):
        old = write(tmp_path, "old.json",
                    openapi({"a": {"type": "string"}, "b": {"type": "string"}}))
        new = write(tmp_path, "new.json", openapi({"a": {"type": "string"}}))
        usage = write(tmp_path, "usage.json", {
            "window_days": 60, "usage": {"/x/get": 0}})
        engine = CompatEngineService(telemetry=JsonFileTelemetrySource(usage))
        report = engine.check(old, new)
        assert report.status == CompatStatus.CONDITIONALLY_PASSED
        assert report.score == 100  # unused => usage probability 0
        assert report.confidence == "high"

    def test_short_window_lowers_confidence(self, tmp_path):
        old = write(tmp_path, "old.json",
                    openapi({"a": {"type": "string"}, "b": {"type": "string"}}))
        new = write(tmp_path, "new.json", openapi({"a": {"type": "string"}}))
        usage = write(tmp_path, "usage.json", {
            "window_days": 7, "usage": {"/x/get": 120}})
        engine = CompatEngineService(telemetry=JsonFileTelemetrySource(usage))
        report = engine.check(old, new)
        assert report.confidence == "low"
        assert report.status == CompatStatus.FAILED  # actively used => still fails


class TestCompatCLI:
    def test_check_pass_and_fail_exit_codes(self, tmp_path, capsys):
        old = write(tmp_path, "old.json",
                    openapi({"a": {"type": "string"}, "b": {"type": "string"}}))
        new = write(tmp_path, "new.json", openapi({"a": {"type": "string"}}))
        assert cli_main(["compat", "check", old, old]) == 0
        assert cli_main(["compat", "check", old, new]) == 1
        out = capsys.readouterr().out
        assert "Blast Radius Receipt" in out
        assert "OAS-RES-FIELD-REMOVED" in out

    def test_json_output_and_min_score(self, tmp_path, capsys):
        old = write(tmp_path, "old.json", openapi({"a": {"type": "string"}}))
        new = write(tmp_path, "new.json",
                    openapi({"a": {"type": "string"}, "b": {"type": "string"}}))
        rc = cli_main(["--format", "json", "compat", "check", old, new])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["score"] == 100
        rc = cli_main(["compat", "check", old, new, "--min-score", "101"])
        assert rc == 1

    def test_missing_file_is_input_error(self, tmp_path):
        assert cli_main(["compat", "check", "/nope.json", "/nada.json"]) == 2

    def test_transitive_cli(self, tmp_path):
        v1 = write(tmp_path, "v1.avsc", avro([{"name": "a", "type": "string"}]))
        v2 = write(tmp_path, "v2.avsc", avro([{"name": "a", "type": "string"}]))
        v3 = write(tmp_path, "v3.avsc", avro([{"name": "a", "type": "string"},
                                              {"name": "b", "type": "int"}]))
        rc = cli_main(["compat", "check", v1, v2, v3,
                       "--mode", "backward-transitive"])
        assert rc == 1

    def test_legacy_contract_check_compat_json_gains_score(self, tmp_path, capsys):
        old = write(tmp_path, "old.json",
                    openapi({"a": {"type": "string"}, "b": {"type": "string"}}))
        new = write(tmp_path, "new.json", openapi({"a": {"type": "string"}}))
        cli_main(["--format", "json", "contract", "check-compat", old, new])
        payload = json.loads(capsys.readouterr().out)
        assert "is_compatible" in payload  # legacy shape preserved
        assert "score" in payload          # new engine field
        assert payload["score"] == 85
