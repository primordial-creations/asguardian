# Volundr Upgrade Plan — 02 Terraform Module Builder (P2)

**Scope:** `Asgard/Volundr/Terraform/` (models + services) and the Terraform validators in `Validation/`.
**Depends on:** 07 (scoring), 06 (rules/suppressions).
**Research basis:** RESEARCH_01 (Checkov graph analysis, plan-aware scanning, three-gate model, multi-cloud bias), RESEARCH_08 (plan-JSON schema traversal, `after_unknown`, Sentinel/OPA patterns), RESEARCH_02 (drift: `for_each` over `count`, lifecycle `ignore_changes`, state splitting), DEEPTHINK_05 (evaluated-state scoring, essential vs accidental complexity).

---

## 1. Why (Research Rationale)

Current builder is a keyword-matched canned-block emitter: `_module_builder_blocks.py` picks resource blocks by substring (`"s3" in resource.lower()` → bucket + versioning + SSE; `"vpc"` → VPC…), and validation is four regex checks (`_module_builder_blocks_part2.py:84-88`: SSE missing, `0.0.0.0/0`). Gaps against research:

1. **Security baselines incomplete.** S3 gets versioning+SSE but no `aws_s3_bucket_public_access_block` — the "most notorious cloud vulnerability" per RESEARCH_01 (OWASP IaC section); no RDS `storage_encrypted`, no security-group least-privilege scaffolds, no IAM wildcard prevention.
2. **Fail-open validation style.** "warn if `0.0.0.0/0` present" instead of asserting presence of protections (default-deny, DEEPTHINK_03 §4 via plan 06).
3. **No evaluated-state awareness.** DEEPTHINK_05 §1D: scoring/validation must be schema-aware — secure provider defaults count as pass; redundant explicit defaults are noise. RESEARCH_08 gives the concrete mechanism: consume `terraform show -json` plan output (`resource_changes[].change.{before,after,after_unknown}`), handling `after_unknown` as `<computed>`.
4. **Drift-resilient structure** (RESEARCH_02): `for_each` over `count` (index-shift drift storms), `lifecycle { ignore_changes }` for autoscaler-mutated fields, state-splitting guidance for large modules.
5. **Multi-cloud parity** (RESEARCH_01 bias section): Azure/GCP blocks must receive the same baseline rigor as AWS (tooling ecosystem is AWS-biased; Volundr should not be).

## 2. Target State

- **Hardened resource templates per provider.** Each canned block ships its security companions:
  - AWS S3: bucket + versioning + SSE (KMS option) + `aws_s3_bucket_public_access_block` (all four booleans true) + `aws_s3_bucket_ownership_controls`;
  - AWS RDS: `storage_encrypted = true`, `deletion_protection` (prod profile), no hardcoded credentials (password from variable marked `sensitive = true` or secrets-manager data source);
  - Security groups: no default-open ingress; generated ingress takes CIDR/SG-ref variables with validation blocks; `0.0.0.0/0` only via suppression `VOL-TF-OPEN-INGRESS`;
  - IAM: no `Action: "*"`/`Resource: "*"` in generated policies (finding if user-injected);
  - Azure/GCP equivalents: storage account `min_tls_version`, `allow_nested_items_to_be_public=false`; GCS uniform bucket-level access, CMEK options — same rule IDs, provider-mapped.
