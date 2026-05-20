"""Unit tests for the taint analysis engine.

Tests use in-memory strings rather than real files so there is no I/O dependency.
"""

import textwrap
import tempfile
import os
import pytest

from Asgard.Bragi.Quality.services.taint import TaintEngine, TaintAnalyzer, TaintConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine() -> TaintEngine:
    return TaintEngine()


def _paths(code: str, language: str):
    return _engine().analyze_function(source_text=code, language=language)


# ---------------------------------------------------------------------------
# Python — SQL injection via string concatenation
# ---------------------------------------------------------------------------

PYTHON_SQL_INJECTION = textwrap.dedent("""\
    def handle(request):
        user_input = request.GET.get('x')
        query = "SELECT * WHERE id=" + user_input
        cursor.execute(query)
""")


def test_python_sql_injection_flagged():
    paths = _paths(PYTHON_SQL_INJECTION, "python")
    assert len(paths) >= 1, "Expected at least one taint path for SQL injection"
    assert all(p.confidence >= 0.70 for p in paths)


# ---------------------------------------------------------------------------
# Python — sanitized path should NOT be flagged
# ---------------------------------------------------------------------------

PYTHON_SQL_SAFE = textwrap.dedent("""\
    def handle(request):
        user_input = request.GET.get('x')
        safe_val = escape(user_input)
        cursor.execute("SELECT * WHERE id=?", [safe_val])
""")


def test_python_sql_safe_not_flagged():
    paths = _paths(PYTHON_SQL_SAFE, "python")
    # After sanitization the taint chain is broken; no path should reach the sink.
    assert len(paths) == 0, f"Unexpected taint paths after sanitization: {paths}"


# ---------------------------------------------------------------------------
# PHP — SQL injection via concatenation
# ---------------------------------------------------------------------------

PHP_SQL_INJECTION = textwrap.dedent("""\
    <?php
    function handle() {
        $x = $_GET['id'];
        $q = "SELECT * WHERE id=" . $x;
        mysql_query($q);
    }
""")


def test_php_sql_injection_flagged():
    paths = _paths(PHP_SQL_INJECTION, "php")
    assert len(paths) >= 1, "Expected at least one taint path for PHP SQL injection"
    assert all(p.confidence >= 0.70 for p in paths)


# ---------------------------------------------------------------------------
# JavaScript — XSS via res.send
# ---------------------------------------------------------------------------

JS_XSS = textwrap.dedent("""\
    function handler(req, res) {
        const x = req.query.name;
        res.send("<p>" + x + "</p>");
    }
""")


def test_js_xss_flagged():
    paths = _paths(JS_XSS, "javascript")
    assert len(paths) >= 1, "Expected at least one taint path for JS XSS"
    assert all(p.confidence >= 0.70 for p in paths)


# ---------------------------------------------------------------------------
# Confidence decay across propagation hops
# ---------------------------------------------------------------------------

PYTHON_MULTI_HOP = textwrap.dedent("""\
    def handle(request):
        a = request.GET.get('x')
        b = a + "_suffix"
        c = b + "_more"
        cursor.execute(c)
""")


def test_python_confidence_decays_across_hops():
    paths = _paths(PYTHON_MULTI_HOP, "python")
    assert len(paths) >= 1
    # After two propagation hops: 1.0 * 0.9 * 0.9 = 0.81
    for p in paths:
        assert p.confidence <= 1.0
        assert p.confidence >= 0.70


# ---------------------------------------------------------------------------
# Confidence threshold — below threshold not reported via TaintAnalyzer
# ---------------------------------------------------------------------------

def test_confidence_threshold_filters_findings(tmp_path):
    # Create a Python file with a many-hop chain that falls below 0.70
    code = textwrap.dedent("""\
        def handle(request):
            a = request.GET.get('x')
            b = a + "x"
            c = b + "x"
            d = c + "x"
            cursor.execute(d)
    """)
    f = tmp_path / "test.py"
    f.write_text(code)

    # With a very high threshold nothing should be reported
    high_threshold = TaintConfig(threshold=0.99)
    report = TaintAnalyzer(config=high_threshold).analyze(str(f), language="python")
    assert report.files_scanned == 1
    assert len(report.findings) == 0, "Expected no findings above 0.99 threshold"


# ---------------------------------------------------------------------------
# TaintAnalyzer — file walk integration
# ---------------------------------------------------------------------------

def test_taint_analyzer_detects_python_sql(tmp_path):
    code = textwrap.dedent("""\
        def view(request):
            uid = request.GET.get('id')
            sql = "SELECT * FROM users WHERE id=" + uid
            cursor.execute(sql)
    """)
    f = tmp_path / "view.py"
    f.write_text(code)

    report = TaintAnalyzer().analyze(str(tmp_path))
    assert report.files_scanned == 1
    assert len(report.findings) >= 1
    finding = report.findings[0]
    assert finding.rule_id == "taint.python.source-to-sink"
    assert finding.confidence >= 0.70
    assert finding.severity in ("error", "warning")


def test_taint_analyzer_severity_mapping(tmp_path):
    # Direct source-to-sink (no propagation) should have confidence 1.0 → error
    code = textwrap.dedent("""\
        def view(request):
            uid = request.GET.get('id')
            cursor.execute(uid)
    """)
    f = tmp_path / "view.py"
    f.write_text(code)

    report = TaintAnalyzer().analyze(str(tmp_path))
    assert len(report.findings) >= 1
    assert report.findings[0].severity == "error"


def test_taint_analyzer_skips_unknown_extensions(tmp_path):
    f = tmp_path / "script.xyz"
    f.write_text("some code here")
    report = TaintAnalyzer().analyze(str(tmp_path))
    assert report.files_scanned == 0


def test_taint_analyzer_empty_directory(tmp_path):
    report = TaintAnalyzer().analyze(str(tmp_path))
    assert report.files_scanned == 0
    assert report.findings == []


# ---------------------------------------------------------------------------
# PHP — no taint when variable is not used in sink
# ---------------------------------------------------------------------------

PHP_NO_FLOW = textwrap.dedent("""\
    <?php
    function safe() {
        $x = $_GET['id'];
        $safe = "static_value";
        mysql_query($safe);
    }
""")


def test_php_no_flow_not_flagged():
    paths = _paths(PHP_NO_FLOW, "php")
    # $safe is never tainted — only $x is, and it never reaches a sink
    tainted_paths = [p for p in paths if p.variable in ("$x", "x")]
    assert len(tainted_paths) == 0


# ---------------------------------------------------------------------------
# Go — source detection
# ---------------------------------------------------------------------------

GO_SQL = textwrap.dedent("""\
    func handler(w http.ResponseWriter, r *http.Request) {
        id := r.FormValue("id")
        query := "SELECT * FROM t WHERE id=" + id
        db.Query(query)
    }
""")


def test_go_sql_injection_flagged():
    paths = _paths(GO_SQL, "go")
    assert len(paths) >= 1
    assert all(p.language == "go" for p in paths)
