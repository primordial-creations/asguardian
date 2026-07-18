"""Dual-engine tests for the wave-1 Python pilot rules.

Every behavioural test runs under both engines via ``dual_engine_mode``
(the AST leg is skipped when the optional tree-sitter extra is absent).
"""
import pytest

from Asgard.Heimdall.Security.services._ast_python_rules import (
    PYTHON_PILOT_RULES,
    check_eval_exec,
    check_injection_sink_candidates,
    check_route_missing_auth,
    check_subprocess_shell_true,
    check_yaml_unsafe_load,
    run_python_pilot_rules,
)
from Asgard.Heimdall.treesitter.ast_engine import is_engine_enabled
from Asgard.Heimdall.treesitter.file_context import FileParseContext


def _lines(source: str):
    return source.splitlines()


# ---------------------------------------------------------------------------
# eval / exec
# ---------------------------------------------------------------------------

def test_eval_exec_detected_both_engines(dual_engine_mode):
    src = "def f(payload):\n    return eval(payload)\n"
    findings = check_eval_exec("x.py", _lines(src), True)
    assert len(findings) == 1
    assert findings[0]["line"] == 2
    assert findings[0]["rule_id"] == "python.eval-exec-usage"
    assert findings[0]["engine"] == dual_engine_mode


def test_eval_in_comment_not_flagged(dual_engine_mode):
    src = "# we never call eval(x) here\ny = 1\n"
    assert check_eval_exec("x.py", _lines(src), True) == []


def test_eval_in_string_only_flagged_by_regex(dual_engine_mode):
    src = 'msg = "avoid eval(x) in prod"\n'
    findings = check_eval_exec("x.py", _lines(src), True)
    if dual_engine_mode == "ast":
        assert findings == []  # AST precision gain
    else:
        assert len(findings) == 1  # documented regex ceiling


def test_method_named_eval_not_flagged_as_builtin(dual_engine_mode):
    src = "result = model.eval(data)\n"
    assert check_eval_exec("x.py", _lines(src), True) == []


# ---------------------------------------------------------------------------
# yaml.load
# ---------------------------------------------------------------------------

def test_yaml_load_without_loader_flagged(dual_engine_mode):
    src = "import yaml\ncfg = yaml.load(data)\n"
    findings = check_yaml_unsafe_load("x.py", _lines(src), True)
    assert [f["line"] for f in findings] == [2]


def test_yaml_load_with_safe_loader_ok(dual_engine_mode):
    src = "cfg = yaml.load(data, Loader=yaml.SafeLoader)\n"
    assert check_yaml_unsafe_load("x.py", _lines(src), True) == []


def test_yaml_safe_load_ok(dual_engine_mode):
    src = "cfg = yaml.safe_load(data)\n"
    assert check_yaml_unsafe_load("x.py", _lines(src), True) == []


@pytest.mark.skipif(not is_engine_enabled("python"), reason="tree-sitter not installed")
def test_yaml_multiline_safe_loader_ast_only():
    """Regex cannot see the Loader kwarg on the next line; AST can."""
    src = "cfg = yaml.load(\n    data, Loader=yaml.SafeLoader,\n)\n"
    ast_findings = check_yaml_unsafe_load("x.py", _lines(src), True)
    assert ast_findings == []
    regex_findings = check_yaml_unsafe_load.__regex_impl__("x.py", _lines(src), True)
    assert len(regex_findings) == 1  # documented regex FP


# ---------------------------------------------------------------------------
# subprocess shell=True
# ---------------------------------------------------------------------------

def test_subprocess_shell_true_flagged(dual_engine_mode):
    src = "import subprocess\nsubprocess.run(cmd, shell=True)\n"
    findings = check_subprocess_shell_true("x.py", _lines(src), True)
    assert [f["line"] for f in findings] == [2]
    assert findings[0]["cwe_id"] == "CWE-78"


def test_subprocess_shell_false_ok(dual_engine_mode):
    src = "subprocess.run(cmd, shell=False)\nsubprocess.run(cmd)\n"
    assert check_subprocess_shell_true("x.py", _lines(src), True) == []


@pytest.mark.skipif(not is_engine_enabled("python"), reason="tree-sitter not installed")
def test_subprocess_multiline_shell_true_ast_recall_gain():
    src = "subprocess.run(\n    cmd,\n    shell=True,\n)\n"
    ast_findings = check_subprocess_shell_true("x.py", _lines(src), True)
    assert len(ast_findings) == 1
    assert ast_findings[0]["line"] == 1
    regex_findings = check_subprocess_shell_true.__regex_impl__("x.py", _lines(src), True)
    assert regex_findings == []  # documented regex FN


