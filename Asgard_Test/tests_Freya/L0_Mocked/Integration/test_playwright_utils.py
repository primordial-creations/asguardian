"""
Freya Playwright Utils Tests

Comprehensive L0 unit tests for PlaywrightUtils service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from Asgard.Freya.Integration.models.integration_models import BrowserConfig, DeviceConfig
from Asgard.Freya.Integration.services.playwright_utils import (
    PlaywrightUtils,
    DEVICE_PRESETS,
    NETWORK_PRESETS,
)


@pytest.fixture
def mock_browser_config():
    """Create a mock BrowserConfig."""
    return BrowserConfig(
        browser_type="chromium",
        headless=True,
        slow_mo=0,
        timeout=30000,
        viewport_width=1920,
        viewport_height=1080
    )


@pytest.fixture
def mock_playwright():
    """Create a mock playwright instance."""
    playwright = AsyncMock()
    playwright.chromium = AsyncMock()
    playwright.firefox = AsyncMock()
    playwright.webkit = AsyncMock()
    playwright.stop = AsyncMock()
    return playwright


@pytest.fixture
def mock_browser():
    """Create a mock browser instance."""
    browser = AsyncMock()
    browser.close = AsyncMock()
    browser.new_context = AsyncMock()
    return browser


@pytest.fixture
def mock_context():
    """Create a mock browser context."""
    context = AsyncMock()
    context.new_page = AsyncMock()
    context.new_cdp_session = AsyncMock()
    return context


@pytest.fixture
def mock_page():
    """Create a mock page instance."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.screenshot = AsyncMock()
    page.evaluate = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.set_default_timeout = Mock()
    page.set_viewport_size = AsyncMock()
    page.emulate_media = AsyncMock()
    page.locator = Mock(return_value=AsyncMock())
    page.accessibility = AsyncMock()
    page.accessibility.snapshot = AsyncMock()
    return page


class TestPlaywrightUtilsInit:
    """Tests for PlaywrightUtils initialization."""

    def test_init_without_config(self):
        """Test PlaywrightUtils initialization without config."""
        utils = PlaywrightUtils()
        assert isinstance(utils.config, BrowserConfig)
        assert utils.config.browser_type == "chromium"
        assert utils._playwright is None
        assert utils._browser is None

    def test_init_with_config(self, mock_browser_config):
        """Test PlaywrightUtils initialization with config."""
        utils = PlaywrightUtils(config=mock_browser_config)
        assert utils.config == mock_browser_config
        assert utils.config.browser_type == "chromium"


class TestPlaywrightUtilsLaunchBrowser:
    """Tests for launch_browser method."""

    @patch('Asgard.Freya.Integration.services.playwright_utils.async_playwright')
    def test_launch_browser_chromium(self, mock_async_pw, mock_playwright, mock_browser):
        """Test launching Chromium browser."""
        mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        utils = PlaywrightUtils()

        import asyncio
        result = asyncio.run(utils.launch_browser())

        assert result == mock_browser
        assert utils._playwright == mock_playwright
        assert utils._browser == mock_browser
        mock_playwright.chromium.launch.assert_called_once_with(
            headless=True,
            slow_mo=0
        )

    @patch('Asgard.Freya.Integration.services.playwright_utils.async_playwright')
    def test_launch_browser_firefox(self, mock_async_pw, mock_playwright, mock_browser):
        """Test launching Firefox browser."""
        mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright)
        mock_playwright.firefox.launch = AsyncMock(return_value=mock_browser)

        config = BrowserConfig(browser_type="firefox")
        utils = PlaywrightUtils(config=config)

        import asyncio
        result = asyncio.run(utils.launch_browser())

        mock_playwright.firefox.launch.assert_called_once()

    @patch('Asgard.Freya.Integration.services.playwright_utils.async_playwright')
    def test_launch_browser_webkit(self, mock_async_pw, mock_playwright, mock_browser):
        """Test launching WebKit browser."""
        mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright)
        mock_playwright.webkit.launch = AsyncMock(return_value=mock_browser)

        config = BrowserConfig(browser_type="webkit")
        utils = PlaywrightUtils(config=config)

        import asyncio
        result = asyncio.run(utils.launch_browser())

        mock_playwright.webkit.launch.assert_called_once()

    @patch('Asgard.Freya.Integration.services.playwright_utils.async_playwright')
    def test_launch_browser_headless_false(self, mock_async_pw, mock_playwright, mock_browser):
        """Test launching browser with headless=False."""
        mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        config = BrowserConfig(headless=False, slow_mo=100)
        utils = PlaywrightUtils(config=config)

        import asyncio
        result = asyncio.run(utils.launch_browser())

        mock_playwright.chromium.launch.assert_called_once_with(
            headless=False,
            slow_mo=100
        )


