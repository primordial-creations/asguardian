"""
CLI multi-language wiring tests.

Covers the four uplift fixes:
  1. `security scan` feeds JS/TS/Java to the DispatchEngine (not just .py).
  2. `heimdall scan` (full) merges DispatchEngine multi-language findings
     into the Security step, not just StaticSecurityService.
  3. `security taint` routes JS/TS/Java through the DispatchEngine's CST
     taint path, not just the Python-ast TaintAnalyzer.
  4. Python-only categories (OOP, Test Coverage) report N/A -- not a
     fabricated PASS/100% -- on trees with no Python sources.
"""

import json

import pytest

from Asgard.Heimdall.cli.main import create_parser
from Asgard.Heimdall.cli.handlers.security import run_security_analysis
from Asgard.Heimdall.cli.handlers.taint import run_taint_analysis
from Asgard.Heimdall.cli.handlers.scan import run_full_scan
from Asgard.Heimdall.cli.handlers._security_dispatch import run_dispatch_scan


JS_SQLI_SOURCE = (
    "const mysql = require('mysql');\n"
    "const conn = mysql.createConnection({});\n\n"
    "function getUser(req, res) {\n"
    "  const userId = req.query.id;\n"
    "  const query = \"SELECT * FROM users WHERE id = \" + userId;\n"
    "  conn.query(query, function(err, results) {\n"
    "    res.send(results);\n"
    "  });\n"
    "}\n"
)


@pytest.fixture()
def js_sqli_project(tmp_path):
    (tmp_path / "app.js").write_text(JS_SQLI_SOURCE)
    return tmp_path


@pytest.fixture()
def py_only_project(tmp_path):
    (tmp_path / "app.py").write_text(
        "class Foo:\n"
        "    def bar(self):\n"
        "        return 1\n"
    )
    return tmp_path


# Flask/sqlite3 SQLi that BOTH StaticSecurityService's regex/pattern rules
# and the DispatchEngine's taint path independently flag on the same .py
# file -- the repro case for the Python double-count regression.
PY_FLASK_SQLI_SOURCE = (
    "from flask import Flask, request\n"
    "import sqlite3\n\n"
    "app = Flask(__name__)\n\n"
    "@app.route(\"/user\")\n"
    "def get_user():\n"
    "    user_id = request.args.get(\"id\")\n"
    "    conn = sqlite3.connect(\"db.sqlite\")\n"
    "    cur = conn.cursor()\n"
    "    query = \"SELECT * FROM users WHERE id = \" + user_id\n"
    "    cur.execute(query)\n"
    "    return str(cur.fetchall())\n"
)


@pytest.fixture()
def py_flask_sqli_project(tmp_path):
    (tmp_path / "app.py").write_text(PY_FLASK_SQLI_SOURCE)
    return tmp_path


# --------------------------------------------------------- Fix 1: security scan

def test_dispatch_scan_covers_js_ts_java_files(js_sqli_project):
    entries = run_dispatch_scan(js_sqli_project)
    assert entries, "JS SQLi fixture should surface a dispatch finding"
    assert any(e["file_path"].endswith("app.js") for e in entries)
    assert any("sql" in e["rule_id"].lower() for e in entries)


def test_security_scan_surfaces_js_sqli(js_sqli_project, capsys):
    args = create_parser().parse_args(
        ["security", "scan", str(js_sqli_project), "--format", "json"]
    )
    code = run_security_analysis(args, analysis_type="all")
    out = capsys.readouterr().out
    payload = json.loads(out[out.find("{"):out.rfind("}") + 1])
    assert payload["dispatch_findings"], "expected JS SQLi in dispatch_findings"
    assert any(
        "app.js" in e["file_path"] for e in payload["dispatch_findings"]
    )
    assert code == 1


# --------------------------------------------------- Fix 2: full `heimdall scan`

def test_full_scan_merges_multilang_security_findings(js_sqli_project, capsys):
    args = create_parser().parse_args(["scan", str(js_sqli_project)])
    run_full_scan(args)
    out = capsys.readouterr().out
    assert "Security" in out
    # Security step must FAIL (not PASS) since a real JS SQLi is present.
    for line in out.splitlines():
        if line.strip().startswith("Security "):
            assert "FAIL" in line
            break
    else:
        pytest.fail("Security row not found in scan summary")


# ------------------------------------------------------------ Fix 3: security taint

