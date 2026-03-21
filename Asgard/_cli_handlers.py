"""
Asgard CLI - Handler functions.

Contains handler functions for the init, init-backend, setup-hooks,
and install-browsers commands.
"""

import argparse
import subprocess
from pathlib import Path
from typing import cast

from Asgard.BackendInit.service import init_backend
from Asgard.HooksSetup.service import setup_hooks
from Asgard._cli_help import COMPREHENSIVE_HELP
from Asgard.config.loader import AsgardConfigLoader


def handle_install_browsers(args: argparse.Namespace) -> int:
    """Install Playwright browser binaries required for Freya."""
    browsers = getattr(args, "browsers", ["chromium"])

    print("Installing Playwright browsers for Freya...")
    print(f"Browsers: {', '.join(browsers)}")
    print()

    try:
        cmd = ["playwright", "install"] + browsers
        result = subprocess.run(cmd, check=False)

        if result.returncode == 0:
            print()
            print("Browser installation complete!")
            print("You can now use Freya's browser-based features:")
            print("  asguardian freya performance audit <url>")
            print("  asguardian freya visual capture <url>")
            print("  asguardian freya accessibility audit <url>")
            return 0
        else:
            print(f"Browser installation failed with exit code {result.returncode}")
            return result.returncode

    except FileNotFoundError:
        print("Error: 'playwright' command not found.")
        print("Please ensure Asgard is installed: pip install Asgard")
        return 1
    except Exception as e:
        print(f"Error installing browsers: {e}")
        return 1


def handle_setup_hooks(args: argparse.Namespace) -> int:
    """Handle the 'setup-hooks' command to install pre-commit git hooks."""
    return cast(int, setup_hooks(
        project_path=Path(getattr(args, "path", ".")).resolve(),
        install_pre_push=getattr(args, "pre_push", False),
        setup_vscode=getattr(args, "vscode", False),
    ))


def handle_init_backend(args: argparse.Namespace) -> int:
    """Handle the 'init-backend' command to scaffold a backend project."""
    return cast(int, init_backend(args.folder_name))


def handle_init(args: argparse.Namespace) -> int:
    """Handle the 'init' command to generate configuration file."""
    output_format = getattr(args, "format", "yaml")
    output_path = Path.cwd()

    if output_format == "yaml":
        content = AsgardConfigLoader.generate_default_yaml()
        filename = "asgard.yaml"
    elif output_format == "toml":
        content = AsgardConfigLoader.generate_default_toml()
        filename = "pyproject.toml.asguardian"
        print(f"Note: Add the following to your pyproject.toml [tool.asguardian] section:")
    elif output_format == "json":
        content = AsgardConfigLoader.generate_default_json()
        filename = ".asgardrc"
    else:
        print(f"Unknown format: {output_format}")
        return 1

    output_file = output_path / filename

    if output_file.exists() and not getattr(args, "force", False):
        print(f"File {filename} already exists. Use --force to overwrite.")
        return 1

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Created {filename}")
    return 0


__all__ = [
    "COMPREHENSIVE_HELP",
    "handle_init",
    "handle_init_backend",
    "handle_install_browsers",
    "handle_setup_hooks",
]
