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
    # purl spec for pkg:pypi: lowercase and normalize runs of ., _, - to a
    # single hyphen (PEP 503). The old code did the OPPOSITE ("-" -> "_"),
    # emitting spec-invalid purls for every hyphenated package.
    if ecosystem == "pypi":
        normalized = re.sub(r"[-_.]+", "-", name).lower()
    else:
        normalized = name.lower()
    if version:
        clean_version = re.sub(r"^[><=!~]+\s*", "", version).strip()
        return f"pkg:{ecosystem}/{normalized}@{clean_version}"
    return f"pkg:{ecosystem}/{normalized}"


def get_installed_version(package_name: str) -> str:
    """
    Resolved installed version for a package via importlib.metadata.

    Returns '' when the package is not installed in the current environment.
    """
    try:
        return importlib.metadata.version(package_name) or ""
    except importlib.metadata.PackageNotFoundError:
        return ""
    except Exception:
        return ""


def get_license_from_metadata(package_name: str) -> str:
    """
    Retrieve the license identifier for an installed package using importlib.metadata.

    Args:
        package_name: The package name to look up.

    Returns:
        SPDX license identifier string, or empty string if not available.

    Precedence (Plan 03): PEP 639 License-Expression, then trove license
    classifier, then the legacy License header.
    """
    try:
        meta = importlib.metadata.metadata(package_name)
    except importlib.metadata.PackageNotFoundError:
        return ""
    except Exception:
        return ""

    try:
        expression = meta.get("License-Expression", "")  # type: ignore[attr-defined]
    except Exception:
        expression = ""
    if expression:
        return expression.strip()

    try:
        classifiers = meta.get_all("Classifier") or []
    except Exception:
        classifiers = []
    for classifier in classifiers:
        if classifier.startswith("License ::"):
            return classifier.split(" :: ")[-1].strip()

    try:
        license_value = meta.get("License", "") or ""
    except Exception:
        license_value = ""
    return license_value.strip()


def parse_requires_dist(requires: str) -> str:
    """
    Extract the bare package name from a Requires-Dist entry.

    Returns '' for extra-gated requirements (``; extra == "..."``) so the
    closure walk follows the default (non-extra) dependency set only.
    """
    if not requires:
        return ""
    if ";" in requires:
        marker_text = requires.split(";", 1)[1].strip()
        if "extra" in marker_text:
            return ""
        # Evaluate environment markers so platform/version-gated
        # requirements absent from THIS environment do not count against
        # closure completeness (e.g. tomli on Python >= 3.11).
        try:
            from packaging.markers import Marker
            if not Marker(marker_text).evaluate():
                return ""
        except Exception:
            pass  # unevaluable marker: keep the requirement conservatively
    head = requires.split(";")[0].strip()
    match = re.match(r"^([A-Za-z0-9_\-\.]+)", head)
    return match.group(1) if match else ""


def get_requires(package_name: str) -> List[str]:
    """
    Names of a package's default (non-extra) requirements, from installed
    metadata. Empty when the package is not installed.
    """
    try:
        meta = importlib.metadata.metadata(package_name)
    except importlib.metadata.PackageNotFoundError:
        return []
    except Exception:
        return []
    try:
        entries = meta.get_all("Requires-Dist") or []
    except Exception:
        entries = []
    names = []
    for entry in entries:
        name = parse_requires_dist(entry)
        if name and name.lower() not in {n.lower() for n in names}:
            names.append(name)
    return names


def get_record_checksum(package_name: str) -> str:
    """
    Deterministic sha256 over the package's installed RECORD file-hash lines.

    Per-file wheel hashes live in dist-info/RECORD; a package-level checksum
    is derived as sha256 of the sorted "path,hash" lines, so an identical
    installation always yields the same value. '' when unavailable.
    """
    import hashlib

    try:
        dist = importlib.metadata.distribution(package_name)
    except importlib.metadata.PackageNotFoundError:
        return ""
    except Exception:
        return ""
    try:
        record = dist.read_text("RECORD")
    except Exception:
        record = None
    if not record:
        return ""
    lines = []
    for line in record.splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[1].strip():
            lines.append(f"{parts[0]},{parts[1]}")
    if not lines:
        return ""
    payload = "\n".join(sorted(lines))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_package_meta_fields(package_name: str) -> dict:
    """Supplier/author/homepage/summary from installed metadata ('' absent)."""
    try:
        meta = importlib.metadata.metadata(package_name)
    except importlib.metadata.PackageNotFoundError:
        return {}
    except Exception:
        return {}

    def _get(key: str) -> str:
        try:
            return (meta.get(key) or "").strip()
        except Exception:
            return ""

    return {
        "author": _get("Author") or _get("Author-email"),
        "supplier": _get("Author") or _get("Maintainer") or _get("Author-email"),
        "homepage": _get("Home-page"),
        "description": _get("Summary"),
    }
