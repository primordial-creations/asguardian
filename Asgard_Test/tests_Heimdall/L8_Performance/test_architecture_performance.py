"""
L8 Performance Tests — Architecture Analyzer Benchmarks.

Benchmarks SOLIDValidator.validate() and HexagonalAnalyzer.analyze() against
a synthetic directory of 10 Python files (~100 lines each).
"""

from pathlib import Path
from textwrap import dedent

import pytest

from Asgard.Bragi.Architecture.services.solid_validator import SOLIDValidator
from Asgard.Bragi.Architecture.services.hexagonal_analyzer import HexagonalAnalyzer
from Asgard.Bragi.Architecture.models.architecture_models import ArchitectureConfig

# ---------------------------------------------------------------------------
# Fixture factory
# ---------------------------------------------------------------------------
_FILE_TEMPLATE = dedent("""\
    class Service{n}:
        def fetch(self) -> None:
            pass

        def process(self) -> None:
            pass

        def validate(self) -> None:
            pass

        def save(self) -> None:
            pass

        def delete(self) -> None:
            pass

        def list_items(self) -> None:
            pass

        def get_by_id(self, item_id: int) -> None:
            pass

        def count(self) -> int:
            return 0

        def exists(self, item_id: int) -> bool:
            return False

        def update(self) -> None:
            pass
    """)


def _make_synthetic_project(tmp_path: Path) -> Path:
    """Create a project directory with 10 Python files of ~100 lines each."""
    for i in range(10):
        content = (_FILE_TEMPLATE.format(n=i) + "\n") * 4  # ~100 lines per file
        (tmp_path / f"module_{i}.py").write_text(content)
    return tmp_path


# ===========================================================================
# SOLID Validator
# ===========================================================================
class TestSOLIDValidatorPerformance:
    def test_validate_benchmark(self, benchmark, tmp_path: Path) -> None:
        project = _make_synthetic_project(tmp_path)
        validator = SOLIDValidator()
        result = benchmark(validator.validate, project)
        assert result is not None


# ===========================================================================
# Hexagonal Analyzer
# ===========================================================================
class TestHexagonalAnalyzerPerformance:
    def test_analyze_benchmark(self, benchmark, tmp_path: Path) -> None:
        project = _make_synthetic_project(tmp_path)
        analyzer = HexagonalAnalyzer()
        result = benchmark(analyzer.analyze, project)
        assert result is not None
