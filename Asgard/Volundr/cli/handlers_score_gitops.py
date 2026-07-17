"""
CLI handlers for `volundr score` and `volundr gitops validate`.

`volundr score <artifact-or-dir>` renders (kustomize/helm dirs) or reads
an artifact, validates it through the four-tier Validation engine, then
computes the composite ScoreReport: letter grade, per-dimension scores,
and remediation hints. Exits non-zero when the composite falls below the
threshold.

`volundr gitops validate <manifest>` checks ArgoCD Application manifests
against the VOL-GITOPS rules (HEAD pinning, default AppProject, prune
blast radius, Helm version ranges).
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


# ---------------------------------------------------------------- score

def _detect_artifact_kind(path: Path) -> Tuple[str, Optional[str]]:
    """Return (kind, content). kind in {kustomize, helm, kubernetes,
    compose, pipeline}; content is None for rendered directory kinds."""
    if path.is_dir():
        if (path / "Chart.yaml").exists():
            return "helm", None
        if any((path / n).exists()
               for n in ("kustomization.yaml", "kustomization.yml")):
            return "kustomize", None
        return "kubernetes-dir", None

    content = path.read_text(encoding="utf-8", errors="ignore")
    name = path.name.lower()
    try:
        docs = [d for d in yaml.safe_load_all(content) if isinstance(d, dict)]
    except yaml.YAMLError:
        docs = []
    if "compose" in name or any(
        "services" in d and "kind" not in d for d in docs
    ):
        return "compose", content
    if any("jobs" in d and ("on" in d or True in d) for d in docs):
        # PyYAML parses a bare `on:` key as boolean True.
        return "pipeline", content
    return "kubernetes", content


def _validate_artifact(path: Path):
    """Run the Validation engine over the artifact; returns the report."""
    from Asgard.Volundr.Validation.services.render_pipeline import (
        render_and_validate,
    )
    from Asgard.Volundr.Validation.services.validation_engine import (
        ValidationEngine,
    )

    kind, content = _detect_artifact_kind(path)
    if kind in ("kustomize", "helm"):
        return render_and_validate(str(path), kind=kind)

    engine = ValidationEngine()
    if kind == "kubernetes-dir":
        parts: List[str] = []
        for f in sorted(path.rglob("*.y*ml")):
            try:
                parts.append(f.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
        return engine.validate_kubernetes(
            "\n---\n".join(parts), source=str(path)
        )
    if kind == "compose":
        return engine.validate_compose(content or "", source=str(path))
    if kind == "pipeline":
        return engine.validate_pipeline(content or "", source=str(path))
    return engine.validate_kubernetes(content or "", source=str(path))


def run_score(args: argparse.Namespace) -> int:
    """`volundr score <artifact-or-dir>`."""
    from Asgard.Volundr.Validation.services.scoring_engine import (
        score_report_from_validation,
    )

    path = Path(args.path)
    if not path.exists():
        print(f"Error: Path does not exist: {path}")
        return 2

    try:
        report = _validate_artifact(path)
    except Exception as e:
        print(f"Error: Could not validate artifact: {e}")
        return 2

    score = score_report_from_validation(
        report, environment=getattr(args, "environment", "production")
    )

    output_format = getattr(args, "format", "text")
    if output_format == "json":
        payload = (score.model_dump(mode="json")
                   if hasattr(score, "model_dump") else score.dict())
        print(json.dumps(payload, indent=2, default=str))
    else:
        lines = ["", "VOLUNDR ARTIFACT SCORE", "=" * 60,
                 f"  Artifact:   {path}",
                 f"  Composite:  {score.composite:.1f}/100  "
                 f"(grade {score.grade})",
                 f"  Findings:   {score.total_findings}  "
                 f"(suppressed: {score.suppressed_count})"]
        if score.veto_applied:
            lines.append(f"  Security veto applied: {score.veto_applied}")
        for dim in score.dimensions:
            dim_name = getattr(dim.dimension, "value", dim.dimension)
            lines.append(f"    {dim_name:16} {dim.score:.1f}")
        if score.remediation:
            lines.append("")
            lines.append("  Remediation hints (highest impact first):")
            for hint in score.remediation[:10]:
                lines.append(
                    f"    - [{hint.rule_id}] {hint.message} "
                    f"(effort: {hint.effort})"
                    if hasattr(hint, "message") and hasattr(hint, "effort")
                    else f"    - {hint}"
                )
        lines.append("")
        print("\n".join(lines))

    threshold = float(getattr(args, "threshold", 50.0))
    return 1 if score.composite < threshold else 0


# ---------------------------------------------------------------- gitops

def _manifest_to_application(doc: Dict[str, Any]):
    """Coerce a raw ArgoCD Application manifest into ArgoApplication."""
    from Asgard.Volundr.GitOps.models.gitops_models import (
        ArgoApplication,
        ArgoDestination,
        ArgoSource,
        ArgoSourceHelm,
        SyncPolicy,
    )

    metadata = doc.get("metadata", {}) or {}
    spec = doc.get("spec", {}) or {}
    source = spec.get("source", {}) or {}
    destination = spec.get("destination", {}) or {}
    sync = spec.get("syncPolicy", {}) or {}
    automated = sync.get("automated")

    helm = None
    if source.get("chart"):
        helm = ArgoSourceHelm(
            chart=source.get("chart", ""),
            repo_url=source.get("repoURL", ""),
            target_revision=source.get("targetRevision", "*"),
        )

    return ArgoApplication(
        name=metadata.get("name", ""),
        namespace=metadata.get("namespace", "argocd"),
        project=spec.get("project", "default"),
        source=ArgoSource(
            repo_url=source.get("repoURL", ""),
            target_revision=source.get("targetRevision", "main"),
            path=source.get("path", "."),
            helm=helm,
        ),
        destination=ArgoDestination(
            server=destination.get(
                "server", "https://kubernetes.default.svc"
            ),
            namespace=destination.get("namespace", ""),
        ),
        sync_policy=SyncPolicy(
            automated=automated is not None,
            prune=bool((automated or {}).get("prune", False)),
            self_heal=bool((automated or {}).get("selfHeal", False)),
        ),
        finalizers=metadata.get("finalizers", []) or [],
    )


def run_gitops_validate(args: argparse.Namespace) -> int:
    """`volundr gitops validate <manifest>`."""
    from Asgard.Volundr.GitOps.services.argocd_generator_helpers import (
        validate_application,
    )

    path = Path(args.path)
    if not path.exists():
        print(f"Error: Path does not exist: {path}")
        return 2

    files = ([path] if path.is_file()
             else sorted(path.rglob("*.y*ml")))
    total_issues = 0
    applications = 0
    results: List[Dict[str, Any]] = []

    for f in files:
        try:
            docs = list(yaml.safe_load_all(
                f.read_text(encoding="utf-8", errors="ignore")
            ))
        except (yaml.YAMLError, OSError) as e:
            print(f"Error: Could not parse {f}: {e}")
            return 2
        for doc in docs:
            if not isinstance(doc, dict) or doc.get("kind") != "Application":
                continue
            applications += 1
            try:
                app = _manifest_to_application(doc)
            except Exception as e:
                print(f"Error: Invalid Application manifest in {f}: {e}")
                total_issues += 1
                continue
            issues = validate_application(app)
            total_issues += len(issues)
            results.append({
                "file": str(f),
                "application": app.name,
                "issues": issues,
            })

    output_format = getattr(args, "format", "text")
    if output_format == "json":
        print(json.dumps({
            "applications": applications,
            "total_issues": total_issues,
            "results": results,
        }, indent=2))
    else:
        lines = ["", "VOLUNDR GITOPS VALIDATION", "=" * 60]
        if applications == 0:
            lines.append("  No ArgoCD Application manifests found.")
        for r in results:
            lines.append(f"  Application '{r['application']}' ({r['file']}):")
            if r["issues"]:
                for issue in r["issues"]:
                    lines.append(f"    ! {issue}")
            else:
                lines.append("    No issues.")
        lines.append("")
        lines.append(f"  Applications: {applications}  Issues: {total_issues}")
        print("\n".join(lines))

    if applications == 0:
        return 2
    return 1 if total_issues > 0 else 0
