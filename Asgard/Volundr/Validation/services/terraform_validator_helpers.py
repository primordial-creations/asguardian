import hashlib
import os
import re
import time
from typing import Any, Dict, List

from Asgard.Volundr.Validation.models.validation_models import (
    FileValidationSummary,
    ValidationCategory,
    ValidationContext,
    ValidationReport,
    ValidationResult,
    ValidationSeverity,
)

SENSITIVE_PATTERNS = [
    "password", "secret", "key", "token", "api_key", "apikey",
    "auth", "credential", "private", "cert", "ssh",
]


def validate_aws_security_group(
    content: str, name: str, file_path: str, line_num: int
) -> List[ValidationResult]:
    results: List[ValidationResult] = []

    if '0.0.0.0/0' in content and ('ingress' in content.lower()):
        results.append(ValidationResult(
            rule_id="sg-open-ingress",
            message=f"Security group '{name}' allows ingress from 0.0.0.0/0",
            severity=ValidationSeverity.WARNING,
            category=ValidationCategory.SECURITY,
            file_path=file_path,
            line_number=line_num,
            resource_name=name,
            suggestion="Restrict ingress to specific CIDR blocks",
        ))

    if 'from_port = 0' in content and 'to_port = 65535' in content:
        results.append(ValidationResult(
            rule_id="sg-all-ports",
            message=f"Security group '{name}' opens all ports",
            severity=ValidationSeverity.ERROR,
            category=ValidationCategory.SECURITY,
            file_path=file_path,
            line_number=line_num,
            resource_name=name,
        ))

    return results


def validate_aws_s3_bucket(
    content: str, name: str, file_path: str, line_num: int
) -> List[ValidationResult]:
    results: List[ValidationResult] = []

    if 'versioning' not in content.lower():
        results.append(ValidationResult(
            rule_id="s3-no-versioning",
            message=f"S3 bucket '{name}' may not have versioning enabled",
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.BEST_PRACTICE,
            file_path=file_path,
            line_number=line_num,
            resource_name=name,
            suggestion="Consider enabling versioning for data protection",
        ))

    if 'server_side_encryption' not in content.lower() and 'aws_s3_bucket_server_side_encryption_configuration' not in content:
        results.append(ValidationResult(
            rule_id="s3-no-encryption",
            message=f"S3 bucket '{name}' may not have encryption configured",
            severity=ValidationSeverity.WARNING,
            category=ValidationCategory.SECURITY,
            file_path=file_path,
            line_number=line_num,
            resource_name=name,
            suggestion="Enable server-side encryption",
        ))

    return results


def validate_aws_iam_policy(
    content: str, name: str, file_path: str, line_num: int
) -> List[ValidationResult]:
    results: List[ValidationResult] = []

    if '"Action": "*"' in content or "'Action': '*'" in content or 'Action = "*"' in content:
        results.append(ValidationResult(
            rule_id="iam-wildcard-action",
            message=f"IAM policy '{name}' uses wildcard (*) action",
            severity=ValidationSeverity.ERROR,
            category=ValidationCategory.SECURITY,
            file_path=file_path,
            line_number=line_num,
            resource_name=name,
            suggestion="Use specific actions instead of wildcard",
        ))

    if '"Resource": "*"' in content or "'Resource': '*'" in content or 'Resource = "*"' in content:
        results.append(ValidationResult(
            rule_id="iam-wildcard-resource",
            message=f"IAM policy '{name}' uses wildcard (*) resource",
            severity=ValidationSeverity.WARNING,
            category=ValidationCategory.SECURITY,
            file_path=file_path,
            line_number=line_num,
            resource_name=name,
            suggestion="Scope resources to specific ARNs",
        ))

    return results


