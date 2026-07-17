"""
Terraform Azure/GCP resource validators (plan 02 multi-cloud parity).

The AWS tooling ecosystem is systematically biased (RESEARCH_01 bias
section); these mirror the AWS storage-hardening checks with the same
``VOL-TF-*`` rule IDs so the same logical misconfiguration (a publicly
readable object store) fires identically across providers.
"""

import re
from typing import List, Optional

from Asgard.Volundr.Validation.models.rule_registry import default_registry
from Asgard.Volundr.Validation.models.validation_models import ValidationResult

_REGISTRY = default_registry()


def _finding(
    rule_id: str, message: str, file_path: str, line_num: int, name: str
) -> Optional[ValidationResult]:
    rule = _REGISTRY.get(rule_id)
    if rule is None or not rule.enabled:
        return None
    return ValidationResult(
        rule_id=rule_id,
        message=message,
        severity=rule.severity.to_validation_severity(),
        category=rule.category,
        file_path=file_path,
        line_number=line_num,
        resource_name=name,
        suggestion=rule.remediation or None,
        context={"target": name},
    )


def validate_azurerm_storage_account(
    block_content: str, name: str, file_path: str, line_num: int
) -> List[ValidationResult]:
    """Default-deny: azurerm_storage_account must block public nested items."""
    results: List[ValidationResult] = []
    if not re.search(
        r'allow_nested_items_to_be_public\s*=\s*false', block_content
    ):
        f = _finding(
            "VOL-TF-0010",
            f"Storage account '{name}' does not set "
            "allow_nested_items_to_be_public = false",
            file_path, line_num, name,
        )
        if f:
            results.append(f)
    return results


def validate_google_storage_bucket(
    block_content: str, name: str, file_path: str, line_num: int
) -> List[ValidationResult]:
    """Default-deny: google_storage_bucket must enable uniform bucket-level access."""
    results: List[ValidationResult] = []
    if not re.search(r'uniform_bucket_level_access\s*=\s*true', block_content):
        f = _finding(
            "VOL-TF-0011",
            f"GCS bucket '{name}' does not set uniform_bucket_level_access = true",
            file_path, line_num, name,
        )
        if f:
            results.append(f)
    return results
