"""
Freya Link Validator helper functions.

Helper functions extracted from link_validator.py.
"""

import re
from typing import Any, Dict, List, Set, cast
from urllib.parse import urljoin, urlparse

from Asgard.Freya.Links.models.link_models import (
    BrokenLink,
    LinkConfig,
    LinkReport,
    LinkResult,
    LinkSeverity,
    LinkStatus,
    LinkType,
    RedirectChain,
)


def get_link_type(url: str, href: str, parsed_base: Any) -> LinkType:
    """Determine the type of a link."""
    href_lower = href.lower()

    if href.startswith("#"):
        return LinkType.ANCHOR
    if href_lower.startswith("mailto:"):
        return LinkType.MAILTO
    if href_lower.startswith("tel:"):
        return LinkType.TEL
    if href_lower.startswith("javascript:"):
        return LinkType.JAVASCRIPT

    try:
        parsed = urlparse(url)
        if parsed.netloc == parsed_base.netloc:
            return LinkType.INTERNAL
        elif parsed.scheme in ["http", "https"]:
            return LinkType.EXTERNAL
    except Exception:
        pass

    return LinkType.OTHER


def filter_links(links: List[Dict], base_url: str, config: LinkConfig) -> List[Dict]:
    """Filter links based on configuration."""
    filtered = []
    seen_urls: Set[str] = set()

    parsed_base = urlparse(base_url)

    for link in links:
        url = link.get("url", "")
        href = link.get("href", "")

        if not url and not href:
            continue

        if url in seen_urls:
            continue
        seen_urls.add(url)

        link_type = get_link_type(url, href, parsed_base)
        link["link_type"] = link_type

        if link_type == LinkType.MAILTO and config.skip_mailto:
            continue
        if link_type == LinkType.TEL and config.skip_tel:
            continue
        if link_type == LinkType.JAVASCRIPT and config.skip_javascript:
            continue

        if link_type == LinkType.INTERNAL and not config.check_internal:
            continue
        if link_type == LinkType.EXTERNAL and not config.check_external:
            continue
        if link_type == LinkType.ANCHOR and not config.check_anchors:
            continue

        skip = False
        for pattern in config.skip_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                skip = True
                break

        if not skip:
            filtered.append(link)

    return filtered


def build_report(
    url: str,
    all_links: List[Dict],
    results: List[LinkResult],
    analysis_duration: float,
    config: LinkConfig,
) -> LinkReport:
    """Build the link validation report."""
    report = LinkReport(
        url=url,
        analysis_duration_ms=analysis_duration,
        results=results if config.include_ok_links else [
            r for r in results if r.status != LinkStatus.OK
        ],
        total_links=len(all_links),
    )

    for result in results:
        if result.link_type == LinkType.INTERNAL:
            report.internal_links += 1
        elif result.link_type == LinkType.EXTERNAL:
            report.external_links += 1
        elif result.link_type == LinkType.ANCHOR:
            report.anchor_links += 1

    for result in results:
        if result.status == LinkStatus.OK:
            report.ok_count += 1
        elif result.status == LinkStatus.BROKEN:
            report.broken_count += 1
        elif result.status == LinkStatus.REDIRECT:
            report.redirect_count += 1
        elif result.status == LinkStatus.TIMEOUT:
            report.timeout_count += 1
        elif result.status == LinkStatus.ERROR:
            report.error_count += 1
        elif result.status == LinkStatus.SKIPPED:
            report.skipped_count += 1

    for result in results:
        if result.is_broken:
            severity = LinkSeverity.CRITICAL
            if result.status_code and result.status_code in [403, 404]:
                severity = LinkSeverity.WARNING

            suggested_fix = "Fix or remove the broken link"
            if result.status_code == 404:
                suggested_fix = "Update link to correct URL or remove"
            elif result.status_code == 403:
                suggested_fix = "Check access permissions or remove link"
            elif result.status == LinkStatus.TIMEOUT:
                suggested_fix = "Check if target server is responding"

            report.broken_links.append(BrokenLink(
                url=result.url,
                source_url=result.source_url,
                link_text=result.link_text,
                status_code=result.status_code,
                error_message=result.error_message,
                severity=severity,
                suggested_fix=suggested_fix,
            ))

    if config.report_redirects:
        for result in results:
            if result.redirect_count >= config.min_redirect_chain:
                chain = result.redirect_chain + [result.final_url or result.url]
                report.redirect_chains.append(RedirectChain(
                    start_url=result.url,
                    final_url=result.final_url or result.url,
                    chain=chain,
                    chain_length=result.redirect_count,
                    source_url=result.source_url,
                    total_time_ms=result.response_time_ms or 0,
                ))

    domains: Set[str] = set()
    for result in results:
        if result.link_type == LinkType.EXTERNAL:
            try:
                domain = urlparse(result.url).netloc
                if domain:
                    domains.add(domain)
            except Exception:
                pass
    report.unique_domains = sorted(domains)

    for result in results:
        if result.response_time_ms and result.response_time_ms > 1000:
            report.slow_links.append(result.url)

    report.health_score = calculate_health_score(report)

    if report.broken_count > 0:
        report.suggestions.append(f"Fix {report.broken_count} broken link(s)")
    if len(report.redirect_chains) > 0:
        report.suggestions.append(
            f"Update {len(report.redirect_chains)} link(s) to use final URLs"
        )
    if len(report.slow_links) > 5:
        report.suggestions.append(f"{len(report.slow_links)} links are slow to respond")

    return report


def calculate_health_score(report: LinkReport) -> float:
    """Calculate link health score (0-100)."""
    if report.total_links == 0:
        return 100

    score = 100.0

    broken_penalty = min(50, report.broken_count * 10)
    score -= broken_penalty

    timeout_penalty = min(20, report.timeout_count * 5)
    score -= timeout_penalty

    redirect_penalty = min(20, len(report.redirect_chains) * 2)
    score -= redirect_penalty

    error_penalty = min(10, report.error_count * 5)
    score -= error_penalty

    return cast(float, max(0, score))
