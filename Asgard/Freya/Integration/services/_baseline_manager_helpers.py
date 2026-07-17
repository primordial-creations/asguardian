"""
Freya Baseline Manager helper functions.

Helper functions extracted from baseline_manager.py.
"""

import hashlib
import json
import platform
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from Asgard.Freya.Integration.models.integration_models import (
    BaselineConfig,
    BaselineEntry,
    EnvironmentFingerprint,
)

#: Fingerprint fields whose mismatch makes pixel comparison meaningless
#: (text metrics / rasterization differ): comparison is refused by default.
HARD_MISMATCH_FIELDS = ("device_scale_factor", "viewport", "os_name")

#: Fields whose mismatch degrades confidence but allows comparison.
SOFT_MISMATCH_FIELDS = ("browser_version", "font_stack_hash")

#: DEEPTHINK_03 rationale attached to environment_mismatch results.
ENV_MISMATCH_RATIONALE = (
    "Cross-environment pixel comparison measures the environment, not "
    "your code. A baseline is only valid as a controlled delta: same OS, "
    "viewport, and device scale factor on both sides. Re-capture the "
    "baseline in this environment, or pass allow_env_mismatch to compare "
    "anyway (result will be capped at WARNING severity)."
)

_FONT_STACK_JS = (
    "() => { try { return [...document.fonts]"
    ".map(f => f.family + ':' + f.weight).sort().join('|'); }"
    " catch (e) { return null; } }"
)


def _playwright_version() -> str:
    """Best-effort Playwright package version."""
    try:
        from importlib.metadata import version
        return version("playwright")
    except Exception:
        return ""


async def capture_fingerprint(
    page: Optional[Any] = None,
    viewport_width: int = 0,
    viewport_height: int = 0,
    device_scale_factor: float = 1.0,
    browser_name: str = "chromium",
) -> EnvironmentFingerprint:
    """
    Capture the current environment fingerprint.

    Platform facts always come from `platform`; browser/page facts are
    best-effort introspection when a live page is supplied.
    """
    browser_version = ""
    font_stack_hash: Optional[str] = None
    if page is not None:
        try:
            context = getattr(page, "context", None)
            browser = getattr(context, "browser", None) if context else None
            if browser is not None:
                browser_version = str(getattr(browser, "version", "") or "")
                browser_type = getattr(browser, "browser_type", None)
                name = getattr(browser_type, "name", None) if browser_type else None
                if name:
                    browser_name = str(name)
        except Exception:
            pass
        try:
            viewport = getattr(page, "viewport_size", None)
            if viewport:
                viewport_width = viewport.get("width", viewport_width)
                viewport_height = viewport.get("height", viewport_height)
        except Exception:
            pass
        try:
            fonts = await page.evaluate(_FONT_STACK_JS)
            if fonts:
                font_stack_hash = hashlib.sha256(fonts.encode()).hexdigest()[:32]
        except Exception:
            pass

    return EnvironmentFingerprint(
        os_name=platform.system(),
        os_release=platform.release(),
        browser_name=browser_name,
        browser_version=browser_version,
        playwright_version=_playwright_version(),
        viewport=f"{viewport_width}x{viewport_height}",
        device_scale_factor=device_scale_factor,
        font_stack_hash=font_stack_hash,
    )


def classify_fingerprint_mismatch(
    baseline: Optional[EnvironmentFingerprint],
    current: Optional[EnvironmentFingerprint],
) -> Tuple[str, List[str]]:
    """
    Classify the mismatch between two fingerprints.

    Returns (level, differing_fields) where level is:
        "unverified" — baseline (or current) has no fingerprint
        "hard"       — comparison meaningless (DPR/viewport/OS differ)
        "soft"       — comparison allowed, result flagged
        "none"       — environments match
    Fields that are empty/None on either side are not compared
    (absence of evidence is not evidence of mismatch).
    """
    if baseline is None or current is None:
        return "unverified", []

    def _differs(field: str) -> bool:
        a, b = getattr(baseline, field), getattr(current, field)
        if a in (None, "", 0.0) or b in (None, "", 0.0):
            return False
        return bool(a != b)

    hard = [f for f in HARD_MISMATCH_FIELDS if _differs(f)]
    soft = [f for f in SOFT_MISMATCH_FIELDS if _differs(f)]
    if hard:
        return "hard", hard + soft
    if soft:
        return "soft", soft
    return "none", []


def load_index(index_file: Path) -> Dict[str, BaselineEntry]:
    """Load baseline index from file."""
    if index_file.exists():
        with open(index_file, "r") as f:
            data = json.load(f)
            return {k: BaselineEntry(**v) for k, v in data.items()}
    return {}


def save_index(index_file: Path, baselines: Dict[str, BaselineEntry]) -> None:
    """Save baseline index to file."""
    data = {k: v.model_dump() for k, v in baselines.items()}
    with open(index_file, "w") as f:
        json.dump(data, f, indent=2, default=str)


def generate_key(url: str, name: str, device: Optional[str]) -> str:
    """Generate a unique key for a baseline."""
    key_parts = [url, name]
    if device:
        key_parts.append(device)

    key_string = ":".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()[:16]


def calculate_hash(image_path: str) -> str:
    """Calculate hash of an image file."""
    with open(image_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:32]


def version_baseline(
    storage_dir: Path,
    baseline_key: str,
    screenshot_path: str,
    max_versions: int,
) -> None:
    """Create a versioned copy of a baseline."""
    versions_dir = storage_dir / baseline_key / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_path = versions_dir / f"v_{timestamp}.png"

    shutil.copy(screenshot_path, version_path)

    versions = sorted(versions_dir.glob("*.png"))
    if len(versions) > max_versions:
        for old_version in versions[:-max_versions]:
            old_version.unlink()