def validate_variable(
    content: str, var_name: str, file_path: str, line_num: int, start_pos: int
) -> List[ValidationResult]:
    results: List[ValidationResult] = []

    block_content = extract_block(content, start_pos)

    if 'description' not in block_content:
        results.append(ValidationResult(
            rule_id="variable-no-description",
            message=f"Variable '{var_name}' missing description",
            severity=ValidationSeverity.WARNING,
            category=ValidationCategory.MAINTAINABILITY,
            file_path=file_path,
            line_number=line_num,
            suggestion="Add a description for documentation",
        ))

    if 'type' not in block_content:
        results.append(ValidationResult(
            rule_id="variable-no-type",
            message=f"Variable '{var_name}' missing type constraint",
            severity=ValidationSeverity.WARNING,
            category=ValidationCategory.BEST_PRACTICE,
            file_path=file_path,
            line_number=line_num,
            suggestion="Add a type constraint for better validation",
        ))

    if any(p in var_name.lower() for p in SENSITIVE_PATTERNS):
        if 'sensitive' not in block_content or 'sensitive = true' not in block_content:
            results.append(ValidationResult(
                rule_id="variable-not-sensitive",
                message=f"Variable '{var_name}' appears to be sensitive but not marked as such",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.SECURITY,
                file_path=file_path,
                line_number=line_num,
                suggestion="Add 'sensitive = true' to the variable",
            ))

    return results


def validate_output(
    content: str, output_name: str, file_path: str, line_num: int, start_pos: int
) -> List[ValidationResult]:
    results: List[ValidationResult] = []

    block_content = extract_block(content, start_pos)

    if 'description' not in block_content:
        results.append(ValidationResult(
            rule_id="output-no-description",
            message=f"Output '{output_name}' missing description",
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.MAINTAINABILITY,
            file_path=file_path,
            line_number=line_num,
        ))

    if any(p in output_name.lower() for p in SENSITIVE_PATTERNS):
        if 'sensitive' not in block_content or 'sensitive = true' not in block_content:
            results.append(ValidationResult(
                rule_id="output-not-sensitive",
                message=f"Output '{output_name}' appears to be sensitive but not marked as such",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.SECURITY,
                file_path=file_path,
                line_number=line_num,
                suggestion="Add 'sensitive = true' to the output",
            ))

    return results


def validate_module_call(
    content: str, module_name: str, file_path: str, line_num: int, start_pos: int
) -> List[ValidationResult]:
    results: List[ValidationResult] = []

    block_content = extract_block(content, start_pos)

    if 'source' not in block_content:
        results.append(ValidationResult(
            rule_id="module-no-source",
            message=f"Module '{module_name}' missing source",
            severity=ValidationSeverity.ERROR,
            category=ValidationCategory.SCHEMA,
            file_path=file_path,
            line_number=line_num,
        ))

    if 'registry.terraform.io' in block_content or ('source' in block_content and 'version' not in block_content):
        source_match = re.search(r'source\s*=\s*"([^"]+)"', block_content)
        if source_match:
            source = source_match.group(1)
            if not source.startswith('./') and not source.startswith('../') and '://' not in source:
                if 'version' not in block_content:
                    results.append(ValidationResult(
                        rule_id="module-no-version",
                        message=f"Module '{module_name}' should pin version for registry module",
                        severity=ValidationSeverity.WARNING,
                        category=ValidationCategory.BEST_PRACTICE,
                        file_path=file_path,
                        line_number=line_num,
                        suggestion="Add version constraint for reproducible builds",
                    ))

    return results


def validate_module_structure(
    directory: str, files: List[str]
) -> List[ValidationResult]:
    results: List[ValidationResult] = []
    file_names = [os.path.basename(f) for f in files]

    if "main.tf" not in file_names:
        results.append(ValidationResult(
            rule_id="missing-main-tf",
            message="Module missing main.tf file",
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.BEST_PRACTICE,
            file_path=directory,
        ))

    if "variables.tf" not in file_names:
        results.append(ValidationResult(
            rule_id="missing-variables-tf",
            message="Module missing variables.tf file",
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.BEST_PRACTICE,
            file_path=directory,
        ))

    if "outputs.tf" not in file_names:
        results.append(ValidationResult(
            rule_id="missing-outputs-tf",
            message="Module missing outputs.tf file",
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.BEST_PRACTICE,
            file_path=directory,
        ))

    return results


