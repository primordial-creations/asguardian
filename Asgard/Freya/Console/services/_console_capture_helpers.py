"""
Freya Console Capture helper functions.

Helper functions extracted from console_capture.py.
"""

import re
from typing import Dict, List, Optional, cast

from playwright.async_api import ConsoleMessage as PWConsoleMessage
from playwright.async_api import Error

from Asgard.Freya.Console.models.console_models import (
    ConsoleConfig,
    ConsoleMessage,
    ConsoleMessageType,
    ConsoleReport,
    ConsoleSeverity,
    PageError,
    ResourceError,
)


TYPE_MAP: Dict[str, ConsoleMessageType] = {
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

SEVERITY_MAP: Dict[ConsoleMessageType, ConsoleSeverity] = {
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


def process_console_message(
    msg: PWConsoleMessage,
    config: ConsoleConfig,
) -> Optional[ConsoleMessage]:
    """Process a Playwright console message."""
    msg_type_str = msg.type
    msg_type = TYPE_MAP.get(msg_type_str, ConsoleMessageType.LOG)
    severity = SEVERITY_MAP.get(msg_type, ConsoleSeverity.INFO)

    text = msg.text
    if len(text) > config.max_message_length:
        text = text[: config.max_message_length] + "..."

    for pattern in config.ignore_patterns:
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


def process_page_error(error: Error, config: ConsoleConfig) -> Optional[PageError]:
    """Process a page error."""
    if not config.capture_page_errors:
        return None

    message = str(error)
    if len(message) > config.max_message_length:
        message = message[: config.max_message_length] + "..."

    for pattern in config.ignore_patterns:
        if re.search(pattern, message, re.IGNORECASE):
            return None

    stack = None
    if config.include_stack_traces and hasattr(error, "stack"):
        stack = error.stack

    return PageError(
        message=message,
        name=error.name if hasattr(error, "name") else "Error",
        stack=stack,
    )


def should_capture(message: ConsoleMessage, config: ConsoleConfig) -> bool:
    """Check if a message should be captured based on config."""
    if message.message_type == ConsoleMessageType.ERROR:
        return cast(bool, config.capture_errors)
    elif message.message_type == ConsoleMessageType.WARNING:
        return cast(bool, config.capture_warnings)
    elif message.message_type == ConsoleMessageType.INFO:
        return cast(bool, config.capture_info)
    elif message.message_type == ConsoleMessageType.LOG:
        return cast(bool, config.capture_logs)
    elif message.message_type == ConsoleMessageType.DEBUG:
        return cast(bool, config.capture_debug)
    elif message.message_type == ConsoleMessageType.TRACE:
        return cast(bool, config.capture_debug)
    return True


def build_report(
    url: str,
    messages: List[ConsoleMessage],
    errors: List[PageError],
    resource_errors: List[ResourceError],
    capture_duration: float,
) -> ConsoleReport:
    """Build the console report."""
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

    error_count += len(errors)

    unique_errors = list(
        set(
            m.text
            for m in messages
            if m.message_type == ConsoleMessageType.ERROR
        )
    )
    unique_errors.extend(set(e.message for e in errors))

    error_sources: Dict[str, int] = {}
    for msg in messages:
        if msg.message_type == ConsoleMessageType.ERROR and msg.url:
            source = msg.url.split("?")[0]
            error_sources[source] = error_sources.get(source, 0) + 1

    has_critical = any(
        "uncaught" in m.text.lower() or "typeerror" in m.text.lower()
        for m in messages
        if m.message_type == ConsoleMessageType.ERROR
    ) or len(errors) > 0

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
        unique_errors=unique_errors[:20],
        error_sources=dict(sorted(error_sources.items(), key=lambda x: -x[1])[:10]),
        has_critical_errors=has_critical,
        suggestions=suggestions,
    )
