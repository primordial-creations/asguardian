"""
Heimdall Requirements Parser

Parser classes for Python dependency files.
"""

import re
from pathlib import Path
from typing import Dict

import tomllib


class RequirementsParser:
    """Parser for Python requirements files."""

    @staticmethod
    def parse_requirements_txt(file_path: Path) -> Dict[str, str]:
        """
        Parse a requirements.txt file.

        Args:
            file_path: Path to the requirements file

        Returns:
            Dictionary mapping package names to versions
        """
        dependencies: Dict[str, str] = {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()

                    if not line or line.startswith("#") or line.startswith("-"):
                        continue

                    if line.startswith("git+") or line.startswith("http"):
                        continue

                    match = re.match(
                        r"^([a-zA-Z0-9_-]+)\s*([>=<!=~]+)?\s*([0-9a-zA-Z.*,>=<!=~\s]+)?",
                        line.split("[")[0]
                    )

                    if match:
                        name = match.group(1).lower()
                        version = match.group(3) if match.group(3) else "*"
                        dependencies[name] = version.strip()

        except (IOError, OSError):
            pass

        return dependencies

    @staticmethod
    def parse_pyproject_toml(file_path: Path) -> Dict[str, str]:
        """
        Parse dependencies from pyproject.toml.

        Args:
            file_path: Path to pyproject.toml

        Returns:
            Dictionary mapping package names to versions
        """
        dependencies: Dict[str, str] = {}

        try:
            with open(file_path, "rb") as f:
                data = tomllib.load(f)

            deps_section = data.get("project", {}).get("dependencies", [])
            if isinstance(deps_section, list):
                for dep in deps_section:
                    match = re.match(r"^([a-zA-Z0-9_-]+)\s*([>=<!=~]+)?\s*([0-9.]+)?", dep)
                    if match:
                        name = match.group(1).lower()
                        version = match.group(3) if match.group(3) else "*"
                        dependencies[name] = version

            poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
            for name, spec in poetry_deps.items():
                if name.lower() == "python":
                    continue
                if isinstance(spec, str):
                    dependencies[name.lower()] = spec.lstrip("^~>=<")
                elif isinstance(spec, dict):
                    version = spec.get("version", "*")
                    dependencies[name.lower()] = version.lstrip("^~>=<")

        except (IOError, OSError, Exception):
            pass

        return dependencies

    @staticmethod
    def parse_setup_py(file_path: Path) -> Dict[str, str]:
        """
        Parse dependencies from setup.py (basic parsing).

        Args:
            file_path: Path to setup.py

        Returns:
            Dictionary mapping package names to versions
        """
        dependencies: Dict[str, str] = {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            pattern = r"install_requires\s*=\s*\[([\s\S]*?)\]"
            match = re.search(pattern, content)

            if match:
                deps_str = match.group(1)
                for dep_match in re.finditer(r"['\"]([^'\"]+)['\"]", deps_str):
                    dep = dep_match.group(1)
                    name_match = re.match(r"^([a-zA-Z0-9_-]+)", dep)
                    if name_match:
                        name = name_match.group(1).lower()
                        version_match = re.search(r"([>=<!=~]+)\s*([0-9.]+)", dep)
                        version = version_match.group(2) if version_match else "*"
                        dependencies[name] = version

        except (IOError, OSError):
            pass

        return dependencies
