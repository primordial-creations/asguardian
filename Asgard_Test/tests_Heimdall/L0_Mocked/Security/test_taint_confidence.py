"""Tests for confidence-scored taint analysis (plan 04 P1)."""

import tempfile
from pathlib import Path

import pytest

from Asgard.Heimdall.Security.TaintAnalysis import TaintAnalyzer, TaintConfig


def _scan(code: str, **config_kwargs):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)
        (path / "app.py").write_text(code)
        config = TaintConfig(
            exclude_patterns=["__pycache__", ".git"], **config_kwargs)
        return TaintAnalyzer(config=config).scan(path)


class TestConfidencePropagation:
    def test_exact_source_direct_sink_is_certain(self):
        report = _scan(
            "def handler():\n"
            "    q = request.args.get('q')\n"
            "    cursor.execute(q)\n"
        )
        assert len(report.flows) == 1
        flow = report.flows[0]
        assert flow.confidence > 0.85
        assert flow.confidence_bucket == "certain"
        assert flow.hop_count == 0

    def test_fstring_propagator_decays(self):
        report = _scan(
            "def handler():\n"
            "    q = request.args.get('q')\n"
            "    sql = f'SELECT * FROM t WHERE x = {q}'\n"
            "    cursor.execute(sql)\n"
        )
        assert len(report.flows) == 1
        assert report.flows[0].confidence == pytest.approx(0.9, abs=0.001)

    def test_conventional_source_lower_confidence(self):
        report = _scan(
            "def handler():\n"
            "    v = request.values.get('v')\n"
            "    cursor.execute(v)\n"
        )
        assert len(report.flows) == 1
        assert report.flows[0].confidence == pytest.approx(0.8, abs=0.001)

    def test_generic_execute_sink_low_confidence(self):
        report = _scan(
            "def handler():\n"
            "    v = request.args.get('v')\n"
            "    runner.execute(v)\n"
        )
        assert len(report.flows) == 1
        assert report.flows[0].confidence == pytest.approx(0.4, abs=0.001)
        assert report.flows[0].confidence_bucket == "possible"

    def test_confidence_bucket_is_qualitative(self):
        report = _scan(
            "def handler():\n"
            "    q = request.args.get('q')\n"
            "    cursor.execute(q)\n"
        )
        assert report.flows[0].confidence_bucket in (
            "certain", "probable", "possible", "unlikely")

    def test_severity_never_diluted_by_confidence(self):
        """Orthogonality: a heavily-decayed SQL flow keeps critical severity."""
        report = _scan(
            "def handler():\n"
            "    q = request.values.get('q')\n"
            "    a = f'{q}!'\n"
            "    b = a + '?'\n"
            "    runner.execute(b)\n"
        )
        assert len(report.flows) == 1
        flow = report.flows[0]
        assert flow.severity == "critical"
        assert flow.confidence < 0.5


class TestSanitizerTaxonomy:
    def test_exact_sanitizer_drops_flow(self):
        report = _scan(
            "import shlex\n"
            "def handler():\n"
            "    c = request.args.get('c')\n"
            "    safe = shlex.quote(c)\n"
            "    os.system('ls ' + safe)\n"
        )
        assert len(report.flows) == 0

    def test_int_coercion_drops_flow(self):
        report = _scan(
            "def handler():\n"
            "    c = request.args.get('c')\n"
            "    n = int(c)\n"
            "    cursor.execute('SELECT * FROM t LIMIT ' + str(n))\n"
        )
        assert len(report.flows) == 0

    def test_heuristic_sanitizer_downgrades_not_drops(self):
        report = _scan(
            "def handler():\n"
            "    c = request.args.get('c')\n"
            "    safe = sanitize_sql(c)\n"
            "    cursor.execute(safe)\n",
            min_confidence=0.0,
        )
        assert len(report.flows) == 1
        flow = report.flows[0]
        assert flow.confidence == pytest.approx(0.4, abs=0.001)
        assert flow.sanitizers_present is True
        records = flow.sanitizers_applied
        assert len(records) == 1
        assert records[0].kind == "heuristic"
        assert records[0].factor == pytest.approx(0.4)

    def test_re_sub_is_heuristic(self):
        report = _scan(
            "import re\n"
            "def handler():\n"
            "    c = request.args.get('c')\n"
            "    safe = re.sub(r'[^a-z]', '', c)\n"
            "    cursor.execute(safe)\n",
            min_confidence=0.0,
        )
        assert len(report.flows) == 1
        assert report.flows[0].confidence == pytest.approx(0.4, abs=0.001)


