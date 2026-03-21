"""
Freya Site Crawler inline page checks.

Inline accessibility, visual, and responsive checks run during crawling.
Extracted from site_crawler.py to keep file size manageable.
"""

from typing import Any, Dict, List

from playwright.async_api import Page


async def run_accessibility_checks(page: Page) -> List[Dict[str, Any]]:
    """Run accessibility checks on a page."""
    issues = []

    checks = await page.evaluate("""
        () => {
            const issues = [];

            document.querySelectorAll('img').forEach(img => {
                if (!img.alt && !img.getAttribute('role')) {
                    issues.push({
                        type: 'missing-alt',
                        severity: 'serious',
                        element: img.outerHTML.substring(0, 100),
                        message: 'Image missing alt text',
                        wcag: '1.1.1'
                    });
                }
            });

            document.querySelectorAll('input, select, textarea').forEach(input => {
                if (input.type !== 'hidden' && input.type !== 'submit' && input.type !== 'button') {
                    const id = input.id;
                    const label = id ? document.querySelector(`label[for="${id}"]`) : null;
                    const ariaLabel = input.getAttribute('aria-label');
                    const ariaLabelledBy = input.getAttribute('aria-labelledby');
                    if (!label && !ariaLabel && !ariaLabelledBy) {
                        issues.push({
                            type: 'missing-label',
                            severity: 'serious',
                            element: input.outerHTML.substring(0, 100),
                            message: 'Form input missing label',
                            wcag: '1.3.1'
                        });
                    }
                }
            });

            const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
            let lastLevel = 0;
            headings.forEach(h => {
                const level = parseInt(h.tagName[1]);
                if (level > lastLevel + 1 && lastLevel > 0) {
                    issues.push({
                        type: 'heading-skip',
                        severity: 'moderate',
                        element: h.outerHTML.substring(0, 100),
                        message: `Heading level skipped from h${lastLevel} to h${level}`,
                        wcag: '1.3.1'
                    });
                }
                lastLevel = level;
            });

            if (!document.querySelector('main, [role="main"]')) {
                issues.push({
                    type: 'missing-main',
                    severity: 'moderate',
                    element: 'body',
                    message: 'Page missing main landmark',
                    wcag: '1.3.1'
                });
            }

            document.querySelectorAll('a').forEach(a => {
                const text = a.textContent.trim().toLowerCase();
                if (['click here', 'here', 'read more', 'learn more', 'more'].includes(text)) {
                    issues.push({
                        type: 'non-descriptive-link',
                        severity: 'moderate',
                        element: a.outerHTML.substring(0, 100),
                        message: `Link text "${a.textContent.trim()}" is not descriptive`,
                        wcag: '2.4.4'
                    });
                }
            });

            document.querySelectorAll('*').forEach(el => {
                const style = window.getComputedStyle(el);
                if (style.color === style.backgroundColor && el.textContent.trim()) {
                    issues.push({
                        type: 'contrast-issue',
                        severity: 'serious',
                        element: el.outerHTML.substring(0, 100),
                        message: 'Text may have insufficient color contrast',
                        wcag: '1.4.3'
                    });
                }
            });

            return issues;
        }
    """)

    for check in checks:
        issues.append({
            "category": "accessibility",
            "type": check["type"],
            "severity": check["severity"],
            "message": check["message"],
            "element": check.get("element", ""),
            "wcag": check.get("wcag", ""),
        })

    return issues


async def run_visual_checks(page: Page) -> List[Dict[str, Any]]:
    """Run visual checks on a page."""
    issues = []

    checks = await page.evaluate("""
        () => {
            const issues = [];

            document.querySelectorAll('img').forEach(img => {
                if (!img.complete || img.naturalWidth === 0) {
                    issues.push({
                        type: 'broken-image',
                        severity: 'moderate',
                        element: img.src,
                        message: 'Image failed to load'
                    });
                }
            });

            if (document.documentElement.scrollWidth > document.documentElement.clientWidth) {
                issues.push({
                    type: 'horizontal-overflow',
                    severity: 'moderate',
                    element: 'body',
                    message: 'Page has horizontal scroll'
                });
            }

            document.querySelectorAll('*').forEach(el => {
                const style = window.getComputedStyle(el);
                const fontSize = parseFloat(style.fontSize);
                if (fontSize < 12 && el.textContent.trim().length > 0) {
                    issues.push({
                        type: 'small-text',
                        severity: 'minor',
                        element: el.tagName,
                        message: `Text size ${fontSize}px is below recommended minimum`
                    });
                }
            });

            const highZElements = [];
            document.querySelectorAll('*').forEach(el => {
                const style = window.getComputedStyle(el);
                const zIndex = parseInt(style.zIndex);
                if (zIndex > 9999) {
                    highZElements.push({ element: el.tagName, zIndex: zIndex });
                }
            });
            if (highZElements.length > 3) {
                issues.push({
                    type: 'z-index-complexity',
                    severity: 'minor',
                    element: 'multiple',
                    message: 'Multiple elements with very high z-index values'
                });
            }

            return issues;
        }
    """)

    for check in checks:
        issues.append({
            "category": "visual",
            "type": check["type"],
            "severity": check["severity"],
            "message": check["message"],
            "element": check.get("element", ""),
        })

    return issues


async def run_responsive_checks(page: Page) -> List[Dict[str, Any]]:
    """Run responsive design checks on a page."""
    issues = []

    checks = await page.evaluate("""
        () => {
            const issues = [];

            const viewport = document.querySelector('meta[name="viewport"]');
            if (!viewport) {
                issues.push({
                    type: 'missing-viewport',
                    severity: 'serious',
                    element: 'head',
                    message: 'Missing viewport meta tag'
                });
            } else {
                const content = viewport.getAttribute('content') || '';
                if (!content.includes('width=device-width')) {
                    issues.push({
                        type: 'viewport-config',
                        severity: 'moderate',
                        element: 'viewport',
                        message: 'Viewport meta tag missing width=device-width'
                    });
                }
            }

            const minTouchSize = 44;
            document.querySelectorAll('a, button, input[type="submit"], input[type="button"]').forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.width < minTouchSize || rect.height < minTouchSize) {
                    if (rect.width > 0 && rect.height > 0) {
                        issues.push({
                            type: 'small-touch-target',
                            severity: 'moderate',
                            element: el.outerHTML.substring(0, 100),
                            message: `Touch target ${Math.round(rect.width)}x${Math.round(rect.height)}px is below 44x44px minimum`
                        });
                    }
                }
            });

            document.querySelectorAll('*').forEach(el => {
                const style = window.getComputedStyle(el);
                const width = parseInt(style.width);
                if (width > window.innerWidth && style.position !== 'fixed' && style.position !== 'absolute') {
                    issues.push({
                        type: 'fixed-width',
                        severity: 'moderate',
                        element: el.tagName,
                        message: 'Element has fixed width larger than viewport'
                    });
                }
            });

            return issues;
        }
    """)

    for check in checks:
        issues.append({
            "category": "responsive",
            "type": check["type"],
            "severity": check["severity"],
            "message": check["message"],
            "element": check.get("element", ""),
        })

    return issues
