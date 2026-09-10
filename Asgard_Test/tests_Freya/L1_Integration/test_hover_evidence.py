"""Real Chromium observations on local HTML; no remote site or live interaction."""

import pytest

from Asgard.Freya.Responsive.services._mobile_compatibility_checks import check_hover_dependencies


@pytest.fixture
async def browser():
    # Keep the browser transport in the same event loop as page interactions.
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        instance = await playwright.chromium.launch(headless=True)
        try:
            yield instance
        finally:
            await instance.close()


@pytest.mark.asyncio
async def test_hidden_click_menu_is_not_hover_evidence(page):
    await page.set_content(
        '<button onclick="document.querySelector(\'#menu\').hidden=false">Open</button><div id="menu" class="dropdown" hidden>Links</div>'
    )
    assert await check_hover_dependencies(page) == []


@pytest.mark.asyncio
async def test_hover_reveal_requires_real_visibility_change(page):
    from Asgard.Freya.Responsive.services._hover_evidence import assess_hover_dependencies

    await page.set_content(
        '<style>#menu{display:none}#trigger:hover #menu{display:block}</style><div id="trigger">Open<div id="menu">Links</div></div>'
    )
    result = await assess_hover_dependencies(page)
    assert not result.limitations
    assert len(result.issues) == 1
    assert result.issues[0].element_selector == "#menu"
    assert "Hovering #trigger revealed" in result.issues[0].description


@pytest.mark.asyncio
async def test_focus_reveal_is_an_observed_alternative(page):
    from Asgard.Freya.Responsive.services._hover_evidence import assess_hover_dependencies

    await page.set_content(
        '<style>#menu{display:none}#trigger:hover #menu,#trigger:focus #menu{display:block}</style><div id="trigger" tabindex="0">Open<div id="menu">Links</div></div>'
    )
    result = await assess_hover_dependencies(page)
    assert not result.issues
    assert not result.limitations


@pytest.mark.asyncio
async def test_touch_control_is_not_activated_or_called_a_defect(page):
    from Asgard.Freya.Responsive.services._hover_evidence import assess_hover_dependencies

    await page.set_content(
        '<style>#menu{display:none}#trigger:hover #menu{display:block}</style><div id="trigger" ontouchend="window.activated=true">Open<div id="menu">Links</div></div>'
    )
    result = await assess_hover_dependencies(page)
    assert not result.issues
    assert "declared_click_or_touch_alternative_unverified" in result.limitations
    assert await page.evaluate("window.activated === undefined")


@pytest.mark.asyncio
async def test_cascade_that_prevents_reveal_is_not_evidence(page):
    from Asgard.Freya.Responsive.services._hover_evidence import assess_hover_dependencies

    await page.set_content(
        '<style>#menu{display:none!important}#trigger:hover #menu{display:block}</style><div id="trigger">Open<div id="menu">Links</div></div>'
    )
    assert not (await assess_hover_dependencies(page)).issues


@pytest.mark.asyncio
async def test_cross_origin_stylesheet_is_unknown_coverage(page):
    from Asgard.Freya.Responsive.services._hover_evidence import assess_hover_dependencies

    async def fulfill(route):
        if route.request.url.endswith(".css"):
            await route.fulfill(content_type="text/css", body=".menu{display:none}")
        else:
            await route.fulfill(
                content_type="text/html",
                body='<link rel="stylesheet" href="https://style.fixture.invalid/site.css"><div>Local fixture</div>',
            )

    await page.route("**/*", fulfill)
    await page.goto("https://page.fixture.invalid/")
    result = await assess_hover_dependencies(page)
    assert "unreadable_stylesheet" in result.limitations
    assert not result.issues


@pytest.mark.asyncio
async def test_rule_and_element_limits_are_visible(page):
    from Asgard.Freya.Responsive.services._hover_evidence import assess_hover_dependencies

    await page.set_content(
        "<style>" + "".join(f".item{i}{{color:red}}" for i in range(2100)) + "</style>" + "<div>node</div>" * 2100
    )
    result = await assess_hover_dependencies(page)
    assert "rule_limit" in result.limitations
    assert "element_limit" in result.limitations


@pytest.mark.asyncio
async def test_closed_page_is_an_explicit_check_failure(page):
    from Asgard.Freya.Responsive.services._mobile_compatibility_checks import MobileCheckError

    await page.close()
    with pytest.raises(MobileCheckError, match="Hover observation failed"):
        await check_hover_dependencies(page)


@pytest.mark.asyncio
async def test_candidate_limit_keeps_observations_and_reports_gap(page):
    from Asgard.Freya.Responsive.services._hover_evidence import assess_hover_dependencies

    await page.set_content(
        "<style>.menu{display:none}.trigger:hover .menu{display:block}</style>"
        + "".join(
            f'<div class="trigger" id="t{i}">Open<div class="menu" id="m{i}">Links</div></div>' for i in range(21)
        )
    )
    result = await assess_hover_dependencies(page)
    assert len(result.issues) == 20
    assert "candidate_limit" in result.limitations


@pytest.mark.asyncio
async def test_script_interaction_coverage_stays_unknown(page):
    from Asgard.Freya.Responsive.services._hover_evidence import assess_hover_dependencies

    await page.set_content(
        '<style>#menu{display:none}#trigger:hover #menu{display:block}</style><div id="trigger">Open<div id="menu">Links</div></div><script>window.fixtureLoaded=true</script>'
    )
    result = await assess_hover_dependencies(page)
    assert len(result.issues) == 1
    assert "script_interactions_unassessed" in result.limitations
