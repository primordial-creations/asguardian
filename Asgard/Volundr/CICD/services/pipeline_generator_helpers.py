"""
Platform emitters for zero-trust CI/CD pipeline generation.

Zero-trust by construction (DEEPTHINK_04):
- ``permissions: {}`` at workflow level; each job gets explicit
  least-privilege scopes (default ``contents: read``).
- Every well-known action SHA-pinned with a trailing version comment.
- ``${{ ... }}`` never appears inside ``run:`` — expressions are hoisted
  into ``env:`` variables (interpolation immunity).
- ``timeout-minutes`` on every job; default ``concurrency`` with
  ``cancel-in-progress`` for PR-triggered workflows.
- OIDC token exchange over static secrets; optional SLSA provenance,
  SBOM, harden-runner egress hardening, and build/deploy trust split.
"""

from typing import Any, Dict, List, Optional, Tuple, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.CICD.models.cicd_models import (
    CICDPlatform,
    OIDCConfig,
    OIDCProvider,
    PipelineConfig,
    PipelineStage,
    TriggerType,
)
from Asgard.Volundr.CICD.services.action_pins import (
    annotate_pinned_uses,
    pinned,
    resolve_action_ref,
)
from Asgard.Volundr.CICD.services.context_hardening import harden_steps

DEFAULT_JOB_PERMISSIONS: Dict[str, str] = {"contents": "read"}
DEFAULT_TIMEOUT_MINUTES = 30


def _job_id(name: str) -> str:
    return name.lower().replace(" ", "-")


def _is_deploy_stage(stage: PipelineStage) -> bool:
    """A stage is deploy-trusted if it targets an environment or is named so."""
    if stage.environment:
        return True
    return "deploy" in stage.name.lower()


def _oidc_steps(oidc: OIDCConfig) -> List[Dict[str, Any]]:
    """Token-exchange step(s) for the configured OIDC provider."""
    if oidc.provider == OIDCProvider.AWS:
        with_params: Dict[str, Any] = {"role-to-assume": oidc.role}
        with_params["aws-region"] = oidc.region or "us-east-1"
        if oidc.audience:
            with_params["audience"] = oidc.audience
        return [{
            "name": "Configure AWS credentials (OIDC)",
            "uses": pinned("aws-actions/configure-aws-credentials@v4"),
            "with": with_params,
        }]
    if oidc.provider == OIDCProvider.GCP:
        with_params = {"workload_identity_provider": oidc.role}
        if oidc.service_account:
            with_params["service_account"] = oidc.service_account
        return [{
            "name": "Authenticate to Google Cloud (OIDC)",
            "uses": pinned("google-github-actions/auth@v2"),
            "with": with_params,
        }]
    if oidc.provider == OIDCProvider.AZURE:
        return [{
            "name": "Azure login (OIDC)",
            "uses": pinned("azure/login@v2"),
            "with": {
                "client-id": "${{ vars.AZURE_CLIENT_ID }}",
                "tenant-id": "${{ vars.AZURE_TENANT_ID }}",
                "subscription-id": "${{ vars.AZURE_SUBSCRIPTION_ID }}",
            },
        }]
    # Vault
    with_params = {"method": "jwt", "role": oidc.role}
    if oidc.vault_url:
        with_params["url"] = oidc.vault_url
    return [{
        "name": "Vault OIDC login",
        "uses": pinned("hashicorp/vault-action@v3"),
        "with": with_params,
    }]


def _render_step(step: Any) -> Dict[str, Any]:
    step_dict: Dict[str, Any] = {"name": step.name}
    if step.uses:
        pinned_ref, _version = resolve_action_ref(step.uses)
        step_dict["uses"] = pinned_ref
        if step.with_params:
            step_dict["with"] = step.with_params
    elif step.run:
        step_dict["run"] = step.run
    if step.env:
        step_dict["env"] = step.env
    if step.if_condition:
        step_dict["if"] = step.if_condition
    if step.continue_on_error:
        step_dict["continue-on-error"] = step.continue_on_error
    if step.timeout_minutes:
        step_dict["timeout-minutes"] = step.timeout_minutes
    return step_dict


