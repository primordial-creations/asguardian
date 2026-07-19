"""Tests for the CIR->OOPAnalyzer bridge (Asgard/Bragi/OOP/services/_cir_oop_bridge.py).

Confirms ``OOPAnalyzer.analyze()`` reports real LCOM4/CBO/RFC for non-Python
languages via the tree-sitter CIR (cir_metrics.py), tagged with
``metrics_source="cir"`` so callers can tell DIT/NOC/WMC are honestly
unmeasured (0) rather than real ast-derived values, distinguishing them from
Python's ``metrics_source="ast"`` entries.
"""
import pytest

from Asgard.Heimdall.treesitter._language_loader import is_available
from Asgard.Bragi.OOP.services.oop_analyzer import OOPAnalyzer


pytestmark = pytest.mark.skipif(
    not is_available("javascript") or not is_available("go"),
    reason="tree-sitter javascript/go grammars unavailable",
)


class TestJavaScriptCIRMetrics:
    def _write_fixture(self, tmp_path):
        (tmp_path / "calc.js").write_text(
            "class Calculator {\n"
            "  multiply(a, b) {\n"
            "    this.x = a;\n"
            "    return a * b;\n"
            "  }\n"
            "  divide(a, b) {\n"
            "    return this.x / b;\n"
            "  }\n"
            "}\n"
        )
        return tmp_path

    def test_real_cir_metrics_reported(self, tmp_path):
        self._write_fixture(tmp_path)
        report = OOPAnalyzer().analyze(tmp_path)

        calc = next(c for c in report.class_metrics if c.class_name == "Calculator")
        assert calc.language == "javascript"
        assert calc.metrics_source == "cir"
        # Both methods touch the shared field `x`: cohesive, one component.
        assert calc.lcom4 == 1.0
        assert calc.cbo == 0
        assert calc.rfc == 2
        assert calc.method_count == 2

    def test_unmeasured_metrics_stay_at_honest_zero(self, tmp_path):
        self._write_fixture(tmp_path)
        report = OOPAnalyzer().analyze(tmp_path)

        calc = next(c for c in report.class_metrics if c.class_name == "Calculator")
        # DIT/NOC/WMC are not computed by the CIR path yet; they must stay
        # at the honest "not measured" 0 rather than a fabricated value —
        # metrics_source="cir" is the label a consumer checks before
        # trusting these three fields.
        assert calc.dit == 0
        assert calc.noc == 0
        assert calc.wmc == 0
        assert calc.metrics_source == "cir"


class TestGoCIRMetrics:
    def _write_fixture(self, tmp_path):
        (tmp_path / "calc.go").write_text(
            "package calc\n"
            "\n"
            "type Calculator struct {\n"
            "\tx int\n"
            "}\n"
            "\n"
            "func (c *Calculator) Multiply(a, b int) int {\n"
            "\tc.x = a\n"
            "\treturn a * b\n"
            "}\n"
            "\n"
            "func (c *Calculator) Divide(a, b int) int {\n"
            "\treturn c.x / b\n"
            "}\n"
        )
        return tmp_path

    def test_real_cir_metrics_reported(self, tmp_path):
        self._write_fixture(tmp_path)
        report = OOPAnalyzer().analyze(tmp_path)

        calc = next(c for c in report.class_metrics if c.class_name == "Calculator")
        assert calc.language == "go"
        assert calc.metrics_source == "cir"
        assert calc.lcom4 == 1.0
        assert calc.method_count == 2

    def test_unmeasured_metrics_stay_at_honest_zero(self, tmp_path):
        self._write_fixture(tmp_path)
        report = OOPAnalyzer().analyze(tmp_path)

        calc = next(c for c in report.class_metrics if c.class_name == "Calculator")
        assert calc.dit == 0
        assert calc.noc == 0
        assert calc.wmc == 0


class TestPythonUnaffected:
    """Python must keep using the dedicated ast-based path — metrics_source
    stays "ast", not "cir" — since it's the reference-language
    implementation with real DIT/NOC/WMC support the CIR path lacks."""

    def test_python_class_uses_ast_source(self, tmp_path):
        (tmp_path / "calc.py").write_text(
            "class Calculator:\n"
            "    def multiply(self, a, b):\n"
            "        self.x = a\n"
            "        return a * b\n"
            "    def divide(self, a, b):\n"
            "        return self.x / b\n"
        )
        report = OOPAnalyzer().analyze(tmp_path)

        calc = next(c for c in report.class_metrics if c.class_name == "Calculator")
        assert calc.metrics_source == "ast"
        assert calc.language == "python"
