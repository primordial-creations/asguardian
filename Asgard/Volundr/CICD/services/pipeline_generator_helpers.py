from typing import Any, Dict, List, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.CICD.models.cicd_models import (
    CICDPlatform,
    PipelineConfig,
    TriggerType,
)


def generate_github_actions(config: PipelineConfig) -> str:
    workflow: Dict[str, Any] = {"name": config.name}

    on_triggers: Dict[str, Any] = {}
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

    workflow["on"] = on_triggers

    if config.env:
        workflow["env"] = config.env

    if config.concurrency:
        workflow["concurrency"] = config.concurrency

    jobs: Dict[str, Any] = {}
    for stage in config.stages:
        job: Dict[str, Any] = {"runs-on": stage.runs_on}

        if stage.needs:
            job["needs"] = stage.needs

        if stage.if_condition:
            job["if"] = stage.if_condition

        if stage.timeout_minutes:
            job["timeout-minutes"] = stage.timeout_minutes

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
        for step in stage.steps:
            step_dict: Dict[str, Any] = {"name": step.name}

            if step.uses:
                step_dict["uses"] = step.uses
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

            steps.append(step_dict)

        job["steps"] = steps
        jobs[stage.name.lower().replace(" ", "-")] = job

    workflow["jobs"] = jobs

    return cast(str, yaml.dump(workflow, default_flow_style=False, sort_keys=False, allow_unicode=True))


def generate_gitlab_ci(config: PipelineConfig) -> str:
    pipeline: Dict[str, Any] = {}

    stage_names = [stage.name.lower().replace(" ", "-") for stage in config.stages]
    pipeline["stages"] = stage_names

    if config.env:
        pipeline["variables"] = config.env

    for stage in config.stages:
        job_name = stage.name.lower().replace(" ", "-")
        job: Dict[str, Any] = {
            "stage": job_name,
            "image": stage.runs_on if ":" in stage.runs_on else f"ubuntu:{stage.runs_on.split('-')[-1] if '-' in stage.runs_on else 'latest'}",
        }

        if stage.needs:
            job["needs"] = stage.needs

        if stage.env:
            job["variables"] = stage.env

        if stage.services:
            job["services"] = list(stage.services.keys())

        scripts: List[str] = []
        for step in stage.steps:
            if step.run:
                scripts.append(step.run)

        if scripts:
            job["script"] = scripts

        if stage.if_condition:
            job["rules"] = [{"if": stage.if_condition}]

        pipeline[job_name] = job

    return cast(str, yaml.dump(pipeline, default_flow_style=False, sort_keys=False, allow_unicode=True))


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

    return cast(str, yaml.dump(pipeline, default_flow_style=False, sort_keys=False, allow_unicode=True))


def generate_jenkins(config: PipelineConfig) -> str:
    lines: List[str] = ["pipeline {", "    agent any", ""]

    if config.env:
        lines.append("    environment {")
        for key, value in config.env.items():
            lines.append(f"        {key} = '{value}'")
        lines.append("    }")
        lines.append("")

    lines.append("    stages {")

    for stage in config.stages:
        lines.append(f"        stage('{stage.name}') {{")
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


def validate_pipeline(content: str, config: PipelineConfig) -> List[str]:
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

    return issues


def calculate_best_practice_score(config: PipelineConfig) -> float:
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