class TestPlaywrightUtilsCloseBrowser:
    """Tests for close_browser method."""

    @patch('Asgard.Freya.Integration.services.playwright_utils.async_playwright')
    def test_close_browser(self, mock_async_pw, mock_playwright, mock_browser):
        """Test closing browser."""
        mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        utils = PlaywrightUtils()

        import asyncio
        asyncio.run(utils.launch_browser())
        asyncio.run(utils.close_browser())

        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        assert utils._browser is None
        assert utils._playwright is None

    def test_close_browser_when_not_launched(self):
        """Test closing browser when not launched."""
        utils = PlaywrightUtils()

        import asyncio
        asyncio.run(utils.close_browser())

        assert utils._browser is None
        assert utils._playwright is None


class TestPlaywrightUtilsCreateContext:
    """Tests for create_context method."""

    @patch('Asgard.Freya.Integration.services.playwright_utils.async_playwright')
    def test_create_context_default(
        self, mock_async_pw, mock_playwright, mock_browser, mock_context
    ):
        """Test creating context with default settings."""
        mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        utils = PlaywrightUtils()

        import asyncio
        result = asyncio.run(utils.create_context())

        assert result == mock_context
        mock_browser.new_context.assert_called_once()
        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["viewport"]["width"] == 1920
        assert call_kwargs["viewport"]["height"] == 1080

    @patch('Asgard.Freya.Integration.services.playwright_utils.async_playwright')
    def test_create_context_with_device(
        self, mock_async_pw, mock_playwright, mock_browser, mock_context
    ):
        """Test creating context with device preset."""
        mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        utils = PlaywrightUtils()

        import asyncio
        result = asyncio.run(utils.create_context(device="iphone-14"))

        mock_browser.new_context.assert_called_once()
        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["viewport"]["width"] == 390
        assert call_kwargs["is_mobile"] is True
        assert call_kwargs["has_touch"] is True

    @patch('Asgard.Freya.Integration.services.playwright_utils.async_playwright')
    def test_create_context_with_video_recording(
        self, mock_async_pw, mock_playwright, mock_browser, mock_context
    ):
        """Test creating context with video recording."""
        mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        utils = PlaywrightUtils()

        import asyncio
        result = asyncio.run(utils.create_context(
            record_video=True,
            video_dir="/tmp/videos"
        ))

        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["record_video_dir"] == "/tmp/videos"

    @patch('Asgard.Freya.Integration.services.playwright_utils.async_playwright')
    def test_create_context_launches_browser_if_needed(
        self, mock_async_pw, mock_playwright, mock_browser, mock_context
    ):
        """Test creating context launches browser if not already launched."""
        mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        utils = PlaywrightUtils()
        assert utils._browser is None

        import asyncio
        result = asyncio.run(utils.create_context())

        assert utils._browser is not None

    @patch('Asgard.Freya.Integration.services.playwright_utils.async_playwright')
    def test_create_context_with_network_conditions(
        self, mock_async_pw, mock_playwright, mock_browser, mock_context
    ):
        """Test creating context with network throttling."""
        mock_cdp_session = AsyncMock()
        mock_context.new_page = AsyncMock()
        mock_context.new_cdp_session = AsyncMock(return_value=mock_cdp_session)

        mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        utils = PlaywrightUtils()

        import asyncio
        result = asyncio.run(utils.create_context(network="slow-3g"))

        mock_cdp_session.send.assert_called_once()
        call_args = mock_cdp_session.send.call_args
        assert call_args[0][0] == "Network.emulateNetworkConditions"


