"""
Freya L8 Performance Benchmarks — Helper Functions

Benchmarks for all Freya sub-packages using pure-Python helper modules
that require no browser or network I/O. Browser-dependent service
classes (screenshot_capture, site_crawler, breakpoint_tester, etc.)
are covered by benchmarking their extracted helper functions instead.

Sub-packages covered
--------------------
- Accessibility  : _color_contrast_math, _wcag_checks.generate_id
- Console        : _console_capture_helpers.should_capture / build_report
- Images         : _image_scanner_checks.detect_format / build_image_info
- Integration    : _crawler_discovery.normalize_url / should_crawl
- Links          : _link_validator_helpers.get_link_type / filter_links
- Performance    : _page_load_helpers.build_metrics / identify_issues / calculate_score
                   _resource_timing_helpers.parse_resource
- Responsive     : (no pure-Python helpers — benchmarks Responsive models construction)
- SEO            : _meta_tag_analyzers.analyze_title / analyze_description
                   _robots_analyzer_helpers / _structured_data_checks
- Security       : _security_header_analyzers.analyze_csp / analyze_hsts (already: CSPAnalyzer)
- Visual         : image_ops.Image / _visual_regression_compare.pixel_comparison
                   _image_ops_analysis helpers
"""

import re
import pytest


# ---------------------------------------------------------------------------
# Accessibility — _color_contrast_math (pure Python, no Playwright)
# ---------------------------------------------------------------------------

class TestAccessibilityColorContrastMathBenchmark:
    """Benchmarks for Accessibility._color_contrast_math pure helpers."""

    def test_parse_hex_color(self, benchmark):
        """Benchmark parsing a hex color string to RGB."""
        from Asgard.Freya.Accessibility.services._color_contrast_math import parse_color

        result = benchmark(parse_color, "#1a2b3c")
        assert result == (0x1a, 0x2b, 0x3c)

    def test_parse_rgb_color(self, benchmark):
        """Benchmark parsing an rgb() color string."""
        from Asgard.Freya.Accessibility.services._color_contrast_math import parse_color

        result = benchmark(parse_color, "rgb(200, 150, 50)")
        assert result == (200, 150, 50)

    def test_parse_named_color(self, benchmark):
        """Benchmark parsing a named color."""
        from Asgard.Freya.Accessibility.services._color_contrast_math import parse_color

        result = benchmark(parse_color, "white")
        assert result == (255, 255, 255)

    def test_calculate_contrast_ratio(self, benchmark):
        """Benchmark WCAG contrast ratio calculation."""
        from Asgard.Freya.Accessibility.services._color_contrast_math import (
            calculate_contrast_ratio,
        )

        ratio = benchmark(calculate_contrast_ratio, (0, 0, 0), (255, 255, 255))
        assert ratio > 20  # black-on-white should be ~21:1

    def test_calculate_relative_luminance(self, benchmark):
        """Benchmark relative luminance calculation."""
        from Asgard.Freya.Accessibility.services._color_contrast_math import (
            calculate_relative_luminance,
        )

        lum = benchmark(calculate_relative_luminance, (128, 64, 32))
        assert 0.0 <= lum <= 1.0

    def test_parse_font_size(self, benchmark):
        """Benchmark font size string parsing."""
        from Asgard.Freya.Accessibility.services._color_contrast_math import parse_font_size

        px = benchmark(parse_font_size, "1.5rem")
        assert px == 24.0

    def test_rgb_to_hex(self, benchmark):
        """Benchmark RGB-to-hex conversion."""
        from Asgard.Freya.Accessibility.services._color_contrast_math import rgb_to_hex

        result = benchmark(rgb_to_hex, (255, 128, 0))
        assert result == "#ff8000"


# ---------------------------------------------------------------------------
# Accessibility — _wcag_checks.generate_id (pure Python)
# ---------------------------------------------------------------------------

class TestAccessibilityWcagChecksBenchmark:
    """Benchmarks for pure-Python helpers in _wcag_checks."""

    def test_generate_violation_id(self, benchmark):
        """Benchmark generating a violation ID via MD5 hash."""
        from Asgard.Freya.Accessibility.services._wcag_checks import generate_id

        result = benchmark(generate_id, "img-alt", "https://example.com/hero.jpg")
        assert len(result) == 12


