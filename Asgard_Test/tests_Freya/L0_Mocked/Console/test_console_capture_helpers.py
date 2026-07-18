"""L0 tests: Console capture helpers (classification, dedup, report build)."""

from unittest.mock import MagicMock

import pytest

from Asgard.Freya.Console.models.console_models import (
    ConsoleConfig,
    ConsoleMessage,
    ConsoleMessageType,
    ConsoleSeverity,
    PageError,
    ResourceError,
)
from Asgard.Freya.Console.services._console_capture_helpers import (
    SEVERITY_MAP,
    TYPE_MAP,
    build_report,
    process_console_message,
    process_page_error,
    should_capture,
)


def _mock_console_message(msg_type="error", text="Something broke", url="https://x.com/a.js",
                           line=10, col=5):
    msg = MagicMock()
    msg.type = msg_type
    msg.text = text
    msg.location = {"url": url, "lineNumber": line, "columnNumber": col}
    return msg


class TestTypeAndSeverityMaps:
    def test_all_message_types_mapped(self):
        for enum_value in ConsoleMessageType:
            assert enum_value in SEVERITY_MAP

    @pytest.mark.parametrize(
        "type_str,expected_type",
        [
            ("error", ConsoleMessageType.ERROR),
            ("warning", ConsoleMessageType.WARNING),
            ("log", ConsoleMessageType.LOG),
        ],
    )
    def test_type_map_matrix(self, type_str, expected_type):
        assert TYPE_MAP[type_str] == expected_type

    def test_unknown_type_defaults_to_log(self):
        assert TYPE_MAP.get("weird-type", ConsoleMessageType.LOG) == ConsoleMessageType.LOG


class TestProcessConsoleMessage:
    def test_basic_error_message(self):
        config = ConsoleConfig()
        msg = _mock_console_message(msg_type="error", text="TypeError: boom")
        result = process_console_message(msg, config)
        assert result is not None
        assert result.message_type == ConsoleMessageType.ERROR
        assert result.severity == ConsoleSeverity.ERROR
        assert result.url == "https://x.com/a.js"
        assert result.line_number == 10

    def test_ignore_pattern_filters_message(self):
        config = ConsoleConfig(ignore_patterns=["boom"])
        msg = _mock_console_message(text="TypeError: boom")
        assert process_console_message(msg, config) is None

    def test_message_truncated_to_max_length(self):
        config = ConsoleConfig(max_message_length=5)
        msg = _mock_console_message(text="0123456789")
        result = process_console_message(msg, config)
        assert result.text == "01234..."

    def test_missing_location_yields_none_fields(self):
        config = ConsoleConfig()
        msg = MagicMock()
        msg.type = "log"
        msg.text = "hello"
        msg.location = None
        result = process_console_message(msg, config)
        assert result.url is None
        assert result.line_number is None


class TestProcessPageError:
    def test_disabled_capture_returns_none(self):
        config = ConsoleConfig(capture_page_errors=False)
        error = MagicMock()
        error.name = "TypeError"
        assert process_page_error(error, config) is None

    def test_basic_error_captured(self):
        config = ConsoleConfig()
        error = MagicMock()
        error.name = "TypeError"
        error.stack = "at foo (bar.js:1:1)"
        error.__str__ = lambda self: "TypeError: undefined is not a function"
        result = process_page_error(error, config)
        assert result is not None
        assert result.name == "TypeError"
        assert "TypeError" in result.message

    def test_ignore_pattern_filters_error(self):
        config = ConsoleConfig(ignore_patterns=["undefined"])
        error = MagicMock()
        error.name = "TypeError"
        error.__str__ = lambda self: "TypeError: undefined is not a function"
        assert process_page_error(error, config) is None

    def test_stack_omitted_when_disabled(self):
        config = ConsoleConfig(include_stack_traces=False)
        error = MagicMock()
        error.name = "Error"
        error.stack = "some stack"
        error.__str__ = lambda self: "boom"
        result = process_page_error(error, config)
        assert result.stack is None


class TestShouldCapture:
    @pytest.mark.parametrize(
        "message_type,flag_name",
        [
            (ConsoleMessageType.ERROR, "capture_errors"),
            (ConsoleMessageType.WARNING, "capture_warnings"),
            (ConsoleMessageType.INFO, "capture_info"),
            (ConsoleMessageType.LOG, "capture_logs"),
            (ConsoleMessageType.DEBUG, "capture_debug"),
        ],
    )
    def test_respects_config_flag(self, message_type, flag_name):
        message = ConsoleMessage(message_type=message_type, severity=ConsoleSeverity.INFO, text="x")
        config_true = ConsoleConfig(**{flag_name: True})
        config_false = ConsoleConfig(**{flag_name: False})
        assert should_capture(message, config_true) is True
        assert should_capture(message, config_false) is False

    def test_unmapped_type_defaults_true(self):
        message = ConsoleMessage(message_type=ConsoleMessageType.TABLE, severity=ConsoleSeverity.DEBUG, text="x")
        assert should_capture(message, ConsoleConfig()) is True


class TestBuildReport:
    def test_counts_and_dedup(self):
        messages = [
            ConsoleMessage(message_type=ConsoleMessageType.ERROR, severity=ConsoleSeverity.ERROR, text="fail A"),
            ConsoleMessage(message_type=ConsoleMessageType.ERROR, severity=ConsoleSeverity.ERROR, text="fail A"),
            ConsoleMessage(message_type=ConsoleMessageType.WARNING, severity=ConsoleSeverity.WARNING, text="warn"),
        ]
        report = build_report("https://x.com", messages, [], [], 100.0)
        assert report.error_count == 2
        assert report.warning_count == 1
        assert report.unique_errors == ["fail A"]
        assert report.has_critical_errors is False

    def test_uncaught_typeerror_marks_critical(self):
        messages = [
            ConsoleMessage(message_type=ConsoleMessageType.ERROR, severity=ConsoleSeverity.ERROR,
                            text="Uncaught TypeError: x is not a function"),
        ]
        report = build_report("https://x.com", messages, [], [], 10.0)
        assert report.has_critical_errors is True

    def test_page_errors_counted_and_flagged_critical(self):
        errors = [PageError(message="boom", name="Error")]
        report = build_report("https://x.com", [], errors, [], 10.0)
        assert report.error_count == 1
        assert report.has_critical_errors is True

    def test_resource_errors_trigger_suggestion(self):
        resource_errors = [ResourceError(url="https://x.com/img.png", resource_type="image", status=404)]
        report = build_report("https://x.com", [], [], resource_errors, 10.0)
        assert any("failed resource" in s.lower() for s in report.suggestions)

    def test_error_sources_aggregated_by_stripped_url(self):
        messages = [
            ConsoleMessage(message_type=ConsoleMessageType.ERROR, severity=ConsoleSeverity.ERROR,
                            text="e1", url="https://x.com/a.js?v=1"),
            ConsoleMessage(message_type=ConsoleMessageType.ERROR, severity=ConsoleSeverity.ERROR,
                            text="e2", url="https://x.com/a.js?v=2"),
        ]
        report = build_report("https://x.com", messages, [], [], 10.0)
        assert report.error_sources.get("https://x.com/a.js") == 2

    def test_empty_input_produces_zeroed_report(self):
        report = build_report("https://x.com", [], [], [], 0.0)
        assert report.total_messages == 0
        assert report.error_count == 0
        assert report.has_critical_errors is False
