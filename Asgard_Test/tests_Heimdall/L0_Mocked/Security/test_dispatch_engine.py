"""Tests for the 3-layer security dispatch engine (plan 04 A)."""

import tempfile
from pathlib import Path

from Asgard.Heimdall.Security.engine import DispatchEngine


def _scan(code: str, filename: str = "app.py", **engine_kwargs):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / filename
        path.write_text(code)
        return DispatchEngine(**engine_kwargs).scan_file(path)


class TestLayer1RegexSweep:
    def test_aws_key_prefix_detected_in_raw_text(self):
        result = _scan("KEY = 'AKIAJG74NB5XQTJ7Q2VZ'\n")
        hits = [f for f in result.structural_findings if f.layer == 1]
        assert len(hits) == 1
        assert hits[0].rule_id == "L1.aws_access_key"
        assert hits[0].mechanism_id == "secret.cloud_admin.validated"
        assert hits[0].severity == "critical"

    def test_layer1_runs_even_on_unparsable_files(self):
        result = _scan("def broken(:\nTOKEN = 'ghp_" + "a" * 36 + "'\n")
        assert result.parse_failed is True
        assert any(f.rule_id == "L1.github_token"
                   for f in result.structural_findings)


class TestLayer2Structural:
    def test_yaml_unsafe_load_flagged(self):
        result = _scan("import yaml\nyaml.load(data)\n")
        assert any(f.rule_id == "L2.yaml_unsafe_load"
                   for f in result.structural_findings)

    def test_yaml_safe_loader_not_flagged(self):
        result = _scan(
            "import yaml\nyaml.load(data, Loader=yaml.SafeLoader)\n")
        assert not any(f.rule_id == "L2.yaml_unsafe_load"
                       for f in result.structural_findings)

    def test_alias_resolution_in_dispatch(self):
        """Import-alias resolution is mandatory in the dispatch phase."""
        result = _scan("import yaml as y\ny.load(data)\n")
        assert any(f.rule_id == "L2.yaml_unsafe_load"
                   for f in result.structural_findings)


class TestTriggerIndexAndLazyTaint:
    def test_trigger_index_maps_functions(self):
        result = _scan(
            "def clean():\n"
            "    return 1 + 1\n"
            "def dirty():\n"
            "    q = request.args.get('q')\n"
            "    cursor.execute(q)\n"
        )
        assert "dirty" in result.trigger_index
        assert "clean" not in result.trigger_index
        assert result.trigger_index["dirty"]["sources"]
        assert result.trigger_index["dirty"]["sinks"]

    def test_taint_flows_only_from_triggered_functions(self):
        result = _scan(
            "def dirty():\n"
            "    q = request.args.get('q')\n"
            "    cursor.execute(q)\n"
        )
        assert len(result.taint_flows) == 1
        assert result.taint_flows[0].sink_location.function_name == "dirty"

    def test_no_triggers_no_taint_analysis(self):
        result = _scan("def clean():\n    return 42\n")
        assert result.trigger_index == {}
        assert result.taint_flows == []


class TestDedupAndDeterminism:
    def test_dedup_by_file_sinkline_cwe(self):
        # Two tainted paths into the same sink line: one finding.
        result = _scan(
            "def handler(flag):\n"
            "    a = request.args.get('a')\n"
            "    b = request.form.get('b')\n"
            "    q = a if flag else b\n"
            "    cursor.execute(q)\n"
        )
        keys = {
            (f.sink_location.line_number, f.cwe_id) for f in result.taint_flows
        }
        assert len(result.taint_flows) == len(keys)

    def test_two_scans_identical_output(self):
        """Determinism gate: consecutive scans yield identical findings."""
        code = (
            "import yaml\n"
            "KEY = 'AKIAJG74NB5XQTJ7Q2VZ'\n"
            "def handler():\n"
            "    q = request.args.get('q')\n"
            "    cursor.execute(q)\n"
            "    yaml.load(q)\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "app.py"
            path.write_text(code)
            engine = DispatchEngine()
            r1 = engine.scan_file(path)
            r2 = engine.scan_file(path)
            assert [f.__dict__ for f in r1.structural_findings] == \
                   [f.__dict__ for f in r2.structural_findings]
            assert [f.model_dump() for f in r1.taint_flows] == \
                   [f.model_dump() for f in r2.taint_flows]


class TestTestContextCap:
    def test_test_context_caps_confidence(self):
        result = _scan(
            "def handler():\n"
            "    q = request.args.get('q')\n"
            "    cursor.execute(q)\n",
            is_test_context=True,
        )
        assert len(result.taint_flows) == 1
        assert result.taint_flows[0].confidence <= 0.1
        assert result.taint_flows[0].confidence_bucket == "unlikely"
        # severity untouched by the confidence cap
        assert result.taint_flows[0].severity == "critical"
