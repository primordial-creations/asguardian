"""
L1 Integration Tests for Freya Unified Testing

Comprehensive integration tests for unified site testing that combines accessibility,
visual, and responsive testing into a single comprehensive test suite with HTML
report generation and baseline management.

All tests use file:// URLs for local HTML fixtures, making them CI-friendly.
"""

import pytest
from pathlib import Path
import shutil

from Asgard.Freya.Integration.services.unified_tester import UnifiedTester
from Asgard.Freya.Integration.services.html_reporter import HTMLReporter
from Asgard.Freya.Integration.services.baseline_manager import BaselineManager
from Asgard.Freya.Integration.services.site_crawler import SiteCrawler
from Asgard.Freya.Integration.models.integration_models import (
    UnifiedTestConfig,
    TestCategory,
    TestSeverity,
)
from Asgard.Freya.Visual.services.screenshot_capture import ScreenshotCapture
from Asgard.Freya.Visual.models.visual_models import ScreenshotConfig

from Asgard_Test.tests_Freya.L1_Integration.conftest import file_url


class TestUnifiedIntegrationUnifiedTester:
    """Integration tests for Unified Tester with real HTML pages."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_unified_tester_all_categories(self, sample_accessible_page, output_dir):
        """Test unified tester runs all test categories."""
        config = UnifiedTestConfig(
            url="",
            output_directory=str(output_dir / "unified"),
            categories=[TestCategory.ALL],
            min_severity=TestSeverity.MINOR,
            capture_screenshots=False,
        )
        tester = UnifiedTester(config)

        url = file_url(sample_accessible_page)
        report = await tester.test(url)

        assert report is not None
        assert report.url == url
        assert report.total_tests > 0
        assert report.duration_ms > 0

        assert len(report.accessibility_results) > 0
        assert len(report.visual_results) > 0
        assert len(report.responsive_results) > 0

        assert 0.0 <= report.overall_score <= 100.0
        assert 0.0 <= report.accessibility_score <= 100.0
        assert 0.0 <= report.visual_score <= 100.0
        assert 0.0 <= report.responsive_score <= 100.0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_unified_tester_accessibility_only(self, sample_accessible_page, output_dir):
        """Test unified tester with accessibility category only."""
        config = UnifiedTestConfig(
            url="",
            output_directory=str(output_dir / "unified"),
            categories=[TestCategory.ACCESSIBILITY],
            capture_screenshots=False,
        )
        tester = UnifiedTester(config)

        url = file_url(sample_accessible_page)
        report = await tester.test(url)

        assert report is not None
        assert len(report.accessibility_results) > 0
        assert len(report.visual_results) == 0
        assert len(report.responsive_results) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_unified_tester_visual_only(self, sample_visual_page, output_dir):
        """Test unified tester with visual category only."""
        config = UnifiedTestConfig(
            url="",
            output_directory=str(output_dir / "unified"),
            categories=[TestCategory.VISUAL],
            capture_screenshots=False,
        )
        tester = UnifiedTester(config)

        url = file_url(sample_visual_page)
        report = await tester.test(url)

        assert report is not None
        assert len(report.accessibility_results) == 0
        assert len(report.visual_results) > 0
        assert len(report.responsive_results) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_unified_tester_responsive_only(self, sample_responsive_page, output_dir):
        """Test unified tester with responsive category only."""
        config = UnifiedTestConfig(
            url="",
            output_directory=str(output_dir / "unified"),
            categories=[TestCategory.RESPONSIVE],
            capture_screenshots=False,
        )
        tester = UnifiedTester(config)

        url = file_url(sample_responsive_page)
        report = await tester.test(url)

        assert report is not None
        assert len(report.accessibility_results) == 0
        assert len(report.visual_results) == 0
        assert len(report.responsive_results) > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_unified_tester_severity_filtering(self, sample_inaccessible_page, output_dir):
        """Test unified tester filters results by severity."""
        config_critical = UnifiedTestConfig(
            url="",
            output_directory=str(output_dir / "unified"),
            categories=[TestCategory.ACCESSIBILITY],
            min_severity=TestSeverity.CRITICAL,
            capture_screenshots=False,
        )
        tester_critical = UnifiedTester(config_critical)

        url = file_url(sample_inaccessible_page)
        report_critical = await tester_critical.test(url, min_severity=TestSeverity.CRITICAL)

        config_all = UnifiedTestConfig(
            url="",
            output_directory=str(output_dir / "unified"),
            categories=[TestCategory.ACCESSIBILITY],
            min_severity=TestSeverity.MINOR,
            capture_screenshots=False,
        )
        tester_all = UnifiedTester(config_all)
        report_all = await tester_all.test(url, min_severity=TestSeverity.MINOR)

        assert report_critical.total_tests <= report_all.total_tests

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_unified_tester_with_screenshots(self, sample_visual_page, output_dir):
        """Test unified tester captures screenshots when enabled."""
        config = UnifiedTestConfig(
            url="",
            output_directory=str(output_dir / "unified_screenshots"),
            categories=[TestCategory.RESPONSIVE],
            capture_screenshots=True,
        )
        tester = UnifiedTester(config)

        url = file_url(sample_visual_page)
        report = await tester.test(url)

        assert report is not None
        if len(report.screenshots) > 0:
            for screenshot_path in report.screenshots.values():
                assert Path(screenshot_path).exists()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_unified_tester_report_structure(self, sample_accessible_page, output_dir):
        """Test unified tester report has correct structure."""
        config = UnifiedTestConfig(
            url="",
            output_directory=str(output_dir / "unified"),
            capture_screenshots=False,
        )
        tester = UnifiedTester(config)

        url = file_url(sample_accessible_page)
        report = await tester.test(url)

        assert report.url is not None
        assert report.tested_at is not None
        assert report.duration_ms >= 0
        assert report.total_tests >= 0
        assert report.passed >= 0
        assert report.failed >= 0
        assert report.passed + report.failed <= report.total_tests

        assert report.critical_count >= 0
        assert report.serious_count >= 0
        assert report.moderate_count >= 0
        assert report.minor_count >= 0

        assert isinstance(report.accessibility_results, list)
        assert isinstance(report.visual_results, list)
        assert isinstance(report.responsive_results, list)
        assert isinstance(report.screenshots, dict)
        assert hasattr(report, 'config')


class TestUnifiedIntegrationHTMLReporter:
    """Integration tests for HTML Reporter with real test results."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_html_reporter_generates_report(self, sample_accessible_page, output_dir):
        """Test HTML reporter generates valid HTML report."""
        config = UnifiedTestConfig(
            url="",
            output_directory=str(output_dir / "unified"),
            capture_screenshots=False,
        )
        tester = UnifiedTester(config)

        url = file_url(sample_accessible_page)
        test_report = await tester.test(url)

        reporter = HTMLReporter(output_directory=str(output_dir / "reports"))
        html_path = reporter.generate(test_report)

        assert html_path is not None
        assert Path(html_path).exists()
        assert Path(html_path).suffix == ".html"

        html_content = Path(html_path).read_text()
        assert "<!DOCTYPE html>" in html_content or "<html" in html_content
        assert test_report.url in html_content

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_html_reporter_includes_test_results(self, sample_inaccessible_page, output_dir):
        """Test HTML reporter includes test results in report."""
        config = UnifiedTestConfig(
            url="",
            output_directory=str(output_dir / "unified"),
            categories=[TestCategory.ACCESSIBILITY],
            capture_screenshots=False,
        )
        tester = UnifiedTester(config)

        url = file_url(sample_inaccessible_page)
        test_report = await tester.test(url)

        reporter = HTMLReporter(output_directory=str(output_dir / "reports"))
        html_path = reporter.generate(test_report)

        html_content = Path(html_path).read_text()
        assert str(test_report.total_tests) in html_content
        assert str(test_report.overall_score) in html_content or "score" in html_content.lower()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_html_reporter_custom_template(self, sample_accessible_page, output_dir):
        """Test HTML reporter with custom template."""
        config = UnifiedTestConfig(
            url="",
            output_directory=str(output_dir / "unified"),
            capture_screenshots=False,
        )
        tester = UnifiedTester(config)

        url = file_url(sample_accessible_page)
        test_report = await tester.test(url)

        reporter = HTMLReporter(output_directory=str(output_dir / "reports"))
        html_path = reporter.generate(test_report, title="Custom Test Report")

        assert Path(html_path).exists()

        html_content = Path(html_path).read_text()
        assert "Custom Test Report" in html_content or "Test Report" in html_content