def check_hardcoded_credentials(
    content: str, file_path: str, lines: List[str]
) -> List[ValidationResult]:
    results: List[ValidationResult] = []

    patterns = [
        (r'access_key\s*=\s*"[A-Z0-9]{20}"', "AWS access key"),
        (r'secret_key\s*=\s*"[A-Za-z0-9/+=]{40}"', "AWS secret key"),
        (r'password\s*=\s*"[^"]+"', "hardcoded password"),
        (r'api_key\s*=\s*"[^"]+"', "hardcoded API key"),
    ]

    for i, line in enumerate(lines):
        for pattern, description in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                results.append(ValidationResult(
                    rule_id="hardcoded-credential",
                    message=f"Possible {description} found",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.SECURITY,
                    file_path=file_path,
                    line_number=i + 1,
                    suggestion="Use variables or environment variables for sensitive values",
                ))

    return results


def check_deprecated_syntax(
    content: str, file_path: str, lines: List[str]
) -> List[ValidationResult]:
    results: List[ValidationResult] = []

    for i, line in enumerate(lines):
        if re.search(r'=\s*"\$\{[^}]+\}"$', line.strip()):
            results.append(ValidationResult(
                rule_id="deprecated-interpolation",
                message="Unnecessary interpolation syntax (deprecated in Terraform 0.12+)",
                severity=ValidationSeverity.INFO,
                category=ValidationCategory.BEST_PRACTICE,
                file_path=file_path,
                line_number=i + 1,
                suggestion="Use direct reference instead of interpolation",
            ))

    return results


def extract_block(content: str, start_pos: int) -> str:
    brace_count = 0
    started = False
    end_pos = start_pos

    for i in range(start_pos, len(content)):
        char = content[i]
        if char == '{':
            brace_count += 1
            started = True
        elif char == '}':
            brace_count -= 1
            if started and brace_count == 0:
                end_pos = i + 1
                break

    return content[start_pos:end_pos]


def build_report(
    files: List[str],
    results: List[ValidationResult],
    start_time: float,
    context: ValidationContext,
) -> ValidationReport:
    duration_ms = int((time.time() - start_time) * 1000)

    error_count = sum(1 for r in results if r.severity == ValidationSeverity.ERROR)
    warning_count = sum(1 for r in results if r.severity == ValidationSeverity.WARNING)
    info_count = sum(1 for r in results if r.severity == ValidationSeverity.INFO)

    score = 100.0
    score -= error_count * 10
    score -= warning_count * 3
    score -= info_count * 1
    score = max(0.0, score)

    file_summaries = []
    results_by_file: Dict[str, List[ValidationResult]] = {}
    for result in results:
        fp = result.file_path or "(no file)"
        if fp not in results_by_file:
            results_by_file[fp] = []
        results_by_file[fp].append(result)

    for fp in files:
        file_results = results_by_file.get(fp, [])
        file_errors = sum(1 for r in file_results if r.severity == ValidationSeverity.ERROR)
        file_warnings = sum(1 for r in file_results if r.severity == ValidationSeverity.WARNING)
        file_info = sum(1 for r in file_results if r.severity == ValidationSeverity.INFO)
        file_summaries.append(FileValidationSummary(
            file_path=fp,
            error_count=file_errors,
            warning_count=file_warnings,
            info_count=file_info,
            passed=file_errors == 0,
        ))

    report_id = hashlib.sha256(str(results).encode()).hexdigest()[:16]

    return ValidationReport(
        id=f"terraform-validation-{report_id}",
        title="Terraform Configuration Validation",
        validator="TerraformValidator",
        results=results,
        file_summaries=file_summaries,
        total_files=len(files),
        total_errors=error_count,
        total_warnings=warning_count,
        total_info=info_count,
        passed=error_count == 0,
        score=score,
        duration_ms=duration_ms,
        context=context,
    )
