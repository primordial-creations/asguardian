# Volundr - Scoring

## Overview

`ScoringEngine` (`Asgard/Volundr/Validation/services/scoring_engine.py`)
turns `ValidationResult` findings from the Validation engine into a
composite `ScoreReport`. It is the single scorer for every generator in
Volundr — CICD, Terraform, Kubernetes, Kustomize, Helm, GitOps — so no
generator can tune its own grading logic to flatter its own output (the
"Collusion Problem", DEEPTHINK_05 §1A).

```python
from Asgard.Volundr.Validation.services.scoring_engine import ScoringEngine

report = ScoringEngine().score(findings, resources=["deployment.yaml", "service.yaml"])
report.composite      # 0-100
report.grade          # letter_grade(composite): A>=90, B>=80, C>=65, D>=50, F<50
```

Scores are computed **exclusively** from findings on the rendered
artifact — never from the generator's input config. Properties enforced
by construction:

- **Subtractive severity penalties**, per logical resource: CRITICAL
  −20, HIGH −10, MEDIUM −5, LOW −2, INFO 0 (`SEVERITY_PENALTY`), floored
  at 0 against a base of 100. Adding a finding can never raise a score.
- **Security veto**: any un-suppressed CRITICAL security finding caps
  the composite at 50; any HIGH security finding caps it at 70
  (`ScoreReport.veto_applied`).
- **Dilution defense**: a clean (zero-finding) resource gets
  `CLEAN_RESOURCE_WEIGHT = 0.05` in the artifact mean instead of full
  weight — padding a report with trivially-secure resources cannot pull
  the composite up.
- **Suppression as receipt, not erasure**: a suppressed finding scores
  as passed but remains visible via `ScoreReport.suppressed_receipts`
  (`SuppressedReceipt(rule_id, target, reason)`) — accepted risk stays
  auditable.
- **Environment profiles change weights only**, never rule outcomes
  (`scoring_profiles.profile_weights(environment)`) — a rule that fires
  in `production` fires identically in `dev`; only how much each
  dimension counts toward the composite shifts.

## Four Dimensions

```python
class ScoreDimension(str, Enum):
    SECURITY = "security"
    OPERABILITY = "operability"
    COMPLETENESS = "completeness"
    MAINTAINABILITY = "maintainability"
```

`CATEGORY_DIMENSION` maps each `ValidationCategory` to a dimension
(`SECURITY`→Security, `RELIABILITY`/`PERFORMANCE`→Operability,
`SCHEMA`/`SYNTAX`→Completeness, `BEST_PRACTICE`/`MAINTAINABILITY`→
Maintainability). A small allowlist, `COMPLETENESS_RULES` (e.g.
`VOL-K8S-0013/14/15`, `VOL-DOCKER-DIGEST`), is always scored as
Completeness regardless of its nominal category — these are "nutrition
label" gaps (missing declarations) rather than defects.

## Scoring a Batch of Findings

```python
def score(
    self,
    findings: Iterable[ValidationResult],
    resources: Optional[Iterable[str]] = None,
    environment: str = "production",
    suppressed: Optional[Iterable[Tuple[Any, ValidationResult]]] = None,
) -> ScoreReport: ...
```

- `findings` — surviving (un-suppressed) findings from the Validation
  engine on the rendered artifact.
- `resources` — the full universe of logical resource names, so clean
  resources still appear in `resource_scores` at near-zero weight rather
  than being invisible.
- `environment` — selects the weight profile (`production` by default).
- `suppressed` — `(suppression, finding)` pairs the suppression engine
  annihilated; reported as receipts, never penalized.

`ScoringEngine.resource_key(result)` picks the grouping key for a
finding in priority order: `result.resource_name`, then
`result.context["target"]`, then `result.file_path`, falling back to the
literal string `"artifact"` if none are set — this is how a generator's
`_issues_to_findings(issues, target)` helper (present in the CICD, GitOps,
and Helm generators) attaches every finding to the resource it belongs to
before scoring.

## ScoreReport

```python
class ScoreReport(BaseModel):
    composite: float                       # 0-100
    grade: str                             # letter_grade(composite)
    environment: str
    dimensions: List[DimensionScore]       # one per ScoreDimension, weighted
    resource_scores: List[ResourceScore]   # per-logical-resource defect density
    resource_density_score: float
    veto_applied: Optional[str]            # "critical" | "high" | None
    remediation: List[RemediationHint]     # rule_id, message, effort estimate
    suppressed_count: int
    suppressed_receipts: List[SuppressedReceipt]
    total_findings: int
    created_at: datetime
```

`ScoreReport.delta(baseline)` (plan 07 §2.2) returns the per-dimension and
composite change versus an earlier `ScoreReport` — useful for CI gates
that compare a PR's rendered output against the target branch's.

## Convention: `_issues_to_findings`

Generators that predate a full `ValidationEngine` pass for their domain
(GitOps, Helm) still emit ad-hoc `"RULE-ID: message"` issue strings from
domain-specific `validate_*` helpers. Each such generator defines a local
`_issues_to_findings(issues, target)` that:

1. Splits `"RULE-ID: message"` on the first `:`.
2. Looks the rule ID up in `default_registry()` to recover its real
   `severity`/`category`/`remediation`.
3. Falls back to a generic `"helm-check"`/`"gitops-check"` rule ID at
   `WARNING`/`BEST_PRACTICE` when the issue string carries no recognized
   rule ID.

This keeps every generator's issues on the same `ValidationResult` shape
`ScoringEngine.score()` expects, without requiring every domain to be
fully re-implemented as Tier 4 semantic-policy rules before it can be
scored fairly.

## Anti-Gaming Test Pattern

Because scoring changes are high-leverage (a bug here silently raises
every generator's reported quality), scoring-affecting changes in this
codebase are expected to ship with an adversarial test that proves the
score actually responds to real content — not just file/field presence.
Example (`Asgard_Test/tests_Volundr/test_helm.py`,
`TestScoringEngineWiring.test_missing_resources_lowers_score_via_shared_engine`):
a chart with real resource limits scores `100.0`, while feeding
`validate_chart` a `values.yaml` that omits resource declarations
produces a finding — proving the composite is earned from content, not
handed out for having a `values.yaml` file at all.

## Related

- [Validation-Module.md](Validation-Module.md) — where `ValidationResult` findings come from
- [CICD-Module.md](CICD-Module.md), [Terraform-Module.md](Terraform-Module.md), [GitOps-Module.md](GitOps-Module.md), [Helm-Module.md](Helm-Module.md), [Kustomize-Module.md](Kustomize-Module.md) — generators scored by this engine
