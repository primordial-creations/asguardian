"""
Terraform AWS resource validators (plan 02, default-deny style).

Rewritten from the original fail-open "warn if bad thing present" checks
to default-deny "assert presence of safety" checks against ``VOL-TF-*``
registry rules (plan 06 §4 policy style). Companion resources (public
access block, SSE config, versioning) are separate HCL blocks from the
bucket resource itself, so these functions search the *whole file
content*, not just the triggering resource's block.
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


def _blocks_referencing(content: str, resource_type: str, bucket_name: str) -> List[str]:
    """All HCL blocks of ``resource_type`` whose body references ``bucket_name``."""
    matches: List[str] = []
    pattern = re.compile(
        r'resource\s+"' + re.escape(resource_type) + r'"\s+"[^"]+"\s*\{'
    )
    for m in pattern.finditer(content):
        start = m.start()
        depth = 0
        for j in range(m.end() - 1, len(content)):
            if content[j] == "{":
                depth += 1
            elif content[j] == "}":
                depth -= 1
                if depth == 0:
                    body = content[start:j + 1]
                    if f"aws_s3_bucket.{bucket_name}" in body or f'"{bucket_name}"' in body:
                        matches.append(body)
                    break
    return matches


def validate_aws_s3_bucket(
    content: str, name: str, file_path: str, line_num: int
) -> List[ValidationResult]:
    """Default-deny: assert the companion hardening resources are present."""
    results: List[ValidationResult] = []

    pab_blocks = _blocks_referencing(content, "aws_s3_bucket_public_access_block", name)
    if not pab_blocks:
        f = _finding(
            "VOL-TF-0001",
            f"S3 bucket '{name}' has no aws_s3_bucket_public_access_block",
            file_path, line_num, name,
        )
        if f:
            results.append(f)
    else:
        flags = [
            "block_public_acls", "block_public_policy",
            "ignore_public_acls", "restrict_public_buckets",
        ]
        body = pab_blocks[0]
        missing = [flag for flag in flags if not re.search(rf'{flag}\s*=\s*true', body)]
        if missing:
            f = _finding(
                "VOL-TF-0001",
                f"S3 bucket '{name}' public-access-block missing: {', '.join(missing)}",
                file_path, line_num, name,
            )
            if f:
                results.append(f)

    sse_blocks = _blocks_referencing(
        content, "aws_s3_bucket_server_side_encryption_configuration", name
    )
    if not sse_blocks:
        f = _finding(
            "VOL-TF-0002",
            f"S3 bucket '{name}' has no server-side encryption configuration",
            file_path, line_num, name,
        )
        if f:
            results.append(f)

    versioning_blocks = _blocks_referencing(content, "aws_s3_bucket_versioning", name)
    if not versioning_blocks or not any(
        re.search(r'status\s*=\s*"Enabled"', b) for b in versioning_blocks
    ):
        f = _finding(
            "VOL-TF-0003",
            f"S3 bucket '{name}' has no versioning configuration enabled",
            file_path, line_num, name,
        )
        if f:
            results.append(f)

    return results


def validate_aws_db_instance(
    block_content: str, name: str, file_path: str, line_num: int
) -> List[ValidationResult]:
    """Default-deny: RDS storage must be explicitly encrypted."""
    results: List[ValidationResult] = []
    if not re.search(r'storage_encrypted\s*=\s*true', block_content):
        f = _finding(
            "VOL-TF-0004",
            f"RDS instance '{name}' does not set storage_encrypted = true",
            file_path, line_num, name,
        )
        if f:
            results.append(f)
    return results


def validate_aws_security_group(
    content: str, name: str, file_path: str, line_num: int
) -> List[ValidationResult]:
    results: List[ValidationResult] = []

    if '0.0.0.0/0' in content and ('ingress' in content.lower()):
        f = _finding(
            "VOL-TF-0005",
            f"Security group '{name}' allows ingress from 0.0.0.0/0",
            file_path, line_num, name,
        )
        if f:
            results.append(f)

    if 'from_port = 0' in content and 'to_port = 65535' in content:
        f = _finding(
            "VOL-TF-0006",
            f"Security group '{name}' opens all ports", file_path, line_num, name,
        )
        if f:
            results.append(f)

    return results


def validate_aws_iam_policy(
    content: str, name: str, file_path: str, line_num: int
) -> List[ValidationResult]:
    results: List[ValidationResult] = []

    if '"Action": "*"' in content or "'Action': '*'" in content or 'Action = "*"' in content:
        f = _finding(
            "VOL-TF-0007",
            f"IAM policy '{name}' uses wildcard (*) action",
            file_path, line_num, name,
        )
        if f:
            results.append(f)

    if '"Resource": "*"' in content or "'Resource': '*'" in content or 'Resource = "*"' in content:
        f = _finding(
            "VOL-TF-0008",
            f"IAM policy '{name}' uses wildcard (*) resource",
            file_path, line_num, name,
        )
        if f:
            results.append(f)

    return results
