"""
HooksSetup service - installs pre-commit git hooks and optional VS Code config.

Intended to be called from the 'asguardian setup-hooks' CLI command.
"""

import json
import subprocess
from pathlib import Path


def write_vscode_config(project_path: Path) -> int:
    """Create or merge .vscode/settings.json and extensions.json for code quality."""
    vscode_dir = project_path / ".vscode"
    vscode_dir.mkdir(exist_ok=True)

    settings_path = vscode_dir / "settings.json"
    extensions_path = vscode_dir / "extensions.json"

    existing_settings: dict = {}
    if settings_path.exists():
        try:
            with open(settings_path, encoding="utf-8") as f:
                existing_settings = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    quality_settings: dict = {
        "editor.formatOnSave": True,
        "[python]": {
            "editor.defaultFormatter": "charliermarsh.ruff",
            "editor.codeActionsOnSave": {
                "source.fixAll.ruff": "explicit",
                "source.organizeImports.ruff": "explicit",
            },
        },
        "python.analysis.typeCheckingMode": "basic",
    }

    merged_settings = {**existing_settings, **quality_settings}
    if "[python]" in existing_settings:
        merged_settings["[python]"] = {**existing_settings["[python]"], **quality_settings["[python]"]}

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(merged_settings, f, indent=2)
        f.write("\n")

    print(f"  Written: {settings_path.relative_to(project_path)}")

    existing_ext: dict = {"recommendations": []}
    if extensions_path.exists():
        try:
            with open(extensions_path, encoding="utf-8") as f:
                existing_ext = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    recommended = [
        "charliermarsh.ruff",
        "ms-python.mypy-type-checker",
        "ms-python.python",
    ]
    existing_recs: list = existing_ext.get("recommendations", [])
    merged_recs = existing_recs + [r for r in recommended if r not in existing_recs]

    with open(extensions_path, "w", encoding="utf-8") as f:
        json.dump({"recommendations": merged_recs}, f, indent=2)
        f.write("\n")

    print(f"  Written: {extensions_path.relative_to(project_path)}")
    return 0


def setup_hooks(project_path: Path, install_pre_push: bool = False, setup_vscode: bool = False) -> int:
    """Install pre-commit git hooks and optionally write VS Code config.

    Args:
        project_path: Root of the git repository.
        install_pre_push: If True, also installs a pre-push hook.
        setup_vscode: If True, writes .vscode/settings.json and extensions.json.

    Returns:
        0 on success, non-zero on failure.
    """
    print(f"Setting up pre-commit hooks in: {project_path}")
    print()

    git_dir = project_path / ".git"
    if not git_dir.exists():
        print(f"Error: {project_path} is not a git repository.")
        print("Initialize a git repository first with: git init")
        return 1

    try:
        print("Installing pre-commit hook (runs on every git commit)...")
        result = subprocess.run(["pre-commit", "install"], cwd=project_path, check=False)
        if result.returncode != 0:
            print(f"Failed to install pre-commit hook (exit code {result.returncode})")
            print("Make sure pre-commit is installed: pip install pre-commit")
            return result.returncode
        print("  pre-commit hook installed.")
    except FileNotFoundError:
        print("Error: 'pre-commit' command not found.")
        print("Install it with: pip install pre-commit")
        return 1

    if install_pre_push:
        try:
            print("Installing pre-push hook (runs on git push)...")
            result = subprocess.run(
                ["pre-commit", "install", "--hook-type", "pre-push"],
                cwd=project_path,
                check=False,
            )
            if result.returncode != 0:
                print(f"Failed to install pre-push hook (exit code {result.returncode})")
                return result.returncode
            print("  pre-push hook installed.")
        except FileNotFoundError:
            print("Error: 'pre-commit' command not found.")
            return 1

    if setup_vscode:
        print("Setting up VS Code configuration...")
        rc = write_vscode_config(project_path)
        if rc != 0:
            return rc

    print()
    hook_stages = "commit" + (" and push" if install_pre_push else "")
    print(f"Hook setup complete! Hooks will run automatically on {hook_stages}.")
    print()
    print("To run all checks right now:")
    print("  pre-commit run --all-files")
    return 0
