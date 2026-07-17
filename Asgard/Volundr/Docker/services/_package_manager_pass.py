"""
Package-manager hygiene pass for Dockerfile generation (RESEARCH_10 §3.5,
hadolint DL3008/DL3009/DL3013/DL3016/DL3018/DL3042).

Recognizes apt-get / apk / pip / npm install commands in a stage's RUN
list and:
- injects ``--no-install-recommends`` / ``--no-cache`` / ``--no-cache-dir``
  where missing,
- appends the matching same-layer cache cleanup
  (``rm -rf /var/lib/apt/lists/*``, ``npm cache clean --force``),
- reports unpinned installs as findings instead of silently emitting them.

The pass is semantic: install+cleanup are merged into ONE layer, while
unrelated commands are left to the generator's normal layer strategy —
this replaces the old blind ``&&``-join of every RUN.
"""

import re
from typing import List, Optional, Tuple

from Asgard.Volundr.Validation.models.validation_models import (
    ValidationCategory,
    ValidationResult,
    ValidationSeverity,
)

_APT_INSTALL_RE = re.compile(r"\bapt(-get)?\s+(?:-\S+\s+)*install\b")
_APK_ADD_RE = re.compile(r"\bapk\s+(?:-\S+\s+)*add\b")
_PIP_INSTALL_RE = re.compile(r"\bpip3?\s+install\b")
_NPM_INSTALL_RE = re.compile(r"\bnpm\s+(?:install|ci)\b")

_APT_CLEANUP = "rm -rf /var/lib/apt/lists/*"
_NPM_CLEANUP = "npm cache clean --force"

#: Package tokens considered "pinned" per manager.
_PIN_MARKERS = {
    "apt": "=",
    "apk": "=",
    "pip": "==",
    "npm": "@",
}

_PIN_RULES = {
    "apt": "DL3008",
    "apk": "DL3018",
    "pip": "DL3013",
    "npm": "DL3016",
}


def _manager_of(command: str) -> Optional[str]:
    if _APT_INSTALL_RE.search(command):
        return "apt"
    if _APK_ADD_RE.search(command):
        return "apk"
    if _PIP_INSTALL_RE.search(command):
        return "pip"
    if _NPM_INSTALL_RE.search(command):
        return "npm"
    return None


def _packages_of(command: str, manager: str) -> List[str]:
    """Best-effort extraction of package tokens from an install command."""
    if manager == "apt":
        match = _APT_INSTALL_RE.search(command)
    elif manager == "apk":
        match = _APK_ADD_RE.search(command)
    elif manager == "pip":
        match = _PIP_INSTALL_RE.search(command)
    else:
        match = _NPM_INSTALL_RE.search(command)
    if not match:
        return []
    tail = command[match.end():]
    # Stop at shell control operators.
    tail = re.split(r"&&|\|\||;", tail)[0]
    packages = []
    for token in tail.split():
        if token.startswith("-"):
            continue
        if token in ("install", "add", "ci"):
            continue
        # Requirements files / local paths are not version-pin candidates.
        if token.startswith((".", "/", "-r")) or token.endswith(".txt"):
            continue
        packages.append(token)
    return packages


def _harden_command(command: str, manager: str) -> str:
    """Inject hygiene flags and same-layer cleanup for one install command."""
    hardened = command
    if manager == "apt":
        if "--no-install-recommends" not in hardened:
            hardened = _APT_INSTALL_RE.sub(
                lambda m: m.group(0) + " --no-install-recommends", hardened, count=1
            )
        if "-y" not in hardened.split() and "--yes" not in hardened:
            hardened = _APT_INSTALL_RE.sub(
                lambda m: m.group(0) + " -y", hardened, count=1
            )
        if _APT_CLEANUP not in hardened:
            hardened = f"{hardened} && {_APT_CLEANUP}"
    elif manager == "apk":
        if "--no-cache" not in hardened:
            hardened = _APK_ADD_RE.sub(
                lambda m: m.group(0) + " --no-cache", hardened, count=1
            )
    elif manager == "pip":
        if "--no-cache-dir" not in hardened:
            hardened = _PIP_INSTALL_RE.sub(
                lambda m: m.group(0) + " --no-cache-dir", hardened, count=1
            )
    elif manager == "npm":
        if _NPM_CLEANUP not in hardened:
            hardened = f"{hardened} && {_NPM_CLEANUP}"
    return hardened


def apply_package_hygiene(
    run_commands: List[str], stage_name: str, source: str = "Dockerfile"
) -> Tuple[List[str], List[ValidationResult]]:
    """Harden install commands and report unpinned packages.

    Returns (rewritten_commands, findings).
    """
    findings: List[ValidationResult] = []
    rewritten: List[str] = []
    for command in run_commands:
        manager = _manager_of(command)
        if manager is None:
            rewritten.append(command)
            continue
        rewritten.append(_harden_command(command, manager))
        marker = _PIN_MARKERS[manager]
        unpinned = [
            pkg for pkg in _packages_of(command, manager) if marker not in pkg
        ]
        if unpinned:
            findings.append(ValidationResult(
                rule_id=_PIN_RULES[manager],
                message=(
                    f"Stage '{stage_name}': unpinned {manager} package(s): "
                    f"{', '.join(sorted(unpinned))}"
                ),
                severity=ValidationSeverity.INFO,
                category=ValidationCategory.BEST_PRACTICE,
                file_path=source,
                suggestion=f"Pin versions (e.g. pkg{marker}<version>) for reproducible builds.",
                context={"target": stage_name},
            ))
    return rewritten, findings
