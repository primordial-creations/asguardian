# Volundr - GitOps Module

## Overview

The GitOps module generates ArgoCD and Flux manifests — `Application`,
`AppProject`, `GitRepository`, `Kustomization` — with the guard rails
identified in RESEARCH_05 (App-of-Apps sprawl, `default` project overuse,
unpinned `HEAD` revisions).

Generated manifests are never self-graded: every generator method converts
its validation issues into `ValidationResult` findings and scores them
through the shared `ScoringEngine` composite (plan 07, "generators never
grade their own intent") — the same engine used by CICD, Terraform, and
Helm.

## Models

### GitOpsProvider

- `ARGOCD`
- `FLUX`

### ArgoApplication

```python
from Asgard.Volundr.GitOps.models.gitops_models import (
    ArgoApplication, ArgoSource, ArgoDestination, SyncPolicy,
)

app = ArgoApplication(
    name="my-app",
    project="my-team",              # avoid "default" — VOL-GITOPS-0002
    source=ArgoSource(
        repo_url="https://github.com/org/repo.git",
        target_revision="v1.2.0",   # pinned; "HEAD" fails VOL-GITOPS-0001
        path="deploy/production",
    ),
    destination=ArgoDestination(namespace="production"),
    sync_policy=SyncPolicy(automated=True, prune=True, self_heal=True),
)
```

### ArgoAppProject

Scoped alternative to the unrestricted `default` AppProject, with
`source_repos` / `destinations` allowlists so `VOL-GITOPS-0002` can
actually be satisfied instead of just suppressed.

### GitOpsPolicy

Org-level guard rails (`allowed_repo_patterns`, `allowed_destination_servers`)
consulted by `VOL-GITOPS-0003`/`VOL-GITOPS-0004`. Empty lists mean "no
restriction declared" — nothing is flagged until patterns exist.

### FluxGitRepository / FluxKustomization

```python
from Asgard.Volundr.GitOps.models.gitops_models import (
    FluxGitRepository, FluxKustomization,
)

git_repo = FluxGitRepository(
    name="my-app-repo",
    url="https://github.com/org/repo.git",
    branch="main",
    interval="1m",
)

kustomization = FluxKustomization(
    name="my-app",
    source_ref_name="my-app-repo",
    path="./kustomize/overlays/production",
    target_namespace="production",
    prune=True,
    health_checks=[{
        "apiVersion": "apps/v1", "kind": "Deployment",
        "name": "my-app", "namespace": "production",
    }],
)
```

## Services

### ArgoCDGenerator (`Asgard/Volundr/GitOps/services/argocd_generator.py`)

- `generate_application(app)` — a single Application manifest
- `generate_app_project(project)` — a scoped AppProject manifest
- `generate_app_of_apps(name, applications)` — a root Application whose
  source path contains child Application manifests

Also defines `_issues_to_findings(issues, target)`, reused by the Flux and
Helm generators to convert `"RULE-ID: message"` issue strings into
`ValidationResult` objects the shared `ScoringEngine` can score.

### FluxGenerator (`Asgard/Volundr/GitOps/services/flux_generator.py`)

- `generate_git_repository(git_repo)` — GitRepository manifest,
  scored from `validate_git_repository` findings
- `generate_kustomization(kustomization)` — Kustomization manifest,
  scored from `validate_kustomization` findings
- `generate_from_repo(name, repo_url, path, branch, ...)` — convenience
  wrapper producing a matched GitRepository + Kustomization pair
- `generate_multi_env(name, repo_url, base_path, environments, branch)` —
  one GitRepository plus one Kustomization per environment, wired with
  `depends_on` so `staging` waits on `development` and `production` waits
  on `staging`

All four methods return a `GeneratedGitOpsConfig` whose
`best_practice_score` is `ScoringEngine().score(findings, ...).composite`
— computed from the actual accumulated issues across every generated file,
not a fixed constant. (`generate_multi_env` previously hardcoded
`best_practice_score=90.0` regardless of the real findings; this was a
dead-code bug — `all_issues` was declared but never populated — fixed
alongside the ScoringEngine wiring.)

## Validation Rules

Selected `VOL-GITOPS-*` rules enforced by the four-tier Validation engine
(see [Validation-Module.md](Validation-Module.md)):

| Rule | Severity | Check |
|------|----------|-------|
| VOL-GITOPS-0001 | HIGH | `targetRevision` must not be `HEAD` — pin to branch/tag/SHA |
| VOL-GITOPS-0002 | MEDIUM | `project` must not be the unrestricted `default` AppProject |
| VOL-GITOPS-0003 | HIGH | source `repoURL` must match a `GitOpsPolicy` allowlist pattern, once declared |
| VOL-GITOPS-0004 | HIGH | destination `server` must match a `GitOpsPolicy` allowlist pattern, once declared |

## CLI Usage

```bash
# ArgoCD Application
python -m Volundr gitops argocd --name my-app --repo-url https://github.com/org/repo.git \
  --path deploy/production --namespace production

# Flux GitRepository + Kustomization pair
python -m Volundr gitops flux --name my-app --repo-url https://github.com/org/repo.git \
  --path kustomize/overlays/production
```

## Related

- [Kustomize-Module.md](Kustomize-Module.md) — bases/overlays referenced by `path`
- [Helm-Module.md](Helm-Module.md) — charts referenced by ArgoCD's `source.helm`
- [Validation-Module.md](Validation-Module.md) — the four-tier engine that scores generated manifests
- [Scoring.md](Scoring.md) — the composite scoring model
