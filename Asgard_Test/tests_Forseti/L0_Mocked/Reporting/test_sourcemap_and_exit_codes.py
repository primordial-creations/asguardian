"""Tests for source-mapped loading and the uniform 0/1/2 exit-code policy (plan 08)."""

import argparse

from Asgard.Forseti.cli._handler_runner import (
    EXIT_GATE_FAILURE,
    EXIT_INPUT_ERROR,
    EXIT_OK,
    compute_exit_code,
    wants_unified_output,
)
from Asgard.Forseti.Reporting.models.finding_models import Coordinates, Finding
from Asgard.Forseti.Reporting.utilities.sourcemap_loader import (
    annotate_findings,
    build_sourcemap,
    load_with_sourcemap,
    lookup,
)
from Asgard.Forseti.Rules.models._rule_base_models import Severity

YAML_DOC = """openapi: 3.0.0
info:
  title: Test
  version: "1.0"
paths:
  /users/{id}:
    get:
      responses:
        "200":
          description: OK
"""


class TestSourcemap:
    def test_known_key_positions_are_exact(self):
        sourcemap = build_sourcemap(YAML_DOC)
        assert sourcemap["/openapi"] == (1, 1)
        assert sourcemap["/info/title"] == (3, 3)
        assert sourcemap["/paths/~1users~1{id}/get"] == (7, 5)

    def test_lookup_merges_raw_slash_keys(self):
        sourcemap = build_sourcemap(YAML_DOC)
        # legacy finding paths embed raw path keys containing '/'
        assert lookup(sourcemap, "/paths/users/{id}/get") == (7, 5)

    def test_unmapped_path_falls_back_to_ancestor_or_none(self):
        sourcemap = build_sourcemap(YAML_DOC)
        line, column = lookup(sourcemap, "/paths/users/{id}/get/summary")
        assert (line, column) == (7, 5)  # deepest mapped ancestor
        assert lookup({}, "/anything") == (None, None)

    def test_json_documents_are_supported(self):
        data_map = build_sourcemap('{"a": {"b": 1}}')
        assert "/a/b" in data_map

    def test_invalid_yaml_yields_empty_map(self):
        assert build_sourcemap("a: [unclosed") == {}

    def test_load_with_sourcemap(self, tmp_path):
        path = tmp_path / "doc.yaml"
        path.write_text(YAML_DOC)
        data, sourcemap = load_with_sourcemap(path)
        assert data["openapi"] == "3.0.0"
        assert sourcemap["/openapi"] == (1, 1)

    def test_annotate_findings(self):
        sourcemap = build_sourcemap(YAML_DOC)
        finding = Finding(rule_id="x", severity=Severity.ERROR, message="m",
                          coordinates=Coordinates(json_path="/info/title"))
        annotate_findings([finding], sourcemap)
        assert (finding.coordinates.line, finding.coordinates.column) == (3, 3)


def _finding(severity: Severity, suppressed: bool = False) -> Finding:
    return Finding(rule_id="r", severity=severity, message="m", suppressed=suppressed)


class TestExitCodePolicy:
    def test_input_error_is_2(self):
        assert compute_exit_code([], input_error=True) == EXIT_INPUT_ERROR

    def test_error_finding_is_1(self):
        assert compute_exit_code([_finding(Severity.ERROR)]) == EXIT_GATE_FAILURE

    def test_warnings_only_is_0(self):
        assert compute_exit_code([_finding(Severity.WARNING)]) == EXIT_OK

    def test_warnings_block_under_strict(self):
        assert compute_exit_code([_finding(Severity.WARNING)],
                                 strict=True) == EXIT_GATE_FAILURE

    def test_suppressed_errors_do_not_block(self):
        assert compute_exit_code([_finding(Severity.ERROR, suppressed=True)]) == EXIT_OK

    def test_never_blocking_profile_exits_0(self):
        assert compute_exit_code([_finding(Severity.ERROR)], blocking="never") == EXIT_OK

    def test_audit_report_profile_exits_0(self):
        assert compute_exit_code([_finding(Severity.ERROR)], blocking="report") == EXIT_OK


class TestCliExitCodes:
    def _run(self, argv):
        from Asgard.Forseti.cli import main

        return main(argv)

    def test_missing_file_exits_2(self, capsys):
        assert self._run(["openapi", "validate", "/definitely/not/here.yaml"]) == 2

    def test_error_findings_exit_1(self, tmp_path, capsys):
        spec = tmp_path / "bad.yaml"
        spec.write_text("openapi: 3.0.0\npaths: {}\n")  # missing info
        assert self._run(["openapi", "validate", str(spec)]) == 1

    def test_valid_spec_exits_0(self, tmp_path, capsys):
        spec = tmp_path / "ok.yaml"
        spec.write_text(
            "openapi: 3.0.0\n"
            "info: {title: T, version: '1'}\n"
            "paths: {}\n"
        )
        assert self._run(["openapi", "validate", str(spec)]) == 0

    def test_deprecated_only_spec_exits_0(self, tmp_path, capsys):
        spec = tmp_path / "dep.yaml"
        spec.write_text(
            "openapi: 3.0.0\n"
            "info: {title: T, version: '1'}\n"
            "paths:\n"
            "  /old:\n"
            "    get:\n"
            "      deprecated: true\n"
            "      responses:\n"
            "        '200': {description: OK}\n"
        )
        assert self._run(["--format", "github", "openapi", "validate", str(spec)]) == 0
        output = capsys.readouterr().out
        assert "deprecated" in output and "::notice" in output

    def test_sarif_output_from_cli(self, tmp_path, capsys):
        import json

        spec = tmp_path / "ok.yaml"
        spec.write_text(
            "openapi: 3.0.0\ninfo: {title: T, version: '1'}\npaths: {}\n"
        )
        assert self._run(["--format", "sarif", "openapi", "validate", str(spec)]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["version"] == "2.1.0"

    def test_ide_profile_never_blocks(self, tmp_path, capsys):
        spec = tmp_path / "bad.yaml"
        spec.write_text("openapi: 3.0.0\npaths: {}\n")
        assert self._run(["--profile", "ide", "openapi", "validate", str(spec)]) == 0

    def test_wants_unified_output(self):
        args = argparse.Namespace(format="sarif", quiet=False, explain=False, profile=None)
        assert wants_unified_output(args)
        args = argparse.Namespace(format="text", quiet=False, explain=False, profile=None)
        assert not wants_unified_output(args)