class TestPlaywrightUtilsCreatePage:
    """Tests for create_page method."""

    @patch('Asgard.Freya.Integration.services.playwright_utils.async_playwright')
    def test_create_page_with_context(
        self, mock_async_pw, mock_playwright, mock_browser, mock_context, mock_page
    ):
        """Test creating page with existing context."""
        mock_context.new_page = AsyncMock(return_value=mock_page)

        utils = PlaywrightUtils()

        import asyncio
        result = asyncio.run(utils.create_page(context=mock_context))

        assert result == mock_page
        mock_context.new_page.assert_called_once()
        mock_page.set_default_timeout.assert_called_once_with(30000)

    @patch('Asgard.Freya.Integration.services.playwright_utils.async_playwright')
    def test_create_page_without_context(
        self, mock_async_pw, mock_playwright, mock_browser, mock_context, mock_page
    ):
        """Test creating page without existing context."""
        mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        utils = PlaywrightUtils()

        import asyncio
        result = asyncio.run(utils.create_page())

        assert result == mock_page
        mock_browser.new_context.assert_called_once()


class TestPlaywrightUtilsNavigate:
    """Tests for navigate method."""

    def test_navigate_default_wait(self, mock_page):
        """Test navigating to URL with default wait."""
        utils = PlaywrightUtils()

        import asyncio
        asyncio.run(utils.navigate(mock_page, "https://example.com"))

        mock_page.goto.assert_called_once_with(
            "https://example.com",
            wait_until="networkidle",
            timeout=30000
        )

    def test_navigate_custom_wait(self, mock_page):
        """Test navigating to URL with custom wait condition."""
        utils = PlaywrightUtils()

        import asyncio
        asyncio.run(utils.navigate(
            mock_page,
            "https://example.com",
            wait_until="domcontentloaded"
        ))

        call_kwargs = mock_page.goto.call_args[1]
        assert call_kwargs["wait_until"] == "domcontentloaded"


class TestPlaywrightUtilsWaitForNetworkIdle:
    """Tests for wait_for_network_idle method."""

    def test_wait_for_network_idle_default_timeout(self, mock_page):
        """Test waiting for network idle with default timeout."""
        utils = PlaywrightUtils()

        import asyncio
        asyncio.run(utils.wait_for_network_idle(mock_page))

        mock_page.wait_for_load_state.assert_called_once_with(
            "networkidle",
            timeout=30000
        )

    def test_wait_for_network_idle_custom_timeout(self, mock_page):
        """Test waiting for network idle with custom timeout."""
        utils = PlaywrightUtils()

        import asyncio
        asyncio.run(utils.wait_for_network_idle(mock_page, timeout=60000))

        mock_page.wait_for_load_state.assert_called_once_with(
            "networkidle",
            timeout=60000
        )


