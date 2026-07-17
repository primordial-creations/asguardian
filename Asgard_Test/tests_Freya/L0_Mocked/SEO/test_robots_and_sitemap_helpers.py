"""L0 tests: SEO robots.txt / sitemap.xml pure-function parsers."""

import pytest

from Asgard.Freya.SEO.models.seo_models import RobotsTxtReport, SitemapReport
from Asgard.Freya.SEO.services._robots_analyzer_helpers import (
    analyze_robots_issues,
    analyze_sitemap_issues,
    parse_robots_txt,
    parse_sitemap,
)


def _robots_report():
    return RobotsTxtReport(url="https://example.com", robots_url="https://example.com/robots.txt")


def _sitemap_report():
    return SitemapReport(url="https://example.com", sitemap_url="https://example.com/sitemap.xml")


class TestParseRobotsTxt:
    def test_basic_directives(self):
        report = _robots_report()
        parse_robots_txt(
            "User-agent: *\nDisallow: /admin\nAllow: /admin/public\nSitemap: https://example.com/sitemap.xml\n",
            report,
        )
        assert "*" in report.user_agents
        assert len(report.disallow_directives) == 1
        assert report.disallow_directives[0].value == "/admin"
        assert len(report.allow_directives) == 1
        assert report.sitemap_urls == ["https://example.com/sitemap.xml"]

    def test_comments_and_blank_lines_ignored(self):
        report = _robots_report()
        parse_robots_txt("# comment\n\nUser-agent: *\n", report)
        assert report.user_agents == ["*"]

    def test_crawl_delay_parsed(self):
        report = _robots_report()
        parse_robots_txt("User-agent: *\nCrawl-delay: 5\n", report)
        assert report.crawl_delay == 5.0

    def test_invalid_crawl_delay_warns(self):
        report = _robots_report()
        parse_robots_txt("User-agent: *\nCrawl-delay: not-a-number\n", report)
        assert report.crawl_delay is None
        assert any("Invalid crawl-delay" in w for w in report.warnings)

    def test_duplicate_sitemap_not_repeated(self):
        report = _robots_report()
        parse_robots_txt("Sitemap: https://example.com/s.xml\nSitemap: https://example.com/s.xml\n", report)
        assert report.sitemap_urls == ["https://example.com/s.xml"]

    def test_malformed_line_skipped(self):
        report = _robots_report()
        parse_robots_txt("this is not a directive line\nUser-agent: *\n", report)
        assert report.user_agents == ["*"]


class TestAnalyzeRobotsIssues:
    def test_full_block_flagged(self):
        report = _robots_report()
        parse_robots_txt("User-agent: *\nDisallow: /\n", report)
        analyze_robots_issues(report)
        assert any("blocked from the entire site" in i for i in report.issues)

    def test_no_sitemap_warns_and_suggests(self):
        report = _robots_report()
        parse_robots_txt("User-agent: *\nDisallow: /admin\n", report)
        analyze_robots_issues(report)
        assert any("sitemap" in w.lower() for w in report.warnings)
        assert report.suggestions

    def test_high_crawl_delay_warns(self):
        report = _robots_report()
        parse_robots_txt("User-agent: *\nCrawl-delay: 30\nSitemap: https://example.com/s.xml\n", report)
        analyze_robots_issues(report)
        assert any("Crawl-delay" in w for w in report.warnings)

    def test_blocked_api_endpoints_warns(self):
        report = _robots_report()
        parse_robots_txt(
            "User-agent: *\nDisallow: /api\nSitemap: https://example.com/s.xml\n", report
        )
        analyze_robots_issues(report)
        assert any("API endpoints" in w for w in report.warnings)


class TestParseSitemap:
    def test_urlset_parsed(self):
        report = _sitemap_report()
        xml = """<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/a</loc><lastmod>2024-01-01</lastmod><priority>0.8</priority></url>
          <url><loc>https://example.com/b</loc></url>
        </urlset>"""
        parse_sitemap(xml, report)
        assert report.is_valid_xml is True
        assert report.is_sitemap_index is False
        assert report.total_urls == 2
        assert report.urls_with_lastmod == 1
        assert report.urls_with_priority == 1

    def test_sitemap_index_parsed(self):
        report = _sitemap_report()
        xml = """<?xml version="1.0"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap><loc>https://example.com/s1.xml</loc></sitemap>
          <sitemap><loc>https://example.com/s2.xml</loc></sitemap>
        </sitemapindex>"""
        parse_sitemap(xml, report)
        assert report.is_sitemap_index is True
        assert report.child_sitemaps == ["https://example.com/s1.xml", "https://example.com/s2.xml"]
        assert report.total_urls == 2

    def test_invalid_xml_recorded_as_issue(self):
        report = _sitemap_report()
        parse_sitemap("<not-xml", report)
        assert report.is_valid_xml is False
        assert any("Invalid XML" in i for i in report.issues)

    def test_invalid_priority_value_ignored_gracefully(self):
        report = _sitemap_report()
        xml = """<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/a</loc><priority>not-a-number</priority></url>
        </urlset>"""
        parse_sitemap(xml, report)
        assert report.urls_with_priority == 0


class TestAnalyzeSitemapIssues:
    def test_empty_sitemap_flagged(self):
        report = _sitemap_report()
        report.is_valid_xml = True
        report.total_urls = 0
        analyze_sitemap_issues(report)
        assert any("no URLs" in i for i in report.issues)

    def test_invalid_xml_short_circuits(self):
        report = _sitemap_report()
        report.is_valid_xml = False
        analyze_sitemap_issues(report)
        assert report.issues == []
        assert report.warnings == []

    def test_large_sitemap_suggests_index(self):
        report = _sitemap_report()
        report.is_valid_xml = True
        report.total_urls = 60000
        analyze_sitemap_issues(report)
        assert any("sitemap index" in w for w in report.warnings)

    def test_low_lastmod_ratio_warns(self):
        report = _sitemap_report()
        report.is_valid_xml = True
        report.total_urls = 10
        report.urls_with_lastmod = 2
        analyze_sitemap_issues(report)
        assert any("lastmod" in w for w in report.warnings)
