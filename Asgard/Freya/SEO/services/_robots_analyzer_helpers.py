"""
Freya Robots Analyzer helper functions.

Helper functions extracted from robots_analyzer.py.
"""

import re
import xml.etree.ElementTree as ET
from typing import Optional

from Asgard.Freya.SEO.models.seo_models import (
    RobotDirective,
    RobotsTxtReport,
    SitemapEntry,
    SitemapReport,
)


def parse_robots_txt(content: str, report: RobotsTxtReport) -> None:
    """Parse robots.txt content."""
    current_user_agent = None
    line_number = 0

    for line in content.split("\n"):
        line_number += 1
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        match = re.match(r"^([^:]+):\s*(.*)$", line, re.IGNORECASE)
        if not match:
            continue

        directive = match.group(1).lower()
        value = match.group(2).strip()

        if directive == "user-agent":
            current_user_agent = value
            if value not in report.user_agents:
                report.user_agents.append(value)

        elif directive == "allow":
            report.allow_directives.append(RobotDirective(
                directive="Allow",
                value=value,
                line_number=line_number,
            ))

        elif directive == "disallow":
            report.disallow_directives.append(RobotDirective(
                directive="Disallow",
                value=value,
                line_number=line_number,
            ))

        elif directive == "sitemap":
            if value not in report.sitemap_urls:
                report.sitemap_urls.append(value)

        elif directive == "crawl-delay":
            try:
                report.crawl_delay = float(value)
            except ValueError:
                report.warnings.append(
                    f"Invalid crawl-delay value on line {line_number}"
                )


def analyze_robots_issues(report: RobotsTxtReport) -> None:
    """Analyze robots.txt for potential issues."""
    for directive in report.disallow_directives:
        if directive.value == "/" and "*" in report.user_agents:
            report.issues.append(
                "All crawlers are blocked from the entire site (Disallow: /)"
            )

    if not report.sitemap_urls:
        report.warnings.append("No sitemap URL specified in robots.txt")
        report.suggestions.append(
            "Add Sitemap: directive to help crawlers find your sitemap"
        )

    if report.crawl_delay and report.crawl_delay > 10:
        report.warnings.append(
            f"Crawl-delay of {report.crawl_delay}s is quite high"
        )

    for directive in report.disallow_directives:
        if "/admin" in directive.value or "/wp-admin" in directive.value:
            pass
        elif "/api" in directive.value:
            report.warnings.append(
                "API endpoints are blocked - this may affect SEO for API-driven content"
            )


def get_elem_text(parent: ET.Element, tag: str, ns: dict) -> Optional[str]:
    """Get text content of a child element."""
    elem = parent.find(tag, ns)
    return elem.text if elem is not None else None


def parse_sitemap(content: str, report: SitemapReport) -> None:
    """Parse sitemap XML content."""
    try:
        root = ET.fromstring(content)
        report.is_valid_xml = True

        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        if root.tag.endswith("sitemapindex"):
            report.is_sitemap_index = True

            for sitemap in root.findall(".//sm:sitemap/sm:loc", ns):
                if sitemap.text:
                    report.child_sitemaps.append(sitemap.text)

            report.total_urls = len(report.child_sitemaps)

        else:
            report.is_sitemap_index = False

            for url_elem in root.findall(".//sm:url", ns):
                entry = SitemapEntry(
                    loc=get_elem_text(url_elem, "sm:loc", ns) or ""
                )

                lastmod = get_elem_text(url_elem, "sm:lastmod", ns)
                if lastmod:
                    entry.lastmod = lastmod
                    report.urls_with_lastmod += 1

                changefreq = get_elem_text(url_elem, "sm:changefreq", ns)
                if changefreq:
                    entry.changefreq = changefreq

                priority = get_elem_text(url_elem, "sm:priority", ns)
                if priority:
                    try:
                        entry.priority = float(priority)
                        report.urls_with_priority += 1
                    except ValueError:
                        pass

                report.entries.append(entry)

            report.total_urls = len(report.entries)

    except ET.ParseError as e:
        report.is_valid_xml = False
        report.issues.append(f"Invalid XML: {str(e)}")


def analyze_sitemap_issues(report: SitemapReport) -> None:
    """Analyze sitemap for potential issues."""
    if not report.is_valid_xml:
        return

    if report.total_urls == 0:
        report.issues.append("Sitemap contains no URLs")
    elif report.total_urls > 50000:
        report.warnings.append(
            f"Sitemap has {report.total_urls} URLs - consider using sitemap index"
        )

    if report.total_urls > 0:
        lastmod_ratio = report.urls_with_lastmod / report.total_urls
        if lastmod_ratio < 0.5:
            report.warnings.append(
                f"Only {report.urls_with_lastmod}/{report.total_urls} URLs have lastmod"
            )

    if report.urls_with_priority > 0:
        priorities = set(
            e.priority for e in report.entries if e.priority is not None
        )
        if len(priorities) == 1:
            report.warnings.append(
                "All URLs have the same priority - consider differentiating"
            )
