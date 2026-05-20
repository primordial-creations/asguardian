"""
Heimdall SBOM Generator - Dependency File Parsers

Standalone functions for parsing Python dependency declaration files
(requirements.txt, pyproject.toml) and building package metadata.
"""

import importlib.metadata
import re
import tomllib
from typing import List, Tuple


def parse_requirements_txt(file_path: str) -> List[Tuple[str, str]]:
    """
    Parse a requirements.txt file and return (name, version_spec) pairs.

    Handles standard pin syntax (==, >=, <=, ~=, !=, >).
    Skips comments, blank lines, -r includes, and -e editable installs.

    Args:
        file_path: Absolute path to the requirements file.

    Returns:
        List of (package_name, version_spec) tuples.
    """
    results: List[Tuple[str, str]] = []

    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    continue
                if line.startswith("-r ") or line.startswith("--requirement"):
                    continue
                if line.startswith("-e ") or line.startswith("--editable"):
                    continue
                if line.startswith("-"):
                    continue

                line = line.split(" #")[0].strip()
                line = line.split("\t#")[0].strip()

                match = re.match(
                    r"^([A-Za-z0-9_\-\.]+)\s*([><=!~][><=!~]?\s*[^\s;,]+)?",
                    line,
                )
                if match:
                    name = match.group(1).strip()
                    version_spec = match.group(2).strip() if match.group(2) else ""
                    results.append((name, version_spec))
    except (OSError, IOError):
        pass

    return results


def parse_pyproject_toml(file_path: str) -> List[Tuple[str, str]]:
    """
    Parse a pyproject.toml file and return (name, version_spec) pairs.

    Reads from [project.dependencies] (PEP 621) and
    [tool.poetry.dependencies] (Poetry). Returns empty list on parse failure.

    Args:
        file_path: Absolute path to pyproject.toml.

    Returns:
        List of (package_name, version_spec) tuples.
    """
    results: List[Tuple[str, str]] = []

    try:
        with open(file_path, "rb") as fh:
            data = tomllib.load(fh)
    except Exception:
        return results

    project_deps = data.get("project", {}).get("dependencies", [])
    for dep in project_deps:
        if not isinstance(dep, str):
            continue
        match = re.match(
            r"^([A-Za-z0-9_\-\.]+)\s*([><=!~][><=!~]?\s*[^\s;,]+)?",
            dep.strip(),
        )
        if match:
            name = match.group(1).strip()
            version_spec = match.group(2).strip() if match.group(2) else ""
            results.append((name, version_spec))

    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    for name, spec in poetry_deps.items():
        if name.lower() == "python":
            continue
        if isinstance(spec, str):
            version_spec = spec
        elif isinstance(spec, dict):
            version_spec = spec.get("version", "")
        else:
            version_spec = ""
        results.append((name, version_spec))

    return results


def make_purl(name: str, version: str, ecosystem: str = "pypi") -> str:
    """
    Build a Package URL (purl) for the given package.

    Args:
        name: Package name.
        version: Version string or version spec.
        ecosystem: Package ecosystem identifier (default: pypi).

    Returns:
        A purl string such as "pkg:pypi/requests@2.28.0".
    """
    normalized = name.lower().replace("-", "_")
    if version:
        clean_version = re.sub(r"^[><=!~]+\s*", "", version).strip()
        return f"pkg:{ecosystem}/{normalized}@{clean_version}"
    return f"pkg:{ecosystem}/{normalized}"


def get_license_from_metadata(package_name: str) -> str:
    """
    Retrieve the license identifier for an installed package using importlib.metadata.

    Args:
        package_name: The package name to look up.

    Returns:
        SPDX license identifier string, or empty string if not available.
    """
    try:
        meta = importlib.metadata.metadata(package_name)
        try:
            license_value = meta["License"]
        except KeyError:
            license_value = ""
        if license_value:
            return license_value.strip()
    except importlib.metadata.PackageNotFoundError:
        pass
    except Exception:
        pass
    return ""
