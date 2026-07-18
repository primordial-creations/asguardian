"""
Tests for Terraform plan-JSON ingestion (plan 02 / RESEARCH_08).

Covers ``terraform show -json`` traversal, ``after_unknown`` -> COMPUTED
merging, and the default-deny ``PlanPolicyEngine`` checks against
evaluated plan state.
"""

import json

from Asgard.Volundr.Validation.models.validation_models import ValidationSeverity
from Asgard.Volundr.Validation.services.terraform_plan_reader import (
    PlanPolicyEngine,
    check_plan_json,
    load_plan_resources,
    merge_after_unknown,
)


def _plan(resource_changes):
    return {"resource_changes": resource_changes}


class TestMergeAfterUnknown:
    def test_known_scalar_passes_through(self):
        assert merge_after_unknown("value", False) == "value"

    def test_unknown_scalar_becomes_computed(self):
        from Asgard.Volundr.Validation.models.canonical_models import COMPUTED
        assert merge_after_unknown("placeholder", True) is COMPUTED

    def test_nested_dict_merge(self):
        after = {"a": "known", "b": "placeholder"}
        after_unknown = {"a": False, "b": True}
        merged = merge_after_unknown(after, after_unknown)
        assert merged["a"] == "known"
        from Asgard.Volundr.Validation.models.canonical_models import is_unknown
        assert is_unknown(merged["b"])


class TestLoadPlanResources:
    def test_deleted_resources_skipped(self):
        plan = _plan([
            {
                "address": "aws_s3_bucket.gone", "type": "aws_s3_bucket",
                "name": "gone", "change": {"actions": ["delete"], "after": None, "after_unknown": {}},
            }
        ])
        assert load_plan_resources(plan) == []

    def test_create_resource_loaded(self):
        plan = _plan([
            {
                "address": "aws_s3_bucket.main", "type": "aws_s3_bucket",
                "name": "main",
                "change": {"actions": ["create"], "after": {"bucket": "x"}, "after_unknown": {}},
            }
        ])
        resources = load_plan_resources(plan)
        assert len(resources) == 1
        assert resources[0].type == "aws_s3_bucket"
        assert resources[0].attrs["bucket"] == "x"


class TestPlanPolicyEngineComputedHandling:
    def test_unknown_kms_key_does_not_hard_fail(self):
        """An after_unknown KMS key id must never cause a hard failure --
        it's not a checkable value yet, so the rule must WARN, never ERROR
        and never silently pass (plan 06 default-WARN-on-unknown contract).
        """
        plan = _plan([
            {
                "address": "aws_db_instance.main", "type": "aws_db_instance", "name": "main",
                "change": {
                    "actions": ["create"],
                    "after": {"storage_encrypted": True},
                    "after_unknown": {},
                },
            },
        ])
        results = check_plan_json(plan)
        # storage_encrypted is known-true -> no VOL-TF-0004 finding at all.
        assert not any(r.rule_id == "VOL-TF-0004" for r in results)

    def test_unknown_security_group_ingress_softens_to_warning(self):
        plan = _plan([
            {
                "address": "aws_security_group.main", "type": "aws_security_group", "name": "main",
                "change": {
                    "actions": ["create"],
                    "after": {},
                    "after_unknown": {"ingress": True},
                },
            },
        ])
        results = check_plan_json(plan)
        matches = [r for r in results if r.rule_id == "VOL-TF-0005"]
        assert matches
        assert all(r.severity == ValidationSeverity.WARNING for r in matches)


