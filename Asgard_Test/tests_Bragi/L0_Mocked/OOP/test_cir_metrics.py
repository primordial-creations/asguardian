"""Tests for multi-language cohesion/coupling via the CIR.

Covers ``Asgard/Bragi/OOP/services/cir_metrics.py`` and the true LCOM4
helper in ``Asgard/Bragi/OOP/services/_cohesion_helpers.py``, per
``_Docs/Planning/Heimdall/05_Cohesion_Coupling.md``.
"""
import pytest

from Asgard.Heimdall.treesitter._language_loader import is_available
from Asgard.Bragi.OOP.services.cir_metrics import analyze_file
from Asgard.Bragi.OOP.services._cohesion_helpers import calculate_true_lcom4

pytestmark = pytest.mark.skipif(not is_available("python"), reason="tree-sitter python grammar unavailable")


class TestCIRMetricsPython:
    def test_cohesive_class_lcom4_one(self):
        src = (
            "class Cohesive:\n"
            "    def a(self):\n        self.x = 1\n"
            "    def b(self):\n        return self.x\n"
        )
        metrics = analyze_file("c.py", src, "python")
        assert len(metrics) == 1
        assert metrics[0].lcom4 == 1
        assert not metrics[0].is_low_cohesion

    def test_two_island_class_lcom4_two(self):
        src = (
            "class TwoIslands:\n"
            "    def a(self):\n        self.x = 1\n"
            "    def b(self):\n        return self.x\n"
            "    def c(self):\n        self.y = 1\n"
            "    def d(self):\n        return self.y\n"
        )
        metrics = analyze_file("t.py", src, "python")
        assert metrics[0].lcom4 == 2
        assert metrics[0].is_low_cohesion

    def test_coupling_detects_instantiations(self):
        src = (
            "class Orchestrator:\n"
            "    def run(self):\n"
            "        self.svc = OrderService()\n"
            "        self.repo = UserRepository()\n"
        )
        metrics = analyze_file("o.py", src, "python")
        assert metrics[0].cbo >= 2
        assert "OrderService" in metrics[0].coupled_types
        assert "UserRepository" in metrics[0].coupled_types

    def test_unsupported_language_returns_empty(self):
        assert analyze_file("f.kt", "class Foo", "kotlin") == []

    def test_explain_is_actionable(self):
        src = "class Solo:\n    def a(self):\n        self.x = 1\n"
        metrics = analyze_file("s.py", src, "python")
        text = metrics[0].explain()
        assert "LCOM4" in text and "CBO" in text


class TestTrueLCOM4Helper:
    def test_shared_field_connects_methods(self):
        usage = {"a": {"x"}, "b": {"x"}}
        calls = {"a": set(), "b": set()}
        assert calculate_true_lcom4(usage, calls) == 1

    def test_disjoint_fields_split_class(self):
        usage = {"a": {"x"}, "b": {"y"}}
        calls = {"a": set(), "b": set()}
        assert calculate_true_lcom4(usage, calls) == 2

    def test_method_call_edge_merges_components(self):
        # LCOM3 would treat 'helper' as its own island (no field overlap);
        # true LCOM4 must merge it via the call edge.
        usage = {"a": {"x"}, "helper": set()}
        calls = {"a": {"helper"}, "helper": set()}
        assert calculate_true_lcom4(usage, calls) == 1

    def test_init_excluded(self):
        usage = {"__init__": {"x", "y"}, "a": {"x"}, "b": {"y"}}
        calls = {"__init__": set(), "a": set(), "b": set()}
        assert calculate_true_lcom4(usage, calls) == 2