# ---------------------------------------------------------------------------
# Console — _console_capture_helpers (pure Python, no Playwright objects)
# ---------------------------------------------------------------------------

class TestConsoleCaptureBenchmark:
    """Benchmarks for Console._console_capture_helpers pure helpers."""

    def test_should_capture_error(self, benchmark):
        """Benchmark should_capture for an error message."""
        from Asgard.Freya.Console.services._console_capture_helpers import should_capture
        from Asgard.Freya.Console.models.console_models import (
            ConsoleConfig,
            ConsoleMessage,
            ConsoleMessageType,
            ConsoleSeverity,
        )

        config = ConsoleConfig()
        msg = ConsoleMessage(
            message_type=ConsoleMessageType.ERROR,
            severity=ConsoleSeverity.ERROR,
            text="Uncaught TypeError: Cannot read property 'x' of undefined",
        )

        result = benchmark(should_capture, msg, config)
        assert result is True

    def test_build_report(self, benchmark):
        """Benchmark building a ConsoleReport from message lists."""
        from Asgard.Freya.Console.services._console_capture_helpers import build_report
        from Asgard.Freya.Console.models.console_models import (
            ConsoleMessage,
            ConsoleMessageType,
            ConsoleSeverity,
            PageError,
            ResourceError,
        )

        messages = [
            ConsoleMessage(
                message_type=ConsoleMessageType.ERROR,
                severity=ConsoleSeverity.ERROR,
                text="TypeError: x is not defined",
                url="https://example.com/app.js",
            ),
            ConsoleMessage(
                message_type=ConsoleMessageType.WARNING,
                severity=ConsoleSeverity.WARNING,
                text="Deprecated API usage",
            ),
            ConsoleMessage(
                message_type=ConsoleMessageType.LOG,
                severity=ConsoleSeverity.INFO,
                text="App loaded",
            ),
        ]
        errors = [PageError(message="Script error", name="Error")]
        resource_errors: list = []

        report = benchmark(
            build_report,
            "https://example.com",
            messages,
            errors,
            resource_errors,
            0.123,
        )
        assert report is not None
        assert report.error_count >= 1


# ---------------------------------------------------------------------------
# Images — _image_scanner_checks (pure Python, no httpx/Playwright)
# ---------------------------------------------------------------------------

class TestImageScannerChecksBenchmark:
    """Benchmarks for Images._image_scanner_checks pure helpers."""

    def test_detect_format_webp(self, benchmark):
        """Benchmark format detection for a WebP URL."""
        from Asgard.Freya.Images.services._image_scanner_checks import detect_format
        from Asgard.Freya.Images.models.image_models import ImageFormat

        result = benchmark(detect_format, "https://cdn.example.com/hero.webp")
        assert result == ImageFormat.WEBP

    def test_detect_format_jpeg(self, benchmark):
        """Benchmark format detection for a JPEG URL."""
        from Asgard.Freya.Images.services._image_scanner_checks import detect_format
        from Asgard.Freya.Images.models.image_models import ImageFormat

        result = benchmark(detect_format, "https://cdn.example.com/photo.jpg")
        assert result == ImageFormat.JPG

    def test_build_image_info(self, benchmark):
        """Benchmark building an ImageInfo from extracted DOM data."""
        from Asgard.Freya.Images.services._image_scanner_checks import build_image_info

        data = {
            "src": "https://cdn.example.com/hero.jpg",
            "alt": "Hero image",
            "hasAlt": True,
            "loading": "lazy",
            "width": "800",
            "height": "600",
            "naturalWidth": 1600,
            "naturalHeight": 1200,
            "displayWidth": 800,
            "displayHeight": 600,
            "srcset": "hero-800.jpg 800w, hero-1600.jpg 1600w",
            "role": None,
            "ariaHidden": None,
            "fetchPriority": None,
            "decoding": None,
            "sizes": "(max-width: 800px) 100vw, 800px",
        }

        result = benchmark(build_image_info, data)
        assert result is not None
        assert result.src == "https://cdn.example.com/hero.jpg"


