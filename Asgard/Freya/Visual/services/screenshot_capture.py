"""
Freya Screenshot Capture

Captures screenshots with device emulation, full-page support,
element targeting, and various configuration options.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, Browser

from Asgard.Freya.Visual.models.visual_models import (
    ScreenshotConfig,
    ScreenshotResult,
    DeviceConfig,
    COMMON_DEVICES,
)
from Asgard.Freya.Visual.services._screenshot_capture_helpers import (
    capture,
    capture_element,
    url_to_filename,
)


class ScreenshotCapture:
    """
    Screenshot capture service.

    Captures full-page, viewport, and element screenshots
    with device emulation support.
    """

    def __init__(self, output_directory: str = "./screenshots"):
        """
        Initialize the Screenshot Capture service.

        Args:
            output_directory: Directory to save screenshots
        """
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)

    async def capture_full_page(
        self,
        url: str,
        filename: Optional[str] = None,
        config: Optional[ScreenshotConfig] = None
    ) -> ScreenshotResult:
        """
        Capture a full-page screenshot.

        Args:
            url: URL to capture
            filename: Output filename (auto-generated if not provided)
            config: Screenshot configuration

        Returns:
            ScreenshotResult with capture details
        """
        if config is None:
            config = ScreenshotConfig(full_page=True)
        else:
            config = config.model_copy(update={"full_page": True})

        return await capture(url, filename, config, self.output_directory)

    async def capture_viewport(
        self,
        url: str,
        filename: Optional[str] = None,
        config: Optional[ScreenshotConfig] = None
    ) -> ScreenshotResult:
        """
        Capture a viewport screenshot.

        Args:
            url: URL to capture
            filename: Output filename
            config: Screenshot configuration

        Returns:
            ScreenshotResult with capture details
        """
        if config is None:
            config = ScreenshotConfig(full_page=False)
        else:
            config = config.model_copy(update={"full_page": False})

        return await capture(url, filename, config, self.output_directory)

    async def capture_element(
        self,
        url: str,
        selector: str,
        filename: Optional[str] = None,
        config: Optional[ScreenshotConfig] = None
    ) -> ScreenshotResult:
        """
        Capture a screenshot of a specific element.

        Args:
            url: URL to capture
            selector: CSS selector for the element
            filename: Output filename
            config: Screenshot configuration

        Returns:
            ScreenshotResult with capture details
        """
        if config is None:
            config = ScreenshotConfig(full_page=False)

        return await capture_element(url, selector, filename, config, self.output_directory)

    async def capture_with_devices(
        self,
        url: str,
        devices: list[str],
        filename_prefix: Optional[str] = None
    ) -> list[ScreenshotResult]:
        """
        Capture screenshots across multiple devices.

        Args:
            url: URL to capture
            devices: List of device names from COMMON_DEVICES
            filename_prefix: Prefix for filenames

        Returns:
            List of ScreenshotResult for each device
        """
        results = []

        for device_name in devices:
            if device_name not in COMMON_DEVICES:
                continue

            config = ScreenshotConfig(
                full_page=True,
                device=device_name,
            )

            prefix = filename_prefix or url_to_filename(url)
            filename = f"{prefix}_{device_name}.png"

            result = await capture(url, filename, config, self.output_directory)
            results.append(result)

        return results

    async def _capture(
        self,
        url: str,
        filename: Optional[str],
        config: ScreenshotConfig
    ) -> ScreenshotResult:
        """Internal capture implementation."""
        return await capture(url, filename, config, self.output_directory)

    async def _capture_element(
        self,
        url: str,
        selector: str,
        filename: Optional[str],
        config: ScreenshotConfig
    ) -> ScreenshotResult:
        """Capture a specific element."""
        return await capture_element(url, selector, filename, config, self.output_directory)

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to safe filename."""
        return url_to_filename(url)
