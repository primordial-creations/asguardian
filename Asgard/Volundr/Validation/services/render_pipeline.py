"""
Render -> validate pipeline for Helm / Kustomize / GitOps output
(plan 05, mirroring RESEARCH_05's four-phase pre-merge pipeline):

    1. render      kustomize build / helm template   (external tool)
    2. schema      ValidationEngine tiers 1-3 (+ kubeconform if present)
    3. policy      ValidationEngine tier 4 (default-deny packs)
    4. deprecation pluto detect (external tool)

External tools are OPTIONAL: every step degrades to a skip notice when
the tool is unavailable, and nothing here runs in the default generation
path — callers opt in explicitly.
"""

import subprocess
from typing import List, Optional

from Asgard.Volundr.Validation.models.validation_models import (
    ValidationCategory,
    ValidationContext,
    ValidationReport,
    ValidationResult,
    ValidationSeverity,
)
from Asgard.Volundr.Validation.services.external_tools import (
    is_available,
    run_kubeconform,
)
from Asgard.Volundr.Validation.services.validation_engine import ValidationEngine


def _skip_notice(tool: str, phase: str) -> ValidationResult:
    return ValidationResult(
        rule_id="VOL-EXTERNAL-TOOL-SKIPPED",
        message=(
            f"{phase}: '{tool}' is not installed — step skipped "
            "(install it to buy down validation uncertainty)"
        ),
        severity=ValidationSeverity.HINT,
        category=ValidationCategory.BEST_PRACTICE,
        context={"external_tool": tool},
    )


def render_kustomize(path: str, timeout: int = 120) -> Optional[str]:
    """`kustomize build <path>` (falls back to `kubectl kustomize`).

    Returns rendered YAML, or None when no renderer is available.
    Raises RuntimeError when rendering fails.
    """
    if is_available("kustomize"):
        cmd = ["kustomize", "build", path]
    elif is_available("kubectl"):
        cmd = ["kubectl", "kustomize", path]
    else:
        return None
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(f"kustomize build failed: {proc.stderr.strip()}")
    return proc.stdout


def render_helm(
    chart_path: str,
    values_files: Optional[List[str]] = None,
    release_name: str = "volundr-render",
    timeout: int = 120,
) -> Optional[str]:
    """`helm template` a local chart. None when helm is unavailable."""
    if not is_available("helm"):
        return None
    cmd = ["helm", "template", release_name, chart_path]
    for values_file in values_files or []:
        cmd.extend(["-f", values_file])
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(f"helm template failed: {proc.stderr.strip()}")
    return proc.stdout


def run_pluto(content: str, timeout: int = 120) -> List[ValidationResult]:
    """pluto detect (deprecated-API scan) over rendered manifests."""
    if not is_available("pluto"):
        return [_skip_notice("pluto", "deprecation scan")]
    proc = subprocess.run(
        ["pluto", "detect", "-", "--output", "json"],
        input=content, capture_output=True, text=True,
        timeout=timeout, check=False,
    )
    results: List[ValidationResult] = []
    import json
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return results
    for item in data.get("items", []) or []:
        results.append(ValidationResult(
            rule_id="VOL-K8S-0012",
            message=(
                f"pluto: {item.get('name', '?')} uses deprecated apiVersion "
                f"{item.get('api', {}).get('version', '?')} "
                f"(replacement: {item.get('api', {}).get('replacement-api', 'n/a')})"
            ),
            severity=ValidationSeverity.WARNING,
            category=ValidationCategory.SCHEMA,
            resource_name=item.get("name"),
            context={"external_tool": "pluto"},
        ))
    return results


def render_and_validate(
    path: str,
    kind: str = "kustomize",
    values_files: Optional[List[str]] = None,
    context: Optional[ValidationContext] = None,
    use_external_tools: bool = True,
) -> ValidationReport:
    """Render a local kustomization/chart and validate the output.

    Args:
        path: kustomization directory or chart directory.
        kind: "kustomize" or "helm".
        use_external_tools: additionally run kubeconform/pluto if present.
    """
    context = context or ValidationContext()
    extra: List[ValidationResult] = []

    if kind == "helm":
        rendered = render_helm(path, values_files=values_files)
        renderer = "helm"
    else:
        rendered = render_kustomize(path)
        renderer = "kustomize"

    engine = ValidationEngine(context=context)
    if rendered is None:
        report = engine.validate_kubernetes("", source=path)
        report.results.append(_skip_notice(renderer, "render"))
        return report

    report = engine.validate_kubernetes(rendered, source=path)

    if use_external_tools:
        if is_available("kubeconform"):
            extra.extend(run_kubeconform(rendered, context.kubernetes_version))
        else:
            extra.append(_skip_notice("kubeconform", "schema validation"))
        extra.extend(run_pluto(rendered))

    report.results.extend(extra)
    report.total_errors = sum(
        1 for r in report.results if r.severity == ValidationSeverity.ERROR
    )
    report.total_warnings = sum(
        1 for r in report.results if r.severity == ValidationSeverity.WARNING
    )
    report.passed = report.total_errors == 0
    return report
