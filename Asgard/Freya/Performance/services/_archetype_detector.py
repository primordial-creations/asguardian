"""
Freya Route Archetype Detector

Heuristic classification of a page into Document / Transactional /
Rich-App archetypes (DEEPTHINK_02). An explicit archetype from config
always wins; the heuristic is a fallback and the report always states
which archetype was applied and why.
"""

from typing import Any, Dict, Optional, Tuple

from Asgard.Freya.Performance.models._budget_models import RouteArchetype

#: JS-injected page-signal extraction (used by detect_archetype_from_page).
PAGE_SIGNALS_JS = """
() => {
    const root = document.querySelector('#root, #app, [data-reactroot]');
    let rootTextNodes = 0;
    if (root) {
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
            if (walker.currentNode.textContent.trim()) rootTextNodes += 1;
            if (rootTextNodes >= 10) break;
        }
    }
    const scripts = Array.from(document.querySelectorAll('script[src]'));
    const forms = Array.from(document.querySelectorAll('form'));
    const searchForms = forms.filter(f =>
        (f.getAttribute('role') === 'search') ||
        f.querySelector('input[type=search]') !== null
    );
    const text = document.body ? (document.body.innerText || '') : '';
    return {
        has_spa_root: root !== null,
        spa_root_text_nodes: rootTextNodes,
        html_bytes: document.documentElement.outerHTML.length,
        script_count: scripts.length,
        form_count: forms.length,
        search_form_count: searchForms.length,
        article_count: document.querySelectorAll('article').length,
        heading_count: document.querySelectorAll('h1,h2,h3,h4,h5,h6').length,
        dom_node_count: document.getElementsByTagName('*').length,
        text_bytes: text.length,
        has_history_routing: !!(window.history && window.history.pushState &&
            (window.__NEXT_DATA__ || window.__NUXT__ || root !== null)),
    };
}
"""


def detect_archetype(
    signals: Dict[str, Any],
    js_bytes: Optional[float] = None,
) -> Tuple[RouteArchetype, str]:
    """
    Classify page signals into an archetype.

    Args:
        signals: dict of page signals (see PAGE_SIGNALS_JS)
        js_bytes: total JavaScript payload bytes, if known

    Returns:
        (archetype, reason) — reason states this is a heuristic and
        can be overridden in the budget config.
    """
    has_spa_root = bool(signals.get("has_spa_root"))
    spa_root_text_nodes = int(signals.get("spa_root_text_nodes", 0) or 0)
    html_bytes = float(signals.get("html_bytes", 0) or 0)
    js_html_ratio = (js_bytes / html_bytes) if (js_bytes and html_bytes) else 0.0
    has_history_routing = bool(signals.get("has_history_routing"))

    spa_markers = 0
    if has_spa_root and spa_root_text_nodes < 5:
        spa_markers += 1
    if js_html_ratio > 4:
        spa_markers += 1
    if has_history_routing:
        spa_markers += 1
    if spa_markers >= 2 or (has_spa_root and spa_root_text_nodes < 5 and has_history_routing):
        return (
            RouteArchetype.RICH_APP,
            "archetype: rich_app (heuristic — SPA markers detected: "
            f"empty app root={has_spa_root and spa_root_text_nodes < 5}, "
            f"js/html ratio>{4}={js_html_ratio > 4}, "
            f"history routing={has_history_routing}; override in budget config)",
        )

    dom_nodes = int(signals.get("dom_node_count", 0) or 0)
    text_bytes = float(signals.get("text_bytes", 0) or 0)
    text_density = (text_bytes / dom_nodes) if dom_nodes else 0.0
    form_count = int(signals.get("form_count", 0) or 0)
    search_forms = int(signals.get("search_form_count", 0) or 0)
    non_search_forms = max(0, form_count - search_forms)
    article_count = int(signals.get("article_count", 0) or 0)
    heading_count = int(signals.get("heading_count", 0) or 0)

    if non_search_forms == 0 and (text_density >= 10 or article_count > 0 or heading_count >= 3):
        return (
            RouteArchetype.DOCUMENT,
            "archetype: document (heuristic — text-dominant page, "
            f"text density={text_density:.1f} bytes/node, "
            f"articles={article_count}, headings={heading_count}, "
            "no non-search forms; override in budget config)",
        )

    return (
        RouteArchetype.TRANSACTIONAL,
        "archetype: transactional (heuristic — default; neither SPA markers "
        "nor document-dominance detected; override in budget config)",
    )


async def detect_archetype_from_page(
    page: Any,
    js_bytes: Optional[float] = None,
) -> Tuple[RouteArchetype, str]:
    """Extract signals from a live Playwright page and classify them."""
    try:
        signals = await page.evaluate(PAGE_SIGNALS_JS)
    except Exception:
        return (
            RouteArchetype.TRANSACTIONAL,
            "archetype: transactional (heuristic fallback — page signals "
            "unavailable; override in budget config)",
        )
    return detect_archetype(signals or {}, js_bytes=js_bytes)
