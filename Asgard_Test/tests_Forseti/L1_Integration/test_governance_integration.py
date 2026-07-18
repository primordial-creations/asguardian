"""Integration tests for the governance CLI surface (plans 02 + 08)."""

import json

from Asgard.Forseti.cli import main

BAD_SPEC = (
    "openapi: 3.0.0\n"
    "info: {title: T, version: '1'}\n"
    "paths:\n"
    "  /users/{id}:\n"
    "    get:\n"
    "      responses:\n"
    "        '200': {description: OK}\n"
)


class TestRulesList:
    def test_rules_list_text(self, capsys):
        assert main(["rules", "list"]) == 0
        out = capsys.readouterr().out
        assert "oas.lifecycle.deprecated-operation" in out
        assert "Ruleset version: 1.0.0" in out

    def test_rules_list_json(self, capsys):
        assert main(["--format", "json", "rules", "list"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["ruleset_version"] == "1.0.0"
        ids = [r["rule_id"] for r in data["rules"]]
        assert "oas.structure.required-field" in ids

    def test_rules_list_format_filter(self, capsys):
        assert main(["--format", "json", "rules", "list", "--rule-format", "avro"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert all(r["rule_id"].startswith("avro.") for r in data["rules"])


class TestBaselineCli:
    def test_baseline_update_then_clean_run(self, tmp_path, capsys, monkeypatch):
        monkeypatch.chdir(tmp_path)
        spec = tmp_path / "api.yaml"
        spec.write_text(BAD_SPEC)  # path param {id} not defined -> ERROR
        baseline = tmp_path / ".forseti-baseline.json"

        # bad spec blocks before baselining
        assert main(["--format", "github", "openapi", "validate", str(spec)]) == 1
        capsys.readouterr()

        assert main(["baseline", "update", str(spec),
                     "--baseline", str(baseline)]) == 0
        assert baseline.is_file()
        capsys.readouterr()

        # with the baseline applied, the run gates clean
        assert main(["--format", "github", "openapi", "validate", str(spec)]) == 0

        # --no-baseline restores the failure
        assert main(["--no-baseline", "--format", "github",
                     "openapi", "validate", str(spec)]) == 1

    def test_baseline_show(self, tmp_path, capsys, monkeypatch):
        monkeypatch.chdir(tmp_path)
        spec = tmp_path / "api.yaml"
        spec.write_text(BAD_SPEC)
        baseline = tmp_path / "b.json"
        main(["baseline", "update", str(spec), "--baseline", str(baseline)])
        capsys.readouterr()
        assert main(["baseline", "show", "--baseline", str(baseline)]) == 0
        entries = json.loads(capsys.readouterr().out)
        assert entries and entries[0]["rule_id"]


class TestInlineSuppressionEndToEnd:
    def test_suppressed_finding_reported_but_not_blocking(self, tmp_path, capsys, monkeypatch):
        monkeypatch.chdir(tmp_path)
        spec = tmp_path / "api.yaml"
        spec.write_text(
            "openapi: 3.0.0\n"
            "info: {title: T, version: '1'}\n"
            "paths:\n"
            "  /users/{id}:\n"
            "    get:\n"
            "      x-forseti-ignore:\n"
            "        - rule: oas.paths.path-parameter-defined\n"
            "          reason: parameters injected by gateway\n"
            "      responses:\n"
            "        '200': {description: OK}\n"
        )
        assert main(["--format", "json", "openapi", "validate", str(spec)]) == 0
        data = json.loads(capsys.readouterr().out)
        suppressed = [f for f in data["findings"] if f["suppressed"]]
        assert suppressed
        assert suppressed[0]["suppression_reason"] == "parameters injected by gateway"
        assert data["summary"]["suppressed"] >= 1

    def test_missing_reason_produces_warning(self, tmp_path, capsys, monkeypatch):
        monkeypatch.chdir(tmp_path)
        spec = tmp_path / "api.yaml"
        spec.write_text(
            "openapi: 3.0.0\n"
            "info: {title: T, version: '1'}\n"
            "paths:\n"
            "  /users/{id}:\n"
            "    get:\n"
            "      x-forseti-ignore:\n"
            "        - rule: oas.paths.path-parameter-defined\n"
            "      responses:\n"
            "        '200': {description: OK}\n"
        )
        main(["--format", "json", "openapi", "validate", str(spec)])
        data = json.loads(capsys.readouterr().out)
        assert any(f["rule_id"] == "forseti.suppression.missing-reason"
                   for f in data["findings"])


class TestCompatWaivers:
    def _specs(self, tmp_path):
        old = tmp_path / "old.yaml"
        new = tmp_path / "new.yaml"
        old.write_text(
            "openapi: 3.0.0\ninfo: {title: T, version: v1.5}\n"
            "paths:\n  /users: {get: {responses: {'200': {description: OK}}}}\n"
        )
        new.write_text(
            "openapi: 3.0.0\ninfo: {title: T, version: v2.0}\npaths: {}\n"
        )
        return old, new

    def test_unwaived_break_blocks(self, tmp_path, capsys, monkeypatch):
        monkeypatch.chdir(tmp_path)
        old, new = self._specs(tmp_path)
        assert main(["contract", "check-compat", str(old), str(new)]) == 1

    def test_waived_break_passes_for_exact_epoch(self, tmp_path, capsys, monkeypatch):
        monkeypatch.chdir(tmp_path)
        old, new = self._specs(tmp_path)
        waivers = tmp_path / "waivers.yaml"
        waivers.write_text(
            "waivers:\n"
            "  - rule: '*removed*'\n"
            "    location: '/users'\n"
            "    from: v1.5\n"
            "    to: v2.0\n"
            "    reason: endpoint moved to v2 gateway\n"
            "    expires: 2099-01-01\n"
        )
        assert main(["contract", "check-compat", str(old), str(new),
                     "--waivers", str(waivers)]) == 0
        out = capsys.readouterr().out
        assert "WAIVED" in out or "Compatible: Yes" in out or "warning" in out.lower()
