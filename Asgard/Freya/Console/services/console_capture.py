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


class ConsoleCapture:
    """
    Captures JavaScript console messages.

    Uses Playwright to load pages and capture all console output
    including errors, warnings, and failed resource loads.
    """

    # Map Playwright message types to our types
    TYPE_MAP = {
        "error": ConsoleMessageType.ERROR,
        "warning": ConsoleMessageType.WARNING,
        "info": ConsoleMessageType.INFO,
        "log": ConsoleMessageType.LOG,
        "debug": ConsoleMessageType.DEBUG,
        "trace": ConsoleMessageType.TRACE,
        "dir": ConsoleMessageType.DIR,
        "assert": ConsoleMessageType.ASSERT,
        "count": ConsoleMessageType.COUNT,
        "table": ConsoleMessageType.TABLE,
        "time": ConsoleMessageType.TIME,
        "timeEnd": ConsoleMessageType.TIME_END,
    }

    # Map message types to severity
    SEVERITY_MAP = {
        ConsoleMessageType.ERROR: ConsoleSeverity.ERROR,
        ConsoleMessageType.WARNING: ConsoleSeverity.WARNING,
        ConsoleMessageType.INFO: ConsoleSeverity.INFO,
        ConsoleMessageType.LOG: ConsoleSeverity.INFO,
        ConsoleMessageType.DEBUG: ConsoleSeverity.DEBUG,
        ConsoleMessageType.TRACE: ConsoleSeverity.DEBUG,
        ConsoleMessageType.DIR: ConsoleSeverity.DEBUG,
        ConsoleMessageType.ASSERT: ConsoleSeverity.ERROR,
        ConsoleMessageType.COUNT: ConsoleSeverity.DEBUG,
        ConsoleMessageType.TABLE: ConsoleSeverity.DEBUG,
        ConsoleMessageType.TIME: ConsoleSeverity.DEBUG,
        ConsoleMessageType.TIME_END: ConsoleSeverity.DEBUG,
    }

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

            # Set up console listener
            def on_console(msg: PWConsoleMessage) -> None:
                if len(messages) >= self.config.max_messages:
                    return

                message = self._process_console_message(msg)
                if message and self._should_capture(message):
                    messages.append(message)

            # Set up error listener
            def on_page_error(error: Error) -> None:
                page_error = self._process_page_error(error)
                if page_error:
                    errors.append(page_error)

            # Set up request failed listener
            def on_request_failed(request) -> None:
                if not self.config.capture_resource_errors:
                    return

                resource_error = ResourceError(
                    url=request.url,
                    resource_type=request.resource_type,
                    error_text=request.failure,
                )
                resource_errors.append(resource_error)

            # Attach listeners
            page.on("console", on_console)
            page.on("pageerror", on_page_error)
            page.on("requestfailed", on_request_failed)

            try:
                # Navigate to the page
                if self.config.wait_for_network_idle:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                else:
                    await page.goto(url, wait_until="load", timeout=30000)

                # Wait additional time for any async errors
                if self.config.wait_time_ms > 0:
                    await asyncio.sleep(self.config.wait_time_ms / 1000)

            except Exception as e:
                # Capture navigation errors
                errors.append(PageError(
                    message=str(e),
                    name="NavigationError",
                ))

            finally:
                await browser.close()

        # Build report
        capture_duration = (datetime.now() - start_time).total_seconds() * 1000

        return self._build_report(
            url,
            messages,
            errors,
            resource_errors,
            capture_duration,
        )

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

        # Set up listeners
        def on_console(msg: PWConsoleMessage) -> None:
            if len(messages) >= self.config.max_messages:
                return
            message = self._process_console_message(msg)
            if message and self._should_capture(message):
                messages.append(message)

        def on_page_error(error: Error) -> None:
            page_error = self._process_page_error(error)
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

        # Attach listeners
        page.on("console", on_console)
        page.on("pageerror", on_page_error)
        page.on("requestfailed", on_request_failed)

        # Wait for messages
        await asyncio.sleep(duration_ms / 1000)

        # Remove listeners
        page.remove_listener("console", on_console)
        page.remove_listener("pageerror", on_page_error)
        page.remove_listener("requestfailed", on_request_failed)

        capture_duration = (datetime.now() - start_time).total_seconds() * 1000

        return self._build_report(
            url,
            messages,
            errors,
            resource_errors,
            capture_duration,
        )

    def _process_console_message(
        self, msg: PWConsoleMessage
    ) -> Optional[ConsoleMessage]:
        """Process a Playwright console message."""
        msg_type_str = msg.type
        msg_type = self.TYPE_MAP.get(msg_type_str, ConsoleMessageType.LOG)
        severity = self.SEVERITY_MAP.get(msg_type, ConsoleSeverity.INFO)

        text = msg.text
        if len(text) > self.config.max_message_length:
            text = text[: self.config.max_message_length] + "..."

        # Check ignore patterns
        for pattern in self.config.ignore_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return None

        location = msg.location
        url = location.get("url") if location else None
        line_number = location.get("lineNumber") if location else None
        column_number = location.get("columnNumber") if location else None

        return ConsoleMessage(
            message_type=msg_type,
            severity=severity,
            text=text,
            url=url,
            line_number=line_number,
            column_number=column_number,
        )

    def _process_page_error(self, error: Error) -> Optional[PageError]:
        """Process a page error."""
        if not self.config.capture_page_errors:
            return None

        message = str(error)
        if len(message) > self.config.max_message_length:
            message = message[: self.config.max_message_length] + "..."

        # Check ignore patterns
        for pattern in self.config.ignore_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return None

        stack = None
        if self.config.include_stack_traces and hasattr(error, "stack"):
            stack = error.stack

        return PageError(
            message=message,
            name=error.name if hasattr(error, "name") else "Error",
            stack=stack,
        )

    def _should_capture(self, message: ConsoleMessage) -> bool:
        """Check if a message should be captured based on config."""
        if message.message_type == ConsoleMessageType.ERROR:
            return cast(bool, self.config.capture_errors)
        elif message.message_type == ConsoleMessageType.WARNING:
            return cast(bool, self.config.capture_warnings)
        elif message.message_type == ConsoleMessageType.INFO:
            return cast(bool, self.config.capture_info)
        elif message.message_type == ConsoleMessageType.LOG:
            return cast(bool, self.config.capture_logs)
        elif message.message_type == ConsoleMessageType.DEBUG:
            return cast(bool, self.config.capture_debug)
        elif message.message_type == ConsoleMessageType.TRACE:
            return cast(bool, self.config.capture_debug)
        return True

    def _build_report(
        self,
        url: str,
        messages: List[ConsoleMessage],
        errors: List[PageError],
        resource_errors: List[ResourceError],
        capture_duration: float,
    ) -> ConsoleReport:
        """Build the console report."""
        # Count by type
        error_count = sum(
            1 for m in messages if m.message_type == ConsoleMessageType.ERROR
        )
        warning_count = sum(
            1 for m in messages if m.message_type == ConsoleMessageType.WARNING
        )
        info_count = sum(
            1 for m in messages if m.message_type == ConsoleMessageType.INFO
        )
        log_count = sum(
            1 for m in messages if m.message_type == ConsoleMessageType.LOG
        )

        # Add page errors to error count
        error_count += len(errors)

        # Get unique errors
        unique_errors = list(
            set(
                m.text
                for m in messages
                if m.message_type == ConsoleMessageType.ERROR
            )
        )
        unique_errors.extend(set(e.message for e in errors))

        # Count errors by source
        error_sources: Dict[str, int] = {}
        for msg in messages:
            if msg.message_type == ConsoleMessageType.ERROR and msg.url:
                source = msg.url.split("?")[0]
                error_sources[source] = error_sources.get(source, 0) + 1

        # Check for critical errors
        has_critical = any(
            "uncaught" in m.text.lower() or "typeerror" in m.text.lower()
            for m in messages
            if m.message_type == ConsoleMessageType.ERROR
        ) or len(errors) > 0

        # Generate suggestions
        suggestions = []
        if error_count > 0:
            suggestions.append(
                f"Fix {error_count} JavaScript error(s) to improve functionality"
            )
        if warning_count > 10:
            suggestions.append(
                f"Reduce {warning_count} console warnings for cleaner output"
            )
        if len(resource_errors) > 0:
            suggestions.append(
                f"Fix {len(resource_errors)} failed resource load(s)"
            )

        return ConsoleReport(
            url=url,
            capture_duration_ms=capture_duration,
            messages=messages,
            errors=errors,
            resource_errors=resource_errors,
            total_messages=len(messages),
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            log_count=log_count,
            unique_errors=unique_errors[:20],  # Limit to 20 unique errors
            error_sources=dict(sorted(error_sources.items(), key=lambda x: -x[1])[:10]),
            has_critical_errors=has_critical,
            suggestions=suggestions,
        )
