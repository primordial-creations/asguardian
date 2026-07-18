# Volundr - Helm Module

## Overview

The Helm module generates complete chart structures — `Chart.yaml`,
`values.yaml`, `values.schema.json`, templates, hooks, and helpers — with
security and operability defaults baked in (non-root security context,
resource requests/limits, probes, `.helmignore`).

`ChartGenerator.generate()` renders every file, runs `validate_chart` over
the result, converts the issues into `ValidationResult` findings, and
scores them with the shared `ScoringEngine` (plan 07) — the chart never
grades its own intent via a local fixed-weight percentage.

## Models

### HelmChart (`Chart.yaml`)

```python
from Asgard.Volundr.Helm.models.helm_models import HelmChart, HelmConfig, HelmValues

config = HelmConfig(
    chart=HelmChart(
        name="my-app",
        version="0.1.0",
        app_version="1.0.0",
        description="My application chart",
        maintainers=[{"name": "Platform Team", "email": "platform@example.com"}],
    ),
    values=HelmValues(image_repository="myorg/my-app", image_tag="1.0.0"),
)
```

### HelmValues (`values.yaml`)

Covers `replica_count`, `image` (repository/pullPolicy/tag),
`service_account`, `pod_security_context` / `security_context`
(`run_as_non_root`, `read_only_root_filesystem`,
`allow_privilege_escalation`), `service`, `ingress`, `resources`
(`ResourceRequirements` limits/requests), `autoscaling` (HPA),
`liveness_probe` / `readiness_probe`, `node_selector`, `tolerations`,
`affinity`, plus `env`/`volumes`/`volume_mounts`/`extra_config` for
arbitrary passthrough. `image_repository` is the only required field.

### GeneratedHelmChart

Result type returned by `ChartGenerator.generate()`:

```python
class GeneratedHelmChart(BaseModel):
    id: str
    config_hash: str
    chart_files: Dict[str, str]           # path -> rendered content
    validation_results: List[str]
    best_practice_score: float            # ScoringEngine composite, 0-100
    created_at: datetime
```

## Services

### ChartGenerator (`Asgard/Volundr/Helm/services/chart_generator.py`)

`generate(config)` produces:

| File | Notes |
|------|-------|
| `Chart.yaml` | |
| `values.yaml` | built once via `_build_values_data()`, reused for the schema below |
| `values.schema.json` | draft-07 JSON Schema, types inferred directly from the same `values_data` dict that rendered `values.yaml` — the schema cannot drift from the values it validates (plan 05) |
| `templates/deployment.yaml`, `service.yaml` | always generated |
| `templates/_helpers.tpl` | if `config.generate_helpers` |
| `templates/NOTES.txt` | if `config.generate_notes`; never dereferences `.Values.secret*` or prints Secret data |
| `templates/serviceaccount.yaml`, `hpa.yaml`, `ingress.yaml`, `networkpolicy.yaml`, `pdb.yaml`, `configmap.yaml`, `secret.yaml` | gated on the matching `config.include_*` flag |
| `templates/tests/test-connection.yaml` | if `config.generate_tests`; carries `helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded` so a stale test pod from a prior release never blocks or accumulates across re-installs (plan 05 hook hygiene) |
| `.helmignore` | |

`_generate_values_schema(values_data)` walks the values dict and maps
Python types to JSON Schema primitives (`bool`→boolean, `int`→integer,
`float`→number, `str`→string, `list`→array with an `items` schema from the
first element, `dict`→object with per-key `properties`). All objects set
`additionalProperties: true` since charts commonly accept passthrough
values via `extra_config`.

`best_practice_score` = `ScoringEngine().score(findings, resources=[config.chart.name]).composite`,
where `findings` is `_issues_to_findings(validate_chart(...), config.chart.name)` —
the same conversion helper pattern used by the GitOps generators.

## Validation

`validate_chart(chart_files, config)` (in `_chart_generator_extras_part2.py`)
checks rendered output for missing resource requests/limits, missing
probes, `latest` image tags, and disabled security-context flags. Findings
route through the shared four-tier `ValidationEngine`/`ScoringEngine`
rather than a chart-local scoring function.

## CLI Usage

```bash
# Initialize a new chart
python -m Volundr helm init --name my-app --output-dir charts

# Generate values.yaml for an environment
python -m Volundr helm values --name my-app --environment production
```

## Related

- [Kubernetes-Module.md](Kubernetes-Module.md) — the manifest shapes Helm templates render
- [GitOps-Module.md](GitOps-Module.md) — ArgoCD's `source.helm` deploys generated charts
- [Validation-Module.md](Validation-Module.md) — the shared four-tier engine
- [Scoring.md](Scoring.md) — the composite scoring model
