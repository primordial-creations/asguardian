"""Tests for multi-language coverage extraction (JS/TS, Go) via the CIR and
tree-sitter, and honest language_status reporting for unsupported / grammar-
absent languages.

Covers ``Asgard/Bragi/Coverage/utilities/multilang_extractor.py`` and
``Asgard/Bragi/Coverage/services/_multilang_gap_helpers.py`` as exercised
through the public ``CoverageAnalyzer.analyze()`` entry point, per the
Bragi/Coverage uplift slice (real per-language coverage instead of silent
N/A for non-Python code).
"""
import pytest

from Asgard.Heimdall.treesitter._language_loader import is_available
from Asgard.Bragi.Coverage.services.coverage_analyzer import CoverageAnalyzer
from Asgard.Bragi.Coverage.services._multilang_gap_helpers import (
    collect_multilang_methods,
)
from Asgard.Bragi.Coverage.models.coverage_models import CoverageConfig


pytestmark = pytest.mark.skipif(
    not is_available("javascript") or not is_available("go"),
    reason="tree-sitter javascript/go grammars unavailable",
)


class TestJavaScriptCoverage:
    """JS project: two top-level functions + a two-method class, only one
    function is exercised by a *.test.js file that calls it by name."""

    def _write_fixture(self, tmp_path):
        (tmp_path / "app.js").write_text(
            "function add(a, b) {\n"
            "  return a + b;\n"
            "}\n"
            "\n"
            "function subtract(a, b) {\n"
            "  return a - b;\n"
            "}\n"
            "\n"
            "class Calculator {\n"
            "  multiply(a, b) {\n"
            "    return a * b;\n"
            "  }\n"
            "  divide(a, b) {\n"
            "    return a / b;\n"
            "  }\n"
            "}\n"
        )
        (tmp_path / "app.test.js").write_text(
            "const { add } = require('./app');\n"
            "\n"
            "describe('add', () => {\n"
            "  it('adds numbers', () => {\n"
            "    expect(add(1, 2)).toBe(3);\n"
            "  });\n"
            "});\n"
        )
        return tmp_path

    def test_real_nonzero_method_coverage_percent(self, tmp_path):
        self._write_fixture(tmp_path)
        report = CoverageAnalyzer().analyze(tmp_path)

        # 1 of 4 production methods/functions (add/subtract/multiply/divide)
        # is called from the test file: coverage must be a real, non-trivial
        # fraction — neither 0 nor a fabricated 100.
        assert report.metrics.total_methods == 4
        assert report.metrics.covered_methods == 1
        assert report.metrics.method_coverage_percent == pytest.approx(25.0)

    def test_gap_list_names_uncovered_methods(self, tmp_path):
        self._write_fixture(tmp_path)
        report = CoverageAnalyzer().analyze(tmp_path)

        gap_names = {g.method.name for g in report.gaps}
        assert gap_names == {"subtract", "multiply", "divide"}
        assert all(g.method.language == "javascript" for g in report.gaps)

    def test_class_coverage_reflects_partial_coverage(self, tmp_path):
        self._write_fixture(tmp_path)
        report = CoverageAnalyzer().analyze(tmp_path)

        calc = next(c for c in report.class_coverage if c.class_name == "Calculator")
        assert calc.total_methods == 2
        assert calc.covered_methods == 0
        assert set(calc.uncovered_methods) == {"multiply", "divide"}

    def test_language_status_ok(self, tmp_path):
        self._write_fixture(tmp_path)
        report = CoverageAnalyzer().analyze(tmp_path)
        assert report.language_status.get("javascript") == "ok"


class TestGoCoverage:
    """Go project: two receiver methods + one free function; only one
    receiver method is exercised by a _test.go file."""

    def _write_fixture(self, tmp_path):
        (tmp_path / "calc.go").write_text(
            "package calc\n"
            "\n"
            "type Calculator struct{}\n"
            "\n"
            "func (c *Calculator) Add(a, b int) int {\n"
            "\treturn a + b\n"
            "}\n"
            "\n"
            "func (c *Calculator) Sub(a, b int) int {\n"
            "\treturn a - b\n"
            "}\n"
            "\n"
            "func Multiply(a, b int) int {\n"
            "\treturn a * b\n"
            "}\n"
        )
        (tmp_path / "calc_test.go").write_text(
            "package calc\n"
            "\n"
            "import \"testing\"\n"
            "\n"
            "func TestAdd(t *testing.T) {\n"
            "\tc := &Calculator{}\n"
            "\tif c.Add(1, 2) != 3 {\n"
            "\t\tt.Fail()\n"
            "\t}\n"
            "}\n"
        )
        return tmp_path

    def test_real_nonzero_method_coverage_percent(self, tmp_path):
        self._write_fixture(tmp_path)
        report = CoverageAnalyzer().analyze(tmp_path)

        assert report.metrics.total_methods == 3
        assert report.metrics.covered_methods == 1
        assert report.metrics.method_coverage_percent == pytest.approx(33.333, rel=1e-3)

    def test_gap_list_names_uncovered_methods(self, tmp_path):
        self._write_fixture(tmp_path)
        report = CoverageAnalyzer().analyze(tmp_path)

        gap_names = {g.method.name for g in report.gaps}
        assert gap_names == {"Sub", "Multiply"}
        assert all(g.method.language == "go" for g in report.gaps)

    def test_class_coverage_reflects_partial_coverage(self, tmp_path):
        self._write_fixture(tmp_path)
        report = CoverageAnalyzer().analyze(tmp_path)

        calc = next(c for c in report.class_coverage if c.class_name == "Calculator")
        assert calc.total_methods == 2
        assert calc.covered_methods == 1
        assert calc.uncovered_methods == ["Sub"]

    def test_language_status_ok(self, tmp_path):
        self._write_fixture(tmp_path)
        report = CoverageAnalyzer().analyze(tmp_path)
        assert report.language_status.get("go") == "ok"


class TestUnsupportedLanguageHonestNA:
    """Rust is CIR-supported for OOP but has no coverage test-file
    convention wired up yet: it must be reported as honestly unsupported,
    never a fabricated coverage number."""

    def test_rust_reports_unsupported_status_no_fabricated_number(self, tmp_path):
        (tmp_path / "lib.rs").write_text(
            "fn add(a: i32, b: i32) -> i32 { a + b }\n"
        )
        report = CoverageAnalyzer().analyze(tmp_path)

        assert report.language_status.get("rust", "").startswith("unsupported")
        # No Rust methods were folded into the (Python-only-by-default)
        # method count — nothing fabricated for a language we don't measure.
        assert report.metrics.total_methods == 0
        assert report.gaps == []


class TestGrammarAbsentHonestInsufficientData:
    """Simulate an unavailable tree-sitter grammar and confirm the status
    reported is "insufficient_data", not a silently-dropped or fabricated
    result."""

    def test_missing_grammar_reports_insufficient_data(self, tmp_path, monkeypatch):
        (tmp_path / "app.js").write_text("function add(a, b) { return a + b; }\n")

        import Asgard.Bragi.Coverage.services._multilang_gap_helpers as helpers_mod
        monkeypatch.setattr(helpers_mod, "is_available", lambda lang: False)

        production, tests, status = collect_multilang_methods(tmp_path, CoverageConfig())

        assert status.get("javascript") == "insufficient_data: tree-sitter grammar unavailable"
        assert production == []
        assert tests == []
