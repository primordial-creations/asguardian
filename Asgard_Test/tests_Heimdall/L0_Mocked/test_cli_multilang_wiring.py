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

def test_full_scan_reports_na_not_100pct_on_non_python_tree(
    js_sqli_project, capsys
):
    args = create_parser().parse_args(["scan", str(js_sqli_project)])
    run_full_scan(args)
    out = capsys.readouterr().out
    assert "100.0% method coverage" not in out
    assert "100.0%" not in out.split("Object Oriented")[1].split("\n")[0] \
        if "Object Oriented" in out else True
    coverage_line = next(
        l for l in out.splitlines() if l.strip().startswith("Test Coverage")
    )
    assert "N/A" in coverage_line
    oop_line = next(
        l for l in out.splitlines()
        if l.strip().startswith("Object Oriented Programming")
    )
    assert "N/A" in oop_line


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
