"""Tests for automatic context stamping in ParallelScanner (Plan 04 Phase A)."""

from dataclasses import dataclass
from pathlib import Path

from Asgard.Bragi.Quality.services.parallel_scanner import (
    ParallelConfig,
    ParallelScanner,
    stamp_context,
)


@dataclass
class _Result:
    file_path: str
    context: str = "production"


class TestStampContext:
    def test_stamps_test_context_for_test_path(self) -> None:
        result = stamp_context("tests/test_foo.py", _Result(file_path="tests/test_foo.py"))
        assert result.context == "test"

    def test_leaves_production_default_for_normal_path(self) -> None:
        result = stamp_context("src/foo.py", _Result(file_path="src/foo.py"))
        assert result.context == "production"

    def test_none_result_passes_through(self) -> None:
        assert stamp_context("src/foo.py", None) is None

    def test_result_without_context_attr_passes_through(self) -> None:
        assert stamp_context("src/foo.py", 42) == 42


class TestParallelScannerStampsContext:
    def test_sequential_scan_stamps_context(self, tmp_path: Path) -> None:
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        f = test_dir / "test_thing.py"
        f.write_text("def test_x(): pass\n")

        def analyze(file_path: Path, config: dict) -> _Result:
            return _Result(file_path=str(file_path))

        scanner: ParallelScanner = ParallelScanner(analyze, ParallelConfig(enabled=False))
        chunked = scanner.scan([f])
        assert len(chunked.results) == 1
        assert chunked.results[0].context == "test"