def _render_github_job(
    stage: PipelineStage, config: PipelineConfig, is_deploy: bool
) -> Dict[str, Any]:
    job: Dict[str, Any] = {"runs-on": stage.runs_on}

    permissions: Dict[str, str] = dict(
        stage.permissions if stage.permissions is not None
        else DEFAULT_JOB_PERMISSIONS
    )
    if is_deploy and config.oidc is not None:
        permissions.setdefault("id-token", "write")
    job["permissions"] = permissions

    if stage.needs:
        job["needs"] = [_job_id(n) for n in stage.needs]
    if stage.if_condition:
        job["if"] = stage.if_condition

    job["timeout-minutes"] = stage.timeout_minutes or DEFAULT_TIMEOUT_MINUTES

    if stage.continue_on_error:
        job["continue-on-error"] = stage.continue_on_error
    if stage.env:
        job["env"] = stage.env
    if stage.environment:
        job["environment"] = stage.environment
    if stage.services:
        job["services"] = stage.services
    if stage.strategy:
        job["strategy"] = stage.strategy

    steps: List[Dict[str, Any]] = []
    if config.harden_runner:
        steps.append({
            "name": "Harden runner (egress audit)",
            "uses": pinned("step-security/harden-runner@v2"),
            "with": {"egress-policy": "audit"},
        })
    if is_deploy and config.oidc is not None:
        steps.extend(_oidc_steps(config.oidc))

    for step in harden_steps(stage.steps):
        steps.append(_render_step(step))

    if config.sbom and not is_deploy:
        steps.append({
            "name": "Generate SBOM",
            "uses": pinned("anchore/sbom-action@v0"),
            "with": {"format": "spdx-json", "output-file": "sbom.spdx.json"},
        })

    job["steps"] = steps
    return job


def _github_triggers(config: PipelineConfig) -> Tuple[Dict[str, Any], bool]:
    on_triggers: Dict[str, Any] = {}
    has_pr = False
    for trigger in config.triggers:
        if trigger.type == TriggerType.PUSH:
            push_config: Dict[str, Any] = {}
            if trigger.branches:
                push_config["branches"] = trigger.branches
            if trigger.paths:
                push_config["paths"] = trigger.paths
            if trigger.paths_ignore:
                push_config["paths-ignore"] = trigger.paths_ignore
            if trigger.tags:
                push_config["tags"] = trigger.tags
            on_triggers["push"] = push_config if push_config else None
        elif trigger.type == TriggerType.PULL_REQUEST:
            has_pr = True
            pr_config: Dict[str, Any] = {}
            if trigger.branches:
                pr_config["branches"] = trigger.branches
            if trigger.paths:
                pr_config["paths"] = trigger.paths
            on_triggers["pull_request"] = pr_config if pr_config else None
        elif trigger.type == TriggerType.SCHEDULE:
            on_triggers["schedule"] = [{"cron": trigger.schedule}]
        elif trigger.type == TriggerType.WORKFLOW_DISPATCH:
            on_triggers["workflow_dispatch"] = {}
    return on_triggers, has_pr


def _provenance_job(config: PipelineConfig, build_job_ids: List[str]) -> Dict[str, Any]:
    return {
        "runs-on": "ubuntu-latest",
        "needs": build_job_ids,
        "permissions": {
            "id-token": "write",
            "attestations": "write",
            "contents": "read",
        },
        "timeout-minutes": 15,
        "steps": [
            {
                "name": "Download build artifacts",
                "uses": pinned("actions/download-artifact@v4"),
                "with": {"path": "dist"},
            },
            {
                "name": "Attest build provenance (SLSA)",
                "uses": pinned("actions/attest-build-provenance@v2"),
                "with": {"subject-path": "dist/**"},
            },
        ],
    }


def _dump(data: Dict[str, Any]) -> str:
    rendered = cast(str, yaml.dump(
        data, default_flow_style=False, sort_keys=False, allow_unicode=True
    ))
    return annotate_pinned_uses(rendered)


def generate_github_actions(config: PipelineConfig) -> str:
    """Render the primary (build/CI) GitHub Actions workflow."""
    content, _files = generate_github_actions_files(config)
    return content


