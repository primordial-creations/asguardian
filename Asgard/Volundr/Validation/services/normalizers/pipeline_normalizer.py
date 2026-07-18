"""Tier 3 normalizer: CI pipeline YAML (GitHub Actions first) -> canonical jobs."""

from typing import Any, Dict, List, Optional

from Asgard.Volundr.Validation.models.canonical_models import (
    CanonicalPipelineJob,
    CanonicalPipelineStep,
)


def normalize_github_workflow(
    workflow: Dict[str, Any],
    file_path: Optional[str] = None,
) -> List[CanonicalPipelineJob]:
    """Normalize a GitHub Actions workflow dict into canonical pipeline jobs."""
    workflow_permissions = workflow.get("permissions")
    jobs: List[CanonicalPipelineJob] = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        steps = []
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            steps.append(CanonicalPipelineStep(
                name=str(step.get("name", "")),
                uses=step.get("uses"),
                run=step.get("run"),
                env=step.get("env") if isinstance(step.get("env"), dict) else {},
                with_params=step.get("with") if isinstance(step.get("with"), dict) else {},
            ))
        jobs.append(CanonicalPipelineJob(
            name=job_name,
            permissions=job.get("permissions"),
            workflow_permissions=workflow_permissions,
            timeout_minutes=job.get("timeout-minutes"),
            steps=steps,
        ))
    return jobs


def looks_like_github_workflow(data: Dict[str, Any]) -> bool:
    return isinstance(data, dict) and "jobs" in data
