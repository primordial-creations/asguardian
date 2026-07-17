"""
Terraform plan-JSON ingestion (plan 02, RESEARCH_08 schema traversal).

Reads `terraform show -json <plan>` output and traverses
``resource_changes[].change.{after, after_unknown}``, applying the same
``VOL-TF-*`` registry rules to evaluated state as the raw-HCL validators.

``after_unknown`` leaves (apply-time-only values, e.g. a KMS key id that
doesn't exist yet) are merged into the canonical ``COMPUTED`` sentinel
(``Validation/models/canonical_models.py``). Per DEEPTHINK_03 / plan 06,
a rule never fails outright on a computed value — it softens to WARN
(never a silent pass, never a confident false positive).

Terraform's schema is effectively unbounded (thousands of resource
types across providers), so this module uses duck-typed capability
checks over plain dicts rather than a canonical hub model, per plan
06 §2 tier-3 note ("For Terraform's unbounded schema, use structural
duck typing instead of a hub model").
"""

import json
from typing import Any, Dict, List, Optional

from Asgard.Volundr.Validation.models.canonical_models import COMPUTED, is_unknown
from Asgard.Volundr.Validation.models.rule_registry import (
    RuleRegistry,
    UnknownValueBehavior,
    default_registry,
)
from Asgard.Volundr.Validation.models.validation_models import (
    ValidationResult,
    ValidationSeverity,
)


def merge_after_unknown(after: Any, after_unknown: Any) -> Any:
    """Merge ``change.after`` with ``change.after_unknown``.

    Any leaf marked ``True`` in ``after_unknown`` becomes the ``COMPUTED``
    sentinel in the merged structure; nested dicts/lists are merged
    recursively.
    """
    if after_unknown is True:
        return COMPUTED
    if isinstance(after_unknown, dict) and isinstance(after, dict):
        merged = dict(after)
        for key, unknown in after_unknown.items():
            merged[key] = merge_after_unknown(after.get(key), unknown)
        return merged
    if isinstance(after_unknown, list) and isinstance(after, list):
        merged_list = list(after)
        for i, item_unknown in enumerate(after_unknown):
            if i < len(merged_list):
                merged_list[i] = merge_after_unknown(merged_list[i], item_unknown)
        return merged_list
    return after


class TerraformPlanResource:
    """A single ``resource_changes[]`` entry normalized to (type, name, attrs)."""

    def __init__(
        self, address: str, resource_type: str, name: str, attrs: Dict[str, Any]
    ):
        self.address = address
        self.type = resource_type
        self.name = name
        self.attrs = attrs


def load_plan_resources(plan_json: Dict[str, Any]) -> List[TerraformPlanResource]:
    """Traverse ``resource_changes`` into normalized plan resources.

    Resources being deleted (actions == ["delete"]) are skipped — there is
    nothing to police in a teardown-only change.
    """
    out: List[TerraformPlanResource] = []
    for rc in plan_json.get("resource_changes", []) or []:
        change = rc.get("change", {}) or {}
        actions = change.get("actions", []) or []
        if actions == ["delete"]:
            continue
        after = change.get("after") or {}
        after_unknown = change.get("after_unknown") or {}
        attrs = merge_after_unknown(after, after_unknown)
        if not isinstance(attrs, dict):
            attrs = {}
        out.append(TerraformPlanResource(
            address=rc.get("address", ""),
            resource_type=rc.get("type", ""),
            name=rc.get("name", ""),
            attrs=attrs,
        ))
    return out


def load_plan_file(path: str) -> List[TerraformPlanResource]:
    with open(path, "r", encoding="utf-8") as f:
        return load_plan_resources(json.load(f))


