"""
Optional external-tool bridge.

If industry tools (kubeconform, hadolint, checkov, actionlint, conftest)
are present on PATH, rendered artifacts can additionally be run through
them and their findings merged into Volundr's report. The bridge is
NEVER required at runtime and is NEVER invoked in the default path —
callers opt in explicitly. No network access is performed by Volundr
itself (tools are invoked with their offline flags where applicable).
"""

import json
import shutil
import subprocess
import tempfile
from typing import List, Optional

from Asgard.Volundr.Validation.models.validation_models import (
    ValidationCategory,
    ValidationResult,
    ValidationSeverity,
)

SUPPORTED_TOOLS = (
    "kubeconform", "hadolint", "checkov", "actionlint", "conftest",
    "kustomize", "helm", "pluto",
)


def is_available(tool: str) -> bool:
    """True if the named external tool is on PATH."""
    return shutil.which(tool) is not None


def available_tools() -> List[str]:
    return [t for t in SUPPORTED_TOOLS if is_available(t)]


def _run(cmd: List[str], stdin_text: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, input=stdin_text, capture_output=True, text=True, timeout=120,
        check=False,
    )


def run_kubeconform(content: str, kubernetes_version: str = "1.29") -> List[ValidationResult]:
    """Run kubeconform -strict against rendered manifests (offline schemas)."""
    if not is_available("kubeconform"):
        return []
    proc = _run(
        [
            "kubeconform", "-strict", "-summary", "-output", "json",
            "-kubernetes-version", kubernetes_version.lstrip("v"),
        ],
        stdin_text=content,
    )
    results: List[ValidationResult] = []
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return results
    for res in data.get("resources", []):
        if res.get("status") in ("statusValid", "statusSkipped", None):
            continue
        results.append(ValidationResult(
            rule_id="VOL-K8S-0011",
            message=f"kubeconform: {res.get('msg', 'schema validation failed')}",
            severity=ValidationSeverity.ERROR,
            category=ValidationCategory.SCHEMA,
            file_path=res.get("filename"),
            resource_kind=res.get("kind"),
            resource_name=res.get("name"),
            context={"external_tool": "kubeconform"},
        ))
    return results


def run_hadolint(dockerfile_content: str) -> List[ValidationResult]:
    """Run hadolint against a rendered Dockerfile."""
    if not is_available("hadolint"):
        return []
    proc = _run(["hadolint", "--format", "json", "-"], stdin_text=dockerfile_content)
    results: List[ValidationResult] = []
    try:
        findings = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return results
    severity_map = {
        "error": ValidationSeverity.ERROR,
        "warning": ValidationSeverity.WARNING,
        "info": ValidationSeverity.INFO,
        "style": ValidationSeverity.HINT,
    }
    for finding in findings:
        results.append(ValidationResult(
            rule_id=finding.get("code", "hadolint"),
            message=f"hadolint: {finding.get('message', '')}",
            severity=severity_map.get(
                finding.get("level", "warning"), ValidationSeverity.WARNING
            ),
            category=ValidationCategory.BEST_PRACTICE,
            line_number=finding.get("line"),
            column=finding.get("column"),
            context={"external_tool": "hadolint"},
        ))
    return results


def run_actionlint(workflow_content: str) -> List[ValidationResult]:
    """Run actionlint against rendered workflow YAML."""
    if not is_available("actionlint"):
        return []
    with tempfile.NamedTemporaryFile(
        "w", suffix=".yml", delete=False
    ) as f:
        f.write(workflow_content)
        path = f.name
    proc = _run([
        "actionlint", "-format", "{{json .}}", path,
    ])
    results: List[ValidationResult] = []
    try:
        findings = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return results
    for finding in findings:
        results.append(ValidationResult(
            rule_id=f"actionlint/{finding.get('kind', 'unknown')}",
            message=f"actionlint: {finding.get('message', '')}",
            severity=ValidationSeverity.ERROR,
            category=ValidationCategory.SYNTAX,
            line_number=finding.get("line"),
            column=finding.get("column"),
            context={"external_tool": "actionlint"},
        ))
    return results
