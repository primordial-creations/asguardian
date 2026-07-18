# Volundr - Kustomize Module

## Overview

The Kustomize module generates bases, environment overlays, patches, and
components using Kustomize v5 semantics (RESEARCH_09): `labels`
transformer instead of `commonLabels`, `replacements` instead of `vars`,
and array field paths addressed by semantic key rather than index.

Every generator (`BaseGenerator`, `OverlayGenerator`, `PatchGenerator`,
`ComponentGenerator`) renders its files, re-parses the `kustomization.yaml`
and any Kubernetes manifests through the shared `ValidationEngine`, and
scores the resulting findings with `ScoringEngine` (plan 07) — the
`best_practice_score` on `GeneratedKustomization` is always
`score_report.composite`, never a hand-tuned percentage.

## Models

### KustomizeBase

```python
from Asgard.Volundr.Kustomize.models.kustomize_models import KustomizeBase

base = KustomizeBase(
    name="my-app",
    namespace="default",
    resources=["deployment.yaml", "service.yaml"],
    common_labels={"app.kubernetes.io/name": "my-app"},
    labels_include_selectors=False,   # True only for a base never yet applied
)
```

`common_labels` is rendered via the v5 `labels` transformer, not the
deprecated `commonLabels` field — `commonLabels` mutates immutable
Service/Deployment selectors on a live cluster (`VOL-KUST-COMMONLABELS`).

### Replacement (the `vars` successor)

```python
from Asgard.Volundr.Kustomize.models.kustomize_models import (
    Replacement, ReplacementSource, ReplacementTarget, ReplacementTargetSelect,
)

Replacement(
    source=ReplacementSource(kind="ConfigMap", name="app-config", field_path="data.image_tag"),
    targets=[ReplacementTarget(
        select=ReplacementTargetSelect(kind="Deployment", name="my-app"),
        field_paths=["spec.template.spec.containers.[name=app].image"],
    )],
)
```

Target field paths should address containers/ports by semantic key
(`[name=app]`), never by numeric index — index-based paths silently point
at the wrong element after an unrelated container is added or reordered.

### KustomizePatch

Supports `PatchType.STRATEGIC_MERGE` (inline YAML `patch_content`) and
`PatchType.JSON6902` (`target` + `operations: List[JsonPatchOperation]`).

### ConfigMapGenerator / SecretGenerator

Standard Kustomize generators (`files`, `literals`, `envs`, `behavior`).
Secrets generated this way are still subject to the same
no-plaintext-secret validation rules as hand-written manifests.

### KustomizeOverlay / KustomizeComponent

An overlay references a base path plus per-environment replica counts,
resource patches, and image overrides; a component is a reusable,
independently-includable bundle of resources/patches/generators.

## Services

- `BaseGenerator.generate(config)` → `base/kustomization.yaml` +
  deployment/service/hpa/networkpolicy manifests, scored via
  `ValidationEngine.validate_kubernetes` per file plus
  `kustomization_findings` for the `kustomization.yaml` itself
- `OverlayGenerator.generate(overlay, base_path, app_name)` →
  `overlays/<env>/kustomization.yaml` + replica/resource patch files,
  with environment defaults pulled from `ENV_DEFAULTS`
- `PatchGenerator` — standalone strategic-merge / JSON6902 patch files
- `ComponentGenerator` — reusable Kustomize components

## Validation Rules

Key `VOL-KUST-*` checks run against the rendered `kustomization.yaml`
(`kustomization_findings`) in addition to the standard `VOL-K8S-*` rules
applied to each generated manifest:

| Rule | Check |
|------|-------|
| VOL-KUST-COMMONLABELS | `commonLabels` used instead of the v5 `labels` transformer |
| VOL-KUST-VARS | deprecated `vars:` used instead of `replacements:` |
| VOL-KUST-INDEXPATH | a replacement/patch field path addresses an array by numeric index |

## CLI Usage

```bash
# Base
python -m Volundr kustomize init --name my-app --namespace default --output-dir kustomize

# Overlay
python -m Volundr kustomize overlay --name production --replicas 5 --output-dir kustomize
```

## Related

- [Kubernetes-Module.md](Kubernetes-Module.md) — manifests referenced as Kustomize `resources`
- [GitOps-Module.md](GitOps-Module.md) — ArgoCD/Flux point at Kustomize overlay paths
- [Validation-Module.md](Validation-Module.md) — the shared engine scoring rendered output
- [Scoring.md](Scoring.md) — the composite scoring model
