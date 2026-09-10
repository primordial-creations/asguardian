"""A browser/check failure must not be serialized as a healthy mobile scan."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from Asgard.Freya.Responsive.services.mobile_compatibility import MobileCompatibilityTester


@pytest.mark.asyncio
async def test_evaluate_failure_keeps_report_incomplete_and_closes_resources():
    page = AsyncMock()
    page.evaluate.side_effect = RuntimeError('synthetic-private-browser-error')
    context = AsyncMock()
    context.new_page.return_value = page
    browser = AsyncMock()
    browser.new_context.return_value = context
    playwright = MagicMock()
    playwright.chromium.launch = AsyncMock(return_value=browser)
    with patch('Asgard.Freya.Responsive.services.mobile_compatibility.async_playwright') as factory:
        factory.return_value.__aenter__ = AsyncMock(return_value=playwright)
        factory.return_value.__aexit__ = AsyncMock()
        with patch('Asgard.Freya.Integration.services._url_safety.safe_goto', new=AsyncMock()):
            report = await MobileCompatibilityTester().test('https://fixture.invalid', devices=['iphone-14'])
    assert not report.is_complete
    assert report.mobile_friendly_score is None
    assert 'synthetic-private-browser-error' not in report.model_dump_json()
    assert report.check_outcomes['iphone-14']['flash'].status == 'failed'
    context.close.assert_awaited_once()
    browser.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('stage', ['new_page', 'navigation', 'serialization'])
async def test_failure_at_each_resource_boundary_closes_context_and_browser(stage):
    import Asgard.Freya.Responsive.services.mobile_compatibility as module
    page, context, browser = AsyncMock(), AsyncMock(), AsyncMock()
    page.evaluate.side_effect = [0, [], [], [], {'resourceCount': 0, 'totalSize': 0}]
    context.new_page.return_value = page
    browser.new_context.return_value = context
    playwright = MagicMock()
    playwright.chromium.launch = AsyncMock(return_value=browser)
    if stage == 'new_page':
        context.new_page.side_effect = RuntimeError('private failure')
    navigation = AsyncMock(side_effect=RuntimeError('private failure') if stage == 'navigation' else None)
    with patch.object(module, 'async_playwright') as factory:
        factory.return_value.__aenter__ = AsyncMock(return_value=playwright)
        factory.return_value.__aexit__ = AsyncMock()
        with patch('Asgard.Freya.Integration.services._url_safety.safe_goto', new=navigation):
            if stage == 'serialization':
                with patch.object(module, 'MobileCompatibilityReport', side_effect=ValueError('fixture serialization')):
                    with pytest.raises(ValueError, match='fixture serialization'):
                        await module.MobileCompatibilityTester().test('https://fixture.invalid', ['iphone-14'])
            else:
                result = await module.MobileCompatibilityTester().test('https://fixture.invalid', ['iphone-14'])
                assert not result.is_complete
                assert result.mobile_friendly_score is None
    context.close.assert_awaited_once()
    browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_mobile_cli_rejects_incomplete_without_findings(monkeypatch, capsys):
    import argparse
    from Asgard.Freya.cli import _handlers_visual_responsive as handlers
    from Asgard.Freya.Responsive.models.responsive_models import MobileCompatibilityReport
    report = MobileCompatibilityReport(url='https://fixture.invalid')
    tester = MagicMock(test=AsyncMock(return_value=report))
    monkeypatch.setattr(handlers, 'MobileCompatibilityTester', lambda: tester)
    args = argparse.Namespace(url=report.url, devices=[], format='text')
    assert await handlers.run_mobile_test(args) == 1
    assert 'INCOMPLETE' in capsys.readouterr().out


@pytest.mark.asyncio
async def test_unified_consumer_does_not_turn_missing_checks_into_mobile_friendly(tmp_path, monkeypatch):
    from Asgard.Freya.Integration.services import _unified_tester_responsive as runner
    from Asgard.Freya.Responsive.models.responsive_models import MobileCompatibilityReport
    report = MobileCompatibilityReport(url='https://fixture.invalid')
    monkeypatch.setattr(runner, 'MobileCompatibilityTester', lambda: MagicMock(test=AsyncMock(return_value=report)))
    for name in ('BreakpointTester', 'TouchTargetValidator', 'ViewportTester'):
        monkeypatch.setattr(runner, name, MagicMock(side_effect=RuntimeError('excluded fixture analyzer')))
    results, _ = await runner.run_responsive_tests(report.url, tmp_path, False)
    mobile = [result for result in results if result.test_name == 'Mobile Compatibility']
    assert len(mobile) == 1
    assert mobile[0].passed is False
    assert mobile[0].details['is_complete'] is False
