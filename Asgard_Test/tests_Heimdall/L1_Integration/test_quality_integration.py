"""
L1 Integration Tests for Heimdall Quality Analysis

Tests full quality analysis on real Python projects.
"""

import json
import pytest
from pathlib import Path

from Asgard.Bragi.Quality import (
    AnalysisConfig,
    FileAnalyzer,
    ComplexityAnalyzer,
    ComplexityConfig,
    DuplicationDetector,
    DuplicationConfig,
    CodeSmellDetector,
    SmellConfig,
    TechnicalDebtAnalyzer,
    DebtConfig,
    MaintainabilityAnalyzer,
    MaintainabilityConfig,
)


class TestQualityIntegration:
    """Integration tests for quality analysis."""

    def test_quality_analyze_simple_project_full(self, simple_project):
        """Test full quality analysis on simple project."""
        # File length analysis
        config = AnalysisConfig(
            scan_path=str(simple_project),
            threshold=300
        )
        analyzer = FileAnalyzer(config)
        result = analyzer.analyze()

        assert result is not None
        assert str(simple_project.resolve()) in str(result.scan_path)
        assert result.total_files_scanned >= 2

    def test_quality_analyze_complexity_simple_project(self, simple_project):
        """Test complexity analysis on simple project."""
        config = ComplexityConfig(
            scan_path=str(simple_project),
            cyclomatic_threshold=10,
            cognitive_threshold=15
        )
        analyzer = ComplexityAnalyzer(config)
        result = analyzer.analyze()

        assert result is not None
        assert str(simple_project.resolve()) in str(result.scan_path)
        assert result.total_files_scanned >= 1
        assert result.total_functions_analyzed >= 2

        # Check that simple functions have low complexity
        for file_analysis in result.file_analyses:
            for func in file_analysis.functions:
                if func.name in ['calculate_sum', 'calculate_product']:
                    assert func.cyclomatic_complexity <= 2

    def test_quality_analyze_complexity_high_complexity(self, high_complexity_project):
        """Test complexity analysis on high complexity project."""
        config = ComplexityConfig(
            scan_path=str(high_complexity_project),
            cyclomatic_threshold=10,
            cognitive_threshold=15
        )
        analyzer = ComplexityAnalyzer(config)
        result = analyzer.analyze()

        assert result is not None
        assert result.total_functions_analyzed >= 1

        # Find the process_data function
        high_complexity_found = False
        for file_analysis in result.file_analyses:
            for func in file_analysis.functions:
                if func.name == 'process_data':
                    high_complexity_found = True
                    assert func.cyclomatic_complexity > 10

        assert high_complexity_found, "High complexity function should be detected"

    def test_quality_analyze_duplication_simple_project(self, simple_project):
        """Test duplication detection on simple project."""
        config = DuplicationConfig(
            scan_path=str(simple_project),
            min_block_size=6,
            similarity_threshold=0.8
        )
        detector = DuplicationDetector(config)
        result = detector.analyze()

        assert result is not None
        assert str(simple_project.resolve()) in str(result.scan_path)
        assert result.total_files_scanned >= 1
        assert isinstance(result.duplication_percentage, float)

    def test_quality_analyze_duplication_complex_project(self, complex_project):
        """Test duplication detection on complex project."""
        config = DuplicationConfig(
            scan_path=str(complex_project),
            min_block_size=4,
            similarity_threshold=0.7
        )
        detector = DuplicationDetector(config)
        result = detector.analyze()

        assert result is not None
        assert result.total_files_scanned >= 1
        assert isinstance(result.clone_families, list)

    def test_quality_analyze_code_smells_simple_project(self, simple_project):
        """Test code smell detection on simple project."""
        config = SmellConfig(scan_path=str(simple_project))
        detector = CodeSmellDetector(config)
        result = detector.analyze(simple_project)

        assert result is not None
        assert isinstance(result.detected_smells, list)
        assert isinstance(result.total_smells, int)

    def test_quality_analyze_code_smells_god_class(self, god_class_project):
        """Test code smell detection on god class project."""
        config = SmellConfig(scan_path=str(god_class_project))
        detector = CodeSmellDetector(config)
        result = detector.analyze(god_class_project)

        assert result is not None
        assert isinstance(result.total_smells, int)
        assert isinstance(result.detected_smells, list)

    def test_quality_analyze_technical_debt_simple_project(self, simple_project):
        """Test technical debt analysis on simple project."""
        config = DebtConfig(scan_path=str(simple_project))
        analyzer = TechnicalDebtAnalyzer(config)
        result = analyzer.analyze(simple_project)

        assert result is not None
        assert isinstance(result.total_debt_hours, float)
        assert result.total_debt_hours >= 0
        assert isinstance(result.debt_items, list)

    def test_quality_analyze_technical_debt_complex_project(self, complex_project):
        """Test technical debt analysis on complex project."""
        config = DebtConfig(scan_path=str(complex_project))
        analyzer = TechnicalDebtAnalyzer(config)
        result = analyzer.analyze(complex_project)

        assert result is not None
        assert isinstance(result.total_debt_hours, float)
        assert result.total_debt_hours >= 0

    def test_quality_analyze_maintainability_simple_project(self, simple_project):
        """Test maintainability analysis on simple project."""
        config = MaintainabilityConfig(scan_path=str(simple_project))
        analyzer = MaintainabilityAnalyzer(config)
        result = analyzer.analyze(simple_project)

        assert result is not None
        assert isinstance(result.overall_index, float)
        assert 0 <= result.overall_index <= 100
        assert isinstance(result.file_results, list)

    def test_quality_analyze_maintainability_complex_project(self, complex_project):
        """Test maintainability analysis on complex project."""
        config = MaintainabilityConfig(scan_path=str(complex_project))
        analyzer = MaintainabilityAnalyzer(config)
        result = analyzer.analyze(complex_project)

        assert result is not None
        assert isinstance(result.overall_index, float)
        assert 0 <= result.overall_index <= 100

    def test_quality_generate_text_report_complexity(self, simple_project):
        """Test generating text report for complexity analysis."""
        config = ComplexityConfig(scan_path=str(simple_project))
        analyzer = ComplexityAnalyzer(config)
        result = analyzer.analyze()
        report = analyzer.generate_report(result, "text")

        assert report is not None
        assert isinstance(report, str)
        assert len(report) > 0
        assert "COMPLEXITY" in report or "complexity" in report.lower()

    def test_quality_generate_json_report_complexity(self, simple_project):
        """Test generating JSON report for complexity analysis."""
        config = ComplexityConfig(scan_path=str(simple_project))
        analyzer = ComplexityAnalyzer(config)
        result = analyzer.analyze()
        report = analyzer.generate_report(result, "json")

        assert report is not None
        assert isinstance(report, str)

        # Validate JSON structure
        data = json.loads(report)
        assert isinstance(data, dict)
        # JSON report should contain at least one expected top-level key
        assert any(k in data for k in ("scan_path", "total_files", "complexity", "scan_info", "summary"))

    def test_quality_generate_text_report_duplication(self, complex_project):
        """Test generating text report for duplication detection."""
        config = DuplicationConfig(scan_path=str(complex_project))
        detector = DuplicationDetector(config)
        result = detector.analyze()
        report = detector.generate_report(result, "text")

        assert report is not None
        assert isinstance(report, str)
        assert len(report) > 0

    def test_quality_generate_json_report_duplication(self, complex_project):
        """Test generating JSON report for duplication detection."""
        config = DuplicationConfig(scan_path=str(complex_project))
        detector = DuplicationDetector(config)
        result = detector.analyze()
        report = detector.generate_report(result, "json")

        assert report is not None
        assert isinstance(report, str)

        # Validate JSON structure
        data = json.loads(report)
        assert isinstance(data, dict)

    def test_quality_file_analyzer_violations(self, tmp_path):
        """Test file analyzer detecting violations."""
        # Create a very long file
        long_file = tmp_path / "long_file.py"
        lines = [f"# Line {i}\n" for i in range(500)]
        long_file.write_text(''.join(lines))

        config = AnalysisConfig(
            scan_path=str(tmp_path),
            threshold=300
        )
        analyzer = FileAnalyzer(config)
        result = analyzer.analyze()

        assert result is not None
        assert len(result.violations) > 0

        # Check that the long file is detected
        violation_found = False
        for violation in result.violations:
            if 'long_file.py' in violation.relative_path:
                violation_found = True
                assert violation.line_count >= 500
                break

        assert violation_found, "Long file should be detected as violation"

    def test_quality_complexity_analyzer_violations(self, high_complexity_project):
        """Test complexity analyzer detecting violations."""
        config = ComplexityConfig(
            scan_path=str(high_complexity_project),
            cyclomatic_threshold=5,
            cognitive_threshold=10
        )
        analyzer = ComplexityAnalyzer(config)
        result = analyzer.analyze()

        assert result is not None
        assert len(result.violations) > 0

        # Check that complex function is in violations
        violation_found = False
        for violation in result.violations:
            if 'process_data' in violation.qualified_name:
                violation_found = True
                break

        assert violation_found, "Complex function should be in violations"

    def test_quality_output_formats_consistency(self, simple_project):
        """Test that analyzers with generate_report support text and json formats."""
        analyzers = [
            ComplexityAnalyzer(ComplexityConfig(scan_path=str(simple_project))),
            DuplicationDetector(DuplicationConfig(scan_path=str(simple_project))),
        ]

        for analyzer in analyzers:
            result = analyzer.analyze()

            # Test text format
            text_report = analyzer.generate_report(result, "text")
            assert isinstance(text_report, str)
            assert len(text_report) > 0

            # Test JSON format
            json_report = analyzer.generate_report(result, "json")
            assert isinstance(json_report, str)
            json_data = json.loads(json_report)
            assert isinstance(json_data, dict)

    def test_quality_empty_directory_handling(self, tmp_path):
        """Test quality analysis on empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        # File length analysis
        config = AnalysisConfig(scan_path=str(empty_dir))
        analyzer = FileAnalyzer(config)
        result = analyzer.analyze()

        assert result is not None
        assert result.total_files_scanned == 0

    def test_quality_nonexistent_path_handling(self):
        """Test quality analysis on nonexistent path."""
        nonexistent = Path("/nonexistent/path/to/nowhere")

        with pytest.raises(FileNotFoundError):
            config = AnalysisConfig(scan_path=str(nonexistent))
            analyzer = FileAnalyzer(config)
            analyzer.analyze()

    def test_quality_single_file_analysis(self, tmp_path):
        """Test quality analysis on single file."""
        single_file = tmp_path / "single.py"
        single_file.write_text('''
def simple_function():
    """A simple function."""
    return 42
''')

        # Complexity analysis on directory containing a single file
        config = ComplexityConfig(scan_path=str(tmp_path))
        analyzer = ComplexityAnalyzer(config)
        result = analyzer.analyze()

        assert result is not None
        assert result.total_files_scanned == 1
        assert result.total_functions_analyzed >= 1