class TestPlaywrightUtilsTakeScreenshot:
    """Tests for take_screenshot method."""

    def test_take_screenshot_full_page(self, mock_page):
        """Test taking full page screenshot."""
        utils = PlaywrightUtils()

        import asyncio
        result = asyncio.run(utils.take_screenshot(
            mock_page,
            "/tmp/screenshot.png",
            full_page=True
        ))

        assert result == "/tmp/screenshot.png"
        mock_page.screenshot.assert_called_once_with(
            path="/tmp/screenshot.png",
            full_page=True
        )

    def test_take_screenshot_viewport_only(self, mock_page):
        """Test taking viewport screenshot."""
        utils = PlaywrightUtils()

        import asyncio
        result = asyncio.run(utils.take_screenshot(
            mock_page,
            "/tmp/screenshot.png",
            full_page=False
        ))

        call_kwargs = mock_page.screenshot.call_args[1]
        assert call_kwargs["full_page"] is False

    def test_take_screenshot_element(self, mock_page):
        """Test taking element screenshot."""
        mock_locator = AsyncMock()
        mock_page.locator.return_value = mock_locator

        utils = PlaywrightUtils()

        import asyncio
        result = asyncio.run(utils.take_screenshot(
            mock_page,
            "/tmp/screenshot.png",
            element=".header"
        ))

        mock_page.locator.assert_called_once_with(".header")
        mock_locator.screenshot.assert_called_once_with(path="/tmp/screenshot.png")


class TestPlaywrightUtilsEvaluate:
    """Tests for evaluate method."""

    def test_evaluate_javascript(self, mock_page):
        """Test evaluating JavaScript on page."""
        mock_page.evaluate = AsyncMock(return_value={"result": "value"})

        utils = PlaywrightUtils()

        import asyncio
        result = asyncio.run(utils.evaluate(
            mock_page,
            "() => { return {result: 'value'}; }"
        ))

        assert result == {"result": "value"}
        mock_page.evaluate.assert_called_once()


class TestPlaywrightUtilsGetPageMetrics:
    """Tests for get_page_metrics method."""

    def test_get_page_metrics(self, mock_page):
        """Test getting page performance metrics."""
        mock_metrics = {
            "loadTime": 1234,
            "domContentLoaded": 567,
            "firstPaint": 100,
            "firstContentfulPaint": 150,
            "resourceCount": 25,
            "transferSize": 500000
        }
        mock_page.evaluate = AsyncMock(return_value=mock_metrics)

        utils = PlaywrightUtils()

        import asyncio
        result = asyncio.run(utils.get_page_metrics(mock_page))

        assert result["loadTime"] == 1234
        assert result["resourceCount"] == 25
        mock_page.evaluate.assert_called_once()


class TestPlaywrightUtilsGetAccessibilityTree:
    """Tests for get_accessibility_tree method."""

    def test_get_accessibility_tree(self, mock_page):
        """Test getting accessibility tree snapshot."""
        mock_tree = {"role": "WebArea", "children": []}
        mock_page.accessibility.snapshot = AsyncMock(return_value=mock_tree)

        utils = PlaywrightUtils()

        import asyncio
        result = asyncio.run(utils.get_accessibility_tree(mock_page))

        assert result == mock_tree
        mock_page.accessibility.snapshot.assert_called_once()


class TestPlaywrightUtilsEmulateMedia:
    """Tests for emulate_media method."""

    def test_emulate_media_color_scheme(self, mock_page):
        """Test emulating color scheme."""
        utils = PlaywrightUtils()

        import asyncio
        asyncio.run(utils.emulate_media(mock_page, color_scheme="dark"))

        mock_page.emulate_media.assert_called_once()
        call_kwargs = mock_page.emulate_media.call_args[1]
        assert call_kwargs["color_scheme"] == "dark"

    def test_emulate_media_reduced_motion(self, mock_page):
        """Test emulating reduced motion."""
        utils = PlaywrightUtils()

        import asyncio
        asyncio.run(utils.emulate_media(mock_page, reduced_motion="reduce"))

        mock_page.emulate_media.assert_called_once()
        call_kwargs = mock_page.emulate_media.call_args[1]
        assert call_kwargs["reduced_motion"] == "reduce"

    def test_emulate_media_multiple_features(self, mock_page):
        """Test emulating multiple media features."""
        utils = PlaywrightUtils()

        import asyncio
        asyncio.run(utils.emulate_media(
            mock_page,
            color_scheme="light",
            reduced_motion="no-preference"
        ))

        mock_page.emulate_media.assert_called_once()


