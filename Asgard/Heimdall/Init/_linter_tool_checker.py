"""
Linter Initializer - Tool and Extension Checker Helpers

Standalone functions for checking CLI tool availability and VSCode extension
installation status. Accept all required data as explicit parameters.
"""

import shutil
import subprocess
from pathlib import Path
from typing import List


def check_tools(
    project_path: Path,
    is_python: bool,
    is_typescript: bool,
    python_tool_requirements: list,
    typescript_tool_requirements: list,
    typescript_npm_requirements: list,
) -> List[dict]:
    """Check which required CLI tools and packages are missing.

    Args:
        project_path: Resolved path to the project root.
        is_python: Whether to check Python tools.
        is_typescript: Whether to check TypeScript tools.
        python_tool_requirements: List of Python tool requirement dicts.
        typescript_tool_requirements: List of TypeScript CLI tool requirement dicts.
        typescript_npm_requirements: List of TypeScript npm package requirement dicts.

    Returns:
        List of dicts with keys: name, installed (bool), install, purpose.
    """
    results = []

    if is_python:
        for tool in python_tool_requirements:
            installed = shutil.which(tool["command"]) is not None
            results.append({
                "name": tool["name"],
                "installed": installed,
                "install": tool["install"],
                "purpose": tool["purpose"],
            })

    if is_typescript:
        for tool in typescript_tool_requirements:
            installed = shutil.which(tool["command"]) is not None
            results.append({
                "name": tool["name"],
                "installed": installed,
                "install": tool["install"],
                "purpose": tool["purpose"],
            })

        npx_available = shutil.which("npx") is not None
        if npx_available:
            for pkg in typescript_npm_requirements:
                pkg_path = project_path / "node_modules" / pkg["package"]
                installed = pkg_path.exists()
                results.append({
                    "name": pkg["name"],
                    "installed": installed,
                    "install": pkg["install"],
                    "purpose": pkg["purpose"],
                })
        else:
            for pkg in typescript_npm_requirements:
                results.append({
                    "name": pkg["name"],
                    "installed": False,
                    "install": pkg["install"],
                    "purpose": pkg["purpose"],
                })

    return results


def check_vscode_extensions(
    is_python: bool,
    is_typescript: bool,
    vscode_extensions_python: list,
    vscode_extensions_typescript: list,
) -> List[dict]:
    """Check which recommended VSCode extensions are installed.

    Args:
        is_python: Whether to check Python extensions.
        is_typescript: Whether to check TypeScript extensions.
        vscode_extensions_python: List of Python extension IDs.
        vscode_extensions_typescript: List of TypeScript extension IDs.

    Returns:
        List of dicts with keys: extension_id, installed (bool).
    """
    results: List[dict] = []
    extension_ids: List[str] = []
    if is_python:
        extension_ids.extend(vscode_extensions_python)
    if is_typescript:
        extension_ids.extend(vscode_extensions_typescript)

    if not extension_ids:
        return results

    installed_extensions: set = set()
    code_cmd = shutil.which("code")
    if code_cmd:
        try:
            proc = subprocess.run(
                [code_cmd, "--list-extensions"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0:
                installed_extensions = {ext.strip().lower() for ext in proc.stdout.splitlines()}
        except (subprocess.TimeoutExpired, OSError):
            pass

    for ext_id in sorted(set(extension_ids)):
        installed = ext_id.lower() in installed_extensions
        results.append({
            "extension_id": ext_id,
            "installed": installed,
        })

    return results
