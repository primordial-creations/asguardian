"""
Unit tests for the Node toolchain-orchestrating analysers (ESLint, npm audit,
tsc).

These tests monkeypatch Asgard.Bragi.Quality.languages.common.tool_runner's
run_tool/resolve_node_tool/require_executable so the parsing logic is
exercised without depending on node/npm/eslint/tsc actually being installed.
A separate, skip-cleanly integration test at the bottom of this file
exercises the real tools against the checked-in fixture project when they
are available.
"""

import json
import shutil
from pathlib import Path

import pytest

from Asgard.Bragi.Quality.languages.common.tool_runner import ToolNotAvailableError, ToolRunResult
from Asgard.Bragi.Quality.languages.node.models.node_toolchain_models import (
    NodeAuditConfig,
    NodeLintConfig,
    NodeTypecheckConfig,
)
from Asgard.Bragi.Quality.languages.node.services import (
    node_audit_analyzer,
    node_eslint_analyzer,
    node_typecheck_analyzer,
)
from Asgard.Bragi.Quality.languages.node.services.node_audit_analyzer import NodeAuditAnalyzer
from Asgard.Bragi.Quality.languages.node.services.node_eslint_analyzer import NodeEslintAnalyzer
from Asgard.Bragi.Quality.languages.node.services.node_typecheck_analyzer import NodeTypecheckAnalyzer


def _project(tmp_path: Path, *, with_eslint_config: bool = True) -> Path:
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    (project_dir / "package.json").write_text(json.dumps({"name": "proj"}), encoding="utf-8")
    if with_eslint_config:
        (project_dir / "eslint.config.js").write_text("module.exports = [];\n", encoding="utf-8")
    return project_dir


