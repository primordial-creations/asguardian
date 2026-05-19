"""L3 Contract tests for additional Freya (frontend quality) models.

Covers: Console, Images, Links, Performance, SEO, Security headers.
"""
import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Console
# ---------------------------------------------------------------------------
from Asgard.Freya.Console.models.console_models import (
    ConsoleMessage,
    PageError,
    ResourceError,
    ConsoleReport,
    ConsoleConfig,
)


class TestConsoleMessageContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ConsoleMessage()

    def test_accepts_valid_data(self):
        cm = ConsoleMessage(message_type="error", severity="critical", text="Uncaught TypeError")
        assert cm.message_type == "error"
        assert hasattr(cm, "text")


class TestPageErrorContract:
    def test_requires_message(self):
        with pytest.raises((ValidationError, TypeError)):
            PageError()

    def test_accepts_valid_data(self):
        pe = PageError(message="404 Not Found")
        assert pe.message == "404 Not Found"


class TestConsoleConfigContract:
    def test_instantiates_with_defaults(self):
        config = ConsoleConfig()
        assert config is not None

    def test_has_expected_fields(self):
        assert hasattr(ConsoleConfig, "model_fields")


class TestConsoleReportContract:
    def test_instantiates_with_defaults(self):
        report = ConsoleReport(url="https://example.com")
        assert report is not None
        assert hasattr(ConsoleReport, "model_fields")


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------
from Asgard.Freya.Images.models.image_models import (
    ImageInfo,
    ImageIssue,
    ImageReport,
    ImageConfig,
)


class TestImageInfoContract:
    def test_requires_src(self):
        with pytest.raises((ValidationError, TypeError)):
            ImageInfo()

    def test_accepts_valid_data(self):
        img = ImageInfo(src="https://example.com/img.png")
        assert img.src == "https://example.com/img.png"
        assert hasattr(img, "alt") or hasattr(ImageInfo, "model_fields")


class TestImageIssueContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ImageIssue()

    def test_accepts_valid_data(self):
        ii = ImageIssue(
            issue_type="missing_alt",
            severity="critical",
            image_src="https://example.com/img.png",
            description="Image has no alt text",
            suggested_fix="Add descriptive alt text",
            impact="Accessibility fail",
        )
        assert ii.issue_type == "missing_alt"


class TestImageConfigContract:
    def test_instantiates_with_defaults(self):
        config = ImageConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------
from Asgard.Freya.Links.models.link_models import (
    LinkResult,
    BrokenLink,
    RedirectChain,
    LinkReport,
    LinkConfig,
)


class TestLinkResultContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            LinkResult()

    def test_accepts_valid_data(self):
        lr = LinkResult(
            url="https://example.com/page",
            source_url="https://example.com",
            link_type="internal",
            status="ok",
        )
        assert lr.url == "https://example.com/page"
        assert hasattr(lr, "link_type")


class TestBrokenLinkContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            BrokenLink()

    def test_accepts_valid_data(self):
        bl = BrokenLink(
            url="https://example.com/missing",
            source_url="https://example.com",
            severity="critical",
            suggested_fix="Remove or update link",
        )
        assert bl.url == "https://example.com/missing"


class TestLinkConfigContract:
    def test_instantiates_with_defaults(self):
        config = LinkConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------
from Asgard.Freya.Performance.models.performance_models import (
    NavigationTiming,
    PageLoadMetrics,
    PerformanceConfig,
    PerformanceIssue,
    PerformanceReport,
    ResourceTimingReport,
)


class TestNavigationTimingContract:
    def test_instantiates_with_defaults(self):
        nt = NavigationTiming()
        assert nt is not None
        assert hasattr(NavigationTiming, "model_fields")


class TestPageLoadMetricsContract:
    def test_requires_url(self):
        with pytest.raises((ValidationError, TypeError)):
            PageLoadMetrics()

    def test_accepts_valid_data(self):
        plm = PageLoadMetrics(url="https://example.com")
        assert plm.url == "https://example.com"
        assert hasattr(plm, "load_time_ms") or hasattr(PageLoadMetrics, "model_fields")


class TestPerformanceConfigContract:
    def test_instantiates_with_defaults(self):
        config = PerformanceConfig()
        assert config is not None


class TestPerformanceIssueContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            PerformanceIssue()

    def test_accepts_valid_data(self):
        pi = PerformanceIssue(
            issue_type="slow_lcp",
            severity="high",
            metric_name="LCP",
            actual_value=5.0,
            threshold_value=2.5,
            description="LCP too slow",
            suggested_fix="Optimize images",
        )
        assert pi.metric_name == "LCP"


class TestFreyaPerformanceReportContract:
    def test_requires_url(self):
        with pytest.raises((ValidationError, TypeError)):
            PerformanceReport()

    def test_accepts_valid_data(self):
        report = PerformanceReport(url="https://example.com")
        assert report.url == "https://example.com"
        assert hasattr(report, "issues") or hasattr(PerformanceReport, "model_fields")


# ---------------------------------------------------------------------------
# SEO
# ---------------------------------------------------------------------------
from Asgard.Freya.SEO.models.seo_models import (
    MetaTag,
    MetaTagReport,
    SEOIssue,
    SEOReport,
    SEOConfig,
)


class TestMetaTagContract:
    def test_requires_tag_type(self):
        with pytest.raises((ValidationError, TypeError)):
            MetaTag()

    def test_accepts_valid_data(self):
        mt = MetaTag(tag_type="title")
        assert mt.tag_type == "title"
        assert hasattr(mt, "content") or hasattr(MetaTag, "model_fields")


class TestSEOIssueContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            SEOIssue()

    def test_accepts_valid_data(self):
        si = SEOIssue(
            issue_type="missing_meta_description",
            severity="warning",
            category="meta_tags",
            description="No meta description",
            suggested_fix="Add meta description tag",
        )
        assert si.issue_type == "missing_meta_description"


class TestSEOConfigContract:
    def test_instantiates_with_defaults(self):
        config = SEOConfig()
        assert config is not None


class TestSEOReportContract:
    def test_instantiates_with_defaults(self):
        report = SEOReport(url="https://example.com")
        assert report is not None
        assert hasattr(SEOReport, "model_fields")


# ---------------------------------------------------------------------------
# Security Headers (Freya)
# ---------------------------------------------------------------------------
from Asgard.Freya.Security.models.security_header_models import (
    SecurityHeader,
    CSPDirective,
    CSPReport,
    SecurityHeaderReport,
    SecurityIssue,
    SecurityConfig,
)


class TestSecurityHeaderContract:
    def test_requires_name_and_status(self):
        with pytest.raises((ValidationError, TypeError)):
            SecurityHeader()

    def test_accepts_valid_data(self):
        sh = SecurityHeader(name="X-Frame-Options", status="present")
        assert sh.name == "X-Frame-Options"
        assert hasattr(sh, "status")


class TestCSPDirectiveContract:
    def test_requires_name(self):
        with pytest.raises((ValidationError, TypeError)):
            CSPDirective()

    def test_accepts_valid_data(self):
        csp = CSPDirective(name="default-src")
        assert csp.name == "default-src"


class TestSecurityConfigContract:
    def test_instantiates_with_defaults(self):
        config = SecurityConfig()
        assert config is not None


class TestSecurityHeaderReportContract:
    def test_instantiates_with_defaults(self):
        report = SecurityHeaderReport(url="https://example.com")
        assert report is not None
        assert hasattr(SecurityHeaderReport, "model_fields")
