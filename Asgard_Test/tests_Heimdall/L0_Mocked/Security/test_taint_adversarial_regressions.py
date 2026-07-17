"""Regression tests for adversarial-review findings (taint engine).

Each test uses the reviewer's exact adversarial snippet.
"""

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


class TestBlocker1ContainerLaundering:
    """Taint must survive laundering through dict/list containers."""

    def test_dict_store_and_load_flags(self):
        report = _scan(
            "def handler():\n"
            "    t = {}\n"
            "    t['x'] = request.args['q']\n"
            "    os.system(t['x'])\n"
        )
        assert len(report.flows) == 1
        assert report.flows[0].sink_type == "shell_command"
        assert report.flows[0].severity == "critical"

    def test_list_append_flags(self):
        report = _scan(
            "def handler():\n"
            "    parts = []\n"
            "    parts.append(request.args['q'])\n"
            "    os.system(parts[0])\n"
        )
        assert len(report.flows) == 1
        assert report.flows[0].sink_type == "shell_command"

    def test_list_extend_and_dict_update_flag(self):
        report = _scan(
            "def h1():\n"
            "    xs = []\n"
            "    xs.extend([request.args['a']])\n"
            "    cursor.execute(xs[0])\n"
            "def h2():\n"
            "    d = {}\n"
            "    d.update({'k': request.form['b']})\n"
            "    cursor.execute(d['k'])\n"
        )
        assert len(report.flows) == 2

    def test_attribute_store_flags(self):
        report = _scan(
            "def handler(ctx):\n"
            "    ctx.q = request.args['q']\n"
            "    cursor.execute(ctx.q)\n"
        )
        assert len(report.flows) == 1

    def test_clean_element_store_does_not_clear_container(self):
        """Over-approximation: storing a clean value does not un-taint the
        container (other elements may still hold taint)."""
        report = _scan(
            "def handler():\n"
            "    t = {}\n"
            "    t['x'] = request.args['q']\n"
            "    t['y'] = 'constant'\n"
            "    os.system(t['x'])\n"
        )
        assert len(report.flows) == 1

    def test_untainted_container_still_clean(self):
        report = _scan(
            "def handler():\n"
            "    t = {}\n"
            "    t['x'] = 'constant'\n"
            "    os.system(t['x'])\n"
        )
        assert len(report.flows) == 0


class TestBlocker2NoOpSanitizerWrappers:
    """Name-based sanitizer heuristics must not mute real findings."""

    def test_noop_sanitize_wrapper_resolved_no_downgrade(self):
        """An in-project sanitize_* that just returns its param: the summary
        is authoritative -- NO heuristic downgrade applies."""
        report = _scan(
            "def sanitize_username(u):\n"
            "    return u\n"
            "\n"
            "def handler():\n"
            "    q = request.args.get('q')\n"
            "    safe = sanitize_username(q)\n"
            "    cursor.execute(safe)\n"
        )
        assert len(report.flows) == 1
        flow = report.flows[0]
        # 1.0 source x 0.85 resolved hop x 1.0 sink -- not x0.4
        assert flow.confidence == pytest.approx(0.85, abs=0.001)
        assert flow.confidence_bucket in ("probable", "certain")

    def test_route_param_through_unresolved_sanitizer_stays_visible(self):
        """0.6 route param x 0.4 heuristic = 0.24 would vanish below the
        default 0.25 floor; the clamp keeps it visible as 'possible'."""
        report = _scan(
            "from external_lib import sanitize_name\n"
            "@app.route('/u/<name>')\n"
            "def show(name):\n"
            "    safe = sanitize_name(name)\n"
            "    cursor.execute('SELECT * FROM u WHERE n = ' + safe)\n"
        )
        assert len(report.flows) == 1
        flow = report.flows[0]
        assert flow.confidence_bucket == "possible"
        assert flow.sanitizers_present is True
        assert any(s.kind == "heuristic" for s in flow.sanitizers_applied)

    def test_real_cross_function_exact_sanitizer_not_flagged(self):
        """A wrapper that genuinely applies shlex.quote returns clean."""
        report = _scan(
            "import shlex\n"
            "def clean_cmd(c):\n"
            "    return shlex.quote(c)\n"
            "\n"
            "def handler():\n"
            "    c = request.args.get('c')\n"
            "    safe = clean_cmd(c)\n"
            "    os.system('ls ' + safe)\n"
        )
        assert len(report.flows) == 0


class TestMajor1ResolvedCleanCalls:
    """Resolved calls returning clean values must not get the x0.5
    unknown-call over-approximation."""

    def test_resolved_constant_return_is_clean(self):
        report = _scan(
            "def default_query(q):\n"
            "    return 'SELECT 1'\n"
            "\n"
            "def handler():\n"
            "    q = request.args.get('q')\n"
            "    sql = default_query(q)\n"
            "    cursor.execute(sql)\n"
        )
        assert len(report.flows) == 0

    def test_unresolved_call_still_over_approximated(self):
        report = _scan(
            "from mystery_lib import transform\n"
            "def handler():\n"
            "    q = request.args.get('q')\n"
            "    sql = transform(q)\n"
            "    cursor.execute(sql)\n",
            min_confidence=0.0,
        )
        assert len(report.flows) == 1
        assert report.flows[0].confidence == pytest.approx(0.5, abs=0.001)


class TestMajor2SameLineSinks:
    """Two distinct sink calls on one line must survive dedup."""

    def test_two_sinks_same_line_two_flows(self):
        report = _scan(
            "def handler():\n"
            "    a = request.args.get('a')\n"
            "    b = request.form.get('b')\n"
            "    cursor.execute(a); os.system(b)\n"
        )
        assert len(report.flows) == 2
        sink_types = {f.sink_type for f in report.flows}
        assert sink_types == {"sql_query", "shell_command"}

    def test_same_sink_twice_same_line_two_flows(self):
        report = _scan(
            "def handler():\n"
            "    a = request.args.get('a')\n"
            "    b = request.form.get('b')\n"
            "    cursor.execute(a); cursor.execute(b)\n"
        )
        assert len(report.flows) == 2

    def test_identical_duplicate_still_deduped(self):
        """Same sink call site reached twice remains one finding."""
        report = _scan(
            "def handler(flag):\n"
            "    a = request.args.get('a')\n"
            "    b = request.form.get('b')\n"
            "    q = a if flag else b\n"
            "    cursor.execute(q)\n"
        )
        assert len(report.flows) == 1