class TestPlaywrightUtilsSetViewport:
    """Tests for set_viewport method."""

    def test_set_viewport(self, mock_page):
        """Test setting viewport size."""
        utils = PlaywrightUtils()

        import asyncio
        asyncio.run(utils.set_viewport(mock_page, 1280, 720))

        mock_page.set_viewport_size.assert_called_once_with({
            "width": 1280,
            "height": 720
        })


class TestPlaywrightUtilsGetDevicePresets:
    """Tests for get_device_presets method."""

    def test_get_device_presets(self):
        """Test getting list of device presets."""
        utils = PlaywrightUtils()
        presets = utils.get_device_presets()

        assert isinstance(presets, list)
        assert "iphone-14" in presets
        assert "ipad" in presets
        assert "pixel-7" in presets


class TestPlaywrightUtilsGetNetworkPresets:
    """Tests for get_network_presets method."""

    def test_get_network_presets(self):
        """Test getting list of network presets."""
        utils = PlaywrightUtils()
        presets = utils.get_network_presets()

        assert isinstance(presets, list)
        assert "slow-3g" in presets
        assert "fast-3g" in presets
        assert "4g" in presets


class TestPlaywrightUtilsGetDeviceConfig:
    """Tests for get_device_config method."""

    def test_get_device_config_exists(self):
        """Test getting existing device config."""
        utils = PlaywrightUtils()
        config = utils.get_device_config("iphone-14")

        assert isinstance(config, DeviceConfig)
        assert config.name == "iPhone 14"
        assert config.width == 390
        assert config.height == 844

    def test_get_device_config_not_exists(self):
        """Test getting non-existent device config."""
        utils = PlaywrightUtils()
        config = utils.get_device_config("nonexistent-device")

        assert config is None


class TestDevicePresets:
    """Tests for DEVICE_PRESETS constant."""

    def test_device_presets_structure(self):
        """Test DEVICE_PRESETS has correct structure."""
        assert isinstance(DEVICE_PRESETS, dict)
        assert len(DEVICE_PRESETS) > 0

        for device_name, device_config in DEVICE_PRESETS.items():
            assert isinstance(device_config, DeviceConfig)
            assert device_config.width > 0
            assert device_config.height > 0

    def test_device_presets_iphone_14(self):
        """Test iPhone 14 preset configuration."""
        config = DEVICE_PRESETS["iphone-14"]
        assert config.name == "iPhone 14"
        assert config.width == 390
        assert config.height == 844
        assert config.device_scale_factor == 3.0
        assert config.is_mobile is True
        assert config.has_touch is True

    def test_device_presets_ipad(self):
        """Test iPad preset configuration."""
        config = DEVICE_PRESETS["ipad"]
        assert config.name == "iPad"
        assert config.width == 768
        assert config.height == 1024
        assert config.is_mobile is True


class TestNetworkPresets:
    """Tests for NETWORK_PRESETS constant."""

    def test_network_presets_structure(self):
        """Test NETWORK_PRESETS has correct structure."""
        assert isinstance(NETWORK_PRESETS, dict)
        assert len(NETWORK_PRESETS) > 0

        for network_name, network_config in NETWORK_PRESETS.items():
            assert isinstance(network_config, dict)
            assert "offline" in network_config
            assert "download_throughput" in network_config
            assert "upload_throughput" in network_config
            assert "latency" in network_config

    def test_network_presets_slow_3g(self):
        """Test slow 3G preset configuration."""
        config = NETWORK_PRESETS["slow-3g"]
        assert config["offline"] is False
        assert config["latency"] == 400

    def test_network_presets_offline(self):
        """Test offline preset configuration."""
        config = NETWORK_PRESETS["offline"]
        assert config["offline"] is True
        assert config["download_throughput"] == 0
        assert config["upload_throughput"] == 0