def generate_github_actions_files(
    config: PipelineConfig,
) -> Tuple[str, Dict[str, str]]:
    """Render GitHub Actions workflow file(s).

    Returns ``(primary_content, files)`` where ``files`` maps recommended
    paths to content. With ``split_trust`` and a deploy stage present, a
    second ``workflow_run``-triggered deploy workflow is emitted so the
    untrusted build never holds deploy credentials.
    """
    workflow_name = config.name.lower().replace(" ", "-")
    deploy_stages = [s for s in config.stages if _is_deploy_stage(s)]
    build_stages = [s for s in config.stages if not _is_deploy_stage(s)]
    split = bool(config.split_trust and deploy_stages and build_stages)

    workflow: Dict[str, Any] = {"name": config.name}
    on_triggers, has_pr = _github_triggers(config)
    workflow["on"] = on_triggers
    # Workflow-level default: no token scopes at all.
    workflow["permissions"] = dict(config.permissions)

    if config.env:
        workflow["env"] = config.env

    workflow["concurrency"] = config.concurrency or {
        "group": "${{ github.workflow }}-${{ github.ref }}",
        "cancel-in-progress": bool(has_pr),
    }

    main_stages = build_stages if split else config.stages
    jobs: Dict[str, Any] = {}
    for stage in main_stages:
        is_deploy = _is_deploy_stage(stage) and not split
        jobs[_job_id(stage.name)] = _render_github_job(stage, config, is_deploy)

    if config.provenance:
        build_ids = [_job_id(s.name) for s in main_stages if not _is_deploy_stage(s)]
        jobs["provenance"] = _provenance_job(config, build_ids or list(jobs.keys()))

    workflow["jobs"] = jobs
    primary = _dump(workflow)
    primary_path = f".github/workflows/{workflow_name}.yml"
    files: Dict[str, str] = {primary_path: primary}

    if split:
        deploy_workflow: Dict[str, Any] = {
            "name": f"{config.name} deploy",
            # Trust boundary: deploy only ever runs after the untrusted
            # build workflow completed on the protected repository context.
            "on": {
                "workflow_run": {
                    "workflows": [config.name],
                    "types": ["completed"],
                    "branches": ["main"],
                }
            },
            "permissions": {},
        }
        deploy_jobs: Dict[str, Any] = {}
        for stage in deploy_stages:
            job = _render_github_job(stage, config, is_deploy=True)
            # Deploy stages depend on build stages that live in the other
            # workflow; the workflow_run trigger replaces those edges.
            build_ids = {_job_id(s.name) for s in build_stages}
            if "needs" in job:
                job["needs"] = [n for n in job["needs"] if n not in build_ids]
                if not job["needs"]:
                    del job["needs"]
            job.setdefault(
                "if", "${{ github.event.workflow_run.conclusion == 'success' }}"
            )
            steps = job.get("steps", [])
            steps.insert(0, {
                "name": "Download sealed build artifact",
                "uses": pinned("actions/download-artifact@v4"),
                "with": {
                    "run-id": "${{ github.event.workflow_run.id }}",
                    "github-token": "${{ secrets.GITHUB_TOKEN }}",
                },
            })
            job["permissions"] = {
                **job.get("permissions", {}),
                "actions": "read",
            }
            deploy_jobs[_job_id(stage.name)] = job
        deploy_workflow["jobs"] = deploy_jobs
        files[f".github/workflows/{workflow_name}-deploy.yml"] = _dump(deploy_workflow)

    return primary, files


GITLAB_PEP_HEADER = """\
# Zero-trust notes (Volundr):
# - GitLab has no per-job token permissions block; enforce least privilege
#   via job-scoped CI/CD variables and protected environments.
# - Policy Enforcement Point (PEP) hooks: add `id_tokens:` for OIDC
#   federation and use protected branches + environment approval rules as
#   the deploy trust boundary.
"""


def generate_gitlab_ci(config: PipelineConfig) -> str:
    pipeline: Dict[str, Any] = {}

    stage_names = [_job_id(stage.name) for stage in config.stages]
    pipeline["stages"] = stage_names

    variables: Dict[str, Any] = dict(config.env) if config.env else {}
    if config.provenance:
        # Runner-native SLSA provenance (L2); see PEP header for the L3 path.
        variables["RUNNER_GENERATE_ARTIFACTS_METADATA"] = "true"
    if variables:
        pipeline["variables"] = variables

    for stage in config.stages:
        job_name = _job_id(stage.name)
        job: Dict[str, Any] = {
            "stage": job_name,
            "image": stage.runs_on if ":" in stage.runs_on else f"ubuntu:{stage.runs_on.split('-')[-1] if '-' in stage.runs_on else 'latest'}",
        }

        job["timeout"] = f"{stage.timeout_minutes or DEFAULT_TIMEOUT_MINUTES} minutes"

        if stage.needs:
            job["needs"] = [_job_id(n) for n in stage.needs]

        if stage.env:
            job["variables"] = stage.env

        if stage.services:
            job["services"] = list(stage.services.keys())

        if config.oidc is not None and _is_deploy_stage(stage):
            job["id_tokens"] = {
                "VOLUNDR_ID_TOKEN": {
                    "aud": config.oidc.audience
                    or f"https://{config.oidc.provider.value}.volundr.local"
                }
            }

        scripts: List[str] = []
        for step in stage.steps:
            if step.run:
                scripts.append(step.run)

        if scripts:
            job["script"] = scripts

        if stage.if_condition:
            job["rules"] = [{"if": stage.if_condition}]

        pipeline[job_name] = job

    return GITLAB_PEP_HEADER + cast(str, yaml.dump(
        pipeline, default_flow_style=False, sort_keys=False, allow_unicode=True
    ))


