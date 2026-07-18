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


_GITLAB_RESERVED_KEYS = {
    "stages", "variables", "default", "workflow", "include", "image",
    "services", "before_script", "after_script", "cache", "id_tokens",
}


def looks_like_gitlab_ci(data: Dict[str, Any]) -> bool:
    """A GitLab CI doc has ``stages:`` plus dict-valued job entries with a
    ``script``/``stage`` key (distinguishes it from a GH Actions workflow,
    which uses ``jobs:``)."""
    if not isinstance(data, dict) or "jobs" in data:
        return False
    if "stages" not in data:
        return False
    return any(
        isinstance(v, dict) and ("script" in v or "stage" in v)
        for k, v in data.items() if k not in _GITLAB_RESERVED_KEYS
    )


def normalize_gitlab_ci(
    pipeline: Dict[str, Any],
    file_path: Optional[str] = None,
) -> List[CanonicalPipelineJob]:
    """Normalize a GitLab CI pipeline dict into canonical pipeline jobs.

    GitLab has no per-job ``permissions:`` token block, so
    ``permissions``/``workflow_permissions`` are set to ``{}`` (present but
    empty) rather than ``None`` — this deliberately opts jobs out of the
    GHA-specific "missing permissions block" rule (VOL-CICD-0001) instead of
    false-positiving on a platform that has no such concept, while timeout,
    injection, and static-secret checks (which are platform-agnostic) still
    run against these jobs.
    """
    jobs: List[CanonicalPipelineJob] = []
    for job_name, job in pipeline.items():
        if job_name in _GITLAB_RESERVED_KEYS or not isinstance(job, dict):
            continue
        if "script" not in job and "stage" not in job:
            continue
        scripts = job.get("script") or []
        if isinstance(scripts, str):
            scripts = [scripts]
        steps = [
            CanonicalPipelineStep(name=job_name, run=str(s))
            for s in scripts if isinstance(s, str)
        ]
        job_variables = job.get("variables")
        if isinstance(job_variables, dict) and job_variables:
            # Job-scoped CI/CD variables are GitLab's nearest analogue to a
            # step's ``env:`` block; attach so the static-secret rule can
            # inspect their values (a variable is not tied to one script
            # line, so it is modeled on a synthetic step).
            steps.append(CanonicalPipelineStep(name=f"{job_name}:variables", env=job_variables))
        timeout = job.get("timeout")
        jobs.append(CanonicalPipelineJob(
            name=job_name,
            permissions={},
            workflow_permissions={},
            timeout_minutes=timeout,
            steps=steps,
        ))
    return jobs


def looks_like_azure_pipeline(data: Dict[str, Any]) -> bool:
    return isinstance(data, dict) and "stages" in data and "trigger" in data


def normalize_azure_pipeline(
    pipeline: Dict[str, Any],
    file_path: Optional[str] = None,
) -> List[CanonicalPipelineJob]:
    """Normalize an Azure DevOps pipeline dict into canonical pipeline jobs.

    Azure DevOps has no per-job ``permissions:`` token block either;
    ``permissions``/``workflow_permissions`` are set to ``{}`` for the same
    reason as GitLab (see ``normalize_gitlab_ci``).
    """
    jobs: List[CanonicalPipelineJob] = []
    for stage in pipeline.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        for job in stage.get("jobs") or []:
            if not isinstance(job, dict):
                continue
            job_name = str(job.get("job") or job.get("displayName") or "job")
            steps = []
            for step in job.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                script = step.get("script") or step.get("bash") or step.get("powershell")
                steps.append(CanonicalPipelineStep(
                    name=str(step.get("displayName", "")),
                    run=script,
                ))
            job_variables = job.get("variables")
            if isinstance(job_variables, dict) and job_variables:
                steps.append(CanonicalPipelineStep(
                    name=f"{job_name}:variables", env=job_variables,
                ))
            jobs.append(CanonicalPipelineJob(
                name=job_name,
                permissions={},
                workflow_permissions={},
                timeout_minutes=job.get("timeoutInMinutes"),
                steps=steps,
            ))
    return jobs
