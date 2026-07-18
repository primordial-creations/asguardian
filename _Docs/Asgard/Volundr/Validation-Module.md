# Volundr - Validation Module

## Overview

The Validation module is the single independent judge every generator in
Volundr hands its rendered output to. Generators (CICD, Terraform,
Kubernetes, Kustomize, Helm, GitOps) never grade their own intent — they
render an artifact and pass it to `ValidationEngine`, whose findings then
feed `ScoringEngine` (see [Scoring.md](Scoring.md)).

The engine is four-tier, decoupled, and adversarial by design
(`Asgard/Volundr/Validation/services/validation_engine.py`):

```
Tier 1  Lexical parse    YAML -> typed docs, with source line mapping
Tier 2  Schema binding   version-pinned structural validation;
                         version skew softens to WARN + <tainted>
Tier 3  Normalization    version-specific shapes -> Internal Canonical
                         Model (ICM), so semantic rules are written once
Tier 4  Semantic policy  default-deny rule packs evaluated over the ICM
```

Suppressions (`# volundr:suppress=<rule> <reason>`) are applied last, as
warning annihilation with receipts — a suppressed finding scores as
passed but stays visible in the report as accepted posture debt (see
`SuppressedReceipt` in [Scoring.md](Scoring.md)).

## Tier 1 — Lexical Parse

`parse_yaml_with_lines(content)` parses multi-document YAML with
`yaml.safe_load_all` for values and a parallel `yaml.compose_all` walk to
build a per-document `line_map: Dict[dot_path, line_number]`. Every
downstream finding can therefore carry an accurate source line even
though semantic checks operate on plain Python data, not YAML nodes.

## Tier 2/3 — Schema Binding and Normalization

`SchemaBinder` performs version-pinned structural checks per document
type. Where a value is `after_unknown` in a Terraform plan (or otherwise
not resolvable ahead of apply/deploy), it is marked `<computed>` or
`<tainted>` rather than failing outright — see `UnknownValueBehavior` in
`Asgard/Volundr/Validation/models/rule_registry.py` (`SKIP` / `WARN` /
`CONDITIONAL_ASSERT`). Default-deny still applies: a rule may soften to
WARN on unknown data, but it never silently passes unless it explicitly
declares `SKIP`.

Pipeline documents are normalized into a shared `CanonicalPipelineJob` /
`CanonicalPipelineStep` model (`services/normalizers/pipeline_normalizer.py`)
so a single semantic rule set (e.g. the static-secret check) covers
GitHub Actions, GitLab CI, and Azure DevOps without being written three
times:

```python
looks_like_github_workflow(doc) -> normalize_github_workflow(doc)
looks_like_gitlab_ci(doc)        -> normalize_gitlab_ci(doc)
looks_like_azure_pipeline(doc)   -> normalize_azure_pipeline(doc)
```

`ValidationEngine.validate_pipeline()` dispatches through this
detect-then-normalize elif chain automatically — callers do not declare
the platform up front.

GitLab/Azure jobs have no first-class `permissions:`/`with:` concept, so
their canonical jobs carry `permissions={}` / `workflow_permissions={}`;
job-scoped `variables`/parameters are still surfaced as a synthetic
`CanonicalPipelineStep(name=f"{job}:variables", env=...)` so the shared
static-secret rule can see them.

## Tier 4 — Semantic Policy

`PolicyEngine` (`services/semantic_policies.py`) evaluates the registered
rule set (`Asgard/Volundr/Validation/models/rule_registry.py`) against
the ICM. Rule ID namespaces:

| Namespace | Domain |
|-----------|--------|
| `VOL-K8S-*` | Kubernetes manifests |
| `VOL-TF-*` | Terraform |
| `VOL-CICD-*` | CI/CD pipeline YAML (GitHub Actions / GitLab / Azure DevOps) |
| `VOL-GITOPS-*` | ArgoCD / Flux |
| `VOL-HELM-*` | Helm charts |
| `VOL-KUST-*` | Kustomize |
| `VOL-COMPOSE-*` | Docker Compose |
| `DL3xxx`/`DL4xxx` | Dockerfile (hadolint-compatible IDs) |

Every `RegisteredRule` carries a stable ID, a five-level severity
(`RuleSeverity.CRITICAL/HIGH/MEDIUM/LOW/INFO`), remediation markdown,
framework mappings (CIS / NSA-CISA / hadolint / SLSA), and its
`UnknownValueBehavior`. `RuleSeverity` maps bidirectionally onto the
legacy four-level `ValidationSeverity` (`ERROR`/`WARNING`/`INFO`/`HINT`)
used elsewhere in the codebase, so older call sites keep working.

## Entry Points

```python
from Asgard.Volundr.Validation.services.validation_engine import ValidationEngine

engine = ValidationEngine()
report = engine.validate_kubernetes(manifest_yaml, source="deployment.yaml")
report = engine.validate_compose(compose_yaml, source="docker-compose.yml")
report = engine.validate_pipeline(pipeline_yaml, source=".github/workflows/ci.yml")
```

Each returns a `ValidationReport` (`Asgard/Volundr/Validation/models/validation_models.py`)
with `.results: List[ValidationResult]` and a `FileValidationSummary`.
`ValidationResult` is also the type generators convert their own
pre-Tier-4 findings into (via local `_issues_to_findings` helpers in the
GitOps/Helm/CICD generators) before handing everything to `ScoringEngine`.

## Terraform Plan Reader

`Asgard/Volundr/Validation/services/terraform_plan_reader.py` reads a
`terraform show -json` plan and reports on `after_unknown` values using
the same `<computed>`/`<tainted>` sentinel handling as the schema binder.
It is wired into the CLI as:

```bash
python -m Volundr validate terraform --plan tfplan.json
```

as an alternative to validating a static `.tf`/module `path` — see
[CLI-Reference.md](CLI-Reference.md).

## Related

- [Scoring.md](Scoring.md) — how `ValidationResult` findings become a composite score
- [CICD-Module.md](CICD-Module.md), [Terraform-Module.md](Terraform-Module.md), [Kubernetes-Module.md](Kubernetes-Module.md), [Kustomize-Module.md](Kustomize-Module.md), [Helm-Module.md](Helm-Module.md), [GitOps-Module.md](GitOps-Module.md) — generators consuming this engine
