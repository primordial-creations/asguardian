"""
Supply-chain static analysis: typosquat scoring + dependency-confusion
check (plan 07.10, RESEARCH_16).

Both checks are purely static/offline -- no network calls -- consistent
with the "no network in default paths" constraint. They operate on the
manifest package-name list Heimdall already parses from
requirements.txt/pyproject.toml/setup.py (never on installed site-packages,
never by executing setup.py).

Typosquat scoring: Levenshtein edit-distance (+ a same-length
transposition/substitution shortcut for the common "one-character-off"
typosquat pattern, e.g. "reqeusts" vs "requests") against a small bundled
list of top-N popular PyPI package names. A manifest entry within edit
distance 1-2 of a popular name -- and not an exact match, and not itself
the popular name -- is flagged as a possible typosquat.

Honest FP/FN: the top-N list here is small and hand-curated (not a live
PyPI top-8000 snapshot), so this will miss typosquats of less-common but
still-popular packages (FN), and it can flag legitimate short/similar
package family names as a false positive on packages we didn't special-
case (e.g. "flask-login" vs "flask"). Findings are therefore capped at
MEDIUM severity / "possible" confidence, never CRITICAL/HIGH -- this is
an advisory signal for human review, not a confirmed compromise.

Dependency-confusion check: flags manifest entries whose name looks like
an internal/private package (heuristic: contains an org-style prefix such
as "internal-", "corp-", "-internal", or matches a name pattern that is
NOT in the popular-package allowlist AND also not on the small "known
public PyPI names" set used for typosquat comparison) UNLESS the project
also ships a private-index configuration (a pip.conf/pyproject.toml
[[tool.poetry.source]] block, or a requirements.txt --index-url/
--extra-index-url line) naming a non-PyPI index -- in which case the risk
is presumed mitigated and the finding is suppressed. This is a coarse
heuristic (no live query of the public index, per "no network in default
paths"), so it is FN-prone for internal packages that don't match the
naming heuristic, and it is advisory-only (LOW/MEDIUM, "possible").
"""

import re
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Heimdall.Security.models.security_models import (
    DependencyRiskLevel,
    DependencyVulnerability,
)
from Asgard.Heimdall.Security.normalization.priority import confidence_bucket

# Small, hand-curated top-N popular PyPI package names used as the
# typosquat comparison set. Not exhaustive -- see module docstring FN note.
_POPULAR_PACKAGES = {
    "requests", "numpy", "pandas", "django", "flask", "pytest", "urllib3",
    "boto3", "click", "pyyaml", "cryptography", "pillow", "jinja2",
    "werkzeug", "sqlalchemy", "pydantic", "aiohttp", "certifi", "idna",
    "charset-normalizer", "setuptools", "wheel", "pip", "six", "attrs",
    "packaging", "markupsafe", "typing-extensions", "python-dateutil",
    "fastapi", "uvicorn", "starlette", "httpx", "redis", "celery",
    "gunicorn", "psycopg2", "pymysql", "lxml", "beautifulsoup4", "scrapy",
    "tensorflow", "torch", "scikit-learn", "matplotlib", "scipy",
}

_INTERNAL_NAME_HINTS = re.compile(
    r"(^internal[-_]|[-_]internal$|^corp[-_]|^acme[-_]|^private[-_]|-private$)",
    re.IGNORECASE,
)

_PRIVATE_INDEX_HINTS = re.compile(
    r"(--index-url|--extra-index-url|\[\[tool\.poetry\.source\]\]|\[tool\.uv\.index\])",
)


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1]


def _mk(package_name: str, installed_version: str, finding_kind: str,
        risk_level: DependencyRiskLevel, title: str, description: str,
        confidence: float) -> DependencyVulnerability:
    return DependencyVulnerability(
        package_name=package_name,
        installed_version=installed_version,
        vulnerable_versions="n/a",
        fixed_version=None,
        risk_level=risk_level,
        title=title,
        description=description,
        ecosystem="pypi",
        mechanism_id=f"supply_chain.{finding_kind}",
        confidence=confidence,
        confidence_bucket=confidence_bucket(confidence),
        finding_kind=finding_kind,
        source_db="local",
    )


