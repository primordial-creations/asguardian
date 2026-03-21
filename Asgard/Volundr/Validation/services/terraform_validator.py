"""
Terraform Configuration Validator Service

Validates Terraform configurations for best practices,
security issues, and common misconfigurations.
"""

import os
import re
import time
from pathlib import Path
from typing import List, Optional

from Asgard.Volundr.Validation.models.validation_models import (
    ValidationReport,
    ValidationResult,
    ValidationCategory,
    ValidationContext,
    ValidationSeverity,
)
from Asgard.Volundr.Validation.services.terraform_validator_helpers import (
    build_report,
    check_deprecated_syntax,
    check_hardcoded_credentials,
    extract_block,
    validate_aws_iam_policy,
    validate_aws_s3_bucket,
    validate_aws_security_group,
    validate_module_call,
    validate_module_structure,
    validate_output,
    validate_variable,
)


class TerraformValidator:
    """Validates Terraform configurations."""

    # HCL block patterns
    RESOURCE_PATTERN = re.compile(r'resource\s+"([^"]+)"\s+"([^"]+)"\s*{', re.MULTILINE)
    DATA_PATTERN = re.compile(r'data\s+"([^"]+)"\s+"([^"]+)"\s*{', re.MULTILINE)
    VARIABLE_PATTERN = re.compile(r'variable\s+"([^"]+)"\s*{', re.MULTILINE)
    OUTPUT_PATTERN = re.compile(r'output\s+"([^"]+)"\s*{', re.MULTILINE)
    MODULE_PATTERN = re.compile(r'module\s+"([^"]+)"\s*{', re.MULTILINE)
    PROVIDER_PATTERN = re.compile(r'provider\s+"([^"]+)"\s*{', re.MULTILINE)
    TERRAFORM_PATTERN = re.compile(r'terraform\s*{', re.MULTILINE)

    def __init__(self, context: Optional[ValidationContext] = None):
        self.context = context or ValidationContext()

    def validate_file(self, file_path: str) -> ValidationReport:
        start_time = time.time()
        results: List[ValidationResult] = []

        if not os.path.exists(file_path):
            results.append(ValidationResult(
                rule_id="file-not-found",
                message=f"File not found: {file_path}",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SYNTAX,
                file_path=file_path,
            ))
            return build_report([file_path], results, start_time, self.context)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            results.append(ValidationResult(
                rule_id="file-read-error",
                message=f"Error reading file: {e}",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SYNTAX,
                file_path=file_path,
            ))
            return build_report([file_path], results, start_time, self.context)

        results.extend(self._validate_content(content, file_path))
        return build_report([file_path], results, start_time, self.context)

    def validate_directory(self, directory: str) -> ValidationReport:
        start_time = time.time()
        results: List[ValidationResult] = []
        files_validated: List[str] = []

        path = Path(directory)
        if not path.exists():
            results.append(ValidationResult(
                rule_id="directory-not-found",
                message=f"Directory not found: {directory}",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SYNTAX,
            ))
            return build_report([], results, start_time, self.context)

        for file_path in path.rglob("*.tf"):
            files_validated.append(str(file_path))
            file_results = self.validate_file(str(file_path))
            results.extend(file_results.results)

        results.extend(validate_module_structure(directory, files_validated))

        return build_report(files_validated, results, start_time, self.context)

    def _validate_content(self, content: str, file_path: str) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        lines = content.split("\n")

        if "main.tf" in file_path or file_path.endswith("/main.tf"):
            if not self.TERRAFORM_PATTERN.search(content):
                results.append(ValidationResult(
                    rule_id="missing-terraform-block",
                    message="main.tf should contain a terraform {} block",
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.BEST_PRACTICE,
                    file_path=file_path,
                ))

        for match in self.RESOURCE_PATTERN.finditer(content):
            resource_type = match.group(1)
            resource_name = match.group(2)
            line_num = content[:match.start()].count("\n") + 1
            results.extend(self._validate_resource(
                content, resource_type, resource_name, file_path, line_num
            ))

        for match in self.VARIABLE_PATTERN.finditer(content):
            var_name = match.group(1)
            line_num = content[:match.start()].count("\n") + 1
            results.extend(validate_variable(
                content, var_name, file_path, line_num, match.start()
            ))

        for match in self.OUTPUT_PATTERN.finditer(content):
            output_name = match.group(1)
            line_num = content[:match.start()].count("\n") + 1
            results.extend(validate_output(
                content, output_name, file_path, line_num, match.start()
            ))

        for match in self.MODULE_PATTERN.finditer(content):
            module_name = match.group(1)
            line_num = content[:match.start()].count("\n") + 1
            results.extend(validate_module_call(
                content, module_name, file_path, line_num, match.start()
            ))

        results.extend(check_hardcoded_credentials(content, file_path, lines))
        results.extend(check_deprecated_syntax(content, file_path, lines))

        return results

    def _validate_resource(
        self,
        content: str,
        resource_type: str,
        resource_name: str,
        file_path: str,
        line_num: int,
    ) -> List[ValidationResult]:
        results: List[ValidationResult] = []

        if not re.match(r'^[a-z][a-z0-9_]*$', resource_name):
            results.append(ValidationResult(
                rule_id="resource-naming",
                message=f"Resource name '{resource_name}' should use snake_case",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.BEST_PRACTICE,
                file_path=file_path,
                line_number=line_num,
                resource_name=resource_name,
            ))

        if resource_type == "aws_security_group":
            results.extend(validate_aws_security_group(
                content, resource_name, file_path, line_num
            ))
        elif resource_type == "aws_s3_bucket":
            results.extend(validate_aws_s3_bucket(
                content, resource_name, file_path, line_num
            ))
        elif resource_type == "aws_iam_policy":
            results.extend(validate_aws_iam_policy(
                content, resource_name, file_path, line_num
            ))

        return results