def test_taint_surfaces_js_sqli_flow(js_sqli_project, capsys):
    args = create_parser().parse_args(
        ["security", "taint", str(js_sqli_project), "--format", "json"]
    )
    run_taint_analysis(args)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["summary"]["total_flows"] >= 1
    assert any(
        "app.js" in f["sink"]["file_path"] for f in payload["flows"]
    )


# --------------------------------------------------- Fix 4: honest N/A labeling

def test_full_scan_js_tree_reports_real_coverage_not_fabricated(
    js_sqli_project, capsys
):
    # A JS tree must never show the old fabricated "100% coverage" green, and
    # (now that JS coverage is supported) must report a REAL number, not N/A.
    args = create_parser().parse_args(["scan", str(js_sqli_project)])
    run_full_scan(args)
    out = capsys.readouterr().out
    assert "100.0% method coverage" not in out
    coverage_line = next(
        l for l in out.splitlines() if l.strip().startswith("Test Coverage")
    )
    assert "N/A" not in coverage_line
    assert "method coverage" in coverage_line
    # OOP on a supported language is either a real result or honest N/A when the
    # tree has no classes — never a fabricated green PASS with no data.
    oop_line = next(
        l for l in out.splitlines()
        if l.strip().startswith("Object Oriented Programming")
    )
    assert ("N/A" in oop_line) or ("violations" in oop_line)


def test_full_scan_python_project_still_reports_real_coverage(
    py_only_project, capsys
):
    args = create_parser().parse_args(["scan", str(py_only_project)])
    run_full_scan(args)
    out = capsys.readouterr().out
    coverage_line = next(
        l for l in out.splitlines() if l.strip().startswith("Test Coverage")
    )
    assert "N/A" not in coverage_line
    assert "method coverage" in coverage_line


# --------------------------------------------- MAJOR-1: no Python double-count

def test_security_scan_does_not_double_count_python_findings(
    py_flask_sqli_project, capsys
):
    """run_dispatch_scan() also re-scans .py files. StaticSecurityService
    already reports its own findings for the same SQLi -- folding
    DispatchEngine's .py findings back in must NOT double the counts.
    The merged counts (dispatch restricted to non-.py) must equal the
    pre-merge StaticSecurityService-only baseline exactly."""
    from Asgard.Heimdall.Security.models.security_models import SecurityScanConfig
    from Asgard.Heimdall.Security.services.static_security_service import (
        StaticSecurityService,
    )
    from Asgard.Heimdall.cli.handlers._security_dispatch import count_lines_of_code

    baseline_cfg = SecurityScanConfig(
        scan_path=py_flask_sqli_project, scan_type="all", min_severity="low",
        exclude_patterns=[], verbose=False,
    )
    baseline_svc = StaticSecurityService(baseline_cfg)
    baseline_result = baseline_svc.analyze(py_flask_sqli_project)
    baseline_result.total_lines_of_code = count_lines_of_code(
        py_flask_sqli_project, []
    )
    baseline_result.calculate_totals()

    args = create_parser().parse_args(
        ["security", "scan", str(py_flask_sqli_project), "--format", "json"]
    )
    run_security_analysis(args, analysis_type="all")
    out = capsys.readouterr().out
    payload = json.loads(out[out.find("{"):out.rfind("}") + 1])

    assert payload["summary"]["total_issues"] == baseline_result.total_issues
    assert payload["summary"]["critical_issues"] == baseline_result.critical_issues
    assert payload["summary"]["high_issues"] == baseline_result.high_issues
    assert payload["scoring"]["legacy_score"] == baseline_result.legacy_score


# ------------------------------------------- MAJOR-2: score reflects merge

def test_security_scan_score_reflects_multilang_criticals(
    js_sqli_project, capsys
):
    """A JS-only tree with 2 CRITICAL findings must NOT report a false
    security_score of 100 -- the score must be consistent with the
    counts and the FAIL/is_passing verdict."""
    args = create_parser().parse_args(
        ["security", "scan", str(js_sqli_project), "--format", "json"]
    )
    code = run_security_analysis(args, analysis_type="all")
    out = capsys.readouterr().out
    payload = json.loads(out[out.find("{"):out.rfind("}") + 1])

    assert payload["summary"]["critical_issues"] >= 1
    assert payload["scoring"]["legacy_score"] < 100.0
    assert payload["scoring"]["security_score_v2"] < 100.0
    assert payload["summary"]["is_passing"] is False
    assert code == 1