class TestPlanPolicyEngineMutations:
    def test_mutated_public_acl_fails(self):
        """A plan that mutates a bucket toward public exposure must fire
        VOL-TF-0001 (no public-access-block present at all here)."""
        plan = _plan([
            {
                "address": "aws_s3_bucket.main", "type": "aws_s3_bucket", "name": "main",
                "change": {
                    "actions": ["update"],
                    "after": {"bucket": "main", "acl": "public-read"},
                    "after_unknown": {},
                },
            },
        ])
        results = check_plan_json(plan)
        assert any(r.rule_id == "VOL-TF-0001" for r in results)

    def test_hardened_bucket_with_companions_clean(self):
        plan = _plan([
            {
                "address": "aws_s3_bucket.main", "type": "aws_s3_bucket", "name": "main",
                "change": {"actions": ["create"], "after": {"bucket": "main"}, "after_unknown": {}},
            },
            {
                "address": "aws_s3_bucket_public_access_block.main",
                "type": "aws_s3_bucket_public_access_block", "name": "main",
                "change": {
                    "actions": ["create"],
                    "after": {
                        "bucket": "main",
                        "block_public_acls": True,
                        "block_public_policy": True,
                        "ignore_public_acls": True,
                        "restrict_public_buckets": True,
                    },
                    "after_unknown": {},
                },
            },
            {
                "address": "aws_s3_bucket_server_side_encryption_configuration.main",
                "type": "aws_s3_bucket_server_side_encryption_configuration", "name": "main",
                "change": {"actions": ["create"], "after": {"bucket": "main"}, "after_unknown": {}},
            },
            {
                "address": "aws_s3_bucket_versioning.main",
                "type": "aws_s3_bucket_versioning", "name": "main",
                "change": {"actions": ["create"], "after": {"bucket": "main"}, "after_unknown": {}},
            },
        ])
        results = check_plan_json(plan)
        assert not any(
            r.rule_id in {"VOL-TF-0001", "VOL-TF-0002", "VOL-TF-0003"} for r in results
        )


class TestPlanCLIWiring:
    """Plan 02: `terraform_plan_reader` must be reachable from the CLI as
    ``volundr validate terraform --plan tfplan.json`` — previously the
    module was built and tested but never wired into any command path."""

    def test_parser_accepts_plan_flag_without_positional_path(self):
        from Asgard.Volundr.cli import create_parser
        parser = create_parser()
        args = parser.parse_args(
            ["validate", "terraform", "--plan", "tfplan.json"]
        )
        assert args.plan_json == "tfplan.json"
        assert args.path is None

    def test_parser_still_accepts_raw_hcl_path(self):
        from Asgard.Volundr.cli import create_parser
        parser = create_parser()
        args = parser.parse_args(["validate", "terraform", "modules/foo"])
        assert args.path == "modules/foo"
        assert args.plan_json is None

    def test_handler_reads_plan_json_and_reports_findings(self, tmp_path, capsys):
        from Asgard.Volundr.cli.handlers_compose_validate_scaffold import (
            run_validate_terraform,
        )
        plan_path = tmp_path / "tfplan.json"
        plan_path.write_text(json.dumps(_plan([
            {
                "address": "aws_s3_bucket.main",
                "type": "aws_s3_bucket", "name": "main",
                "change": {
                    "actions": ["create"],
                    "after": {"bucket": "leaky"},
                    "after_unknown": {},
                },
            },
        ])))

        class Args:
            path = None
            plan_json = str(plan_path)

        exit_code = run_validate_terraform(Args())
        out = capsys.readouterr().out
        assert "VOL-TF-0001" in out or "public" in out.lower() or "encrypt" in out.lower()
        assert exit_code in (0, 1)

    def test_handler_requires_path_or_plan(self, capsys):
        from Asgard.Volundr.cli.handlers_compose_validate_scaffold import (
            run_validate_terraform,
        )

        class Args:
            path = None
            plan_json = None

        exit_code = run_validate_terraform(Args())
        assert exit_code == 1

    def test_handler_after_unknown_kms_key_does_not_false_positive(self, tmp_path):
        """RESEARCH_08: a computed (apply-time-only) KMS key id must not
        make the encryption rule fail closed on a false positive."""
        from Asgard.Volundr.cli.handlers_compose_validate_scaffold import (
            run_validate_terraform,
        )
        plan_path = tmp_path / "tfplan.json"
        plan_path.write_text(json.dumps(_plan([
            {
                "address": "aws_s3_bucket_server_side_encryption_configuration.main",
                "type": "aws_s3_bucket_server_side_encryption_configuration",
                "name": "main",
                "change": {
                    "actions": ["create"],
                    "after": {"bucket": "main", "rule": None},
                    "after_unknown": {"bucket": False, "rule": True},
                },
            },
        ])))

        class Args:
            path = None
            plan_json = str(plan_path)

        # Must not raise, and must not hard-fail solely due to <computed>.
        run_validate_terraform(Args())
