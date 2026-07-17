"""
Freya Subresource Integrity Checker (Plan 05, DEEPTHINK_06)

Observable signal: SRI absence on cross-origin scripts/stylesheets is
deterministic and externally verifiable. An SRI pass is still only a
version pin — the hash pins a version, not its safety.
"""

import base64
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from Asgard.Freya.Security.models.security_header_models import (
    SRIFinding,
    SRIReport,
)
from Asgard.Freya.Security.services._mitigation_framing import (
    EXECUTIVE_DISCLAIMER,
    MANUAL_VERIFICATION,
    THREAT_CONTEXT,
)

_INTEGRITY_RE = re.compile(r"^(sha256|sha384|sha512)-([A-Za-z0-9+/=]+)$")

#: JS to enumerate external scripts/stylesheets with SRI attributes.
_ELEMENTS_JS = """
() => {
    const collect = (selector, kind, urlAttr) =>
        Array.from(document.querySelectorAll(selector)).map(el => ({
            element: kind,
            url: el.getAttribute(urlAttr),
            integrity: el.getAttribute('integrity'),
            crossorigin: el.getAttribute('crossorigin'),
        }));
    return collect('script[src]', 'script', 'src').concat(
        collect('link[rel="stylesheet"][href]', 'stylesheet', 'href'));
}
"""


def is_valid_integrity(value: Optional[str]) -> bool:
    """
    Validate an SRI integrity attribute: one or more space-separated
    tokens of the form (sha256|sha384|sha512)-<base64>.
    """
    if not value or not value.strip():
        return False
    for token in value.split():
        match = _INTEGRITY_RE.match(token)
        if not match:
            return False
        try:
            base64.b64decode(match.group(2), validate=True)
        except Exception:
            return False
    return True


def _is_cross_origin(resource_url: str, page_url: str) -> bool:
    """True when the resource URL has a different origin than the page."""
    resource = urlparse(resource_url)
    if not resource.scheme and not resource.netloc:
        return False  # relative URL: same origin
    page = urlparse(page_url)
    return (resource.scheme or page.scheme, resource.netloc) != (page.scheme, page.netloc)


def evaluate_sri_elements(
    elements: List[Dict[str, Any]],
    page_url: str,
) -> Tuple[List[SRIFinding], int, int, int]:
    """
    Pure evaluation of collected script/stylesheet elements.

    Returns (findings, cross_origin_scripts, cross_origin_stylesheets,
    protected_count).
    """
    findings: List[SRIFinding] = []
    scripts = stylesheets = protected = 0
    for element in elements:
        url = element.get("url") or ""
        if not url or not _is_cross_origin(url, page_url):
            continue
        kind = element.get("element", "script")
        if kind == "script":
            scripts += 1
        else:
            stylesheets += 1
        integrity = element.get("integrity")
        crossorigin = element.get("crossorigin")
        # Native severities align with the universal Scoring security map:
        # "moderate" -> MAJOR, "minor" -> MINOR (Plan 05 / Plan 01 table).
        severity = "moderate" if kind == "script" else "minor"

        if not integrity:
            findings.append(SRIFinding(
                element=kind, url=url, severity=severity,
                issue_type="sri_missing",
                description=(
                    f"Missing Mitigation: Subresource Integrity on "
                    f"cross-origin {kind} '{url}' — a third-party CDN "
                    "compromise executes with full page privileges."
                ),
                threat_context=THREAT_CONTEXT["Subresource Integrity"],
            ))
            continue
        if not is_valid_integrity(integrity):
            findings.append(SRIFinding(
                element=kind, url=url, severity=severity,
                issue_type="sri_malformed",
                description=(
                    f"Misconfigured Mitigation: integrity attribute on "
                    f"cross-origin {kind} '{url}' is malformed "
                    f"('{integrity}') — browsers ignore invalid hashes, "
                    "so the pin provides no protection."
                ),
                threat_context=THREAT_CONTEXT["Subresource Integrity"],
            ))
            continue
        if crossorigin is None:
            findings.append(SRIFinding(
                element=kind, url=url, severity="moderate",
                issue_type="sri_missing_crossorigin",
                description=(
                    f"Misconfigured Mitigation: cross-origin {kind} "
                    f"'{url}' has an integrity hash but no crossorigin "
                    "attribute — integrity checking requires CORS mode."
                ),
            ))
            continue
        protected += 1
        findings.append(SRIFinding(
            element=kind, url=url, severity="minor",
            issue_type="sri_present_needs_verification",
            description=(
                f"Subresource Integrity present on '{url}'. "
                "Yes, but: the hash pins a version, not its safety."
            ),
            manual_verification=MANUAL_VERIFICATION["Subresource Integrity"],
        ))
    return findings, scripts, stylesheets, protected


class SRIChecker:
    """Playwright-based Subresource Integrity checker."""

    async def check(self, url: str) -> SRIReport:
        """
        Load a page and evaluate SRI on cross-origin scripts/styles.
        Also flags dynamically injected scripts (which bypass SRI —
        an observable but incomplete signal, and the report says so).
        """
        from playwright.async_api import async_playwright

        report = SRIReport(url=url, disclaimer=EXECUTIVE_DISCLAIMER)
        playwright_ctx = await async_playwright().start()
        try:
            browser = await playwright_ctx.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                response = await page.goto(url, wait_until="networkidle", timeout=60000)
                elements = await page.evaluate(_ELEMENTS_JS)

                # Static HTML vs live DOM: extra script srcs indicate
                # dynamic injection, which SRI cannot cover.
                static_html = ""
                try:
                    if response is not None:
                        static_html = await response.text()
                except Exception:
                    static_html = ""
                dom_script_urls = {
                    e.get("url") for e in elements
                    if e.get("element") == "script" and e.get("url")
                }
                dynamic = [u for u in dom_script_urls if u not in static_html]
                report.dynamic_scripts_detected = bool(dynamic)

                findings, scripts, stylesheets, protected = evaluate_sri_elements(
                    elements or [], url
                )
                report.issues = findings
                report.total_cross_origin_scripts = scripts
                report.total_cross_origin_stylesheets = stylesheets
                report.protected_count = protected
                if report.dynamic_scripts_detected:
                    report.issues.append(SRIFinding(
                        element="script",
                        url=", ".join(sorted(dynamic)[:5]),
                        severity="minor",
                        issue_type="sri_dynamic_injection",
                        description=(
                            "Needs Verification: dynamically injected "
                            "scripts detected — SRI attributes cannot cover "
                            "them. This signal is observable but incomplete: "
                            "manual review of the injection source is required."
                        ),
                    ))
            finally:
                await browser.close()
        finally:
            await playwright_ctx.stop()
        return report