# ---------------------------------------------------------------------------
# Integration — _crawler_discovery (pure Python functions)
# ---------------------------------------------------------------------------

class TestCrawlerDiscoveryBenchmark:
    """Benchmarks for Integration._crawler_discovery pure-Python helpers."""

    def test_normalize_url_absolute(self, benchmark):
        """Benchmark normalizing an absolute URL."""
        from Asgard.Freya.Integration.services._crawler_discovery import normalize_url

        result = benchmark(normalize_url, "https://example.com/about/", "https://example.com")
        assert result == "https://example.com/about"

    def test_normalize_url_relative(self, benchmark):
        """Benchmark normalizing a relative URL against a base."""
        from Asgard.Freya.Integration.services._crawler_discovery import normalize_url

        result = benchmark(normalize_url, "/contact", "https://example.com/home")
        assert result == "https://example.com/contact"

    def test_normalize_url_javascript(self, benchmark):
        """Benchmark that javascript: links return None."""
        from Asgard.Freya.Integration.services._crawler_discovery import normalize_url

        result = benchmark(normalize_url, "javascript:void(0)", "https://example.com")
        assert result is None

    def test_should_crawl_same_domain(self, benchmark):
        """Benchmark should_crawl for a same-domain URL."""
        from Asgard.Freya.Integration.services._crawler_discovery import should_crawl

        result = benchmark(
            should_crawl,
            "https://example.com/about",
            "example.com",
            True,
            [],
            [],
        )
        assert result is True

    def test_should_crawl_different_domain(self, benchmark):
        """Benchmark should_crawl rejecting cross-domain when same_domain_only."""
        from Asgard.Freya.Integration.services._crawler_discovery import should_crawl

        result = benchmark(
            should_crawl,
            "https://other.com/page",
            "example.com",
            True,
            [],
            [],
        )
        assert result is False


# ---------------------------------------------------------------------------
# Links — _link_validator_helpers (pure Python)
# ---------------------------------------------------------------------------

class TestLinkValidatorHelpersBenchmark:
    """Benchmarks for Links._link_validator_helpers pure helpers."""

    def test_get_link_type_anchor(self, benchmark):
        """Benchmark link type detection for an anchor link."""
        from Asgard.Freya.Links.services._link_validator_helpers import get_link_type
        from Asgard.Freya.Links.models.link_models import LinkType
        from urllib.parse import urlparse

        base = urlparse("https://example.com")
        result = benchmark(get_link_type, "#section-1", "#section-1", base)
        assert result == LinkType.ANCHOR

    def test_get_link_type_mailto(self, benchmark):
        """Benchmark link type detection for a mailto link."""
        from Asgard.Freya.Links.services._link_validator_helpers import get_link_type
        from Asgard.Freya.Links.models.link_models import LinkType
        from urllib.parse import urlparse

        base = urlparse("https://example.com")
        result = benchmark(get_link_type, "mailto:hello@example.com", "mailto:hello@example.com", base)
        assert result == LinkType.MAILTO

    def test_filter_links_removes_duplicates(self, benchmark):
        """Benchmark filtering a list of links for duplicates."""
        from Asgard.Freya.Links.services._link_validator_helpers import filter_links
        from Asgard.Freya.Links.models.link_models import LinkConfig

        config = LinkConfig()
        links = [
            {"url": "https://example.com/page1", "href": "/page1", "text": "Page 1"},
            {"url": "https://example.com/page1", "href": "/page1", "text": "Page 1 dup"},
            {"url": "https://example.com/page2", "href": "/page2", "text": "Page 2"},
            {"url": "https://example.com/page3", "href": "/page3", "text": "Page 3"},
            {"url": "mailto:info@example.com", "href": "mailto:info@example.com", "text": "Email"},
        ]

        result = benchmark(filter_links, links, "https://example.com", config)
        assert len(result) < len(links)  # duplicates should be removed


# ---------------------------------------------------------------------------
# Performance — _page_load_helpers (pure Python)
# ---------------------------------------------------------------------------

