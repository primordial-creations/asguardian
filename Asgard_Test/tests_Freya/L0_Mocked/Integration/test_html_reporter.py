"""
Freya HTML Reporter Tests

Comprehensive L0 unit tests for HTMLReporter service.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock

from Asgard.Freya.Integration.models.integration_models import (
    ReportConfig,
    ReportFormat,
    TestCategory,
    TestSeverity,
    UnifiedTestConfig,
    UnifiedTestResult,
    UnifiedTestReport,
)
from Asgard.Freya.Integration.services.html_reporter import HTMLReporter
from Asgard.Freya.Integration.services._reporter_styles import get_css, get_javascript


@pytest.fixture
def mock_report_config():
    """Create a mock ReportConfig."""
    return ReportConfig(
        format=ReportFormat.HTML,
        output_path="/tmp/report.html",
        include_screenshots=True,
        include_details=True,
        theme="default",
        title="Test Report"
    )


@pytest.fixture
def mock_test_result_passed():
    """Create a mock passing test result."""
    return UnifiedTestResult(
        category=TestCategory.ACCESSIBILITY,
        test_name="WCAG Validation",
        passed=True,
        message="All accessibility checks passed"
    )


@pytest.fixture
def mock_test_result_failed():
    """Create a mock failing test result."""
    return UnifiedTestResult(
        category=TestCategory.VISUAL,
        test_name="Layout Check",
        passed=False,
        severity=TestSeverity.SERIOUS,
        message="Layout overflow detected",
        element_selector=".main-content",
        suggested_fix="Add overflow: hidden",
        wcag_reference="1.4.10"
    )


@pytest.fixture
def mock_unified_test_report():
    """Create a mock UnifiedTestReport."""
    config = UnifiedTestConfig(url="https://example.com")

    accessibility_result = UnifiedTestResult(
        category=TestCategory.ACCESSIBILITY,
        test_name="WCAG Test",
        passed=True,
        message="Passed"
    )

    visual_result = UnifiedTestResult(
        category=TestCategory.VISUAL,
        test_name="Visual Test",
        passed=False,
        severity=TestSeverity.MODERATE,
        message="Failed",
        element_selector=".header"
    )

    return UnifiedTestReport(
        url="https://example.com",
        tested_at="2025-01-01T00:00:00",
        duration_ms=5000,
        total_tests=2,
        passed=1,
        failed=1,
        accessibility_results=[accessibility_result],
        visual_results=[visual_result],
        responsive_results=[],
        critical_count=0,
        serious_count=0,
        moderate_count=1,
        minor_count=0,
        accessibility_score=100.0,
        visual_score=80.0,
        responsive_score=100.0,
        overall_score=93.3,
        config=config
    )


class TestHTMLReporterInit:
    """Tests for HTMLReporter initialization."""

    def test_init_without_config(self):
        """Test HTMLReporter initialization without config."""
        reporter = HTMLReporter()
        assert reporter.config is None

    def test_init_with_config(self, mock_report_config):
        """Test HTMLReporter initialization with config."""
        reporter = HTMLReporter(config=mock_report_config)
        assert reporter.config == mock_report_config


class TestHTMLReporterGenerate:
    """Tests for generate method."""

    @patch('Asgard.Freya.Integration.services.html_reporter.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_creates_output_directory(
        self, mock_file, mock_path_class, mock_unified_test_report
    ):
        """Test generate creates output directory."""
        mock_path_instance = MagicMock()
        mock_parent = MagicMock()
        mock_path_instance.parent = mock_parent
        mock_path_class.return_value = mock_path_instance

        reporter = HTMLReporter()
        result = reporter.generate(
            report=mock_unified_test_report,
            output_path="/tmp/output/report.html"
        )

        mock_parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch('Asgard.Freya.Integration.services.html_reporter.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_writes_html_file(
        self, mock_file, mock_path_class, mock_unified_test_report
    ):
        """Test generate writes HTML content to file."""
        mock_path_instance = MagicMock()
        mock_path_class.return_value = mock_path_instance

        reporter = HTMLReporter()
        result = reporter.generate(
            report=mock_unified_test_report,
            output_path="/tmp/report.html"
        )

        mock_file.assert_called_once()
        handle = mock_file()
        handle.write.assert_called_once()
        written_content = handle.write.call_args[0][0]
        assert "<!DOCTYPE html>" in written_content

    def test_generate_returns_output_path(self, mock_unified_test_report, tmp_path):
        """Test generate returns output path."""
        reporter = HTMLReporter()
        out = tmp_path / "report.html"
        result = reporter.generate(
            report=mock_unified_test_report,
            output_path=str(out),
        )
        assert str(out) in result

    @patch('Asgard.Freya.Integration.services.html_reporter.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_with_custom_title(
        self, mock_file, mock_path_class, mock_unified_test_report
    ):
        """Test generate with custom title."""
        mock_path_instance = MagicMock()
        mock_path_class.return_value = mock_path_instance

        reporter = HTMLReporter()
        result = reporter.generate(
            report=mock_unified_test_report,
            output_path="/tmp/report.html",
            title="Custom Title"
        )

        handle = mock_file()
        written_content = handle.write.call_args[0][0]
        assert "Custom Title" in written_content

    @patch('Asgard.Freya.Integration.services.html_reporter.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_includes_url(
        self, mock_file, mock_path_class, mock_unified_test_report
    ):
        """Test generate includes tested URL."""
        mock_path_instance = MagicMock()
        mock_path_class.return_value = mock_path_instance

        reporter = HTMLReporter()
        result = reporter.generate(
            report=mock_unified_test_report,
            output_path="/tmp/report.html"
        )

        handle = mock_file()
        written_content = handle.write.call_args[0][0]
        assert "https://example.com" in written_content

    @patch('Asgard.Freya.Integration.services.html_reporter.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_includes_scores(
        self, mock_file, mock_path_class, mock_unified_test_report
    ):
        """Test generate includes score information."""
        mock_path_instance = MagicMock()
        mock_path_class.return_value = mock_path_instance

        reporter = HTMLReporter()
        result = reporter.generate(
            report=mock_unified_test_report,
            output_path="/tmp/report.html"
        )

        handle = mock_file()
        written_content = handle.write.call_args[0][0]
        assert "93" in written_content  # Overall score
        assert "100" in written_content  # Accessibility score


class TestHTMLReporterGenerateJSON:
    """Tests for generate_json method."""

    @patch('Asgard.Freya.Integration.services.html_reporter.Path')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_generate_json_creates_directory(
        self, mock_json_dump, mock_file, mock_path_class, mock_unified_test_report
    ):
        """Test generate_json creates output directory."""
        mock_path_instance = MagicMock()
        mock_parent = MagicMock()
        mock_path_instance.parent = mock_parent
        mock_path_class.return_value = mock_path_instance

        reporter = HTMLReporter()
        result = reporter.generate_json(
            report=mock_unified_test_report,
            output_path="/tmp/report.json"
        )

        mock_parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch('Asgard.Freya.Integration.services.html_reporter.Path')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_generate_json_writes_file(
        self, mock_json_dump, mock_file, mock_path_class, mock_unified_test_report
    ):
        """Test generate_json writes JSON file."""
        mock_path_instance = MagicMock()
        mock_path_class.return_value = mock_path_instance

        reporter = HTMLReporter()
        result = reporter.generate_json(
            report=mock_unified_test_report,
            output_path="/tmp/report.json"
        )

        mock_json_dump.assert_called_once()
        call_args = mock_json_dump.call_args
        dumped_data = call_args[0][0]
        assert "url" in dumped_data

    def test_generate_json_returns_path(self, mock_unified_test_report, tmp_path):
        """Test generate_json returns output path."""
        reporter = HTMLReporter()
        out = tmp_path / "report.json"
        result = reporter.generate_json(
            report=mock_unified_test_report,
            output_path=str(out),
        )
        assert str(out) in result


class TestHTMLReporterGenerateJUnit:
    """Tests for generate_junit method."""

    @patch('Asgard.Freya.Integration.services.html_reporter.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_junit_creates_directory(
        self, mock_file, mock_path_class, mock_unified_test_report
    ):
        """Test generate_junit creates output directory."""
        mock_path_instance = MagicMock()
        mock_parent = MagicMock()
        mock_path_instance.parent = mock_parent
        mock_path_class.return_value = mock_path_instance

        reporter = HTMLReporter()
        result = reporter.generate_junit(
            report=mock_unified_test_report,
            output_path="/tmp/report.xml"
        )

        mock_parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch('Asgard.Freya.Integration.services.html_reporter.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_junit_writes_xml(
        self, mock_file, mock_path_class, mock_unified_test_report
    ):
        """Test generate_junit writes JUnit XML."""
        mock_path_instance = MagicMock()
        mock_path_class.return_value = mock_path_instance

        reporter = HTMLReporter()
        result = reporter.generate_junit(
            report=mock_unified_test_report,
            output_path="/tmp/report.xml"
        )

        handle = mock_file()
        handle.write.assert_called_once()
        written_content = handle.write.call_args[0][0]
        assert "<?xml version=" in written_content
        assert "<testsuite" in written_content

    @patch('Asgard.Freya.Integration.services.html_reporter.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_junit_includes_testcases(
        self, mock_file, mock_path_class, mock_unified_test_report
    ):
        """Test generate_junit includes testcase elements."""
        mock_path_instance = MagicMock()
        mock_path_class.return_value = mock_path_instance

        reporter = HTMLReporter()
        result = reporter.generate_junit(
            report=mock_unified_test_report,
            output_path="/tmp/report.xml"
        )

        handle = mock_file()
        written_content = handle.write.call_args[0][0]
        assert "<testcase" in written_content
        assert 'name="WCAG Test"' in written_content

    @patch('Asgard.Freya.Integration.services.html_reporter.Path')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_junit_includes_failures(
        self, mock_file, mock_path_class, mock_unified_test_report
    ):
        """Test generate_junit includes failure elements."""
        mock_path_instance = MagicMock()
        mock_path_class.return_value = mock_path_instance

        reporter = HTMLReporter()
        result = reporter.generate_junit(
            report=mock_unified_test_report,
            output_path="/tmp/report.xml"
        )

        handle = mock_file()
        written_content = handle.write.call_args[0][0]
        assert "<failure" in written_content


class TestHTMLReporterBuildHTML:
    """Tests for _build_html method."""

    def test_build_html_structure(self, mock_unified_test_report):
        """Test _build_html creates valid HTML structure."""
        reporter = HTMLReporter()
        html = reporter._build_html(mock_unified_test_report, "Test Report")

        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "<head>" in html
        assert "<body>" in html
        assert "</html>" in html

    def test_build_html_includes_title(self, mock_unified_test_report):
        """Test _build_html includes title."""
        reporter = HTMLReporter()
        html = reporter._build_html(mock_unified_test_report, "My Custom Title")

        assert "My Custom Title" in html

    def test_build_html_includes_meta(self, mock_unified_test_report):
        """Test _build_html includes metadata."""
        reporter = HTMLReporter()
        html = reporter._build_html(mock_unified_test_report, "Test Report")

        assert mock_unified_test_report.url in html
        assert str(mock_unified_test_report.duration_ms) in html

    def test_build_html_includes_scores(self, mock_unified_test_report):
        """Test _build_html includes score cards."""
        reporter = HTMLReporter()
        html = reporter._build_html(mock_unified_test_report, "Test Report")

        assert "Overall Score" in html
        assert "Accessibility" in html
        assert "Visual" in html

    def test_build_html_includes_stats(self, mock_unified_test_report):
        """Test _build_html includes test statistics."""
        reporter = HTMLReporter()
        html = reporter._build_html(mock_unified_test_report, "Test Report")

        assert "Total Tests" in html
        assert "Passed" in html
        assert "Failed" in html

    def test_build_html_includes_severity_counts(self, mock_unified_test_report):
        """Test _build_html includes severity counts."""
        reporter = HTMLReporter()
        html = reporter._build_html(mock_unified_test_report, "Test Report")

        assert "Critical" in html
        assert "Serious" in html
        assert "Moderate" in html
        assert "Minor" in html

    def test_build_html_includes_css(self, mock_unified_test_report):
        """Test _build_html includes CSS styles."""
        reporter = HTMLReporter()
        html = reporter._build_html(mock_unified_test_report, "Test Report")

        assert "<style>" in html
        assert "color-primary" in html or ".score-card" in html

    def test_build_html_includes_javascript(self, mock_unified_test_report):
        """Test _build_html includes JavaScript."""
        reporter = HTMLReporter()
        html = reporter._build_html(mock_unified_test_report, "Test Report")

        assert "<script>" in html
        assert "DOMContentLoaded" in html


class TestHTMLReporterBuildResultsSection:
    """Tests for _build_results_section method."""

    def test_build_results_section_empty(self):
        """Test _build_results_section with no results."""
        reporter = HTMLReporter()
        html = reporter._build_results_section("Accessibility", [], 100.0)

        assert html == ""

    def test_build_results_section_with_results(self, mock_test_result_failed):
        """Test _build_results_section with results."""
        reporter = HTMLReporter()
        html = reporter._build_results_section(
            "Visual",
            [mock_test_result_failed],
            80.0
        )

        assert "<section" in html
        assert "Visual" in html
        assert "80" in html
        assert "<table" in html

    def test_build_results_section_includes_failures(self, mock_test_result_failed):
        """Test _build_results_section includes failure information."""
        reporter = HTMLReporter()
        html = reporter._build_results_section(
            "Visual",
            [mock_test_result_failed],
            80.0
        )

        assert mock_test_result_failed.message in html
        assert mock_test_result_failed.element_selector in html
        assert mock_test_result_failed.suggested_fix in html

    def test_build_results_section_includes_passed(self, mock_test_result_passed):
        """Test _build_results_section includes passed tests."""
        reporter = HTMLReporter()
        html = reporter._build_results_section(
            "Accessibility",
            [mock_test_result_passed],
            100.0
        )

        assert mock_test_result_passed.test_name in html
        assert "pass" in html.lower()

    def test_build_results_section_severity_badges(self, mock_test_result_failed):
        """Test _build_results_section includes severity badges."""
        reporter = HTMLReporter()
        html = reporter._build_results_section(
            "Visual",
            [mock_test_result_failed],
            80.0
        )

        assert "severity-badge" in html
        assert "serious" in html


class TestHTMLReporterBuildScreenshotsSection:
    """Tests for _build_screenshots_section method."""

    def test_build_screenshots_section_empty(self):
        """Test _build_screenshots_section with no screenshots."""
        reporter = HTMLReporter()
        html = reporter._build_screenshots_section({})

        assert html == ""

    def test_build_screenshots_section_with_screenshots(self):
        """Test _build_screenshots_section with screenshots."""
        screenshots = {
            "desktop": "/path/to/desktop.png",
            "mobile": "/path/to/mobile.png"
        }

        reporter = HTMLReporter()
        html = reporter._build_screenshots_section(screenshots)

        assert "<section" in html
        assert "Screenshots" in html
        assert "desktop" in html
        assert "mobile" in html
        assert "<img" in html

    def test_build_screenshots_section_image_tags(self):
        """Test _build_screenshots_section creates proper image tags."""
        screenshots = {"test": "/path/to/test.png"}

        reporter = HTMLReporter()
        html = reporter._build_screenshots_section(screenshots)

        assert 'src="/path/to/test.png"' in html
        assert 'alt="test"' in html


class TestHTMLReporterGetCSS:
    """Tests for _get_css method."""

    def test_get_css_returns_string(self):
        """Test _get_css returns CSS string."""
        reporter = HTMLReporter()
        css = get_css()

        assert isinstance(css, str)
        assert len(css) > 0

    def test_get_css_includes_variables(self):
        """Test _get_css includes CSS variables."""
        reporter = HTMLReporter()
        css = get_css()

        assert ":root" in css or "--color" in css

    def test_get_css_includes_responsive(self):
        """Test _get_css includes responsive design."""
        reporter = HTMLReporter()
        css = get_css()

        assert "@media" in css

    def test_get_css_includes_styles(self):
        """Test _get_css includes main styles."""
        reporter = HTMLReporter()
        css = get_css()

        assert "body" in css or ".score-card" in css


class TestHTMLReporterGetJavaScript:
    """Tests for _get_javascript method."""

    def test_get_javascript_returns_string(self):
        """Test _get_javascript returns JavaScript string."""
        reporter = HTMLReporter()
        js = get_javascript()

        assert isinstance(js, str)
        assert len(js) > 0

    def test_get_javascript_includes_event_listener(self):
        """Test _get_javascript includes event listeners."""
        reporter = HTMLReporter()
        js = get_javascript()

        assert "addEventListener" in js
        assert "DOMContentLoaded" in js


class TestHTMLReporterBuildJUnitXML:
    """Tests for _build_junit_xml method."""

    def test_build_junit_xml_structure(self, mock_unified_test_report):
        """Test _build_junit_xml creates valid XML structure."""
        reporter = HTMLReporter()
        xml = reporter._build_junit_xml(mock_unified_test_report)

        assert '<?xml version="1.0"' in xml
        assert "<testsuite" in xml
        assert "</testsuite>" in xml

    def test_build_junit_xml_includes_testcases(self, mock_unified_test_report):
        """Test _build_junit_xml includes testcase elements."""
        reporter = HTMLReporter()
        xml = reporter._build_junit_xml(mock_unified_test_report)

        assert "<testcase" in xml
        assert 'name="WCAG Test"' in xml

    def test_build_junit_xml_includes_failures(self, mock_unified_test_report):
        """Test _build_junit_xml includes failure elements for failed tests."""
        reporter = HTMLReporter()
        xml = reporter._build_junit_xml(mock_unified_test_report)

        assert "<failure" in xml
        assert 'type="moderate"' in xml

    def test_build_junit_xml_test_counts(self, mock_unified_test_report):
        """Test _build_junit_xml includes correct test counts."""
        reporter = HTMLReporter()
        xml = reporter._build_junit_xml(mock_unified_test_report)

        assert f'tests="{mock_unified_test_report.total_tests}"' in xml
        assert f'failures="{mock_unified_test_report.failed}"' in xml

    def test_build_junit_xml_escapes_special_chars(self):
        """Test _build_junit_xml escapes XML special characters."""
        config = UnifiedTestConfig(url="https://example.com")
        result = UnifiedTestResult(
            category=TestCategory.ACCESSIBILITY,
            test_name="Test",
            passed=False,
            severity=TestSeverity.MODERATE,
            message='Contains "quotes" and <tags>'
        )

        report = UnifiedTestReport(
            url="https://example.com",
            tested_at="2025-01-01T00:00:00",
            duration_ms=1000,
            total_tests=1,
            passed=0,
            failed=1,
            accessibility_results=[result],
            config=config
        )

        reporter = HTMLReporter()
        xml = reporter._build_junit_xml(report)

        assert "&quot;" in xml or "&lt;" in xml or "&gt;" in xml
