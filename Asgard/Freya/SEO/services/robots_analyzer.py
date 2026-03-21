"""
Freya Robots Analyzer

Analyzes robots.txt and sitemap.xml files for SEO compliance.
"""

import re
import xml.etree.ElementTree as ET
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import httpx

from Asgard.Freya.SEO.models.seo_models import (
    RobotDirective,
    RobotsTxtReport,
    SEOConfig,
    SitemapEntry,
    SitemapReport,
)
from Asgard.Freya.SEO.services._robots_analyzer_helpers import (
    analyze_robots_issues,
    analyze_sitemap_issues,
    get_elem_text,
    parse_robots_txt,
    parse_sitemap,
)


class RobotsAnalyzer:
    """
    Analyzes robots.txt and sitemap.xml files.

    Checks for proper configuration and identifies potential issues.
    """

    def __init__(self, config: Optional[SEOConfig] = None):
        """
        Initialize the robots analyzer.

        Args:
            config: SEO configuration
        """
        self.config = config or SEOConfig()
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; FreyaBot/1.0; "
                        "+https://github.com/JakeDruett/asgard)"
                    )
                },
            )
        return self._http_client

    async def analyze_robots(self, url: str) -> RobotsTxtReport:
        """
        Analyze robots.txt for a site.

        Args:
            url: Site URL (robots.txt will be fetched from root)

        Returns:
            RobotsTxtReport with analysis results
        """
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        report = RobotsTxtReport(url=url, robots_url=robots_url)

        try:
            client = await self._get_client()
            response = await client.get(robots_url)

            report.status_code = response.status_code

            if response.status_code == 200:
                report.exists = True
                report.is_accessible = True
                report.content_length = len(response.text)

                parse_robots_txt(response.text, report)
                analyze_robots_issues(report)

            elif response.status_code == 404:
                report.exists = False
                report.is_accessible = True
                report.issues.append("robots.txt file does not exist")
                report.suggestions.append("Create a robots.txt file to control crawler access")

            else:
                report.exists = False
                report.is_accessible = False
                report.issues.append(
                    f"robots.txt returned HTTP {response.status_code}"
                )

        except httpx.HTTPError as e:
            report.exists = False
            report.is_accessible = False
            report.issues.append(f"Failed to fetch robots.txt: {str(e)}")

        return report

    async def analyze_sitemap(self, url: str) -> SitemapReport:
        """
        Analyze sitemap.xml for a site.

        Args:
            url: Site URL (sitemap.xml will be fetched from root)

        Returns:
            SitemapReport with analysis results
        """
        parsed = urlparse(url)
        sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"

        report = SitemapReport(url=url, sitemap_url=sitemap_url)

        try:
            client = await self._get_client()
            response = await client.get(sitemap_url)

            report.status_code = response.status_code

            if response.status_code == 200:
                report.exists = True
                report.is_accessible = True

                parse_sitemap(response.text, report)
                analyze_sitemap_issues(report)

            elif response.status_code == 404:
                report.exists = False
                report.is_accessible = True
                report.issues.append("sitemap.xml file does not exist")

            else:
                report.exists = False
                report.is_accessible = False
                report.issues.append(
                    f"sitemap.xml returned HTTP {response.status_code}"
                )

        except httpx.HTTPError as e:
            report.exists = False
            report.is_accessible = False
            report.issues.append(f"Failed to fetch sitemap.xml: {str(e)}")

        return report

    def _parse_robots_txt(self, content: str, report: RobotsTxtReport) -> None:
        """Parse robots.txt content."""
        parse_robots_txt(content, report)

    def _analyze_robots_issues(self, report: RobotsTxtReport) -> None:
        """Analyze robots.txt for potential issues."""
        analyze_robots_issues(report)

    def _parse_sitemap(self, content: str, report: SitemapReport) -> None:
        """Parse sitemap XML content."""
        parse_sitemap(content, report)

    def _get_elem_text(
        self, parent: ET.Element, tag: str, ns: dict
    ) -> Optional[str]:
        """Get text content of a child element."""
        return get_elem_text(parent, tag, ns)

    def _analyze_sitemap_issues(self, report: SitemapReport) -> None:
        """Analyze sitemap for potential issues."""
        analyze_sitemap_issues(report)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