AZURE_HARDENING_HEADER = """\
# Zero-trust notes (Volundr):
# - Prefer Microsoft-hosted (ephemeral) agents; self-hosted agents must be
#   single-use to prevent cross-build contamination.
# - Use workload identity federation (OIDC) service connections instead of
#   secret-bearing service connections.
"""


def generate_azure_devops(config: PipelineConfig) -> str:
    pipeline: Dict[str, Any] = {"name": config.name}

    trigger_config: Dict[str, Any] = {"branches": {"include": []}}
    for trigger in config.triggers:
        if trigger.type == TriggerType.PUSH and trigger.branches:
            trigger_config["branches"]["include"].extend(trigger.branches)

    pipeline["trigger"] = trigger_config

    if config.env:
        pipeline["variables"] = config.env

    stages: List[Dict[str, Any]] = []
    for stage in config.stages:
        stage_dict: Dict[str, Any] = {
            "stage": stage.name.replace(" ", "_"),
            "displayName": stage.name,
        }

        if stage.needs:
            stage_dict["dependsOn"] = [n.replace(" ", "_") for n in stage.needs]

        jobs: List[Dict[str, Any]] = []
        job: Dict[str, Any] = {
            "job": stage.name.replace(" ", "_"),
            "displayName": stage.name,
            "pool": {"vmImage": stage.runs_on},
            "timeoutInMinutes": stage.timeout_minutes or DEFAULT_TIMEOUT_MINUTES,
        }

        if stage.env:
            job["variables"] = stage.env

        steps: List[Dict[str, Any]] = []
        for step in stage.steps:
            if step.run:
                steps.append({
                    "script": step.run,
                    "displayName": step.name,
                })

        job["steps"] = steps
        jobs.append(job)
        stage_dict["jobs"] = jobs
        stages.append(stage_dict)

    pipeline["stages"] = stages

    return AZURE_HARDENING_HEADER + cast(str, yaml.dump(
        pipeline, default_flow_style=False, sort_keys=False, allow_unicode=True
    ))


JENKINS_PROVENANCE_ERROR = (
    "Jenkins cannot produce trustworthy SLSA provenance: the controller is "
    "mutable and attestation would be self-reported by the same environment "
    "that ran the build. Use Tekton Chains (or GitHub/GitLab native "
    "provenance) for attested builds, or set provenance=False."
)


def generate_jenkins(config: PipelineConfig) -> str:
    if config.provenance:
        raise ValueError(JENKINS_PROVENANCE_ERROR)

    max_timeout = max(
        (stage.timeout_minutes or DEFAULT_TIMEOUT_MINUTES for stage in config.stages),
        default=DEFAULT_TIMEOUT_MINUTES,
    )
    lines: List[str] = [
        "pipeline {",
        "    agent any",
        "",
        "    options {",
        f"        timeout(time: {max_timeout * max(len(config.stages), 1)}, unit: 'MINUTES')",
        "        disableConcurrentBuilds()",
        "    }",
        "",
    ]

    if config.env:
        lines.append("    environment {")
        for key, value in config.env.items():
            lines.append(f"        {key} = '{value}'")
        lines.append("    }")
        lines.append("")

    lines.append("    stages {")

    for stage in config.stages:
        lines.append(f"        stage('{stage.name}') {{")
        lines.append("            options {")
        lines.append(
            f"                timeout(time: {stage.timeout_minutes or DEFAULT_TIMEOUT_MINUTES}, unit: 'MINUTES')"
        )
        lines.append("            }")
        lines.append("            steps {")

        for step in stage.steps:
            if step.run:
                lines.append(f"                sh '''{step.run}'''")

        lines.append("            }")
        lines.append("        }")

    lines.append("    }")

    lines.append("")
    lines.append("    post {")
    lines.append("        always {")
    lines.append("            cleanWs()")
    lines.append("        }")
    lines.append("    }")
    lines.append("}")

    return "\n".join(lines)