class TestNodeEslintAnalyzerParsing:
    def test_no_config_is_graceful_not_a_crash(self, tmp_path: Path):
        project_dir = _project(tmp_path, with_eslint_config=False)
        report = NodeEslintAnalyzer(NodeLintConfig(scan_path=project_dir)).analyze()
        assert report.total_findings == 0
        assert report.tools_unavailable
        assert "ESLint configuration" in report.tools_unavailable[0]

    def test_eslint_missing_raises_actionable_error(self, tmp_path: Path, monkeypatch):
        project_dir = _project(tmp_path)

        def _raise(*args, **kwargs):
            raise ToolNotAvailableError("eslint is not available. Install Node.js.")

        monkeypatch.setattr(node_eslint_analyzer, "resolve_node_tool", _raise)
        with pytest.raises(ToolNotAvailableError) as excinfo:
            NodeEslintAnalyzer(NodeLintConfig(scan_path=project_dir)).analyze()
        assert "Install Node.js." in str(excinfo.value)

    def test_parses_eslint_json_output(self, tmp_path: Path, monkeypatch):
        project_dir = _project(tmp_path)
        (project_dir / "index.js").write_text("eval('x');\n", encoding="utf-8")
        eslint_output = json.dumps([
            {
                "filePath": str(project_dir / "index.js"),
                "messages": [
                    {"ruleId": "no-eval", "severity": 2, "message": "eval is bad", "line": 1, "column": 1},
                    {"ruleId": "eqeqeq", "severity": 1, "message": "use ===", "line": 2, "column": 3},
                    {"ruleId": None, "severity": 2, "message": "Parsing error", "line": 3, "column": 1},
                ],
            }
        ])
        monkeypatch.setattr(node_eslint_analyzer, "resolve_node_tool", lambda *a, **k: ["/usr/bin/eslint"])
        monkeypatch.setattr(
            node_eslint_analyzer,
            "run_tool",
            lambda cmd, cwd, timeout: ToolRunResult(returncode=1, stdout=eslint_output, stderr=""),
        )
        report = NodeEslintAnalyzer(NodeLintConfig(scan_path=project_dir)).analyze()
        assert report.total_findings == 3
        assert report.error_count == 2
        assert report.warning_count == 1
        no_eval = next(f for f in report.findings if f.rule_id == "no-eval")
        assert no_eval.category == "security"
        eqeqeq = next(f for f in report.findings if f.rule_id == "eqeqeq")
        assert eqeqeq.category == "style"
        parse_error = next(f for f in report.findings if f.rule_id == "eslint.parse-error")
        assert parse_error.severity == "error"

    def test_unparseable_output_is_graceful(self, tmp_path: Path, monkeypatch):
        project_dir = _project(tmp_path)
        monkeypatch.setattr(node_eslint_analyzer, "resolve_node_tool", lambda *a, **k: ["/usr/bin/eslint"])
        monkeypatch.setattr(
            node_eslint_analyzer,
            "run_tool",
            lambda cmd, cwd, timeout: ToolRunResult(returncode=1, stdout="not json", stderr=""),
        )
        report = NodeEslintAnalyzer(NodeLintConfig(scan_path=project_dir)).analyze()
        assert report.total_findings == 0
        assert report.tools_unavailable

    @pytest.mark.parametrize(
        "returncode,payload",
        [
            (1, []),
            (2, []),
            (0, {}),
            (0, None),
            (0, [{"filePath": "index.js"}]),
            (0, [{"filePath": "index.js", "messages": [None]}]),
            (0, [{"filePath": "index.js", "messages": [{"severity": 2, "message": 7}]}]),
            (0, [{"filePath": "index.js", "messages": [{"severity": True, "message": "bad severity"}]}]),
        ],
    )
    def test_empty_or_incomplete_json_cannot_report_a_clean_scan(
        self, tmp_path: Path, monkeypatch, returncode: int, payload
    ):
        project_dir = _project(tmp_path)
        monkeypatch.setattr(node_eslint_analyzer, "resolve_node_tool", lambda *a, **k: ["/usr/bin/eslint"])
        monkeypatch.setattr(
            node_eslint_analyzer,
            "run_tool",
            lambda cmd, cwd, timeout: ToolRunResult(returncode=returncode, stdout=json.dumps(payload), stderr=""),
        )
        report = NodeEslintAnalyzer(NodeLintConfig(scan_path=project_dir)).analyze()
        assert report.total_findings == 0
        assert report.tool_failed
        assert report.tools_unavailable

    def test_successful_empty_result_is_clean(self, tmp_path: Path, monkeypatch):
        project_dir = _project(tmp_path)
        monkeypatch.setattr(node_eslint_analyzer, "resolve_node_tool", lambda *a, **k: ["/usr/bin/eslint"])
        monkeypatch.setattr(
            node_eslint_analyzer,
            "run_tool",
            lambda cmd, cwd, timeout: ToolRunResult(returncode=0, stdout="[]", stderr=""),
        )
        report = NodeEslintAnalyzer(NodeLintConfig(scan_path=project_dir)).analyze()
        assert report.total_findings == 0
        assert not report.tool_failed
        assert not report.tools_unavailable

    def test_fatal_exit_keeps_valid_findings_but_marks_report_incomplete(self, tmp_path: Path, monkeypatch):
        project_dir = _project(tmp_path)
        eslint_output = json.dumps([
            {
                "filePath": str(project_dir / "index.js"),
                "messages": [{"ruleId": "no-eval", "severity": 2, "message": "eval is bad"}],
            }
        ])
        monkeypatch.setattr(node_eslint_analyzer, "resolve_node_tool", lambda *a, **k: ["/usr/bin/eslint"])
        monkeypatch.setattr(
            node_eslint_analyzer,
            "run_tool",
            lambda cmd, cwd, timeout: ToolRunResult(returncode=2, stdout=eslint_output, stderr="fatal"),
        )
        report = NodeEslintAnalyzer(NodeLintConfig(scan_path=project_dir)).analyze()
        assert report.total_findings == 1
        assert report.findings[0].rule_id == "no-eval"
        assert report.tool_failed
        assert any("exit 2" in note for note in report.tools_unavailable)

    def test_partial_envelope_keeps_valid_findings_and_fails_closed(self, tmp_path: Path, monkeypatch):
        project_dir = _project(tmp_path)
        eslint_output = json.dumps([
            {
                "filePath": str(project_dir / "index.js"),
                "messages": [
                    {"ruleId": "eqeqeq", "severity": 1, "message": "use ==="},
                    {"ruleId": "broken", "message": "missing severity"},
                    {"ruleId": "broken-line", "severity": 2, "message": "bad line", "line": "abc"},
                    {"ruleId": "broken-column", "severity": 2, "message": "bad column", "column": True},
                ],
            }
        ])
        monkeypatch.setattr(node_eslint_analyzer, "resolve_node_tool", lambda *a, **k: ["/usr/bin/eslint"])
        monkeypatch.setattr(
            node_eslint_analyzer,
            "run_tool",
            lambda cmd, cwd, timeout: ToolRunResult(returncode=1, stdout=eslint_output, stderr=""),
        )
        report = NodeEslintAnalyzer(NodeLintConfig(scan_path=project_dir)).analyze()
        assert [finding.rule_id for finding in report.findings] == ["eqeqeq"]
        assert report.tool_failed
        assert any("malformed or unsupported" in note for note in report.tools_unavailable)


