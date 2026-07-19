"""SA4 (context- & path-sensitivity) -- Wave 2 of the Deterministic
Static-Analysis Deepening plan (``_Docs/Planning/StaticDepth/00_Plan.md``).

The bulk of the acceptance-bullet coverage lives in the benchmark corpus
(``Asgard_Test/tests_Heimdall/benchmarks/corpus/taint/`` and
``corpus/taint_js/`` -- see the ``tp_sa4_*``/``fp_sa4_*`` sibling pairs).
This file exercises both engines (Python ``ast`` in
``Security/TaintAnalysis/services/_taint_visitor.py`` and the tree-sitter
CST engine in ``Security/TaintAnalysis/engine/cst_taint_visitor.py``)
directly for the specific invariants SA4 must never violate.

Core invariant under test throughout (from ``ASGARD_UPLIFT_GOAL.md``):
path-sensitivity is where mute bugs are MOST likely -- a guard/validator
must only clear taint when it PROVABLY dominates the sink on that path via
a real, catalog-verified predicate. An unguarded path, or a path guarded by
something the engine cannot verify, must still flag. A branch join must
UNION taint from all arms, never intersect. Context-sensitivity must not
conflate a clean call site with a sinking call site of the same helper.
"""

import tempfile
from pathlib import Path

from Asgard.Heimdall.Security.TaintAnalysis.services.taint_analyzer import TaintAnalyzer
from Asgard.Heimdall.Security.engine.dispatch import DispatchEngine
from Asgard.Heimdall.treesitter.ast_engine import is_engine_enabled