CIRCLECI_HARDENING_HEADER = """\
# Zero-trust notes (Volundr):
# - Use CircleCI OIDC tokens ($CIRCLE_OIDC_TOKEN_V2) with restricted
#   contexts instead of static project environment variables.
# - Restrict contexts to protected branches for deploy jobs.
"""


def generate_circleci(config: PipelineConfig) -> str:
    """Render a CircleCI 2.1 config (OIDC-capable platform)."""
    pipeline: Dict[str, Any] = {"version": 2.1}

    jobs: Dict[str, Any] = {}
    workflow_jobs: List[Any] = []
    for stage in config.stages:
        job_name = _job_id(stage.name)
        steps: List[Any] = ["checkout"]
        for step in harden_steps(stage.steps):
            if step.run:
                steps.append({"run": {"name": step.name, "command": step.run}})
        job: Dict[str, Any] = {
            "docker": [{"image": "cimg/base:current"}],
            "steps": steps,
        }
        if stage.env:
            job["environment"] = stage.env
        jobs[job_name] = job

        entry: Any = job_name
        requirements = [_job_id(n) for n in stage.needs]
        job_config: Dict[str, Any] = {}
        if requirements:
            job_config["requires"] = requirements
        if _is_deploy_stage(stage):
            # Deploy trust boundary: restricted context + protected branch.
            job_config.setdefault("context", ["deploy"])
            job_config["filters"] = {"branches": {"only": ["main"]}}
        if job_config:
            entry = {job_name: job_config}
        workflow_jobs.append(entry)

    pipeline["jobs"] = jobs
    pipeline["workflows"] = {
        _job_id(config.name): {"jobs": workflow_jobs}
    }

    return CIRCLECI_HARDENING_HEADER + cast(str, yaml.dump(
        pipeline, default_flow_style=False, sort_keys=False, allow_unicode=True
    ))


def validate_pipeline(content: str, config: PipelineConfig) -> List[str]:
    """Structural config checks (semantic checks live in the Validation engine)."""
    issues: List[str] = []

    if not config.stages:
        issues.append("Pipeline has no stages defined")

    if not config.triggers:
        issues.append("Pipeline has no triggers defined")

    has_checkout = False
    for stage in config.stages:
        for step in stage.steps:
            if step.uses and "checkout" in step.uses.lower():
                has_checkout = True
            if step.run and "git clone" in step.run.lower():
                has_checkout = True

    if not has_checkout and config.platform == CICDPlatform.GITHUB_ACTIONS:
        issues.append("Consider adding checkout step (actions/checkout)")

    for stage in config.stages:
        for dep in stage.needs:
            if dep not in [s.name for s in config.stages]:
                issues.append(f"Stage '{stage.name}' depends on undefined stage '{dep}'")

    if config.secrets and config.oidc is None:
        static_cloud = [
            s for s in config.secrets
            if any(marker in s.upper() for marker in (
                "AWS_ACCESS", "AWS_SECRET", "GCP_", "GOOGLE_CREDENTIALS",
                "AZURE_CREDENTIALS", "SERVICE_ACCOUNT_KEY",
            ))
        ]
        for secret in static_cloud:
            issues.append(
                f"VOL-CICD-0005: static cloud credential '{secret}' — "
                "use OIDC federation (oidc=...) instead of long-lived secrets"
            )

    return issues


def calculate_best_practice_score(config: PipelineConfig) -> float:
    """Legacy config-shape score (non-GitHub platforms only).

    GitHub Actions pipelines are scored adversarially by the Validation
    engine on the rendered artifact.
    """
    score = 0.0
    max_score = 0.0

    max_score += 20
    if config.triggers:
        score += 20

    max_score += 20
    if len(config.stages) > 1:
        score += 20

    max_score += 15
    if config.concurrency:
        score += 15

    max_score += 15
    has_caching = any(
        step.uses and "cache" in step.uses.lower()
        for stage in config.stages
        for step in stage.steps
    )
    if has_caching:
        score += 15

    max_score += 15
    has_env_specified = bool(config.env) or any(stage.environment for stage in config.stages)
    if has_env_specified:
        score += 15

    max_score += 15
    has_timeout = any(stage.timeout_minutes for stage in config.stages)
    if has_timeout:
        score += 15

    return (score / max_score) * 100 if max_score > 0 else 0.0
