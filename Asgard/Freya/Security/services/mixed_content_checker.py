"""
Freya Mixed Content Checker (Plan 05, DEEPTHINK_06)

Deterministic observable signal: an https:// page loading http://
subresources. Active mixed content (script/iframe/xhr/...) means MITM
exposure is deterministic; passive (img/media) enables tampering with
displayed content.
"""

import re
from typing import List, Optional
from urllib.parse import urlparse

from Asgard.Freya.Security.models.security_header_models import (
    MixedContentFinding,
    MixedContentReport,
)
from Asgard.Freya.Security.services._mitigation_framing import (
    EXECUTIVE_DISCLAIMER,
    THREAT_CONTEXT,
)

#: Resource types whose interception yields code execution / DOM control.
ACTIVE_TYPES = {
    "script", "iframe", "subframe", "xhr", "fetch", "websocket",
    "stylesheet", "font", "object", "document", "eventsource", "manifest",
}
PASSIVE_TYPES = {"image", "img", "media", "audio", "video", "track"}

_LOCALHOST_NAMES = {"localhost", "127.0.0.1", "::1", "[::1]"}

_DOM_HTTP_ATTR_RE = re.compile(
    r"""(?:src|href|action)\s*=\s*["'](http://[^"']+)["']""",
    re.IGNORECASE,
)


def _is_localhost(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in _LOCALHOST_NAMES


def classify_mixed_request(
    page_url: str,
    request_url: str,
    resource_type: str,
) -> Optional[MixedContentFinding]:
    """
    Classify a network request from an https page.

    Returns None when not mixed content (https, non-http scheme, or
    localhost — local development traffic is excluded).
    """
    if urlparse(page_url).scheme != "https":
        return None
    if urlparse(request_url).scheme != "http":
        return None
    if _is_localhost(request_url):
        return None
    rtype = (resource_type or "other").lower()
    if rtype in PASSIVE_TYPES:
        return MixedContentFinding(
            url=request_url, resource_type=rtype, category="passive",
            severity="moderate",  # -> universal MAJOR
            description=(
                f"Missing Mitigation: passive mixed content — {rtype} "
                f"'{request_url}' loads over plain HTTP from an HTTPS page; "
                "a network attacker can observe or replace the displayed content."
            ),
        )
    return MixedContentFinding(
        url=request_url, resource_type=rtype, category="active",
        severity="serious",  # -> universal CRITICAL (MITM is deterministic)
        description=(
            f"Missing Mitigation: active mixed content — {rtype} "
            f"'{request_url}' loads over plain HTTP from an HTTPS page. "
            "MITM exposure is deterministic: an on-path attacker can "
            "execute code with full page privileges. "
            + THREAT_CONTEXT["Mixed Content"]
        ),
    )


def scan_static_dom(html: str, page_url: str) -> List[MixedContentFinding]:
    """
    Scan static DOM attributes (src/href/action) for http:// references.
    Browsers may auto-upgrade or block these; reported as MISCONFIGURED
    with a note rather than as live mixed content.
    """
    if urlparse(page_url).scheme != "https":
        return []
    findings: List[MixedContentFinding] = []
    seen = set()
    for match in _DOM_HTTP_ATTR_RE.finditer(html or ""):
        url = match.group(1)
        if url in seen or _is_localhost(url):
            continue
        seen.add(url)
        findings.append(MixedContentFinding(
            url=url, resource_type="dom_attribute", category="static_dom",
            severity="moderate",
            description=(
                f"Misconfigured Mitigation: static http:// reference "
                f"'{url}' in the DOM of an HTTPS page. Browsers may "
                "auto-upgrade or block it, but behavior varies — use "
                "https:// (or protocol-relative) references."
            ),
        ))
    return findings


class MixedContentChecker:
    """Playwright-based mixed-content scanner for https pages."""

    async def check(self, url: str) -> MixedContentReport:
        """Load the page, record http:// requests, and scan static DOM."""
        from playwright.async_api import async_playwright

        report = MixedContentReport(url=url, disclaimer=EXECUTIVE_DISCLAIMER)
        report.page_is_https = urlparse(url).scheme == "https"
        if not report.page_is_https:
            return report

        requests: List[MixedContentFinding] = []
        total = 0
        playwright_ctx = await async_playwright().start()
        try:
            browser = await playwright_ctx.chromium.launch(headless=True)
            try:
                page = await browser.new_page()

                def on_request(request) -> None:
                    nonlocal total
                    total += 1
                    finding = classify_mixed_request(
                        url, request.url, request.resource_type
                    )
                    if finding is not None:
                        requests.append(finding)

                page.on("request", on_request)
                await page.goto(url, wait_until="networkidle", timeout=60000)
                html = ""
                try:
                    html = await page.content()
                except Exception:
                    pass
                report.issues = requests + scan_static_dom(html, url)
            finally:
                await browser.close()
        finally:
            await playwright_ctx.stop()

        report.total_requests = total
        report.active_count = sum(1 for i in report.issues if i.category == "active")
        report.passive_count = sum(1 for i in report.issues if i.category == "passive")
        return report
