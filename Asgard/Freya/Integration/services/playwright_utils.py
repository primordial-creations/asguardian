"""
Freya Playwright Utilities

Utility functions for Playwright browser automation.
"""

from typing import Any, Dict, List, Literal, Optional, cast

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from Asgard.Freya.Integration.models.integration_models import (
    BrowserConfig,
    DeviceConfig,
)
from Asgard.Freya.Integration.services._playwright_presets import (
    DEVICE_PRESETS,
    NETWORK_PRESETS,
    apply_network_conditions,
)


class PlaywrightUtils:
    """
    Playwright utility functions.

    Provides helpers for browser automation.
    """

    def __init__(self, config: Optional[BrowserConfig] = None):
        """
        Initialize Playwright utilities.

        Args:
            config: Browser configuration
        """
        self.config = config or BrowserConfig()
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None

    async def launch_browser(self) -> Browser:
        """
        Launch a browser instance.

        Returns:
            Browser instance
        """
        pw: Playwright = await async_playwright().start()
        self._playwright = pw

        browser_type = pw.chromium
        if self.config.browser_type == "firefox":
            browser_type = pw.firefox
        elif self.config.browser_type == "webkit":
            browser_type = pw.webkit

        self._browser = await browser_type.launch(
            headless=self.config.headless,
            slow_mo=self.config.slow_mo,
        )

        return self._browser  # type: ignore[return-value]

    async def close_browser(self) -> None:
        """Close the browser instance."""
        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def create_context(
        self,
        device: Optional[str] = None,
        network: Optional[str] = None,
        record_video: bool = False,
        video_dir: Optional[str] = None
    ) -> BrowserContext:
        """
        Create a browser context.

        Args:
            device: Device preset name
            network: Network preset name
            record_video: Whether to record video
            video_dir: Video output directory

        Returns:
            Browser context
        """
        if not self._browser:
            await self.launch_browser()

        context_options = {
            "viewport": {
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            "device_scale_factor": self.config.device_scale_factor,
            "locale": self.config.locale,
        }

        if device and device in DEVICE_PRESETS:
            device_config = DEVICE_PRESETS[device]
            context_options["viewport"] = {
                "width": device_config.width,
                "height": device_config.height,
            }
            context_options["device_scale_factor"] = device_config.device_scale_factor
            context_options["is_mobile"] = device_config.is_mobile
            context_options["has_touch"] = device_config.has_touch
            if device_config.user_agent:
                context_options["user_agent"] = device_config.user_agent

        if self.config.user_agent:
            context_options["user_agent"] = self.config.user_agent

        if record_video and video_dir:
            context_options["record_video_dir"] = video_dir

        assert self._browser is not None
        context = await self._browser.new_context(**context_options)

        if network and network in NETWORK_PRESETS:
            await apply_network_conditions(context, NETWORK_PRESETS[network])

        return cast(BrowserContext, context)

    async def create_page(
        self,
        context: Optional[BrowserContext] = None,
        device: Optional[str] = None
    ) -> Page:
        """
        Create a new page.

        Args:
            context: Existing browser context
            device: Device preset name

        Returns:
            Page instance
        """
        if context is None:
            context = await self.create_context(device=device)

        page = await context.new_page()
        page.set_default_timeout(self.config.timeout)

        return page

    async def navigate(
        self,
        page: Page,
        url: str,
        wait_until: Literal["commit", "domcontentloaded", "load", "networkidle"] = "networkidle"
    ) -> None:
        """
        Navigate to a URL.

        Args:
            page: Page instance
            url: URL to navigate to
            wait_until: Wait condition
        """
        await page.goto(url, wait_until=wait_until, timeout=self.config.timeout)

    async def wait_for_network_idle(self, page: Page, timeout: int = 30000) -> None:
        """
        Wait for network to be idle.

        Args:
            page: Page instance
            timeout: Timeout in milliseconds
        """
        await page.wait_for_load_state("networkidle", timeout=timeout)

    async def take_screenshot(
        self,
        page: Page,
        path: str,
        full_page: bool = False,
        element: Optional[str] = None
    ) -> str:
        """
        Take a screenshot.

        Args:
            page: Page instance
            path: Output path
            full_page: Capture full page
            element: Optional element selector

        Returns:
            Screenshot path
        """
        if element:
            locator = page.locator(element)
            await locator.screenshot(path=path)
        else:
            await page.screenshot(path=path, full_page=full_page)

        return path

    async def evaluate(self, page: Page, script: str) -> Any:
        """
        Evaluate JavaScript on page.

        Args:
            page: Page instance
            script: JavaScript code

        Returns:
            Evaluation result
        """
        return await page.evaluate(script)

    async def get_page_metrics(self, page: Page) -> Dict:
        """
        Get page performance metrics.

        Args:
            page: Page instance

        Returns:
            Performance metrics dict
        """
        metrics = await page.evaluate("""
            () => {
                const timing = performance.timing;
                const navigation = performance.getEntriesByType('navigation')[0];
                const resources = performance.getEntriesByType('resource');

                return {
                    loadTime: timing.loadEventEnd - timing.navigationStart,
                    domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
                    firstPaint: performance.getEntriesByName('first-paint')[0]?.startTime || null,
                    firstContentfulPaint: performance.getEntriesByName('first-contentful-paint')[0]?.startTime || null,
                    resourceCount: resources.length,
                    transferSize: resources.reduce((sum, r) => sum + (r.transferSize || 0), 0),
                };
            }
        """)
        return cast(Dict[Any, Any], metrics)

    async def get_accessibility_tree(self, page: Page) -> Dict:
        """
        Get accessibility tree snapshot.

        Args:
            page: Page instance

        Returns:
            Accessibility tree
        """
        return cast(Dict[Any, Any], await page.accessibility.snapshot())  # type: ignore[attr-defined]

    async def emulate_media(
        self,
        page: Page,
        color_scheme: Optional[str] = None,
        reduced_motion: Optional[str] = None
    ) -> None:
        """
        Emulate media features.

        Args:
            page: Page instance
            color_scheme: 'light', 'dark', or 'no-preference'
            reduced_motion: 'reduce' or 'no-preference'
        """
        media_features = []

        if color_scheme:
            media_features.append({"name": "prefers-color-scheme", "value": color_scheme})

        if reduced_motion:
            media_features.append({"name": "prefers-reduced-motion", "value": reduced_motion})

        if media_features:
            await page.emulate_media(  # type: ignore[arg-type]
                color_scheme=color_scheme,  # type: ignore[arg-type]
                reduced_motion=reduced_motion,  # type: ignore[arg-type]
            )

    async def set_viewport(self, page: Page, width: int, height: int) -> None:
        """
        Set viewport size.

        Args:
            page: Page instance
            width: Viewport width
            height: Viewport height
        """
        await page.set_viewport_size({"width": width, "height": height})

    async def _apply_network_conditions(self, context: BrowserContext, conditions: Dict) -> None:
        """Apply network throttling conditions."""
        await apply_network_conditions(context, conditions)

    def get_device_presets(self) -> List[str]:
        """Get list of available device presets."""
        return list(DEVICE_PRESETS.keys())

    def get_network_presets(self) -> List[str]:
        """Get list of available network presets."""
        return list(NETWORK_PRESETS.keys())

    def get_device_config(self, device: str) -> Optional[DeviceConfig]:
        """Get configuration for a device preset."""
        return DEVICE_PRESETS.get(device)