class TestSinkKwargSemantics:
    def test_subprocess_shell_false_dropped(self):
        report = _scan(
            "import subprocess\n"
            "def handler():\n"
            "    c = request.args.get('c')\n"
            "    subprocess.run(c, shell=False)\n"
        )
        assert len(report.flows) == 0

    def test_subprocess_shell_true_certain(self):
        report = _scan(
            "import subprocess\n"
            "def handler():\n"
            "    c = request.args.get('c')\n"
            "    subprocess.run(c, shell=True)\n"
        )
        assert len(report.flows) == 1
        assert report.flows[0].confidence_bucket == "certain"

    def test_subprocess_no_shell_kwarg_is_possible(self):
        """No shell= means argv execution: shell injection impossible,
        argv-level injection remains -> 'possible', not certain or dropped."""
        report = _scan(
            "import subprocess\n"
            "def handler():\n"
            "    c = request.args.get('c')\n"
            "    subprocess.run(c)\n"
        )
        assert len(report.flows) == 1
        assert report.flows[0].confidence_bucket == "possible"

    def test_yaml_safe_loader_dropped(self):
        report = _scan(
            "import yaml\n"
            "def handler():\n"
            "    d = request.data\n"
            "    yaml.load(d, Loader=yaml.SafeLoader)\n"
        )
        assert len(report.flows) == 0

    def test_yaml_unsafe_load_flagged(self):
        report = _scan(
            "import yaml\n"
            "def handler():\n"
            "    d = request.data\n"
            "    yaml.load(d)\n"
        )
        assert len(report.flows) == 1
        assert report.flows[0].severity == "critical"


class TestAliasResolution:
    def test_import_alias_sink_detected(self):
        report = _scan(
            "import subprocess as sp\n"
            "def handler():\n"
            "    c = request.args.get('c')\n"
            "    sp.run(c, shell=True)\n"
        )
        assert len(report.flows) == 1

    def test_from_import_alias_sink_detected(self):
        report = _scan(
            "from os import system as run_cmd\n"
            "def handler():\n"
            "    c = request.args.get('c')\n"
            "    run_cmd(c)\n"
        )
        assert len(report.flows) == 1
        assert report.flows[0].sink_type == "shell_command"


class TestFlowSensitivityUpgrades:
    def test_branch_union_taint_from_either_arm(self):
        report = _scan(
            "def handler(flag):\n"
            "    q = 'constant'\n"
            "    if flag:\n"
            "        q = request.args.get('q')\n"
            "    cursor.execute(q)\n"
        )
        assert len(report.flows) == 1

    def test_reassignment_kills_taint(self):
        report = _scan(
            "def handler():\n"
            "    q = request.args.get('q')\n"
            "    q = 'SELECT 1'\n"
            "    cursor.execute(q)\n"
        )
        assert len(report.flows) == 0

    def test_parameterized_query_args_not_flagged(self):
        """execute(constant_sql, params) is the parameterized safe path."""
        report = _scan(
            "def handler():\n"
            "    q = request.args.get('q')\n"
            "    cursor.execute('SELECT * FROM t WHERE x = %s', (q,))\n"
        )
        assert len(report.flows) == 0

    def test_mock_variable_context_downgrade(self):
        report = _scan(
            "def handler():\n"
            "    mock_query = request.args.get('q')\n"
            "    cursor.execute(mock_query)\n",
            min_confidence=0.0,
        )
        assert len(report.flows) == 1
        assert report.flows[0].confidence == pytest.approx(0.3, abs=0.001)

    def test_min_confidence_hides_unlikely_by_default(self):
        """Default min_confidence=0.25 hides the 'unlikely' bucket."""
        report = _scan(
            "def handler():\n"
            "    mock_q = request.values.get('q')\n"     # 0.8 source
            "    runner.execute(mock_q)\n"               # x0.4 sink x0.3 mock = 0.096
        )
        assert len(report.flows) == 0
        # ... but visible on an audit scan with min_confidence=0.0
        audit = _scan(
            "def handler():\n"
            "    mock_q = request.values.get('q')\n"
            "    runner.execute(mock_q)\n",
            min_confidence=0.0,
        )
        assert len(audit.flows) == 1
        assert audit.flows[0].confidence_bucket == "unlikely"


class TestRouteDecoratorSeeding:
    def test_flask_route_params_are_heuristic_sources(self):
        report = _scan(
            "@app.route('/user/<name>')\n"
            "def show_user(name):\n"
            "    cursor.execute('SELECT * FROM users WHERE name = ' + name)\n"
        )
        assert len(report.flows) == 1
        flow = report.flows[0]
        # heuristic param on a route-decorated function: 0.6 x 0.9 (concat) x 1.0
        assert flow.confidence == pytest.approx(0.54, abs=0.001)
        assert flow.confidence_bucket == "probable"

    def test_undecorated_params_not_sources(self):
        report = _scan(
            "def helper(name):\n"
            "    cursor.execute('SELECT * FROM users WHERE name = ' + name)\n"
        )
        assert len(report.flows) == 0
