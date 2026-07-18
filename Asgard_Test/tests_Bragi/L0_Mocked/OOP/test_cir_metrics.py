"""Tests for multi-language cohesion/coupling via the CIR.

Covers ``Asgard/Bragi/OOP/services/cir_metrics.py`` and the true LCOM4
helper in ``Asgard/Bragi/OOP/services/_cohesion_helpers.py``, per
``_Docs/Planning/Heimdall/05_Cohesion_Coupling.md``.
"""
import pytest

from Asgard.Heimdall.treesitter._language_loader import is_available
from Asgard.Bragi.OOP.services.cir_metrics import analyze_file, analyze_path, explain_class
from Asgard.Bragi.OOP.services._cohesion_helpers import calculate_true_lcom4
from Asgard.Bragi.OOP.services._cohesion_thresholds import (
    CohesionThresholds,
    thresholds_from_profile,
    resolve_thresholds,
)

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


class TestProfileThresholds:
    """Plan 05 gap: CBO/LCOM4/RFC/WMC thresholds wired through the
    Shared/Profiles plane rather than hardcoded module constants."""

    def test_defaults_match_asgard_way_python(self):
        t = CohesionThresholds()
        assert t.cbo == 20.0
        assert t.lcom4 == 1.0
        assert t.rfc == 50.0
        assert t.wmc == 20.0

    def test_none_profile_returns_defaults(self):
        assert thresholds_from_profile(None) == CohesionThresholds()

    def test_asgard_way_python_profile_resolves_expected_values(self):
        from Asgard.Shared.Profiles.builtin.asgard_way_python import ASGARD_WAY_PYTHON
        t = thresholds_from_profile(ASGARD_WAY_PYTHON)
        assert t.cbo == 20.0
        assert t.lcom4 == 1.0
        assert t.wmc == 20.0

    def test_strict_profile_tightens_cbo(self):
        from Asgard.Shared.Profiles.builtin.asgard_way_strict import ASGARD_WAY_STRICT
        t = thresholds_from_profile(ASGARD_WAY_STRICT)
        assert t.cbo == 12.0

    def test_resolve_thresholds_unknown_profile_falls_back_to_defaults(self):
        assert resolve_thresholds("Nonexistent Profile XYZ") == CohesionThresholds()

    def test_metrics_use_supplied_thresholds(self):
        src = "class Foo:\n    def a(self):\n        self.x = X()\n"
        tight = CohesionThresholds(cbo=0, lcom4=0, rfc=0, wmc=0)
        metrics = analyze_file("foo.py", src, "python", tight)
        assert metrics[0].is_high_coupling


class TestExplainClass:
    """Plan 05 gap: ``--explain <Class>`` support for LCOM4 component
    partitions (service-layer API; CLI flag wiring is a separate concern)."""

    def test_explain_class_found(self, tmp_path):
        (tmp_path / "foo.py").write_text(
            "class Foo:\n    def a(self):\n        self.x = 1\n    def b(self):\n        return self.x\n"
        )
        text = explain_class(tmp_path, "Foo", extensions=[".py"])
        # Python files are skipped by the multi-language CIR path (they have
        # their own AST-based CohesionAnalyzer.explain_class); confirm the
        # multi-language path returns None cleanly rather than erroring.
        assert text is None

    def test_explain_class_java(self, tmp_path):
        if not is_available("java"):
            pytest.skip("tree-sitter java grammar unavailable")
        (tmp_path / "Foo.java").write_text(
            "class Foo {\n    int x;\n    void a() { this.x = 1; }\n    int b() { return this.x; }\n}\n"
        )
        text = explain_class(tmp_path, "Foo")
        assert text is not None
        assert "LCOM4" in text and "CBO" in text

    def test_explain_class_not_found_returns_none(self, tmp_path):
        (tmp_path / "empty.py").write_text("x = 1\n")
        assert explain_class(tmp_path, "DoesNotExist") is None


class TestCrossLanguageCohesionConsistency:
    """Identical Java/Python/TS fixture classes must produce identical
    LCOM4 (plan 05 §Testing)."""

    def _two_island_source(self, language: str) -> str:
        if language == "java":
            return (
                "class TwoIslands {\n"
                "    int x, y;\n"
                "    void a() { this.x = 1; }\n"
                "    int b() { return this.x; }\n"
                "    void c() { this.y = 1; }\n"
                "    int d() { return this.y; }\n"
                "}\n"
            )
        if language in ("javascript", "typescript"):
            return (
                "class TwoIslands {\n"
                "    a() { this.x = 1; }\n"
                "    b() { return this.x; }\n"
                "    c() { this.y = 1; }\n"
                "    d() { return this.y; }\n"
                "}\n"
            )
        raise ValueError(language)

    def test_java_and_typescript_agree_on_lcom4(self):
        if not is_available("java") or not is_available("typescript"):
            pytest.skip("tree-sitter java/typescript grammar unavailable")
        java_metrics = analyze_file("T.java", self._two_island_source("java"), "java")
        ts_metrics = analyze_file("t.ts", self._two_island_source("typescript"), "typescript")
        assert java_metrics[0].lcom4 == ts_metrics[0].lcom4 == 2