class TestUnifiedIntegrationBaselineManager:
    """Integration tests for Baseline Manager with real screenshots."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_baseline_manager_save_baseline(self, sample_visual_page, baseline_fixtures_dir):
        """Test baseline manager saves baselines."""
        config = ScreenshotConfig(
            full_page=True,
            output_directory=str(baseline_fixtures_dir / "temp"),
        )
        capture = ScreenshotCapture(config)

        url = file_url(sample_visual_page)
        screenshot_result = await capture.capture(url, "baseline_test")

        manager = BaselineManager(baseline_directory=str(baseline_fixtures_dir / "managed"))
        saved_path = manager.save_baseline("baseline_test", screenshot_result.screenshot_path)

        assert saved_path is not None
        assert Path(saved_path).exists()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_baseline_manager_load_baseline(self, sample_visual_page, baseline_fixtures_dir):
        """Test baseline manager loads baselines."""
        config = ScreenshotConfig(
            full_page=True,
            output_directory=str(baseline_fixtures_dir / "temp"),
        )
        capture = ScreenshotCapture(config)

        url = file_url(sample_visual_page)
        screenshot_result = await capture.capture(url, "load_test")

        manager = BaselineManager(baseline_directory=str(baseline_fixtures_dir / "managed"))
        saved_path = manager.save_baseline("load_test", screenshot_result.screenshot_path)

        loaded_path = manager.load_baseline("load_test")

        assert loaded_path is not None
        assert Path(loaded_path).exists()
        assert loaded_path == saved_path

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_baseline_manager_update_baseline(self, sample_visual_page, baseline_fixtures_dir):
        """Test baseline manager updates existing baselines."""
        config = ScreenshotConfig(
            full_page=True,
            output_directory=str(baseline_fixtures_dir / "temp"),
        )
        capture = ScreenshotCapture(config)

        url = file_url(sample_visual_page)
        screenshot_result1 = await capture.capture(url, "update_test_1")
        screenshot_result2 = await capture.capture(url, "update_test_2")

        manager = BaselineManager(baseline_directory=str(baseline_fixtures_dir / "managed"))

        saved_path1 = manager.save_baseline("update_test", screenshot_result1.screenshot_path)
        saved_path2 = manager.save_baseline("update_test", screenshot_result2.screenshot_path)

        assert saved_path1 is not None
        assert saved_path2 is not None
        assert Path(saved_path2).exists()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_baseline_manager_list_baselines(self, sample_visual_page, baseline_fixtures_dir):
        """Test baseline manager lists all baselines."""
        config = ScreenshotConfig(
            full_page=True,
            output_directory=str(baseline_fixtures_dir / "temp"),
        )
        capture = ScreenshotCapture(config)

        url = file_url(sample_visual_page)

        manager = BaselineManager(baseline_directory=str(baseline_fixtures_dir / "managed"))

        for i in range(3):
            screenshot_result = await capture.capture(url, f"list_test_{i}")
            manager.save_baseline(f"baseline_{i}", screenshot_result.screenshot_path)

        baselines = manager.list_baselines()

        assert baselines is not None
        assert len(baselines) >= 3

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_baseline_manager_delete_baseline(self, sample_visual_page, baseline_fixtures_dir):
        """Test baseline manager deletes baselines."""
        config = ScreenshotConfig(
            full_page=True,
            output_directory=str(baseline_fixtures_dir / "temp"),
        )
        capture = ScreenshotCapture(config)

        url = file_url(sample_visual_page)
        screenshot_result = await capture.capture(url, "delete_test")

        manager = BaselineManager(baseline_directory=str(baseline_fixtures_dir / "managed"))
        saved_path = manager.save_baseline("delete_test", screenshot_result.screenshot_path)

        assert Path(saved_path).exists()

        success = manager.delete_baseline("delete_test")

        assert success is True
        loaded = manager.load_baseline("delete_test")
        assert loaded is None


class TestUnifiedIntegrationSiteCrawler:
    """Integration tests for Site Crawler with real HTML pages."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_site_crawler_single_page(self, sample_accessible_page):
        """Test site crawler on single page."""
        crawler = SiteCrawler(max_depth=0, max_pages=1)

        url = file_url(sample_accessible_page)
        pages = await crawler.crawl(url)

        assert pages is not None
        assert len(pages) >= 1
        assert url in pages

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_site_crawler_with_links(self, html_fixtures_dir):
        """Test site crawler follows links."""
        page1_html = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Page 1</title></head>