class TestPageLoadHelpersBenchmark:
    """Benchmarks for Performance._page_load_helpers pure helpers."""

    @pytest.fixture()
    def nav_timing(self):
        from Asgard.Freya.Performance.models.performance_models import NavigationTiming
        return NavigationTiming(
            start_time=0,
            domain_lookup_start=5,
            domain_lookup_end=15,
            connect_start=15,
            secure_connection_start=20,
            connect_end=80,
            request_start=80,
            response_start=280,
            response_end=340,
            dom_interactive=600,
            dom_content_loaded_event_end=650,
            load_event_end=900,
        )

    def test_build_metrics(self, benchmark, nav_timing):
        """Benchmark building PageLoadMetrics from NavigationTiming."""
        from Asgard.Freya.Performance.services._page_load_helpers import build_metrics

        web_vitals = {"lcp": 1800.0, "fcp": 700.0, "cls": 0.05}
        result = benchmark(build_metrics, "https://example.com", nav_timing, web_vitals)
        assert result is not None
        assert result.time_to_first_byte > 0

    def test_identify_issues(self, benchmark, nav_timing):
        """Benchmark identifying performance issues from metrics."""
        from Asgard.Freya.Performance.services._page_load_helpers import (
            build_metrics,
            identify_issues,
        )
        from Asgard.Freya.Performance.models.performance_models import PerformanceConfig

        config = PerformanceConfig()
        web_vitals = {"lcp": 5000.0, "fcp": 3000.0, "cls": 0.3}
        metrics = build_metrics("https://example.com", nav_timing, web_vitals)

        result = benchmark(identify_issues, metrics, config)
        assert isinstance(result, list)

    def test_calculate_score(self, benchmark, nav_timing):
        """Benchmark calculating the performance score."""
        from Asgard.Freya.Performance.services._page_load_helpers import (
            build_metrics,
            calculate_score,
        )

        web_vitals = {"lcp": 1500.0, "fcp": 600.0, "cls": 0.02}
        metrics = build_metrics("https://example.com", nav_timing, web_vitals)

        score = benchmark(calculate_score, metrics)
        assert 0.0 <= score <= 100.0


class TestResourceTimingHelpersBenchmark:
    """Benchmarks for Performance._resource_timing_helpers."""

    def test_parse_resource(self, benchmark):
        """Benchmark parsing a raw resource timing dict."""
        from Asgard.Freya.Performance.services._resource_timing_helpers import parse_resource

        raw = {
            "name": "https://cdn.example.com/main.js",
            "initiatorType": "script",
            "domainLookupStart": 10,
            "domainLookupEnd": 20,
            "connectStart": 20,
            "secureConnectionStart": 25,
            "connectEnd": 90,
            "requestStart": 90,
            "responseStart": 200,
            "responseEnd": 250,
            "startTime": 5,
            "duration": 245,
            "transferSize": 45678,
            "encodedBodySize": 45000,
            "decodedBodySize": 120000,
        }

        result = benchmark(parse_resource, raw)
        assert result.url == "https://cdn.example.com/main.js"
        assert result.duration == 245


# ---------------------------------------------------------------------------
# SEO — _meta_tag_analyzers (pure Python)
# ---------------------------------------------------------------------------

