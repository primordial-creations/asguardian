"""
Freya Baseline Manager

Manages visual baselines for regression testing.
"""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Freya.Integration.models.integration_models import (
    BaselineConfig,
    BaselineEntry,
)
from Asgard.Freya.Integration.services._baseline_manager_helpers import (
    calculate_hash,
    generate_key,
    load_index,
    save_index,
    version_baseline,
)
from Asgard.Freya.Visual.models.visual_models import ComparisonConfig
from Asgard.Freya.Visual.services import ScreenshotCapture, VisualRegressionTester


class BaselineManager:
    """
    Baseline management service.

    Manages visual baselines for regression testing.
    """

    def __init__(self, config: Optional[BaselineConfig] = None):
        """
        Initialize the Baseline Manager.

        Args:
            config: Baseline configuration
        """
        self.config = config or BaselineConfig()
        self.storage_dir = Path(self.config.storage_directory)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.storage_dir / "baselines.json"
        self._load_index()

    def _load_index(self) -> None:
        """Load baseline index from file."""
        self.baselines: Dict[str, BaselineEntry] = load_index(self.index_file)

    def _save_index(self) -> None:
        """Save baseline index to file."""
        save_index(self.index_file, self.baselines)

    async def create_baseline(
        self,
        url: str,
        name: str,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        device: Optional[str] = None
    ) -> BaselineEntry:
        """
        Create a new baseline for a URL.

        Args:
            url: URL to capture
            name: Baseline name
            viewport_width: Viewport width
            viewport_height: Viewport height
            device: Optional device name

        Returns:
            Created BaselineEntry
        """
        capture = ScreenshotCapture(output_directory=str(self.storage_dir / "screenshots"))

        if device:
            screenshots = await capture.capture_with_devices(url, devices=[device])
            if not screenshots:
                raise ValueError(f"Device '{device}' not found")
            screenshot = screenshots[0]
        else:
            screenshot = await capture.capture_full_page(url)

        baseline_key = generate_key(url, name, device)
        baseline_dir = self.storage_dir / baseline_key
        baseline_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        baseline_path = baseline_dir / f"baseline_{timestamp}.png"

        shutil.copy(screenshot.file_path, baseline_path)

        image_hash = calculate_hash(str(baseline_path))

        entry = BaselineEntry(
            url=url,
            name=name,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            screenshot_path=str(baseline_path),
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            device=device,
            hash=image_hash,
            metadata={
                "format": screenshot.metadata.get("format", "png"),
                "file_size": screenshot.file_size_bytes,
            },
        )

        self.baselines[baseline_key] = entry
        self._save_index()

        if self.config.version_baselines:
            version_baseline(
                self.storage_dir, baseline_key, str(baseline_path), self.config.max_versions
            )

        return entry

    async def update_baseline(
        self,
        url: str,
        name: str,
        device: Optional[str] = None
    ) -> BaselineEntry:
        """
        Update an existing baseline.

        Args:
            url: URL to capture
            name: Baseline name
            device: Optional device name

        Returns:
            Updated BaselineEntry
        """
        baseline_key = generate_key(url, name, device)

        if baseline_key in self.baselines:
            existing = self.baselines[baseline_key]
            viewport_width = existing.viewport_width
            viewport_height = existing.viewport_height
        else:
            viewport_width = 1920
            viewport_height = 1080

        return await self.create_baseline(url, name, viewport_width, viewport_height, device)

    async def compare_to_baseline(
        self,
        url: str,
        name: str,
        device: Optional[str] = None,
        threshold: Optional[float] = None
    ) -> Dict:
        """
        Compare current page to baseline.

        Args:
            url: URL to compare
            name: Baseline name
            device: Optional device name
            threshold: Difference threshold

        Returns:
            Comparison result dict
        """
        baseline_key = generate_key(url, name, device)

        if baseline_key not in self.baselines:
            return {
                "success": False,
                "error": f"Baseline not found: {name}",
                "baseline_key": baseline_key,
            }

        baseline = self.baselines[baseline_key]

        capture = ScreenshotCapture(output_directory=str(self.storage_dir / "current"))

        if device:
            screenshots = await capture.capture_with_devices(url, devices=[device])
            if not screenshots:
                raise ValueError(f"Device '{device}' not found")
            current = screenshots[0]
        else:
            current = await capture.capture_full_page(url)

        effective_threshold = threshold if threshold is not None else self.config.diff_threshold
        regression = VisualRegressionTester(output_directory=str(self.storage_dir / "diffs"))
        comparison_config = ComparisonConfig(threshold=1.0 - effective_threshold)

        result = regression.compare(baseline.screenshot_path, current.file_path, comparison_config)

        has_difference = not result.is_similar
        difference_percentage = round((1.0 - result.similarity_score) * 100, 2)

        if has_difference and self.config.auto_update:
            await self.update_baseline(url, name, device)

        return {
            "success": True,
            "baseline": baseline.model_dump(),
            "current_screenshot": current.file_path,
            "has_difference": has_difference,
            "difference_percentage": difference_percentage,
            "diff_image_path": result.diff_image_path,
            "passed": not has_difference,
        }

    def list_baselines(self, url: Optional[str] = None) -> List[BaselineEntry]:
        """List all baselines."""
        if url:
            return [b for b in self.baselines.values() if b.url == url]
        return list(self.baselines.values())

    def get_baseline(
        self,
        url: str,
        name: str,
        device: Optional[str] = None
    ) -> Optional[BaselineEntry]:
        """Get a specific baseline."""
        baseline_key = generate_key(url, name, device)
        return self.baselines.get(baseline_key)

    def delete_baseline(
        self,
        url: str,
        name: str,
        device: Optional[str] = None
    ) -> bool:
        """Delete a baseline."""
        baseline_key = generate_key(url, name, device)

        if baseline_key not in self.baselines:
            return False

        baseline = self.baselines[baseline_key]
        baseline_path = Path(baseline.screenshot_path)

        if baseline_path.exists():
            baseline_path.unlink()

        baseline_dir = self.storage_dir / baseline_key
        if baseline_dir.exists():
            shutil.rmtree(baseline_dir)

        del self.baselines[baseline_key]
        self._save_index()

        return True

    def get_versions(
        self,
        url: str,
        name: str,
        device: Optional[str] = None
    ) -> List[str]:
        """Get all versions of a baseline."""
        baseline_key = generate_key(url, name, device)
        versions_dir = self.storage_dir / baseline_key / "versions"

        if not versions_dir.exists():
            return []

        versions = sorted(versions_dir.glob("*.png"))
        return [str(v) for v in versions]

    def _generate_key(self, url: str, name: str, device: Optional[str]) -> str:
        """Generate a unique key for a baseline."""
        return generate_key(url, name, device)

    def _calculate_hash(self, image_path: str) -> str:
        """Calculate hash of an image file."""
        return calculate_hash(image_path)

    def _version_baseline(self, baseline_key: str, screenshot_path: str) -> None:
        """Create a versioned copy of a baseline."""
        version_baseline(
            self.storage_dir, baseline_key, screenshot_path, self.config.max_versions
        )
