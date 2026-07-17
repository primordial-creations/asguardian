# Volundr Upgrade Plan — 06 Validation Engine & Suppression Model (Cross-Cutting, P0)

**Scope:** `Asgard/Volundr/Validation/` plus a new shared suppression/rule subsystem consumed by every generator.
**Research basis:** DEEPTHINK_02 (Intent-Driven Generation with Reified Suppressions), DEEPTHINK_03 (four-tier validation architecture), RESEARCH_01 (graph-based vs AST scanning, three-gate pipeline), RESEARCH_08 (unified validation framework: plan-JSON traversal, SARIF/JUnit telemetry, extensibility), RESEARCH_05 (kubeconform/conftest/pluto pipeline).

---

## 1. Why (Research Rationale)

1. **Rules today are conflated with format shape.** DEEPTHINK_03 identifies the collapse mode of validation systems: hardcoding semantic checks against a specific `apiVersion` or file layout. Volundr's current validators (`Validation/services/kubernetes_validator*.py`, `terraform_validator*.py`, `dockerfile_validator*.py`) walk raw dicts/regex per format with no shared canonical model — the exact anti-pattern DEEPTHINK_03 warns about. A `batch/v1beta1` CronJob or a Compose v2-vs-spec file silently escapes rules.
2. **No suppression concept exists anywhere.** DEEPTHINK_02 shows the four standard generation paradigms all fail (opt-out friction → wrapper scripts; workload ontologies → developers lie; warnings → normalization of deviance; env variants → dev/prod parity violations). The correct model is scoped, justified, reified suppressions with a warning-annihilation contract. Volundr currently has `ValidationContext.ignore_rules: List[str]` (`Validation/models/validation_models.py:76`) — a global, unjustified, untracked ignore list, which is precisely the "silent toggle" failure mode.
3. **Scoring/validation must be decoupled and adversarial** (DEEPTHINK_05 §1A "Collusion Problem"): generators must not grade their own intent. Today each generator computes its own score from its own config object (e.g. `Kubernetes/services/manifest_generator_helpers.py::calculate_best_practice_score` reads `config`, not only rendered YAML).
4. **Telemetry is bespoke.** RESEARCH_08 establishes SARIF as the industry standard for developer-facing findings (rule metadata, `helpUri`, markdown remediation) with JUnit XML for CI orchestrators. Volundr's `ValidationReport` is a custom model with no SARIF/JUnit emitters.
5. **Policies must be default-deny** (DEEPTHINK_03 §4): assert the presence of safety, never the absence of danger, so unknown/new fields fail closed. Current checks are mostly "if bad-thing present → warn" (fail-open).

## 2. Target State

A single `Validation` engine that every Volundr subpackage (Kubernetes, Terraform, Docker, Compose, Helm, Kustomize, GitOps, CICD) calls on **rendered output**, structured as DEEPTHINK_03's four tiers:

1. **Tier 1 — Lexical parse:** YAML/HCL/Dockerfile → typed AST with source mapping (line/col preserved into findings; `ValidationResult.line_number` finally populated for generated content too).
2. **Tier 2 — Schema binding:** version-pinned structural validation. K8s: OpenAPI schemas selected by `ValidationContext.kubernetes_version` (already exists, currently unused for schema binding). Version skew (`V_target > V_known`) downgrades unknown-field errors to WARN and marks nodes `<tainted>` (Protobuf-style lenient forward compatibility, DEEPTHINK_03 §3-4).
3. **Tier 3 — Canonical normalization:** an Internal Canonical Model (ICM). `Canonical_Workload`, `Canonical_Container`, `Canonical_NetworkRule`, `Canonical_PipelineJob`, `Canonical_ComposeService`… Version-specific shapes up-migrate into the ICM; semantic rules are written once against it. For Terraform's unbounded schema, use structural duck typing (`node.has_capability("encryption")`) instead of a hub model (DEEPTHINK_03 §2 note).
4. **Tier 4 — Semantic policies:** default-deny rule packs keyed by stable rule IDs. Policies must yield gracefully on `<computed>` values (Terraform apply-time unknowns; RESEARCH_08's `after_unknown` handling) and `<tainted>` nodes.

Plus the **shared suppression subsystem** (consumed by generators in plans 01–05):

```yaml
# input schema (Pydantic: Volundr/Validation/models/suppression_models.py)
suppressions:
  - rule: VOL-K8S-1042          # required, must match a known rule ID
    target: legacy-backend       # required: container/resource/step name or glob
    reason: "JIRA-4092: vendor image hardcoded to root, migration Q4"  # required, non-empty
    expires: 2026-12-31          # optional; expired suppressions are hard errors
```

Contract (DEEPTHINK_02 §4):
- Violation **without** suppression → generation fails (or validation ERROR).
- Violation **with** valid suppression → **zero warnings** emitted (warning annihilation) and the artifact carries a machine-readable receipt:
  - K8s: `volundr.asgard/suppress-<rule>: "true"` + `volundr.asgard/rationale: "<reason>"` annotations;
  - Dockerfile/HCL: trailing `# volundr:suppress=<rule> <reason>` comment (mirrors Checkov's `#checkov:skip=` idiom, RESEARCH_01);
  - Pipeline YAML: `# volundr:suppress=<rule> <reason>` comment above the offending key.
- Suppression of a rule that did not fire → WARN (stale suppression hygiene).
- `SecurityProfile` / environment enums become **presets of suppressions**, not alternate templates (see 01/03 plans).

## 3. Concrete Changes in `Asgard/Volundr/`

| Change | Files |
|---|---|
| New rule registry: every check becomes a `ValidationRule` instance with stable ID, severity, category, `documentation_url`, remediation markdown. Namespaces: `VOL-K8S-*`, `VOL-TF-*`, `VOL-CICD-*`, `VOL-GITOPS-*`, `VOL-HELM-*`, `VOL-KUST-*`, `VOL-COMPOSE-*`; Dockerfile checks keep hadolint IDs (`DL3xxx`) already used in `dockerfile_validator_helpers.py` and add `CKV_DOCKER_*`-equivalent security rules (RESEARCH_10 §2.2) | new `Validation/models/rule_registry.py`; refactor all `Validation/services/*_helpers.py` to register rules |
| Suppression models + engine (parse, validate justification, match rule×target, expiry, receipt emission helpers) | new `Validation/models/suppression_models.py`, `Validation/services/suppression_engine.py` |
| Canonical model + normalizers (K8s workload paths: `spec` vs `spec.template.spec` vs `spec.jobTemplate.spec.template.spec` — RESEARCH_03 path table) | new `Validation/models/canonical_models.py`, `Validation/services/normalizers/` |
| Schema-binding tier: vendored/downloadable JSON Schemas per K8s minor version; `-strict`-equivalent unknown-field detection with skew downgrade | new `Validation/services/schema_binder.py`; extend `ValidationContext` with `offline: bool`, `schema_dir` |
| Default-deny policy packs rewritten against ICM (rules from plans 01–05 live here) | rewrite `kubernetes_validator*.py`, `terraform_validator*.py`, extend `Compose/services/compose_validator*.py` to delegate |
| SARIF + JUnit XML emitters from `ValidationReport` (RESEARCH_08): SARIF `rules[]` populated from registry incl. `help.markdown` remediation snippets; dual output `-o cli -o sarif` | new `Validation/services/report_emitters.py`; CLI flags in `cli/_parser_flags.py` (`--output-format sarif|junit|json|cli`, `--output-file`) |
| Optional external-tool bridge: if `kubeconform`, `hadolint`, `checkov`, `actionlint`, `conftest` binaries are on PATH, run them against rendered output and merge findings (mapped into registry IDs); never required at runtime | new `Validation/services/external_tools.py` |
| Remove/deprecate `ValidationContext.ignore_rules` in favor of suppressions (keep alias with deprecation warning for one minor version) | `Validation/models/validation_models.py` |

## 4. Policy Style Rules (enforced for all rule authors)

- Assert presence of safety: `if not securityContext.runAsNonRoot → fail`, never `if runAsRoot == true → fail` (DEEPTHINK_03 §4 "fail-open" example).
- Every rule declares behavior for `<computed>` and `<tainted>`: `skip`, `warn`, or `conditional-assert`.
- Severity taxonomy fixed to CRITICAL/HIGH/MEDIUM/LOW/INFO (extends current 4-level `ValidationSeverity`; mapping table for old values), because plan 07's scoring math requires it.
- Rule metadata carries framework mappings (CIS ID / NSA-CISA / SLSA / hadolint ID) mirroring Checkov's compliance-mapping advantage (RESEARCH_01 "regulatory alignment").

## 5. Phased Steps

1. **Phase A (foundations):** rule registry + severity taxonomy + suppression models/engine + receipt helpers. Port existing rules 1:1 (no new checks yet) so all validators emit registry-backed `ValidationResult`s. Ship SARIF/JUnit emitters.
2. **Phase B (canonical model):** ICM + normalizers for K8s (all five workload kinds incl. nested PodSpec paths), Compose (spec, no `version` key), pipeline YAML (GH Actions first). Rewrite K8s/Docker/Compose semantic rules against ICM.
3. **Phase C (schema binding):** version-pinned K8s schema validation with skew WARN downgrade; Terraform duck-typing capability checks; optional plan-JSON ingestion (`terraform show -json`) traversing `resource_changes[].change.after/after_unknown` (RESEARCH_08).
4. **Phase D (integration):** generators call the engine on rendered output (plans 01–05); external-tool bridge; CLI `volundr validate` gains `--format`, `--target-k8s-version`, `--suppressions-file`.

## 6. Testing Notes

- `Asgard_Test/tests_Volundr/`: new `test_validation_engine.py`, `test_suppressions.py`.
- **Suppression contract tests:** (a) violation w/o suppression fails; (b) with suppression emits zero warnings and the receipt annotation/comment is present in output; (c) missing `reason` refuses to compile; (d) expired suppression fails; (e) stale suppression warns.
- **Version-skew tests:** manifest with an unknown field validated against older schema → WARN not ERROR; policy on `<tainted>` node does not fail-open (default-deny asserted).
- **Normalizer table tests:** same rule fires identically for Deployment/StatefulSet/DaemonSet/Job/CronJob nested paths (RESEARCH_03 path matrix as parametrized fixture).
- **SARIF snapshot tests:** validate emitted SARIF against the OASIS schema; assert `help.markdown` present for every rule.
- **L3_Contract:** when `conftest`/`kubeconform` available, engine findings must be a superset of a curated subset of external-tool findings on golden fixtures (skip-if-unavailable).

## 7. Doc Reconciliation

- `_Docs/Asgard/Volundr/` has **no page** for the Validation package — add `Validation-Module.md` documenting the four tiers, rule ID namespaces, suppression schema, SARIF output, and CLI (`volundr validate ...`, currently implemented in `cli/handlers_compose_validate_scaffold.py` but undocumented).