class TestSeoMetaTagAnalyzersBenchmark:
    """Benchmarks for SEO._meta_tag_analyzers pure helpers."""

    @pytest.fixture()
    def seo_config(self):
        from Asgard.Freya.SEO.models.seo_models import SEOConfig
        return SEOConfig()

    def test_analyze_title_valid(self, benchmark, seo_config):
        """Benchmark analyzing a valid title tag."""
        from Asgard.Freya.SEO.services._meta_tag_analyzers import analyze_title

        result = benchmark(analyze_title, "Buy Shoes Online | Best Prices Guaranteed", seo_config)
        assert result.is_valid

    def test_analyze_title_missing(self, benchmark, seo_config):
        """Benchmark analyzing a missing title tag."""
        from Asgard.Freya.SEO.services._meta_tag_analyzers import analyze_title

        result = benchmark(analyze_title, None, seo_config)
        assert not result.is_present

    def test_analyze_title_too_short(self, benchmark, seo_config):
        """Benchmark analyzing a title that is too short."""
        from Asgard.Freya.SEO.services._meta_tag_analyzers import analyze_title

        result = benchmark(analyze_title, "Hi", seo_config)
        assert not result.is_valid

    def test_analyze_description_valid(self, benchmark, seo_config):
        """Benchmark analyzing a valid meta description."""
        from Asgard.Freya.SEO.services._meta_tag_analyzers import analyze_description

        desc = (
            "Shop the latest collection of running shoes with free shipping "
            "and 30-day returns. Find your perfect fit today."
        )
        result = benchmark(analyze_description, desc, seo_config)
        assert result.is_present

    def test_analyze_description_missing(self, benchmark, seo_config):
        """Benchmark analyzing a missing meta description."""
        from Asgard.Freya.SEO.services._meta_tag_analyzers import analyze_description

        result = benchmark(analyze_description, None, seo_config)
        assert not result.is_present


# ---------------------------------------------------------------------------
# Security — _security_header_analyzers (pure Python, uses httpx.Headers)
# ---------------------------------------------------------------------------

class TestSecurityHeaderAnalyzersBenchmark:
    """Benchmarks for Security._security_header_analyzers pure helpers."""

    @pytest.fixture()
    def security_config(self):
        from Asgard.Freya.Security.models.security_header_models import SecurityConfig
        return SecurityConfig()

    def _make_headers(self, header_dict: dict):
        """Build an httpx.Headers object from a plain dict."""
        import httpx
        return httpx.Headers(header_dict)

    def test_analyze_csp_present(self, benchmark, security_config):
        """Benchmark analyzing a present CSP header."""
        from Asgard.Freya.Security.services._security_header_analyzers import analyze_csp

        headers = self._make_headers({
            "Content-Security-Policy": "default-src 'self'; object-src 'none'"
        })
        result = benchmark(analyze_csp, headers, security_config)
        assert result.value is not None

    def test_analyze_csp_missing(self, benchmark, security_config):
        """Benchmark analyzing missing CSP header."""
        from Asgard.Freya.Security.services._security_header_analyzers import analyze_csp
        from Asgard.Freya.Security.models.security_header_models import SecurityHeaderStatus

        headers = self._make_headers({})
        result = benchmark(analyze_csp, headers, security_config)
        assert result.status == SecurityHeaderStatus.MISSING

    def test_analyze_hsts_present(self, benchmark, security_config):
        """Benchmark analyzing a present HSTS header."""
        from Asgard.Freya.Security.services._security_header_analyzers import analyze_hsts
        from Asgard.Freya.Security.models.security_header_models import SecurityHeaderStatus

        headers = self._make_headers({
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload"
        })
        result = benchmark(analyze_hsts, headers, security_config)
        assert result.status == SecurityHeaderStatus.PRESENT

    def test_analyze_frame_options(self, benchmark, security_config):
        """Benchmark analyzing X-Frame-Options header."""
        from Asgard.Freya.Security.services._security_header_analyzers import analyze_frame_options

        headers = self._make_headers({"X-Frame-Options": "DENY"})
        result = benchmark(analyze_frame_options, headers)
        assert result is not None

    def test_analyze_referrer_policy(self, benchmark, security_config):
        """Benchmark analyzing Referrer-Policy header."""
        from Asgard.Freya.Security.services._security_header_analyzers import analyze_referrer_policy

        headers = self._make_headers({"Referrer-Policy": "strict-origin-when-cross-origin"})
        result = benchmark(analyze_referrer_policy, headers)
        assert result is not None


# ---------------------------------------------------------------------------
# Visual — image_ops.Image (pure Python, stdlib only)
# ---------------------------------------------------------------------------

