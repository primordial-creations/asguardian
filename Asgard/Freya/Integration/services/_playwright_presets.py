"""
Freya Playwright Utilities presets and network helpers.

Extracted from playwright_utils.py.
"""

from typing import Any, Dict

from playwright.async_api import BrowserContext

from Asgard.Freya.Integration.models.integration_models import DeviceConfig


DEVICE_PRESETS: Dict[str, DeviceConfig] = {
    "iphone-14": DeviceConfig(
        name="iPhone 14",
        width=390,
        height=844,
        device_scale_factor=3.0,
        is_mobile=True,
        has_touch=True,
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
    ),
    "iphone-14-pro-max": DeviceConfig(
        name="iPhone 14 Pro Max",
        width=430,
        height=932,
        device_scale_factor=3.0,
        is_mobile=True,
        has_touch=True,
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
    ),
    "pixel-7": DeviceConfig(
        name="Pixel 7",
        width=412,
        height=915,
        device_scale_factor=2.625,
        is_mobile=True,
        has_touch=True,
        user_agent="Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36",
    ),
    "ipad": DeviceConfig(
        name="iPad",
        width=768,
        height=1024,
        device_scale_factor=2.0,
        is_mobile=True,
        has_touch=True,
        user_agent="Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
    ),
    "ipad-pro": DeviceConfig(
        name="iPad Pro",
        width=1024,
        height=1366,
        device_scale_factor=2.0,
        is_mobile=True,
        has_touch=True,
        user_agent="Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
    ),
    "galaxy-s21": DeviceConfig(
        name="Galaxy S21",
        width=360,
        height=800,
        device_scale_factor=3.0,
        is_mobile=True,
        has_touch=True,
        user_agent="Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36",
    ),
}


NETWORK_PRESETS: Dict[str, Dict[str, Any]] = {
    "slow-3g": {
        "offline": False,
        "download_throughput": 500 * 1024 / 8,
        "upload_throughput": 500 * 1024 / 8,
        "latency": 400,
    },
    "fast-3g": {
        "offline": False,
        "download_throughput": 1.6 * 1024 * 1024 / 8,
        "upload_throughput": 768 * 1024 / 8,
        "latency": 150,
    },
    "4g": {
        "offline": False,
        "download_throughput": 4 * 1024 * 1024 / 8,
        "upload_throughput": 3 * 1024 * 1024 / 8,
        "latency": 20,
    },
    "offline": {
        "offline": True,
        "download_throughput": 0,
        "upload_throughput": 0,
        "latency": 0,
    },
}


async def apply_network_conditions(context: BrowserContext, conditions: Dict) -> None:
    """Apply network throttling conditions."""
    cdp = await context.new_cdp_session(await context.new_page())
    await cdp.send("Network.emulateNetworkConditions", {
        "offline": conditions["offline"],
        "downloadThroughput": conditions["download_throughput"],
        "uploadThroughput": conditions["upload_throughput"],
        "latency": conditions["latency"],
    })
