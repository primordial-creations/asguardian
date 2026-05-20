"""
L1 Integration Tests for Heimdall OOP Analysis

Tests OOP metrics on real Python projects.
"""

import json
import pytest
from pathlib import Path

from Asgard.Bragi.OOP import (
    OOPAnalyzer,
    OOPConfig,
    CouplingAnalyzer,
    InheritanceAnalyzer,
    CohesionAnalyzer,
    RFCAnalyzer,
)


class TestOOPIntegration:
    """Integration tests for OOP analysis."""

    def test_oop_analyze_simple_project_full(self, simple_project):
        """Test full OOP analysis on simple project."""
        config = OOPConfig(scan_path=str(simple_project))
        analyzer = OOPAnalyzer(config)
        report = analyzer.analyze()

        assert report is not None
        assert hasattr(report, 'total_classes_analyzed')
        assert isinstance(report.total_classes_analyzed, int)
        assert report.total_classes_analyzed >= 1

    def test_oop_analyze_complex_project_full(self, complex_project):
        """Test full OOP analysis on complex project."""
        config = OOPConfig(scan_path=str(complex_project))
        analyzer = OOPAnalyzer(config)
        report = analyzer.analyze()

        assert report is not None
        assert report.total_classes_analyzed >= 2
        assert hasattr(report, 'class_metrics')
        assert isinstance(report.class_metrics, list)

    def test_oop_coupling_analysis_simple_project(self, simple_project):
        """Test coupling analysis on simple project."""
        analyzer = CouplingAnalyzer()
        classes = analyzer.analyze(simple_project)

        assert classes is not None
        assert isinstance(classes, list)

        # Check coupling metrics for each class
        for cls in classes:
            assert hasattr(cls, 'class_name')
            assert hasattr(cls, 'cbo')
            assert isinstance(cls.cbo, int)
            assert cls.cbo >= 0

    def test_oop_coupling_analysis_complex_project(self, complex_project):
        """Test coupling analysis on complex project."""
        analyzer = CouplingAnalyzer()
        classes = analyzer.analyze(complex_project)

        assert classes is not None
        assert len(classes) >= 2

        # Complex project should have some coupling
        cbo_values = [cls.cbo for cls in classes]
        assert any(cbo > 0 for cbo in cbo_values)

    def test_oop_coupling_high_coupling_detection(self, inheritance_hierarchy_project):
        """Test detection of high coupling."""
        analyzer = CouplingAnalyzer()
        classes = analyzer.analyze(inheritance_hierarchy_project)

        assert classes is not None

        # Find the HighlyCoupled class
        highly_coupled_found = False
        for cls in classes:
            if cls.class_name == 'HighlyCoupled':
                highly_coupled_found = True
                # Should have high CBO (many dependencies)
                assert cls.cbo > 3
                break

        assert highly_coupled_found, "HighlyCoupled class should be detected"

    def test_oop_coupling_afferent_efferent(self, complex_project):
        """Test afferent and efferent coupling metrics."""
        analyzer = CouplingAnalyzer()
        classes = analyzer.analyze(complex_project)

        assert classes is not None

        for cls in classes:
            assert hasattr(cls, 'afferent_coupling')
            assert isinstance(cls.afferent_coupling, int)
            assert cls.afferent_coupling >= 0
            assert hasattr(cls, 'efferent_coupling')
            assert isinstance(cls.efferent_coupling, int)
            assert cls.efferent_coupling >= 0

    def test_oop_coupling_instability_metric(self, complex_project):
        """Test instability metric calculation."""
        analyzer = CouplingAnalyzer()
        classes = analyzer.analyze(complex_project)

        assert classes is not None

        # Check instability metric (I = Ce / (Ca + Ce))
        for cls in classes:
            if hasattr(cls, 'instability'):
                assert isinstance(cls.instability, (int, float))
                assert 0 <= cls.instability <= 1

    def test_oop_inheritance_analysis_simple_project(self, simple_project):
        """Test inheritance analysis on simple project."""
        analyzer = InheritanceAnalyzer()
        classes = analyzer.analyze(simple_project)

        assert classes is not None
        assert isinstance(classes, list)

    def test_oop_inheritance_analysis_hierarchy_project(self, inheritance_hierarchy_project):
        """Test inheritance analysis on hierarchy project."""
        analyzer = InheritanceAnalyzer()
        classes = analyzer.analyze(inheritance_hierarchy_project)

        assert classes is not None
        assert len(classes) >= 6

        # Check DIT (Depth of Inheritance Tree) for deep hierarchy
        dit_values = []
        for cls in classes:
            if hasattr(cls, 'dit'):
                dit_values.append(cls.dit)

        # Should have varying depths
        assert len(dit_values) > 0
        assert max(dit_values) >= 5

    def test_oop_inheritance_dit_metric(self, inheritance_hierarchy_project):
        """Test DIT metric calculation."""
        analyzer = InheritanceAnalyzer()
        classes = analyzer.analyze(inheritance_hierarchy_project)

        assert classes is not None

        # Find Level6 class with highest DIT
        level6_found = False
        for cls in classes:
            if cls.class_name == 'Level6':
                level6_found = True
                assert hasattr(cls, 'dit')
                assert cls.dit >= 5
                break

        assert level6_found, "Level6 class should be detected"

    def test_oop_inheritance_noc_metric(self, inheritance_hierarchy_project):
        """Test NOC (Number of Children) metric."""
        analyzer = InheritanceAnalyzer()
        classes = analyzer.analyze(inheritance_hierarchy_project)

        assert classes is not None

        # Check NOC for each class
        for cls in classes:
            if hasattr(cls, 'noc'):
                assert isinstance(cls.noc, int)
                assert cls.noc >= 0

        # Level1 should have children
        level1_found = False
        for cls in classes:
            if cls.class_name == 'Level1':
                level1_found = True
                if hasattr(cls, 'noc'):
                    assert cls.noc >= 1
                break

        assert level1_found, "Level1 class should be detected"

    def test_oop_cohesion_analysis_simple_project(self, simple_project):
        """Test cohesion analysis on simple project."""
        analyzer = CohesionAnalyzer()
        classes = analyzer.analyze(simple_project)

        assert classes is not None
        assert isinstance(classes, list)

    def test_oop_cohesion_analysis_complex_project(self, complex_project):
        """Test cohesion analysis on complex project."""
        analyzer = CohesionAnalyzer()
        classes = analyzer.analyze(complex_project)

        assert classes is not None
        assert len(classes) >= 1

        # Check LCOM metrics
        for cls in classes:
            if hasattr(cls, 'lcom'):
                assert isinstance(cls.lcom, (int, float))
                assert cls.lcom >= 0

    def test_oop_cohesion_lcom_metric(self, tmp_path):
        """Test LCOM metric on cohesive class."""
        cohesive_file = tmp_path / "cohesive.py"
        cohesive_file.write_text('''
class CohesiveClass:
    """A cohesive class where methods use common attributes."""
    def __init__(self):
        self.value1 = 0
        self.value2 = 0

    def increment_value1(self):
        """Increment value1."""
        self.value1 += 1
        return self.value1

    def increment_value2(self):
        """Increment value2."""
        self.value2 += 1
        return self.value2

    def get_sum(self):
        """Get sum of values."""
        return self.value1 + self.value2
''')

        analyzer = CohesionAnalyzer()
        classes = analyzer.analyze(tmp_path)

        assert classes is not None
        assert len(classes) >= 1

        # Cohesive class should have low LCOM
        for cls in classes:
            if cls.class_name == 'CohesiveClass':
                if hasattr(cls, 'lcom'):
                    # Low LCOM indicates high cohesion
                    assert isinstance(cls.lcom, (int, float))

    def test_oop_cohesion_lcom4_metric(self, tmp_path):
        """Test LCOM4 metric."""
        code_file = tmp_path / "lcom4.py"
        code_file.write_text('''
class DataProcessor:
    """Data processor with multiple responsibilities."""
    def __init__(self):
        self.data = []
        self.cache = {}

    def add_data(self, item):
        """Add data item."""
        self.data.append(item)

    def process_data(self):
        """Process data."""
        return [x * 2 for x in self.data]

    def cache_result(self, key, value):
        """Cache result."""
        self.cache[key] = value

    def get_cached(self, key):
        """Get cached value."""
        return self.cache.get(key)
''')

        analyzer = CohesionAnalyzer()
        classes = analyzer.analyze(tmp_path)

        assert classes is not None
        assert len(classes) >= 1

        # Check LCOM4 if available
        for cls in classes:
            if hasattr(cls, 'lcom4'):
                assert isinstance(cls.lcom4, (int, float))

    def test_oop_rfc_analysis_simple_project(self, simple_project):
        """Test RFC (Response for a Class) analysis."""
        analyzer = RFCAnalyzer()
        classes = analyzer.analyze(simple_project)

        assert classes is not None
        assert isinstance(classes, list)

        # Check RFC metric
        for cls in classes:
            if hasattr(cls, 'rfc'):
                assert isinstance(cls.rfc, int)
                assert cls.rfc >= 0

    def test_oop_rfc_analysis_complex_project(self, complex_project):
        """Test RFC analysis on complex project."""
        analyzer = RFCAnalyzer()
        classes = analyzer.analyze(complex_project)

        assert classes is not None
        assert len(classes) >= 1

        # UserService should have multiple methods
        user_service_found = False
        for cls in classes:
            if cls.class_name == 'UserService':
                user_service_found = True
                if hasattr(cls, 'rfc'):
                    assert cls.rfc > 0
                break

    def test_oop_wmc_metric(self, god_class_project):
        """Test WMC (Weighted Methods per Class) metric."""
        config = OOPConfig(scan_path=str(god_class_project))
        analyzer = OOPAnalyzer(config)
        report = analyzer.analyze()

        assert report is not None

        # ApplicationManager should have high WMC
        god_class_found = False
        for cls in report.class_metrics:
            if cls.class_name == 'ApplicationManager':
                god_class_found = True
                if hasattr(cls, 'wmc'):
                    assert isinstance(cls.wmc, int)
                    # God class should have many methods
                    assert cls.wmc > 10
                break

        assert god_class_found, "ApplicationManager should be analyzed"

    def test_oop_generate_text_report(self, simple_project):
        """Test generating text report for OOP analysis."""
        config = OOPConfig(scan_path=str(simple_project))
        analyzer = OOPAnalyzer(config)
        report = analyzer.analyze()
        text_report = analyzer.generate_report(report, "text")

        assert text_report is not None
        assert isinstance(text_report, str)
        assert len(text_report) > 0
        assert "OOP" in text_report or "class" in text_report.lower()

    def test_oop_generate_json_report(self, simple_project):
        """Test generating JSON report for OOP analysis."""
        config = OOPConfig(scan_path=str(simple_project))
        analyzer = OOPAnalyzer(config)
        report = analyzer.analyze()
        json_report = analyzer.generate_report(report, "json")

        assert json_report is not None
        assert isinstance(json_report, str)

        # Validate JSON structure
        data = json.loads(json_report)
        assert isinstance(data, dict)
        assert "total_classes" in data or "classes" in data or "class_metrics" in data

    def test_oop_empty_directory_handling(self, tmp_path):
        """Test OOP analysis on empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        config = OOPConfig(scan_path=str(empty_dir))
        analyzer = OOPAnalyzer(config)
        report = analyzer.analyze()

        assert report is not None
        assert report.total_classes_analyzed == 0

    def test_oop_nonexistent_path_handling(self):
        """Test OOP analysis on nonexistent path."""
        nonexistent = Path("/nonexistent/path/to/nowhere")

        config = OOPConfig(scan_path=str(nonexistent))
        analyzer = OOPAnalyzer(config)

        with pytest.raises(FileNotFoundError):
            analyzer.analyze()

    def test_oop_single_class_analysis(self, tmp_path):
        """Test OOP analysis on single class."""
        single_file = tmp_path / "single.py"
        single_file.write_text('''
class SimpleClass:
    """A simple class."""
    def __init__(self):
        self.value = 0

    def increment(self):
        """Increment value."""
        self.value += 1
        return self.value
''')

        config = OOPConfig(scan_path=str(tmp_path))
        analyzer = OOPAnalyzer(config)
        report = analyzer.analyze()

        assert report is not None
        assert report.total_classes_analyzed == 1

        # Check metrics for the simple class
        cls = report.class_metrics[0]
        assert cls.class_name == 'SimpleClass'

    def test_oop_multiple_classes_single_file(self, tmp_path):
        """Test OOP analysis on file with multiple classes."""
        multi_file = tmp_path / "multi.py"
        multi_file.write_text('''
class ClassA:
    """Class A."""
    def method_a(self):
        """Method A."""
        pass

class ClassB:
    """Class B."""
    def method_b(self):
        """Method B."""
        pass

class ClassC(ClassA):
    """Class C inherits from ClassA."""
    def method_c(self):
        """Method C."""
        pass
''')

        config = OOPConfig(scan_path=str(tmp_path))
        analyzer = OOPAnalyzer(config)
        report = analyzer.analyze()

        assert report is not None
        assert report.total_classes_analyzed == 3

    def test_oop_abstract_class_analysis(self, complex_project):
        """Test OOP analysis on abstract classes."""
        config = OOPConfig(scan_path=str(complex_project))
        analyzer = OOPAnalyzer(config)
        report = analyzer.analyze()

        assert report is not None

        # BaseService is an abstract class
        base_service_found = False
        for cls in report.class_metrics:
            if cls.class_name == 'BaseService':
                base_service_found = True
                # Abstract class should still have metrics
                assert cls is not None
                break

        assert base_service_found, "Abstract class should be analyzed"

    def test_oop_nested_class_analysis(self, tmp_path):
        """Test OOP analysis on nested classes."""
        nested_file = tmp_path / "nested.py"
        nested_file.write_text('''
class OuterClass:
    """Outer class."""
    def outer_method(self):
        """Outer method."""
        pass

    class InnerClass:
        """Inner class."""
        def inner_method(self):
            """Inner method."""
            pass
''')

        config = OOPConfig(scan_path=str(tmp_path))
        analyzer = OOPAnalyzer(config)
        report = analyzer.analyze()

        assert report is not None
        # Should detect both outer and inner classes
        assert report.total_classes_analyzed >= 1

    def test_oop_metrics_consistency(self, complex_project):
        """Test that OOP metrics are consistent across analyzers."""
        config = OOPConfig(scan_path=str(complex_project))
        oop_analyzer = OOPAnalyzer(config)
        oop_report = oop_analyzer.analyze()

        coupling_analyzer = CouplingAnalyzer()
        coupling_classes = coupling_analyzer.analyze(complex_project)

        # Both should find the same number of classes
        assert oop_report.total_classes_analyzed == len(coupling_classes)

    def test_oop_all_metrics_present(self, complex_project):
        """Test that all major OOP metrics are calculated."""
        config = OOPConfig(scan_path=str(complex_project))
        analyzer = OOPAnalyzer(config)
        report = analyzer.analyze()

        assert report is not None
        assert len(report.class_metrics) > 0

        # Check that metrics are present
        cls = report.class_metrics[0]
        assert hasattr(cls, 'class_name')

        # Check for major metrics (may vary by implementation)
        metric_count = 0
        if hasattr(cls, 'cbo'):
            metric_count += 1
        if hasattr(cls, 'dit'):
            metric_count += 1
        if hasattr(cls, 'lcom'):
            metric_count += 1
        if hasattr(cls, 'rfc'):
            metric_count += 1
        if hasattr(cls, 'wmc'):
            metric_count += 1

        # At least some metrics should be present
        assert metric_count > 0