class TestVisualImageOpsBenchmark:
    """Benchmarks for Visual.image_ops pure-Python image operations."""

    def test_create_image(self, benchmark):
        """Benchmark creating a blank Image object."""
        from Asgard.Freya.Visual.services.image_ops import Image

        result = benchmark(Image, 200, 200)
        assert result.width == 200
        assert result.height == 200

    def test_image_copy(self, benchmark):
        """Benchmark copying an Image."""
        from Asgard.Freya.Visual.services.image_ops import Image

        img = Image(100, 100)
        result = benchmark(img.copy)
        assert result.width == 100

    def test_to_grayscale_array(self, benchmark):
        """Benchmark converting an image to a grayscale array."""
        from Asgard.Freya.Visual.services.image_ops import Image

        pixels = [(r % 256, (r * 2) % 256, (r * 3) % 256) for r in range(100 * 100)]
        img = Image(100, 100, pixels)

        result = benchmark(img.to_grayscale_array)
        assert len(result) == 100 * 100

    def test_difference(self, benchmark):
        """Benchmark pixel-level difference between two images."""
        from Asgard.Freya.Visual.services.image_ops import Image, difference

        pixels_a = [(200, 100, 50)] * (80 * 80)
        pixels_b = [(180, 110, 60)] * (80 * 80)
        img_a = Image(80, 80, pixels_a)
        img_b = Image(80, 80, pixels_b)

        result = benchmark(difference, img_a, img_b)
        assert result.width == 80


class TestVisualImageOpsAnalysisBenchmark:
    """Benchmarks for Visual._image_ops_analysis pure helpers."""

    @pytest.fixture()
    def grayscale_diff(self):
        """Fixture providing a synthetic grayscale difference array."""
        from Asgard.Freya.Visual.services.image_ops import Image, difference

        pixels_a = [(i % 256, (i * 2) % 256, (i * 3) % 256) for i in range(60 * 60)]
        pixels_b = [(min(255, (i + 20) % 256), (i * 2) % 256, (i * 3) % 256) for i in range(60 * 60)]
        img_a = Image(60, 60, pixels_a)
        img_b = Image(60, 60, pixels_b)
        from Asgard.Freya.Visual.services._image_ops_analysis import grayscale_difference_array
        return grayscale_difference_array(img_a, img_b)

    def test_count_above_threshold(self, benchmark, grayscale_diff):
        """Benchmark counting pixels above a threshold."""
        from Asgard.Freya.Visual.services._image_ops_analysis import count_above_threshold

        count = benchmark(count_above_threshold, grayscale_diff, 10)
        assert count >= 0

    def test_threshold_to_binary(self, benchmark, grayscale_diff):
        """Benchmark converting a diff array to binary."""
        from Asgard.Freya.Visual.services._image_ops_analysis import threshold_to_binary

        binary = benchmark(threshold_to_binary, grayscale_diff, 10)
        assert len(binary) == len(grayscale_diff)
        assert all(v in (0, 1) for v in binary)


class TestVisualRegressionCompareBenchmark:
    """Benchmarks for Visual._visual_regression_compare.pixel_comparison."""

    def test_pixel_comparison_identical_images(self, benchmark):
        """Benchmark pixel comparison of two identical images."""
        from Asgard.Freya.Visual.services.image_ops import Image
        from Asgard.Freya.Visual.services._visual_regression_compare import pixel_comparison
        from Asgard.Freya.Visual.models.visual_models import ComparisonConfig

        config = ComparisonConfig()
        pixels = [(120, 80, 40)] * (50 * 50)
        img_a = Image(50, 50, list(pixels))
        img_b = Image(50, 50, list(pixels))

        score, regions = benchmark(pixel_comparison, img_a, img_b, config)
        assert score == 1.0
        assert regions == []

    def test_pixel_comparison_different_images(self, benchmark):
        """Benchmark pixel comparison of two visually different images."""
        from Asgard.Freya.Visual.services.image_ops import Image
        from Asgard.Freya.Visual.services._visual_regression_compare import pixel_comparison
        from Asgard.Freya.Visual.models.visual_models import ComparisonConfig

        config = ComparisonConfig()
        pixels_a = [(200, 100, 50)] * (50 * 50)
        pixels_b = [(50, 200, 150)] * (50 * 50)
        img_a = Image(50, 50, pixels_a)
        img_b = Image(50, 50, pixels_b)

        score, regions = benchmark(pixel_comparison, img_a, img_b, config)
        assert score < 1.0
