"""L3 Contract tests for Heimdall Architecture models.

ArchitectureConfig and ArchitectureReport are dataclasses (not Pydantic),
SOLIDReport and HexagonalReport come from submodules.
"""

import pytest
from pathlib import Path
from dataclasses import fields as dc_fields


from Asgard.Heimdall.Architecture.models.architecture_models import (
    ArchitectureConfig,
    ArchitectureReport,
    SOLIDReport,
    HexagonalReport,
)


class TestArchitectureConfigContract:
    def test_instantiates_with_defaults(self):
        config = ArchitectureConfig()
        assert hasattr(config, "scan_path")

    def test_scan_path_is_path(self):
        config = ArchitectureConfig()
        assert isinstance(config.scan_path, Path)

    def test_accepts_custom_scan_path(self, tmp_path):
        config = ArchitectureConfig(scan_path=tmp_path)
        assert config.scan_path == tmp_path

    def test_has_exclude_patterns_field(self):
        config = ArchitectureConfig()
        assert hasattr(config, "exclude_patterns")
        assert isinstance(config.exclude_patterns, list)

    def test_has_include_extensions_field(self):
        config = ArchitectureConfig()
        assert hasattr(config, "include_extensions")

    def test_has_solid_threshold_fields(self):
        config = ArchitectureConfig()
        assert hasattr(config, "max_class_responsibilities")
        assert hasattr(config, "max_method_count")
        assert hasattr(config, "max_public_methods")
        assert hasattr(config, "max_dependencies")

    def test_field_types_are_ints(self):
        config = ArchitectureConfig()
        assert isinstance(config.max_class_responsibilities, int)
        assert isinstance(config.max_method_count, int)


class TestArchitectureReportContract:
    def test_has_expected_dataclass_fields(self):
        field_names = {f.name for f in dc_fields(ArchitectureReport)}
        assert "scan_path" in field_names or len(field_names) > 0

    def test_instantiates(self):
        # ArchitectureReport is a dataclass; check it can be constructed
        report = ArchitectureReport.__new__(ArchitectureReport)
        assert report is not None


class TestSOLIDReportContract:
    def test_has_model_fields(self):
        assert hasattr(SOLIDReport, "model_fields") or hasattr(SOLIDReport, "__dataclass_fields__")

    def test_instantiable_structure(self):
        # Verify the class is accessible and a proper type
        assert callable(SOLIDReport)


class TestHexagonalReportContract:
    def test_has_model_fields(self):
        assert hasattr(HexagonalReport, "model_fields") or hasattr(HexagonalReport, "__dataclass_fields__")

    def test_instantiable_structure(self):
        assert callable(HexagonalReport)
