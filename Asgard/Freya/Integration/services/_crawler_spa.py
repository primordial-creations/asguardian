"""
Freya Site Crawler SPA item discovery.

Single-page application item discovery extracted from site_crawler.py.
"""

import asyncio
from typing import Any, Callable, List, Optional, Set

from playwright.async_api import BrowserContext


ITEM_SELECTORS = [
    '[data-testid*="item"]',
    '[data-testid*="card"]',
    '[data-testid*="note"]',
    '[data-testid*="board"]',
    '[data-testid*="event"]',
    '[data-testid*="task"]',
    '[data-testid*="list-item"]',
    '[data-testid*="row"]',
    '[role="listitem"]',
    '[role="row"]',
    '[role="option"]',
    '.card',
    '.list-item',
    '.item',
    '.note-item',
    '.board-item',
    '.event-item',
    '.task-item',
    '.MuiCard-root',
    '.MuiListItem-root',
    '.MuiTableRow-root',
    'li[class*="item"]',
    'div[class*="card"]',
    'tr[class*="row"]',
    'aside div[style*="cursor: pointer"]',
    'nav div[style*="cursor: pointer"]',
    '[class*="sidebar"] div[style*="cursor: pointer"]',
    'aside [role="button"]',
    'aside button',
    '[role="complementary"] div[style*="cursor"]',
]

MODAL_SELECTORS = [
    '[role="dialog"]',
    '[role="modal"]',
    '.MuiDialog-root',
    '.MuiModal-root',
    '.modal',
    '[class*="modal"]',
    '[class*="dialog"]',
]


async def discover_spa_items(
    context: BrowserContext,
    page_url: str,
    auth_storage: Optional[str],
    report_progress: Callable,
) -> List[str]:
    """
    Discover clickable items in SPAs (notes, boards, calendar events, etc.).
    Clicks on the first item of each type to discover detail pages.

    Returns:
        List of discovered detail page URLs
    """
    discovered_urls: List[Any] = []
    discovered_types: Set[str] = set()

    page = await context.new_page()
    try:
        if auth_storage:
            await page.goto(
                page_url.split('?')[0].split('#')[0],
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await page.evaluate(f"""
                (storage) => {{
                    const data = JSON.parse(storage);
                    for (const [key, value] of Object.entries(data)) {{
                        localStorage.setItem(key, value);
                    }}
                }}
            """, auth_storage)
            await page.reload(wait_until="networkidle", timeout=30000)
        else:
            await page.goto(page_url, wait_until="networkidle", timeout=30000)

        try:
            await page.wait_for_selector('main, [role="main"], .main-content', timeout=5000)
        except Exception:
            pass

        try:
            await page.wait_for_function(
                "() => !document.body.innerText.includes('Loading')",
                timeout=10000
            )
        except Exception:
            pass

        await asyncio.sleep(2)

        page_content = await page.content()
        if 'login' in page.url.lower() or 'sign in' in page_content.lower()[:500]:
            return discovered_urls

        for selector in ITEM_SELECTORS:
            try:
                items = await page.query_selector_all(selector)
                if not items:
                    continue

                item_type = selector.replace('[', '').replace(']', '').replace('*=', '_').replace('"', '')

                if item_type in discovered_types:
                    continue

                for item in items[:3]:
                    try:
                        is_visible = await item.is_visible()
                        if not is_visible:
                            continue

                        url_before = page.url

                        try:
                            async with page.expect_navigation(timeout=5000, wait_until="networkidle"):
                                await item.click(timeout=5000)
                        except Exception:
                            await asyncio.sleep(1)

                        url_after = page.url

                        if url_after != url_before and url_after not in discovered_urls:
                            discovered_urls.append(url_after)
                            discovered_types.add(item_type)
                            report_progress(f"Discovered item page: {url_after}")

                            await page.goto(page_url, wait_until="networkidle", timeout=30000)
                            await asyncio.sleep(1)
                            break
                        else:
                            for modal_sel in MODAL_SELECTORS:
                                modal = await page.query_selector(modal_sel)
                                if modal and await modal.is_visible():
                                    modal_url = f"{page_url}#modal-{item_type}"
                                    if modal_url not in discovered_urls:
                                        discovered_urls.append(modal_url)
                                        discovered_types.add(item_type)
                                        report_progress(f"Discovered modal: {item_type}")

                                    await page.keyboard.press("Escape")
                                    await asyncio.sleep(0.5)
                                    break

                            if item_type in discovered_types:
                                break

                    except Exception:
                        continue

            except Exception:
                continue

    except Exception as e:
        report_progress(f"Item discovery error on {page_url}: {e}")
    finally:
        await page.close()

    return discovered_urls
