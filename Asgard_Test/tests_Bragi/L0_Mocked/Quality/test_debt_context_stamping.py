"""Tests for Plan 04 Phase A context stamping in TechnicalDebtAnalyzer."""

from pathlib import Path

from Asgard.Bragi.Quality.services.technical_debt_analyzer import TechnicalDebtAnalyzer


class TestDebtContextStamping:
    def test_items_carry_context(self, tmp_path: Path) -> None:
        (tmp_path / "prod.py").write_text(
            "def f():\n    pass\n"
        )
        analyzer = TechnicalDebtAnalyzer()
        report = analyzer.analyze(tmp_path)
        for item in report.debt_items:
            assert item.context in (
                "production", "test", "generated", "suspected_generated", "script",
            )

    def test_test_files_exempt_from_documentation_debt(self, tmp_path: Path) -> None:
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_thing.py").write_text(
            "def test_a():\n    assert True\n\n"
            "def test_b():\n    assert True\n"
        )
        analyzer = TechnicalDebtAnalyzer()
        report = analyzer.analyze(tmp_path)
        doc_items_in_tests = [
            item for item in report.debt_items
            if item.debt_type == "documentation" and "test_thing.py" in item.file_path
        ]
        assert doc_items_in_tests == []