def _scan_py(code: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "probe.py"
        path.write_text(code)
        return TaintAnalyzer().scan(Path(tmpdir))


def _scan_js(code: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "probe.js"
        path.write_text(code)
        return DispatchEngine().scan_file(path)


# --------------------------------------------------------------------- Python


class TestPythonGuardClausePathSensitivity:
    def test_real_validator_guard_clause_clears(self):
        """`if not x.isdigit(): return` -- a REAL, catalog-grade value-
        domain predicate dominates every path that reaches the sink. This
        cannot mute a true positive: `str.isdigit()` PROVES the value's
        character class excludes every shell/SQL/HTML metacharacter, so no
        real injection payload can survive it -- clearing here reflects an
        actually-impossible attack path, not a guess."""
        report = _scan_py(
            "import subprocess\n"
            "def run():\n"
            "    host = request.args.get('host')\n"
            "    if not host.isdigit():\n"
            "        return 'invalid'\n"
            "    subprocess.run('ping ' + host, shell=True)\n"
        )
        assert report.flows == []

    def test_real_validator_then_arm_clears(self):
        """`if x.isdigit(): sink(x)` (no early return) -- only the THEN arm,
        where the predicate holds, reaches the sink."""
        report = _scan_py(
            "import subprocess\n"
            "def run():\n"
            "    host = request.args.get('host')\n"
            "    if host.isdigit():\n"
            "        subprocess.run('ping ' + host, shell=True)\n"
        )
        assert report.flows == []

    def test_isinstance_numeric_guard_clears(self):
        """`isinstance(x, (int, float))` is a genuine, unshadowable runtime
        type predicate -- true only when `x` isn't a string at all."""
        report = _scan_py(
            "import subprocess\n"
            "def run():\n"
            "    host = request.args.get('host')\n"
            "    if not isinstance(host, (int, float)):\n"
            "        return\n"
            "    subprocess.run('ping ' + str(host), shell=True)\n"
        )
        assert report.flows == []

    def test_unguarded_path_still_flags(self):
        """Sanity baseline: no guard at all must still flag -- proves the
        path-sensitivity additions cannot suppress a plain flow."""
        report = _scan_py(
            "import subprocess\n"
            "def run():\n"
            "    host = request.args.get('host')\n"
            "    subprocess.run('ping ' + host, shell=True)\n"
        )
        assert len(report.flows) == 1

    def test_non_sanitizer_guard_does_not_clear(self):
        """`if x is not None` is NOT a catalog-verified predicate -- it
        proves nothing about x's content. Never mute: must still flag."""
        report = _scan_py(
            "import subprocess\n"
            "def run():\n"
            "    host = request.args.get('host')\n"
            "    if host is not None:\n"
            "        subprocess.run('ping ' + host, shell=True)\n"
        )
        assert len(report.flows) == 1

    def test_unverified_custom_function_guard_does_not_clear(self):
        """`if is_valid(x)` where `is_valid` is an arbitrary, unverified
        in-scope name -- NOT in the sanitizer catalog. The engine must not
        invent a semantic validator: must still flag."""
        report = _scan_py(
            "import subprocess\n"
            "def run():\n"
            "    host = request.args.get('host')\n"
            "    if is_valid(host):\n"
            "        subprocess.run('ping ' + host, shell=True)\n"
        )
        assert len(report.flows) == 1

    def test_guard_clause_without_early_return_does_not_clear(self):
        """`if not x.isdigit(): log(x)` (no return/raise -- falls through
        regardless) -- the body is NOT terminal, so the ordinary sound union
        applies and the post-if code must still see `host` as tainted."""
        report = _scan_py(
            "import subprocess\n"
            "def run():\n"
            "    host = request.args.get('host')\n"
            "    if not host.isdigit():\n"
            "        print('suspicious')\n"
            "    subprocess.run('ping ' + host, shell=True)\n"
        )
        assert len(report.flows) == 1


class TestPythonBranchJoin:
    def test_branch_join_unions_not_intersects(self):
        """One arm assigns the tainted value, the other a constant -- the
        join must UNION (taint on ANY reaching path survives)."""
        report = _scan_py(
            "import subprocess\n"
            "def run():\n"
            "    host = request.args.get('host')\n"
            "    flag = request.args.get('flag')\n"
            "    if flag:\n"
            "        cmd = host\n"
            "    else:\n"
            "        cmd = 'localhost'\n"
            "    subprocess.run('ping ' + cmd, shell=True)\n"
        )
        assert len(report.flows) == 1

    def test_both_arms_tainted_flags(self):
        report = _scan_py(
            "import subprocess\n"
            "def run():\n"
            "    host = request.args.get('host')\n"
            "    if request.args.get('flag'):\n"
            "        cmd = host\n"
            "    else:\n"
            "        cmd = host + ';ls'\n"
            "    subprocess.run('ping ' + cmd, shell=True)\n"
        )
        assert len(report.flows) == 1


class TestPythonCallSiteContextSensitivity:
    def test_clean_and_tainted_call_sites_not_conflated(self):
        """The SAME helper is called once with a literal (clean) and once
        with tainted user input -- exactly one flow, from the tainted call
        site. A clean call site must not inherit taint from a different
        sinking call site, and vice versa a sinking site must still flag."""
        report = _scan_py(
            "import subprocess\n"
            "def run_cmd(host):\n"
            "    subprocess.run('ping ' + host, shell=True)\n"
            "def clean_call():\n"
            "    run_cmd('localhost')\n"
            "def tainted_call():\n"
            "    host = request.args.get('host')\n"
            "    run_cmd(host)\n"
        )
        assert len(report.flows) == 1
        assert report.flows[0].source_location.function_name == "tainted_call"

    def test_only_clean_call_site_yields_no_flow(self):
        """Same helper, but only the clean call site is present in this
        file -- must be silent (isolates that the clean-site suppression
        above isn't an artifact of the sinking site's presence)."""
        report = _scan_py(
            "import subprocess\n"
            "def run_cmd(host):\n"
            "    subprocess.run('ping ' + host, shell=True)\n"
            "def clean_call():\n"
            "    run_cmd('localhost')\n"
        )
        assert report.flows == []

    def test_two_hop_call_site_sensitivity(self):
        """A 2-hop call chain (helper -> mid -> caller) must still respect
        which OUTER call site actually carried tainted input."""
        report = _scan_py(
            "import subprocess\n"
            "def helper(x):\n"
            "    subprocess.run('ping ' + x, shell=True)\n"
            "def mid(y):\n"
            "    helper(y)\n"
            "def clean_call():\n"
            "    mid('localhost')\n"
            "def tainted_call():\n"
            "    user_input = request.args.get('host')\n"
            "    mid(user_input)\n"
        )
        assert len(report.flows) == 1
        assert report.flows[0].source_location.function_name == "tainted_call"


# ------------------------------------------------------------------- JS (CST)


class TestJsGuardClausePathSensitivity:
    def _require_js(self):
        if not is_engine_enabled("javascript"):
            import pytest
            pytest.skip("tree-sitter-javascript grammar not installed")

    def test_real_validator_guard_clause_clears(self):
        self._require_js()
        result = _scan_js(
            "const { exec } = require('child_process');\n"
            "function run(req) {\n"
            "    const host = req.body.host;\n"
            "    if (!Number.isInteger(host)) {\n"
            "        return;\n"
            "    }\n"
            "    exec('ping ' + host);\n"
            "}\n"
        )
        assert result.taint_flows == []

    def test_unguarded_path_still_flags(self):
        self._require_js()
        result = _scan_js(
            "const { exec } = require('child_process');\n"
            "function run(req) {\n"
            "    const host = req.body.host;\n"
            "    exec('ping ' + host);\n"
            "}\n"
        )
        assert len(result.taint_flows) == 1

    def test_non_validator_guard_does_not_clear(self):
        self._require_js()
        result = _scan_js(
            "const { exec } = require('child_process');\n"
            "function run(req) {\n"
            "    const host = req.body.host;\n"
            "    if (host !== null) {\n"
            "        exec('ping ' + host);\n"
            "    }\n"
            "}\n"
        )
        assert len(result.taint_flows) == 1

    def test_branch_join_unions(self):
        self._require_js()
        result = _scan_js(
            "const { exec } = require('child_process');\n"
            "function run(req) {\n"
            "    const host = req.body.host;\n"
            "    let cmd;\n"
            "    if (req.query.flag) {\n"
            "        cmd = host;\n"
            "    } else {\n"
            "        cmd = 'localhost';\n"
            "    }\n"
            "    exec('ping ' + cmd);\n"
            "}\n"
        )
        assert len(result.taint_flows) == 1

    def test_call_site_sensitivity_not_conflated(self):
        self._require_js()
        result = _scan_js(
            "function lookup(id) {\n"
            "    db.query('SELECT * FROM users WHERE id=' + id);\n"
            "}\n"
            "function cleanCall() {\n"
            "    lookup('admin');\n"
            "}\n"
            "function taintedCall(req) {\n"
            "    const id = req.query.id;\n"
            "    lookup(id);\n"
            "}\n"
        )
        assert len(result.taint_flows) == 1
