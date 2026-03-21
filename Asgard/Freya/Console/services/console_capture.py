"""
Freya Console Capture

Captures JavaScript console messages, errors, and warnings
during page load.
"""

import asyncio
import re
from datetime import datetime
from typing import Callable, Dict, List, Optional, cast

from playwright.async_api import ConsoleMessage as PWConsoleMessage
from playwright.async_api import Error, Page, async_playwright

from Asgard.Freya.Console.models.console_models import (
    ConsoleConfig,
    ConsoleMessage,
    ConsoleMessageType,
    ConsoleReport,
    ConsoleSeverity,
    PageError,
    ResourceError,
)
from Asgard.Freya.Console.services._console_capture_helpers import (
    TYPE_MAP,
    SEVERITY_MAP,
    build_report,
    process_console_message,
    process_page_error,
    should_capture,
)


class ConsoleCapture:
    """
    Captures JavaScript console messages.

    Uses Playwright to load pages and capture all console output
    including errors, warnings, and failed resource loads.
    """

    TYPE_MAP = TYPE_MAP
    SEVERITY_MAP = SEVERITY_MAP

    def __init__(self, config: Optional[ConsoleConfig] = None):
        """
        Initialize the console capture.

        Args:
            config: Console capture configuration
        """
        self.config = config or ConsoleConfig()

    async def capture(self, url: str) -> ConsoleReport:
        """
        Capture console messages for a URL.

        Args:
            url: URL to load and capture

        Returns:
            ConsoleReport with all captured messages
        """
        start_time = datetime.now()

        messages: List[ConsoleMessage] = []
        errors: List[PageError] = []
        resource_errors: List[ResourceError] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            def on_console(msg: PWConsoleMessage) -> None:
                if len(messages) >= self.config.max_messages:
                    return

                message = process_console_message(msg, self.config)
                if message and should_capture(message, self.config):
                    messages.append(message)

            def on_page_error(error: Error) -> None:
                page_error = process_page_error(error, self.config)
                if page_error:
                    errors.append(page_error)

            def on_request_failed(request) -> None:
                if not self.config.capture_resource_errors:
                    return

                resource_error = ResourceError(
                    url=request.url,
                    resource_type=request.resource_type,
                    error_text=request.failure,
                )
                resource_errors.append(resource_error)

            page.on("console", on_console)
            page.on("pageerror", on_page_error)
            page.on("requestfailed", on_request_failed)

            try:
                if self.config.wait_for_network_idle:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                else:
                    await page.goto(url, wait_until="load", timeout=30000)

                if self.config.wait_time_ms > 0:
                    await asyncio.sleep(self.config.wait_time_ms / 1000)

            except Exception as e:
                errors.append(PageError(
                    message=str(e),
                    name="NavigationError",
                ))

            finally:
                await browser.close()

        capture_duration = (datetime.now() - start_time).total_seconds() * 1000

        return build_report(url, messages, errors, resource_errors, capture_duration)

    async def capture_page(
        self,
        page: Page,
        url: str,
        duration_ms: int = 3000,
    ) -> ConsoleReport:
        """
        Capture console messages from an already loaded page.

        Args:
            page: Playwright Page object
            url: URL of the page
            duration_ms: How long to capture messages

        Returns:
            ConsoleReport with captured messages
        """
        start_time = datetime.now()

        messages: List[ConsoleMessage] = []
        errors: List[PageError] = []
        resource_errors: List[ResourceError] = []

        def on_console(msg: PWConsoleMessage) -> None:
            if len(messages) >= self.config.max_messages:
                return
            message = process_console_message(msg, self.config)
            if message and should_capture(message, self.config):
                messages.append(message)

        def on_page_error(error: Error) -> None:
            page_error = process_page_error(error, self.config)
            if page_error:
                errors.append(page_error)

        def on_request_failed(request) -> None:
            if not self.config.capture_resource_errors:
                return
            resource_error = ResourceError(
                url=request.url,
                resource_type=request.resource_type,
                error_text=request.failure,
            )
            resource_errors.append(resource_error)

        page.on("console", on_console)
        page.on("pageerror", on_page_error)
        page.on("requestfailed", on_request_failed)

        await asyncio.sleep(duration_ms / 1000)

        page.remove_listener("console", on_console)
        page.remove_listener("pageerror", on_page_error)
        page.remove_listener("requestfailed", on_request_failed)

        capture_duration = (datetime.now() - start_time).total_seconds() * 1000

        return build_report(url, messages, errors, resource_errors, capture_duration)

    def _process_console_message(
        self, msg: PWConsoleMessage
    ) -> Optional[ConsoleMessage]:
        """Process a Playwright console message."""
        return process_console_message(msg, self.config)

    def _process_page_error(self, error: Error) -> Optional[PageError]:
        """Process a page error."""
        return process_page_error(error, self.config)

    def _should_capture(self, message: ConsoleMessage) -> bool:
        """Check if a message should be captured based on config."""
        return should_capture(message, self.config)

    def _build_report(
        self,
        url: str,
        messages: List[ConsoleMessage],
        errors: List[PageError],
        resource_errors: List[ResourceError],
        capture_duration: float,
    ) -> ConsoleReport:
        """Build the console report."""
        return build_report(url, messages, errors, resource_errors, capture_duration)
