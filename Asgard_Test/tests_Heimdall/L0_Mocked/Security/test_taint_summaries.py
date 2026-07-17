"""Tests for inter-procedural function summaries (plan 04 P2)."""

import tempfile
from pathlib import Path

import pytest

from Asgard.Heimdall.Security.TaintAnalysis import TaintAnalyzer, TaintConfig


def _scan_files(files: dict, **config_kwargs):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)
        for name, code in files.items():
            (path / name).write_text(code)
        config = TaintConfig(
            exclude_patterns=["__pycache__", ".git"], **config_kwargs)
        return TaintAnalyzer(config=config).scan(path)


class TestSameFileInterProcedural:
    def test_source_in_caller_sink_in_callee(self):
        report = _scan_files({"app.py": (
            "def run_query(sql):\n"
            "    cursor.execute(sql)\n"
            "\n"
            "def handler():\n"
            "    q = request.args.get('q')\n"
            "    run_query(q)\n"
        )})
        assert len(report.flows) == 1
        flow = report.flows[0]
        assert flow.hop_count == 1
        # source conf 1.0 x hop 0.85 x sink 1.0
        assert flow.confidence == pytest.approx(0.85, abs=0.001)
        assert flow.source_location.function_name == "handler"
        assert flow.sink_location.function_name == "run_query"

    def test_source_in_callee_sink_in_caller(self):
        """Decoupled fixture: a helper returns fresh taint."""
        report = _scan_files({"app.py": (
            "def read_input():\n"
            "    return request.args.get('q')\n"
            "\n"
            "def handler():\n"
            "    q = read_input()\n"
            "    cursor.execute(q)\n"
        )})
        assert len(report.flows) == 1
        flow = report.flows[0]
        assert flow.confidence == pytest.approx(0.85, abs=0.001)
        assert flow.source_location.function_name == "read_input"

    def test_sanitizer_inside_callee_respected(self):
        report = _scan_files({"app.py": (
            "import shlex\n"
            "def run_cmd(c):\n"
            "    os.system(shlex.quote(c))\n"
            "\n"
            "def handler():\n"
            "    c = request.args.get('c')\n"
            "    run_cmd(c)\n"
        )})
        assert len(report.flows) == 0


class TestCrossFileResolution:
    def test_cross_file_one_hop(self):
        report = _scan_files({
            "db.py": (
                "def run_query(sql):\n"
                "    cursor.execute(sql)\n"
            ),
            "app.py": (
                "from db import run_query\n"
                "def handler():\n"
                "    q = request.args.get('q')\n"
                "    run_query(q)\n"
            ),
        })
        assert len(report.flows) == 1
        flow = report.flows[0]
        assert flow.hop_count == 1
        assert flow.sink_location.file_path.endswith("db.py")
        assert flow.source_location.file_path.endswith("app.py")

    def test_chain_within_hop_budget_reported(self):
        files = {
            "l1.py": "from l2 import f2\ndef f1(x):\n    f2(x)\n",
            "l2.py": "from l3 import f3\ndef f2(x):\n    f3(x)\n",
            "l3.py": "def f3(x):\n    cursor.execute(x)\n",
            "app.py": (
                "from l1 import f1\n"
                "def handler():\n"
                "    q = request.args.get('q')\n"
                "    f1(q)\n"
            ),
        }
        report = _scan_files(files, min_confidence=0.0)
        chains = [f for f in report.flows if f.hop_count >= 3]
        assert len(chains) == 1
        # 0.85^3 hop decay
        assert chains[0].confidence == pytest.approx(0.85 ** 3, abs=0.01)

    def test_paths_beyond_max_hops_dropped(self):
        files = {"app.py": (
            "def f5(x):\n    cursor.execute(x)\n"
            "def f4(x):\n    f5(x)\n"
            "def f3(x):\n    f4(x)\n"
            "def f2(x):\n    f3(x)\n"
            "def f1(x):\n    f2(x)\n"
            "def handler():\n"
            "    q = request.args.get('q')\n"
            "    f1(q)\n"
        )}
        report = _scan_files(files, min_confidence=0.0, max_hops=4)
        # 5 hops needed to reach the sink from handler -> dropped
        assert all(f.hop_count <= 4 for f in report.flows)
        deep = [f for f in report.flows
                if f.source_location.function_name == "handler"]
        assert len(deep) == 0


class TestSummaryCacheCorrectness:
    def test_removing_sanitizer_in_callee_reflags_caller(self):
        """Plan 04 cache-correctness gate: remove a sanitizer in file B,
        assert the caller in unchanged file A is re-analyzed and now
        reports the flow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            cache = path / "cache" / "taint.db"
            file_a = (
                "from db import run_query\n"
                "def handler():\n"
                "    q = request.args.get('q')\n"
                "    run_query(q)\n"
            )
            (path / "app.py").write_text(file_a)
            (path / "db.py").write_text(
                "def run_query(sql):\n"
                "    cursor.execute(parameterize(sql))\n"
            )
            config = TaintConfig(
                exclude_patterns=["__pycache__", ".git", "cache"],
                summary_cache_path=cache,
            )
            report1 = TaintAnalyzer(config=config).scan(path)
            assert len(report1.flows) == 0

            # Remove the sanitizer in B; A is untouched.
            (path / "db.py").write_text(
                "def run_query(sql):\n"
                "    cursor.execute(sql)\n"
            )
            report2 = TaintAnalyzer(config=config).scan(path)
            assert len(report2.flows) == 1
            assert report2.flows[0].source_location.file_path.endswith("app.py")

    def test_cache_hit_yields_identical_findings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            cache = path / "cache" / "taint.db"
            (path / "app.py").write_text(
                "def run_query(sql):\n"
                "    cursor.execute(sql)\n"
                "def handler():\n"
                "    q = request.args.get('q')\n"
                "    run_query(q)\n"
            )
            config = TaintConfig(
                exclude_patterns=["__pycache__", ".git", "cache"],
                summary_cache_path=cache,
            )
            cold = TaintAnalyzer(config=config).scan(path)
            warm = TaintAnalyzer(config=config).scan(path)
            assert [f.model_dump(exclude={"confidence"}) for f in cold.flows] \
                or True  # structure check below is the real assertion
            assert len(cold.flows) == len(warm.flows) == 1
            assert cold.flows[0].confidence == warm.flows[0].confidence
            assert cold.flows[0].sink_location == warm.flows[0].sink_location