def check_typosquat(package_name: str, installed_version: str) -> Optional[DependencyVulnerability]:
    """Flag a manifest package name that is suspiciously close (edit
    distance 1-2, same or similar length) to a popular package name, but
    is not itself that popular package."""
    normalized = package_name.lower().replace("_", "-")
    if normalized in _POPULAR_PACKAGES:
        return None

    best_match = None
    best_distance = 99
    for popular in _POPULAR_PACKAGES:
        if abs(len(popular) - len(normalized)) > 2:
            continue
        distance = _levenshtein(normalized, popular)
        if distance < best_distance:
            best_distance = distance
            best_match = popular

    if best_match and 1 <= best_distance <= 2:
        return _mk(
            package_name, installed_version, "typosquat", DependencyRiskLevel.MODERATE,
            f"'{package_name}' is suspiciously similar to popular package '{best_match}'",
            f"Manifest entry '{package_name}' is edit-distance {best_distance} from the "
            f"popular package '{best_match}'. This may be a legitimate related package "
            "(e.g. a plugin family) or a typosquat attempting to be installed by mistake "
            "-- verify this is the package you intended to depend on.",
            confidence=0.4,
        )
    return None


def check_dependency_confusion(
    package_name: str, installed_version: str, has_private_index: bool,
) -> Optional[DependencyVulnerability]:
    """Flag manifest entries that look like internal/private package
    names, unless a private index is configured (presumed mitigated)."""
    if has_private_index:
        return None
    normalized = package_name.lower().replace("_", "-")
    if _INTERNAL_NAME_HINTS.search(normalized):
        return _mk(
            package_name, installed_version, "dependency_confusion", DependencyRiskLevel.MODERATE,
            f"'{package_name}' looks like an internal package name with no private index configured",
            f"'{package_name}' matches an internal/private naming convention "
            "but no private package index (--index-url/--extra-index-url or a "
            "poetry/uv source block) was found in this project. If this name "
            "is also unclaimed on the public PyPI index, an attacker could "
            "publish a malicious package under this name and have it "
            "resolved instead of your internal one (dependency confusion, "
            "per Birsan 2021).",
            confidence=0.35,
        )
    return None


def detect_private_index(manifest_paths: List[Path]) -> bool:
    """Static text scan for private-index configuration across the
    project's manifest files -- no network query."""
    for path in manifest_paths:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _PRIVATE_INDEX_HINTS.search(content):
            return True
    return False


def is_dev_dependency_file(file_path: Path) -> bool:
    """Filename heuristic for dev/test-only dependency manifests (plan
    07.10 DEEPTHINK_11 severity discount). Static, no execution."""
    name = file_path.name.lower()
    return (
        "dev" in name
        or "test" in name
        or name in ("requirements-dev.txt", "dev-requirements.txt", "test-requirements.txt")
    )


def parse_pyproject_dev_dependencies(file_path: Path) -> Dict[str, str]:
    """Best-effort parse of PEP 621 [project.optional-dependencies] dev/test
    groups and Poetry [tool.poetry.group.dev.dependencies], returning names
    known to be dev-only so the caller can mark them discounted."""
    import tomllib

    dev_names: Dict[str, str] = {}
    try:
        with open(file_path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, Exception):
        return dev_names

    optional = data.get("project", {}).get("optional-dependencies", {})
    for group_name, deps in optional.items():
        if "dev" not in group_name.lower() and "test" not in group_name.lower():
            continue
        if isinstance(deps, list):
            for dep in deps:
                m = re.match(r"^([a-zA-Z0-9_-]+)", dep)
                if m:
                    dev_names[m.group(1).lower()] = "*"

    groups = data.get("tool", {}).get("poetry", {}).get("group", {})
    for group_name, group_data in groups.items():
        if "dev" not in group_name.lower() and "test" not in group_name.lower():
            continue
        deps = group_data.get("dependencies", {}) if isinstance(group_data, dict) else {}
        for name in deps:
            dev_names[name.lower()] = "*"

    return dev_names
