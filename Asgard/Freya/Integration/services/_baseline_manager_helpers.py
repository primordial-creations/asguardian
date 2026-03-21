"""
Freya Baseline Manager helper functions.

Helper functions extracted from baseline_manager.py.
"""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from Asgard.Freya.Integration.models.integration_models import (
    BaselineConfig,
    BaselineEntry,
)


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
