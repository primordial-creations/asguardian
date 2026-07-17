"""L0 tests: Links pure helpers (URL classification, filtering, health score)."""

from urllib.parse import urlparse

import pytest

from Asgard.Freya.Links.models.link_models import (
    LinkConfig,
    LinkReport,
    LinkResult,
    LinkStatus,
    LinkType,
)
from Asgard.Freya.Links.services._link_validator_helpers import (
    build_report,
    calculate_health_score,
    filter_links,
    get_link_type,
)


class TestGetLinkType:
    @pytest.mark.parametrize(
        "url,href,expected",
        [
            ("https://example.com#top", "#top", LinkType.ANCHOR),
            ("mailto:a@b.com", "mailto:a@b.com", LinkType.MAILTO),
            ("tel:+123456", "tel:+123456", LinkType.TEL),
            ("javascript:void(0)", "javascript:void(0)", LinkType.JAVASCRIPT),
            ("https://example.com/page", "/page", LinkType.INTERNAL),
            ("https://other.com/page", "https://other.com/page", LinkType.EXTERNAL),
        ],
    )
    def test_classification_matrix(self, url, href, expected):
        base = urlparse("https://example.com")
        assert get_link_type(url, href, base) == expected

    def test_non_http_scheme_different_host_returns_other(self):
        base = urlparse("https://example.com")
        # ftp scheme, different host -> not same netloc, not http/https -> OTHER
        assert get_link_type("ftp://other.org/f", "ftp://other.org/f", base) == LinkType.OTHER


class TestFilterLinks:
    def _links(self, urls):
        return [{"url": u, "href": u} for u in urls]

    def test_dedupes_by_url(self):
        config = LinkConfig()
        links = self._links(["https://example.com/a", "https://example.com/a"])
        filtered = filter_links(links, "https://example.com", config)
        assert len(filtered) == 1

    def test_skips_mailto_when_configured(self):
        config = LinkConfig(skip_mailto=True)
        links = self._links(["mailto:a@b.com"])
        assert filter_links(links, "https://example.com", config) == []

    def test_keeps_mailto_when_not_skipped(self):
        config = LinkConfig(skip_mailto=False)
        links = self._links(["mailto:a@b.com"])
        assert len(filter_links(links, "https://example.com", config)) == 1

    def test_excludes_internal_when_check_internal_false(self):
        config = LinkConfig(check_internal=False)
        links = self._links(["https://example.com/page"])
        assert filter_links(links, "https://example.com", config) == []

    def test_excludes_external_when_check_external_false(self):
        config = LinkConfig(check_external=False)
        links = self._links(["https://other.com/page"])
        assert filter_links(links, "https://example.com", config) == []

    def test_skip_pattern_removes_matching_link(self):
        config = LinkConfig(skip_patterns=[r"/admin"])
        links = self._links(["https://example.com/admin/x", "https://example.com/page"])
        filtered = filter_links(links, "https://example.com", config)
        assert len(filtered) == 1
        assert filtered[0]["url"] == "https://example.com/page"

    def test_empty_url_and_href_skipped(self):
        config = LinkConfig()
        assert filter_links([{"url": "", "href": ""}], "https://example.com", config) == []


class TestCalculateHealthScore:
    def test_no_links_is_perfect_score(self):
        report = LinkReport(url="https://example.com", total_links=0)
        assert calculate_health_score(report) == 100

    def test_broken_links_penalize_score(self):
        report = LinkReport(url="https://example.com", total_links=10, broken_count=2)
        assert calculate_health_score(report) == 80

    def test_score_floors_at_zero(self):
        report = LinkReport(
            url="https://example.com",
            total_links=10,
            broken_count=20,
            timeout_count=20,
            error_count=20,
            redirect_chains=[{"start_url": "a", "final_url": "b", "chain": ["a", "b"],
                               "chain_length": 1, "source_url": "s", "total_time_ms": 1}] * 20,
        )
        assert calculate_health_score(report) == 0

    def test_broken_penalty_caps_at_50(self):
        report = LinkReport(url="https://example.com", total_links=100, broken_count=100)
        # broken penalty capped at 50 -> score 50 (no other penalties)
        assert calculate_health_score(report) == 50


class TestBuildReport:
    def _result(self, url, status, link_type=LinkType.INTERNAL, status_code=None, is_broken=False):
        return LinkResult(
            url=url,
            source_url="https://example.com",
            link_type=link_type,
            status=status,
            status_code=status_code,
            is_broken=is_broken,
        )

    def test_counts_by_status_and_type(self):
        results = [
            self._result("https://example.com/a", LinkStatus.OK, LinkType.INTERNAL),
            self._result("https://example.com/b", LinkStatus.BROKEN, LinkType.INTERNAL,
                          status_code=404, is_broken=True),
            self._result("https://other.com/c", LinkStatus.OK, LinkType.EXTERNAL),
        ]
        config = LinkConfig()
        report = build_report("https://example.com", results, results, 12.5, config)
        assert report.internal_links == 2
        assert report.external_links == 1
        assert report.ok_count == 2
        assert report.broken_count == 1
        assert len(report.broken_links) == 1
        assert report.broken_links[0].status_code == 404
        assert report.broken_links[0].severity.value == "warning"  # 404 -> warning

    def test_include_ok_links_false_filters_results(self):
        results = [
            self._result("https://example.com/a", LinkStatus.OK),
            self._result("https://example.com/b", LinkStatus.BROKEN, status_code=500, is_broken=True),
        ]
        config = LinkConfig(include_ok_links=False)
        report = build_report("https://example.com", results, results, 1.0, config)
        assert all(r.status != LinkStatus.OK for r in report.results)

    def test_suggestions_present_when_broken_links_exist(self):
        results = [self._result("https://example.com/a", LinkStatus.BROKEN, status_code=500, is_broken=True)]
        config = LinkConfig()
        report = build_report("https://example.com", results, results, 1.0, config)
        assert any("broken link" in s for s in report.suggestions)
