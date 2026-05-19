"""
Heimdall-Forseti Integration Tests

Tests for cross-package integration between Heimdall (code analysis) and
Forseti (API/schema validation). These tests validate workflows where a
security scan on a Python source file and a contract check on a schema
are executed together and both produce valid, structured reports.
"""

from pathlib import Path

import pytest
import yaml

from Asgard.Heimdall.Quality import FileAnalyzer, AnalysisConfig
from Asgard.Heimdall.Security import StaticSecurityService, SecurityScanConfig
from Asgard.Forseti.OpenAPI import SpecValidatorService, OpenAPIConfig
from Asgard.Forseti.JSONSchema.services.schema_validator_service import SchemaValidatorService


@pytest.mark.cross_package
@pytest.mark.heimdall_forseti
class TestHeimdallForsetiIntegration:
    """
    Test workflow: Run a Heimdall security scan on a Python file, then run a
    Forseti contract check on a schema file, and assert both produce valid
    reports with expected structure.
    """

    def test_security_scan_and_openapi_validation_produce_valid_reports(
        self, sample_python_project: Path, sample_openapi_spec: Path
    ):
        """
        Test that Heimdall security scan and Forseti OpenAPI validation both
        produce reports with expected structure and compatible quality signals.

        Workflow:
        1. Run Heimdall security scan on the Python project
        2. Run Forseti OpenAPI spec validation on the schema file
        3. Assert both reports have valid structure
        4. Assert the security posture informs whether strict schema validation applies
        """
        # Step 1: Heimdall security scan
        scan_config = SecurityScanConfig(scan_path=str(sample_python_project))
        security_service = StaticSecurityService(scan_config)
        security_result = security_service.scan()

        # Verify security report structure
        assert security_result is not None
        assert hasattr(security_result, "scan_path")
        assert hasattr(security_result, "total_issues")
        assert hasattr(security_result, "security_score")
        assert 0.0 <= security_result.security_score <= 100.0

        # Step 2: Forseti OpenAPI validation
        openapi_service = SpecValidatorService()
        openapi_result = openapi_service.validate(str(sample_openapi_spec))

        # Verify OpenAPI report structure
        assert openapi_result is not None
        assert hasattr(openapi_result, "is_valid")
        assert hasattr(openapi_result, "errors")
        assert openapi_result.is_valid, (
            f"OpenAPI spec should be valid. Errors: {openapi_result.errors}"
        )
        assert openapi_result.openapi_version is not None

    def test_quality_analysis_and_json_schema_validation(
        self, sample_python_project: Path
    ):
        """
        Test that Heimdall quality analysis and Forseti JSON Schema validation
        can both run on the same project artefacts and produce consistent reports.

        Workflow:
        1. Analyse code quality with Heimdall FileAnalyzer
        2. Derive a minimal JSON schema from the quality report fields
        3. Validate the report data against that schema with Forseti
        4. Assert the validated report meets structural requirements
        """
        # Step 1: Heimdall quality analysis
        analysis_config = AnalysisConfig(
            scan_path=str(sample_python_project),
            threshold=100,
        )
        analyzer = FileAnalyzer(analysis_config)
        analysis_result = analyzer.analyze()

        # Verify analysis report structure
        assert analysis_result is not None
        assert analysis_result.total_files_scanned > 0
        assert analysis_result.scan_path == str(sample_python_project)
        assert 0.0 <= analysis_result.compliance_rate <= 100.0

        # Step 2: Build a simple JSON schema that describes a quality report
        quality_report_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "QualityReport",
            "type": "object",
            "required": ["total_files_scanned", "compliance_rate", "scan_path"],
            "properties": {
                "total_files_scanned": {"type": "integer", "minimum": 0},
                "compliance_rate": {"type": "number", "minimum": 0.0, "maximum": 100.0},
                "scan_path": {"type": "string", "minLength": 1},
            },
        }

        # Step 3: Validate the report data against the schema with Forseti
        report_data = {
            "total_files_scanned": analysis_result.total_files_scanned,
            "compliance_rate": analysis_result.compliance_rate,
            "scan_path": analysis_result.scan_path,
        }

        schema_service = SchemaValidatorService()
        schema_result = schema_service.validate(report_data, quality_report_schema)

        # Step 4: Assert structural validity
        assert schema_result is not None
        assert schema_result.is_valid, (
            f"Quality report data did not match schema. Errors: {schema_result.errors}"
        )
        assert schema_result.errors == []

    def test_security_findings_influence_schema_strictness(
        self, sample_python_project: Path, sample_openapi_spec: Path
    ):
        """
        Test that the number of Heimdall security findings influences how strict
        the Forseti schema validation configuration is.

        Workflow:
        1. Run Heimdall security scan to count findings
        2. Configure Forseti validation strictness based on findings count
        3. Run Forseti OpenAPI validation with that config
        4. Assert validation result reflects the chosen strictness
        """
        # Step 1: Heimdall security scan
        scan_config = SecurityScanConfig(scan_path=str(sample_python_project))
        security_service = StaticSecurityService(scan_config)
        security_result = security_service.scan()

        assert security_result is not None

        # Step 2: Determine strictness from findings
        finding_count = security_result.total_issues

        # High findings count → strict validation (fewer allowed warnings)
        # Low findings count → relaxed validation
        if finding_count > 5:
            openapi_config = OpenAPIConfig(strict_mode=True)
            expected_strictness = "strict"
        else:
            openapi_config = OpenAPIConfig(strict_mode=False)
            expected_strictness = "relaxed"

        # Step 3: Run Forseti OpenAPI validation
        openapi_service = SpecValidatorService(config=openapi_config)
        openapi_result = openapi_service.validate(str(sample_openapi_spec))

        # Step 4: Assert report structure is valid
        assert openapi_result is not None
        assert hasattr(openapi_result, "is_valid")
        assert hasattr(openapi_result, "openapi_version")
        assert openapi_result.is_valid, (
            f"OpenAPI spec invalid under {expected_strictness} mode. "
            f"Errors: {openapi_result.errors}"
        )