_NPM_AUDIT_JSON = json.dumps({
    "vulnerabilities": {
        "lodash": {
            "name": "lodash",
            "severity": "critical",
            "via": [{"title": "Prototype Pollution in lodash", "url": "https://example.test/advisory"}],
            "fixAvailable": {"name": "lodash", "version": "4.18.1"},
        }
    }
})


class TestNodeAuditAnalyzerParsing:
    def test_npm_missing_raises_actionable_error(self, tmp_path: Path, monkeypatch):
        project_dir = _project(tmp_path)

        def _raise(*args, **kwargs):
            raise ToolNotAvailableError("npm is not available. Install Node.js.")

        monkeypatch.setattr(node_audit_analyzer, "require_executable", _raise)
        with pytest.raises(ToolNotAvailableError):
            NodeAuditAnalyzer(NodeAuditConfig(scan_path=project_dir)).analyze()

    def test_no_package_json_is_graceful(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(node_audit_analyzer, "require_executable", lambda *a, **k: "/usr/bin/npm")
        report = NodeAuditAnalyzer(NodeAuditConfig(scan_path=tmp_path)).analyze()
        assert report.total_findings == 0
        assert "package.json" in report.tools_unavailable[0]

    def test_registry_unreachable_is_graceful_not_a_crash(self, tmp_path: Path, monkeypatch):
        project_dir = _project(tmp_path)
        monkeypatch.setattr(node_audit_analyzer, "require_executable", lambda *a, **k: "/usr/bin/npm")
        error_payload = json.dumps({"error": {"code": "ENOAUDIT", "summary": "registry unreachable"}})
        monkeypatch.setattr(
            node_audit_analyzer,
            "run_tool",
            lambda cmd, cwd, timeout: ToolRunResult(returncode=1, stdout=error_payload, stderr=""),
        )
        report = NodeAuditAnalyzer(NodeAuditConfig(scan_path=project_dir)).analyze()
        assert report.total_findings == 0
        assert "registry" in report.tools_unavailable[0]

    def test_parses_vulnerability_entries(self, tmp_path: Path, monkeypatch):
        project_dir = _project(tmp_path)
        monkeypatch.setattr(node_audit_analyzer, "require_executable", lambda *a, **k: "/usr/bin/npm")
        monkeypatch.setattr(
            node_audit_analyzer,
            "run_tool",
            lambda cmd, cwd, timeout: ToolRunResult(returncode=1, stdout=_NPM_AUDIT_JSON, stderr=""),
        )
        report = NodeAuditAnalyzer(NodeAuditConfig(scan_path=project_dir)).analyze()
        assert report.total_findings == 1
        finding = report.findings[0]
        assert finding.severity == "error"
        assert finding.category == "dependency"
        assert "Prototype Pollution" in finding.description
        assert "4.18.1" in finding.fix_suggestion

    @pytest.mark.parametrize(
        "returncode,payload",
        [
            (1, {"vulnerabilities": {}}),
            (2, {"vulnerabilities": {}}),
            (0, {}),
            (0, []),
            (0, None),
            (0, {"vulnerabilities": []}),
            (1, {"vulnerabilities": {"broken": {}}}),
            (1, {"vulnerabilities": {"broken": {"severity": "high", "via": {}}}}),
        ],
    )
    def test_empty_or_incomplete_json_cannot_report_a_clean_scan(
        self, tmp_path: Path, monkeypatch, returncode: int, payload
    ):
        project_dir = _project(tmp_path)
        monkeypatch.setattr(node_audit_analyzer, "require_executable", lambda *a, **k: "/usr/bin/npm")
        monkeypatch.setattr(
            node_audit_analyzer,
            "run_tool",
            lambda cmd, cwd, timeout: ToolRunResult(returncode=returncode, stdout=json.dumps(payload), stderr=""),
        )
        report = NodeAuditAnalyzer(NodeAuditConfig(scan_path=project_dir)).analyze()
        assert report.total_findings == 0
        assert report.tool_failed
        assert report.tools_unavailable

    def test_successful_empty_result_is_clean(self, tmp_path: Path, monkeypatch):
        project_dir = _project(tmp_path)
        monkeypatch.setattr(node_audit_analyzer, "require_executable", lambda *a, **k: "/usr/bin/npm")
        monkeypatch.setattr(
            node_audit_analyzer,
            "run_tool",
            lambda cmd, cwd, timeout: ToolRunResult(
                returncode=0,
                stdout=json.dumps({"vulnerabilities": {}}),
                stderr="",
            ),
        )
        report = NodeAuditAnalyzer(NodeAuditConfig(scan_path=project_dir)).analyze()
        assert report.total_findings == 0
        assert not report.tool_failed
        assert not report.tools_unavailable

    @pytest.mark.parametrize(
        "returncode,error",
        [
            (2, None),
            (1, {"code": "ENOAUDIT", "summary": "registry stopped after partial output"}),
        ],
    )
    def test_failed_or_partial_audit_keeps_valid_findings(
        self, tmp_path: Path, monkeypatch, returncode: int, error
    ):
        project_dir = _project(tmp_path)
        payload = json.loads(_NPM_AUDIT_JSON)
        if error is not None:
            payload["error"] = error
        monkeypatch.setattr(node_audit_analyzer, "require_executable", lambda *a, **k: "/usr/bin/npm")
        monkeypatch.setattr(
            node_audit_analyzer,
            "run_tool",
            lambda cmd, cwd, timeout: ToolRunResult(returncode=returncode, stdout=json.dumps(payload), stderr="fatal"),
        )
        report = NodeAuditAnalyzer(NodeAuditConfig(scan_path=project_dir)).analyze()
        assert report.total_findings == 1
        assert report.findings[0].rule_id == "npm-audit::lodash"
        assert report.tool_failed
        assert report.tools_unavailable

    def test_malformed_entry_does_not_discard_valid_vulnerability(self, tmp_path: Path, monkeypatch):
        project_dir = _project(tmp_path)
        payload = json.loads(_NPM_AUDIT_JSON)
        payload["vulnerabilities"]["broken"] = {"severity": "high", "via": None}
        monkeypatch.setattr(node_audit_analyzer, "require_executable", lambda *a, **k: "/usr/bin/npm")
        monkeypatch.setattr(
            node_audit_analyzer,
            "run_tool",
            lambda cmd, cwd, timeout: ToolRunResult(returncode=1, stdout=json.dumps(payload), stderr=""),
        )
        report = NodeAuditAnalyzer(NodeAuditConfig(scan_path=project_dir)).analyze()
        assert [finding.rule_id for finding in report.findings] == ["npm-audit::lodash"]
        assert report.tool_failed
        assert any("malformed or unsupported" in note for note in report.tools_unavailable)


class TestNodeTypecheckAnalyzerParsing:
    def test_no_tsconfig_is_graceful(self, tmp_path: Path):
        project_dir = _project(tmp_path)
        report = NodeTypecheckAnalyzer(NodeTypecheckConfig(scan_path=project_dir)).analyze()
        assert report.total_findings == 0
        assert "tsconfig.json" in report.tools_unavailable[0]

    def test_parses_tsc_diagnostics(self, tmp_path: Path, monkeypatch):
        project_dir = _project(tmp_path)
        (project_dir / "tsconfig.json").write_text("{}\n", encoding="utf-8")
        tsc_output = (
            "bad.ts(5,7): error TS2322: Type 'number' is not assignable to type 'string'.\n"
            "bad.ts(6,13): error TS2304: Cannot find name 'unknownVar'.\n"
        )
        monkeypatch.setattr(node_typecheck_analyzer, "resolve_node_tool", lambda *a, **k: ["/usr/bin/tsc"])
        monkeypatch.setattr(
            node_typecheck_analyzer,
            "run_tool",
            lambda cmd, cwd, timeout: ToolRunResult(returncode=2, stdout=tsc_output, stderr=""),
        )
        report = NodeTypecheckAnalyzer(NodeTypecheckConfig(scan_path=project_dir)).analyze()
        assert report.total_findings == 2
        assert report.error_count == 2
        rule_ids = {f.rule_id for f in report.findings}
        assert rule_ids == {"TS2322", "TS2304"}
        assert all(f.category == "type" for f in report.findings)

    def test_non_matching_output_lines_are_ignored(self, tmp_path: Path, monkeypatch):
        project_dir = _project(tmp_path)
        (project_dir / "tsconfig.json").write_text("{}\n", encoding="utf-8")
        monkeypatch.setattr(node_typecheck_analyzer, "resolve_node_tool", lambda *a, **k: ["/usr/bin/tsc"])
        monkeypatch.setattr(
            node_typecheck_analyzer,
            "run_tool",
            lambda cmd, cwd, timeout: ToolRunResult(returncode=0, stdout="Compilation complete.\n", stderr=""),
        )
        report = NodeTypecheckAnalyzer(NodeTypecheckConfig(scan_path=project_dir)).analyze()
        assert report.total_findings == 0

    def test_fatal_tsc_failure_with_no_diagnostics_is_reported_not_clean(self, tmp_path: Path, monkeypatch):
        # A malformed tsconfig.json (or a broken toolchain) makes tsc exit
        # with a fatal, non-per-file error such as "error TS18002: The
        # 'files' list in config file 'tsconfig.json' is empty." That line
        # has no "file(line,col):" prefix, so it never matches
        # _DIAGNOSTIC_RE. Zero parsed diagnostics must not be read as "no
        # type errors" when tsc did not actually complete a check.
        project_dir = _project(tmp_path)
        (project_dir / "tsconfig.json").write_text("{}\n", encoding="utf-8")
        monkeypatch.setattr(node_typecheck_analyzer, "resolve_node_tool", lambda *a, **k: ["/usr/bin/tsc"])
        monkeypatch.setattr(
            node_typecheck_analyzer,
            "run_tool",
            lambda cmd, cwd, timeout: ToolRunResult(
                returncode=3,
                stdout="",
                stderr="error TS18002: The 'files' list in config file 'tsconfig.json' is empty.\n",
            ),
        )
        report = NodeTypecheckAnalyzer(NodeTypecheckConfig(scan_path=project_dir)).analyze()
        assert report.total_findings == 0
        assert report.tools_unavailable
        assert "TS18002" in report.tools_unavailable[0]


_NODE_TOOLS_PRESENT = all(
    shutil.which(tool) is not None for tool in ("node", "npm", "eslint", "tsc")
)


@pytest.mark.skipif(not _NODE_TOOLS_PRESENT, reason="node/npm/eslint/tsc not installed in this environment")
class TestNodeRealToolIntegration:
    """Exercises the real Node toolchain against the checked-in fixture project."""

    def _fixture_copy(self, tmp_path: Path) -> Path:
        fixture_src = Path(__file__).resolve().parents[4] / "fixtures" / "node_toolchain_demo"
        project_copy = tmp_path / "node_toolchain_demo"
        shutil.copytree(fixture_src, project_copy)
        return project_copy

    def test_eslint_detects_known_violations_in_fixture(self, tmp_path: Path):
        project_copy = self._fixture_copy(tmp_path)
        report = NodeEslintAnalyzer(NodeLintConfig(scan_path=project_copy, timeout_seconds=60)).analyze()
        assert not report.tools_unavailable
        rule_ids = {f.rule_id for f in report.findings}
        assert "no-eval" in rule_ids
        assert "eqeqeq" in rule_ids

    def test_tsc_detects_known_type_errors_in_fixture(self, tmp_path: Path):
        project_copy = self._fixture_copy(tmp_path)
        report = NodeTypecheckAnalyzer(NodeTypecheckConfig(scan_path=project_copy, timeout_seconds=60)).analyze()
        assert not report.tools_unavailable
        assert report.total_findings >= 2
        rule_ids = {f.rule_id for f in report.findings}
        assert "TS2322" in rule_ids

    def test_npm_audit_either_finds_the_known_vulnerability_or_reports_offline(self, tmp_path: Path):
        project_copy = self._fixture_copy(tmp_path)
        report = NodeAuditAnalyzer(NodeAuditConfig(scan_path=project_copy, timeout_seconds=60)).analyze()
        if report.tools_unavailable:
            pytest.skip(f"npm audit could not reach the registry: {report.tools_unavailable[0]}")
        assert report.total_findings >= 1
        assert any(f.rule_id == "npm-audit::lodash" for f in report.findings)
