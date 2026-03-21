"""
Freya Screenshot Capture helper functions.

Helper functions extracted from screenshot_capture.py.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright

from Asgard.Freya.Visual.models.visual_models import (
    ScreenshotConfig,
    ScreenshotResult,
    COMMON_DEVICES,
)


def url_to_filename(url: str) -> str:
    """Convert URL to safe filename."""
    url = url.replace("https://", "").replace("http://", "")
    url = url.replace("/", "_").replace(":", "_").replace("?", "_")
    url = url.replace("&", "_").replace("=", "_")
    return url[:50]


async def capture(
    url: str,
    filename: Optional[str],
    config: ScreenshotConfig,
    output_directory: Path,
) -> ScreenshotResult:
    """Internal capture implementation."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        url_part = url_to_filename(url)
        filename = f"{url_part}_{timestamp}.{config.format}"

    file_path = output_directory / filename

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context_options = {}

        if config.device and config.device in COMMON_DEVICES:
            device = COMMON_DEVICES[config.device]
            context_options = {
                "viewport": {"width": device.width, "height": device.height},
                "device_scale_factor": device.device_scale_factor,
                "is_mobile": device.is_mobile,
                "has_touch": device.has_touch,
            }
            if device.user_agent:
                context_options["user_agent"] = device.user_agent
        elif config.custom_device:
            device = config.custom_device
            context_options = {
                "viewport": {"width": device.width, "height": device.height},
                "device_scale_factor": device.device_scale_factor,
                "is_mobile": device.is_mobile,
                "has_touch": device.has_touch,
            }
            if device.user_agent:
                context_options["user_agent"] = device.user_agent

        context = await browser.new_context(**context_options)
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)

            if config.wait_for_selector:
                await page.wait_for_selector(config.wait_for_selector, timeout=10000)

            if config.wait_for_timeout > 0:
                await page.wait_for_timeout(config.wait_for_timeout)

            for selector in config.hide_selectors:
                await page.evaluate(f"""
                    () => {{
                        const elements = document.querySelectorAll("{selector}");
                        elements.forEach(el => el.style.visibility = 'hidden');
                    }}
                """)

            screenshot_options = {
                "path": str(file_path),
                "full_page": config.full_page,
                "type": config.format,
            }

            if config.format == "jpeg":
                screenshot_options["quality"] = config.quality

            if config.clip:
                screenshot_options["clip"] = config.clip

            await page.screenshot(**screenshot_options)

            viewport = page.viewport_size
            width = viewport["width"] if viewport else 1920
            height = viewport["height"] if viewport else 1080

            if config.full_page:
                dimensions = await page.evaluate("""
                    () => ({
                        width: document.documentElement.scrollWidth,
                        height: document.documentElement.scrollHeight
                    })
                """)
                width = dimensions["width"]
                height = dimensions["height"]

        finally:
            await browser.close()

    file_size = os.path.getsize(file_path)

    return ScreenshotResult(
        url=url,
        file_path=str(file_path),
        width=width,
        height=height,
        device=config.device,
        captured_at=datetime.now().isoformat(),
        file_size_bytes=file_size,
        metadata={
            "full_page": config.full_page,
            "format": config.format,
        }
    )


async def capture_element(
    url: str,
    selector: str,
    filename: Optional[str],
    config: ScreenshotConfig,
    output_directory: Path,
) -> ScreenshotResult:
    """Capture a specific element."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        selector_part = selector.replace(" ", "_").replace(".", "_")[:20]
        filename = f"element_{selector_part}_{timestamp}.{config.format}"

    file_path = output_directory / filename

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)

            if config.wait_for_timeout > 0:
                await page.wait_for_timeout(config.wait_for_timeout)

            element = await page.wait_for_selector(selector, timeout=10000)

            if element is None:
                raise ValueError(f"Element not found: {selector}")

            screenshot_options = {
                "path": str(file_path),
                "type": config.format,
            }

            if config.format == "jpeg":
                screenshot_options["quality"] = config.quality

            await element.screenshot(**screenshot_options)

            box = await element.bounding_box()
            width = int(box["width"]) if box else 0
            height = int(box["height"]) if box else 0

        finally:
            await browser.close()

    file_size = os.path.getsize(file_path)

    return ScreenshotResult(
        url=url,
        file_path=str(file_path),
        width=width,
        height=height,
        device=config.device,
        captured_at=datetime.now().isoformat(),
        file_size_bytes=file_size,
        metadata={
            "element_selector": selector,
            "format": config.format,
        }
    )