<body>
    <h1>Page 1</h1>
    <a href="page2.html">Go to Page 2</a>
</body>
</html>"""

        page2_html = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Page 2</title></head>
<body>
    <h1>Page 2</h1>
    <a href="page1.html">Back to Page 1</a>
</body>
</html>"""

        page1 = html_fixtures_dir / "page1.html"
        page2 = html_fixtures_dir / "page2.html"
        page1.write_text(page1_html, encoding="utf-8")
        page2.write_text(page2_html, encoding="utf-8")

        crawler = SiteCrawler(max_depth=1, max_pages=5)

        url = file_url(page1)
        pages = await crawler.crawl(url)

        assert pages is not None
        assert len(pages) >= 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_site_crawler_respects_max_pages(self, sample_accessible_page):
        """Test site crawler respects max pages limit."""
        crawler = SiteCrawler(max_depth=2, max_pages=1)

        url = file_url(sample_accessible_page)
        pages = await crawler.crawl(url)

        assert pages is not None
        assert len(pages) <= 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_site_crawler_respects_max_depth(self, html_fixtures_dir):
        """Test site crawler respects max depth limit."""
        page_html = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Depth Test</title></head>
<body>
    <h1>Depth Test</h1>
</body>
</html>"""

        page = html_fixtures_dir / "depth_test.html"
        page.write_text(page_html, encoding="utf-8")

        crawler = SiteCrawler(max_depth=0, max_pages=10)

        url = file_url(page)
        pages = await crawler.crawl(url)

        assert pages is not None
        assert len(pages) == 1


class TestUnifiedIntegrationEndToEnd:
    """End-to-end integration tests for complete workflows."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_site_testing_workflow(self, sample_accessible_page, output_dir):
        """Test complete workflow: test, report, and baseline management."""
        config = UnifiedTestConfig(
            url="",
            output_directory=str(output_dir / "e2e"),
            categories=[TestCategory.ALL],
            capture_screenshots=False,
        )
        tester = UnifiedTester(config)

        url = file_url(sample_accessible_page)
        test_report = await tester.test(url)

        assert test_report is not None
        assert test_report.total_tests > 0

        reporter = HTMLReporter(output_directory=str(output_dir / "e2e_reports"))
        html_path = reporter.generate(test_report)

        assert Path(html_path).exists()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_regression_testing_workflow(self, sample_visual_page, baseline_fixtures_dir, output_dir):
        """Test complete visual regression workflow."""
        config = ScreenshotConfig(
            full_page=True,
            output_directory=str(baseline_fixtures_dir / "regression"),
        )
        capture = ScreenshotCapture(config)

        url = file_url(sample_visual_page)
        baseline_result = await capture.capture(url, "regression_baseline")

        manager = BaselineManager(baseline_directory=str(baseline_fixtures_dir / "regression_managed"))
        baseline_path = manager.save_baseline("regression_test", baseline_result.screenshot_path)

        assert Path(baseline_path).exists()

        current_result = await capture.capture(url, "regression_current")

        from Asgard.Freya.Visual.services.visual_regression import VisualRegressionTester
        from Asgard.Freya.Visual.models.visual_models import ComparisonConfig

        tester = VisualRegressionTester(output_directory=str(output_dir / "regression"))
        comparison_config = ComparisonConfig(threshold=0.95)
        comparison_result = tester.compare(
            baseline_path,
            current_result.screenshot_path,
            comparison_config
        )

        assert comparison_result.similarity_score >= 0.90