# ---------------------------------------------------------------------------
# route missing auth
# ---------------------------------------------------------------------------

_ROUTE_SRC = (
    '@app.route("/admin")\n'
    "def admin_panel():\n"
    "    return render()\n"
    "\n"
    '@app.route("/dash")\n'
    "@login_required\n"
    "def dashboard():\n"
    "    return render()\n"
)


def test_route_missing_auth(dual_engine_mode):
    findings = check_route_missing_auth("x.py", _lines(_ROUTE_SRC), True)
    assert [f["line"] for f in findings] == [2]
    assert findings[0]["rule_id"] == "python.route-missing-auth"


def test_undecorated_function_not_flagged(dual_engine_mode):
    src = "def helper():\n    return 1\n"
    assert check_route_missing_auth("x.py", _lines(src), True) == []


# ---------------------------------------------------------------------------
# injection sink pre-filter
# ---------------------------------------------------------------------------

def test_sink_candidate_string_concat(dual_engine_mode):
    src = 'cur.execute("SELECT * FROM t WHERE id = " + user_id)\n'
    findings = check_injection_sink_candidates("x.py", _lines(src), True)
    assert len(findings) == 1
    assert findings[0]["severity"] == "info"


def test_sink_static_literal_not_flagged(dual_engine_mode):
    src = 'os.system("ls -la")\n'
    assert check_injection_sink_candidates("x.py", _lines(src), True) == []


@pytest.mark.skipif(not is_engine_enabled("python"), reason="tree-sitter not installed")
def test_sink_parameterized_query_ast_precision_gain():
    src = 'cur.execute("SELECT * FROM t WHERE id = %s", (uid,))\n'
    assert check_injection_sink_candidates("x.py", _lines(src), True) == []
    regex_findings = check_injection_sink_candidates.__regex_impl__("x.py", _lines(src), True)
    assert len(regex_findings) == 1  # documented regex FP


# ---------------------------------------------------------------------------
# orchestration: single parse per file
# ---------------------------------------------------------------------------

def test_run_python_pilot_rules_aggregates(dual_engine_mode):
    src = (
        "import yaml, subprocess\n"
        "cfg = yaml.load(data)\n"
        "subprocess.run(cmd, shell=True)\n"
        "eval(payload)\n"
    )
    findings = run_python_pilot_rules("x.py", _lines(src))
    rule_ids = {f["rule_id"] for f in findings}
    assert "python.yaml-unsafe-load" in rule_ids
    assert "python.subprocess-shell-true" in rule_ids
    assert "python.eval-exec-usage" in rule_ids
    assert all(f["engine"] == dual_engine_mode for f in findings)


@pytest.mark.skipif(not is_engine_enabled("python"), reason="tree-sitter not installed")
def test_shared_parse_context_is_used_once():
    src = "eval(x)\n"
    ctx = FileParseContext.parse("x.py", _lines(src), "python")
    assert ctx.root is not None
    findings = run_python_pilot_rules("x.py", _lines(src), parse_context=ctx)
    assert any(f["rule_id"] == "python.eval-exec-usage" for f in findings)


@pytest.mark.skipif(not is_engine_enabled("python"), reason="tree-sitter not installed")
def test_findings_in_error_regions_are_skipped():
    src = "def broken(:\n    eval(x)\n"
    ctx = FileParseContext.parse("x.py", _lines(src), "python")
    assert ctx.has_errors
    findings = check_eval_exec("x.py", _lines(src), True, parse_context=ctx)
    assert all(not ctx.intersects_error(f["line"] - 1) for f in findings)


def test_all_pilot_rules_are_dual_engine():
    for rule in PYTHON_PILOT_RULES:
        assert getattr(rule, "__engine__", None) == "dual"
        assert callable(rule.__ast_impl__)
        assert callable(rule.__regex_impl__)


def test_findings_are_primitive_only(dual_engine_mode):
    src = "eval(x)\nyaml.load(d)\n"
    for f in run_python_pilot_rules("x.py", _lines(src)):
        assert isinstance(f["rule_id"], str)
        assert isinstance(f["line"], int)
        assert isinstance(f["message"], str)
        assert isinstance(f["confidence"], float)