class PlanPolicyEngine:
    """Default-deny ``VOL-TF-*`` checks against plan-JSON evaluated state."""

    def __init__(self, registry: Optional[RuleRegistry] = None):
        self.registry = registry or default_registry()

    def _finding(
        self,
        rule_id: str,
        message: str,
        resource: TerraformPlanResource,
        value: Any = None,
    ) -> Optional[ValidationResult]:
        rule = self.registry.get(rule_id)
        if rule is None or not rule.enabled:
            return None
        severity = rule.severity.to_validation_severity()
        if is_unknown(value):
            if rule.on_computed == UnknownValueBehavior.SKIP:
                return None
            severity = ValidationSeverity.WARNING
            message += " (value unknown until apply — verify manually)"
        return ValidationResult(
            rule_id=rule_id,
            message=message,
            severity=severity,
            category=rule.category,
            file_path=resource.address,
            resource_kind=resource.type,
            resource_name=resource.name,
            suggestion=rule.remediation or None,
            context={"target": resource.name},
        )

    @staticmethod
    def _companion(
        candidates: List[TerraformPlanResource],
        bucket: TerraformPlanResource,
        bucket_count: int,
    ) -> Optional[TerraformPlanResource]:
        """Find the companion resource (public-access-block, versioning,
        SSE config, ...) that references this bucket.

        Matches by substring on the companion's ``bucket`` attribute
        first (handles ``aws_s3_bucket.<name>.id`` references resolved
        at plan time); falls back to positional association when there
        is exactly one bucket and exactly one companion in the plan
        (the common single-bucket-module case, where the reference may
        still be COMPUTED at plan time).
        """
        for c in candidates:
            ref = c.attrs.get("bucket")
            if isinstance(ref, str) and bucket.name in ref:
                return c
        if bucket_count == 1 and len(candidates) == 1:
            return candidates[0]
        return None

    def check(self, resources: List[TerraformPlanResource]) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        by_type: Dict[str, List[TerraformPlanResource]] = {}
        for r in resources:
            by_type.setdefault(r.type, []).append(r)

        buckets = by_type.get("aws_s3_bucket", [])
        pabs = by_type.get("aws_s3_bucket_public_access_block", [])
        sses = by_type.get(
            "aws_s3_bucket_server_side_encryption_configuration", []
        )
        versionings = by_type.get("aws_s3_bucket_versioning", [])
        for bucket in buckets:
            pab = self._companion(pabs, bucket, len(buckets))
            if pab is None:
                f = self._finding(
                    "VOL-TF-0001",
                    f"S3 bucket '{bucket.name}' has no "
                    "aws_s3_bucket_public_access_block",
                    bucket,
                )
            else:
                flags = [
                    "block_public_acls", "block_public_policy",
                    "ignore_public_acls", "restrict_public_buckets",
                ]
                bad = [k for k in flags if pab.attrs.get(k) is not True]
                f = None
                if bad:
                    f = self._finding(
                        "VOL-TF-0001",
                        f"S3 bucket '{bucket.name}' public-access-block "
                        f"missing: {', '.join(bad)}",
                        bucket, value=pab.attrs.get(bad[0]),
                    )
            if f is not None:
                results.append(f)

            if self._companion(sses, bucket, len(buckets)) is None:
                f = self._finding(
                    "VOL-TF-0002",
                    f"S3 bucket '{bucket.name}' has no server-side "
                    "encryption configuration",
                    bucket,
                )
                if f is not None:
                    results.append(f)

            if self._companion(versionings, bucket, len(buckets)) is None:
                f = self._finding(
                    "VOL-TF-0003",
                    f"S3 bucket '{bucket.name}' has no versioning configuration",
                    bucket,
                )
                if f is not None:
                    results.append(f)

        for rds in by_type.get("aws_db_instance", []):
            encrypted = rds.attrs.get("storage_encrypted")
            if encrypted is not True:
                f = self._finding(
                    "VOL-TF-0004",
                    f"RDS instance '{rds.name}' does not set "
                    "storage_encrypted = true",
                    rds, value=encrypted,
                )
                if f is not None:
                    results.append(f)

        for sg in by_type.get("aws_security_group", []):
            ingress = sg.attrs.get("ingress")
            if is_unknown(ingress):
                f = self._finding(
                    "VOL-TF-0005",
                    f"Security group '{sg.name}' ingress rules are "
                    "unknown until apply",
                    sg, value=ingress,
                )
                if f is not None:
                    results.append(f)
            elif isinstance(ingress, list):
                for rule in ingress:
                    if not isinstance(rule, dict):
                        continue
                    cidrs = rule.get("cidr_blocks")
                    if isinstance(cidrs, list) and "0.0.0.0/0" in cidrs:
                        f = self._finding(
                            "VOL-TF-0005",
                            f"Security group '{sg.name}' allows ingress "
                            "from 0.0.0.0/0",
                            sg,
                        )
                        if f is not None:
                            results.append(f)
                    if rule.get("from_port") == 0 and rule.get("to_port") == 65535:
                        f = self._finding(
                            "VOL-TF-0006",
                            f"Security group '{sg.name}' opens all ports",
                            sg,
                        )
                        if f is not None:
                            results.append(f)

        for iam in (
            by_type.get("aws_iam_policy", [])
            + by_type.get("aws_iam_role_policy", [])
        ):
            policy = iam.attrs.get("policy")
            if isinstance(policy, str):
                if '"Action": "*"' in policy or '"Action":"*"' in policy:
                    f = self._finding(
                        "VOL-TF-0007",
                        f"IAM policy '{iam.name}' uses wildcard action", iam,
                    )
                    if f is not None:
                        results.append(f)
                if '"Resource": "*"' in policy or '"Resource":"*"' in policy:
                    f = self._finding(
                        "VOL-TF-0008",
                        f"IAM policy '{iam.name}' uses wildcard resource", iam,
                    )
                    if f is not None:
                        results.append(f)
            elif is_unknown(policy):
                f = self._finding(
                    "VOL-TF-0007",
                    f"IAM policy '{iam.name}' policy document is unknown "
                    "until apply",
                    iam, value=policy,
                )
                if f is not None:
                    results.append(f)

        for sa in by_type.get("azurerm_storage_account", []):
            allow_public = sa.attrs.get("allow_nested_items_to_be_public")
            if allow_public is not False:
                f = self._finding(
                    "VOL-TF-0010",
                    f"Storage account '{sa.name}' does not set "
                    "allow_nested_items_to_be_public = false",
                    sa, value=allow_public,
                )
                if f is not None:
                    results.append(f)

        for gcs in by_type.get("google_storage_bucket", []):
            uniform = gcs.attrs.get("uniform_bucket_level_access")
            if uniform is not True:
                f = self._finding(
                    "VOL-TF-0011",
                    f"GCS bucket '{gcs.name}' does not set "
                    "uniform_bucket_level_access = true",
                    gcs, value=uniform,
                )
                if f is not None:
                    results.append(f)

        return results


def check_plan_json(
    plan_json: Dict[str, Any], registry: Optional[RuleRegistry] = None
) -> List[ValidationResult]:
    """Convenience: parse + check a `terraform show -json` document."""
    resources = load_plan_resources(plan_json)
    return PlanPolicyEngine(registry=registry).check(resources)


def check_plan_file(
    path: str, registry: Optional[RuleRegistry] = None
) -> List[ValidationResult]:
    resources = load_plan_file(path)
    return PlanPolicyEngine(registry=registry).check(resources)