- **Structure quality:** `for_each` in generated multi-instance patterns; `lifecycle { ignore_changes }` emitted for known volatile fields (tags on autoscaled resources, `desired_capacity`) with comments (RESEARCH_02 §4); `sensitive = true` on secret-bearing variables/outputs; `precondition`/`validation` blocks on inputs (already partially present via `VariableConfig.validation`).
- **Plan-aware validation (optional input):** `volundr terraform validate --plan tfplan.json` traverses `resource_changes` per RESEARCH_08's schema, applying the same registry rules to evaluated state; raw-HCL mode remains for generation-time checks. `<computed>` (`after_unknown`) never fails a rule (skip/conditional per rule metadata).
- **Three-gate guidance emission** (RESEARCH_01): generated module README includes a CI recipe — local tfsec/trivy pre-commit, Checkov-on-plan PR gate — rather than Volundr reimplementing those scanners; external-tool bridge (plan 06) can invoke `checkov`/`trivy config` when present.
- **Suppressions:** `# volundr:suppress=<rule> <reason>` trailing HCL comments as receipts (mirrors `#checkov:skip=` codified-risk-acceptance idiom, RESEARCH_01).
- **Scoring:** delete local weights (variables/outputs/locals/docs presence — verbosity-farming bait per DEEPTHINK_05 §1D); plan-07 composite over rendered `.tf` (and plan JSON when supplied). Never penalize `for_each`/`dynamic` (essential complexity, §1C).

## 3. Concrete File/Module Changes

| Change | File |
|---|---|
| Security companions in canned blocks (S3 public-access-block etc.); provider-parity matrix for Azure/GCP | `Terraform/services/_module_builder_blocks.py`, `_module_builder_blocks_part2.py`, `_module_builder_generators.py` |
| `ModuleConfig` additions: `environment_profile`, `suppressions`, `kms_encryption: bool`, `sensitive_variables: List[str]`, per-resource option models replacing pure keyword inference (keyword path kept as fallback with INFO finding "canned template used") | `Terraform/models/terraform_models.py` |
| `for_each` + lifecycle emission in multi-instance templates | `_module_builder_blocks*.py` |
| Plan-JSON ingestion + traversal (`resource_changes`, `after_unknown` → `<computed>`) feeding registry rules | new `Validation/services/terraform_plan_reader.py`; rewrite `terraform_validator*.py`, `_terraform_aws_validators.py` into registry rules (`VOL-TF-*`) incl. Azure/GCP packs |
| README CI-recipe section (three-gate) + Renovate note for provider version bumps | `_module_builder_generators.py` (README builder) |
| Delete local score; wire plan 07 | `module_builder.py`, `module_builder_helpers.py` |
| CLI: `--plan tfplan.json` on validate; `--suppress`; `--profile prod|dev` | `cli/_parser_commands_1.py:46-70`, handlers |

## 4. Phased Steps

1. Security companions for AWS blocks (S3 public-access block first) + fail-closed rule rewrites in registry form.
2. Azure/GCP parity packs; `for_each`/lifecycle/sensitive structure upgrades.
3. Plan-JSON validation path with `<computed>` handling.
4. Scoring delegation, suppression receipts, README CI recipe, CLI flags.

## 5. Testing Notes

- `tests_Volundr/test_terraform.py`: golden modules per (provider × category × profile); assert S3 module contains `aws_s3_bucket_public_access_block` with all four flags; assert no generated SG has `0.0.0.0/0` without suppression comment.
- L3_Contract: `terraform fmt -check` + `terraform validate` (init-free via `-backend=false`) and `checkov -d` zero-findings gate on goldens (skip-if-unavailable).
- Plan-path tests: fixture `tfplan.json` with `after_unknown` KMS key id — encryption rule must not false-positive (RESEARCH_08 `after_unknown` handling); mutated `after` with `acl: public-read` must fail.
- Adversarial scoring: module stuffed with redundant `enable_dns_support = true` style defaults must not outscore a lean equivalent (DEEPTHINK_05 §1D).
- Multi-cloud parity test: same logical misconfiguration (public storage) fires the same rule ID on AWS, Azure, GCP fixtures.

## 6. Doc Reconciliation (`_Docs/Asgard/Volundr/Terraform-Module.md`)

- Doc's `ModuleConfig` example uses `include_examples/include_tests/terraform_version` and `OutputConfig(value=...)` — verify against actual model fields and regenerate examples from code.
- Doc scoring table (variables 20 / outputs 15 / locals 10 / …) replaced by plan-07 pointer.
- Add sections: security companions per provider, suppression comments, plan-aware validation, three-gate CI recipe.
