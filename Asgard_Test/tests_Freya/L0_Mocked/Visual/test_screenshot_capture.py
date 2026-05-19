"""
Freya Visual L0 Mocked Tests - Screenshot Capture

Comprehensive tests for screenshot capture service with mocked Playwright.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from Asgard.Freya.Visual.models.visual_models import ScreenshotConfig, COMMON_DEVICES, DeviceConfig
from Asgard.Freya.Visual.services.screenshot_capture import ScreenshotCapture


# =============================================================================
# Test ScreenshotCapture Initialization
# =============================================================================

class TestScreenshotCaptureInit:
    """Tests for ScreenshotCapture initialization."""

    @pytest.mark.L0
    def test_init_default_directory(self):
        """Test initialization with default output directory."""
        capture = ScreenshotCapture()

        assert capture.output_directory == Path("./screenshots")

    @pytest.mark.L0
    def test_init_custom_directory(self, temp_output_dir):
        """Test initialization with custom output directory."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))

        assert capture.output_directory == temp_output_dir

    @pytest.mark.L0
    def test_init_creates_directory(self, tmp_path):
        """Test initialization creates output directory if it doesn't exist."""
        output_dir = tmp_path / "new_screenshots"
        assert not output_dir.exists()

        capture = ScreenshotCapture(output_directory=str(output_dir))

        assert output_dir.exists()
        assert output_dir.is_dir()


# =============================================================================
# Test capture_full_page
# =============================================================================

class TestCaptureFullPage:
    """Tests for capture_full_page method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_full_page_basic(self, temp_output_dir, mock_async_playwright):
        """Test basic full page screenshot capture."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            result = await capture.capture_full_page(
                url="https://example.com",
                filename="test.png",
            )

        assert result.url == "https://example.com"
        assert "test.png" in result.file_path
        assert result.width == 1920
        assert result.height == 1080
        assert result.file_size_bytes == 12345
        assert result.metadata["full_page"] is True

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_full_page_auto_filename(self, temp_output_dir, mock_async_playwright):
        """Test full page capture with auto-generated filename."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            result = await capture.capture_full_page(
                url="https://example.com/page",
            )

        assert result.url == "https://example.com/page"
        assert "example.com_page" in result.file_path
        assert result.file_path.endswith(".png")

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_full_page_with_config(self, temp_output_dir, mock_async_playwright):
        """Test full page capture with custom config."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))
        config = ScreenshotConfig(
            full_page=False,  # Will be overridden
            wait_for_timeout=2000,
            format="jpeg",
        )

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            result = await capture.capture_full_page(
                url="https://example.com",
                filename="test.jpeg",
                config=config,
            )

        assert result.metadata["full_page"] is True
        assert result.metadata["format"] == "jpeg"

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_full_page_calls_playwright_correctly(self, temp_output_dir, mock_async_playwright, mock_page):
        """Test that capture_full_page calls Playwright methods correctly."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))

        # Configure mock page to return full page dimensions
        mock_page.evaluate.return_value = {"width": 1920, "height": 3000}

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            result = await capture.capture_full_page(
                url="https://example.com",
                filename="test.png",
            )

        # Verify Playwright calls
        mock_page.goto.assert_called_once()
        assert mock_page.goto.call_args[0][0] == "https://example.com"
        mock_page.screenshot.assert_called_once()
        assert result.width == 1920
        assert result.height == 3000


# =============================================================================
# Test capture_viewport
# =============================================================================

class TestCaptureViewport:
    """Tests for capture_viewport method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_viewport_basic(self, temp_output_dir, mock_async_playwright):
        """Test basic viewport screenshot capture."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            result = await capture.capture_viewport(
                url="https://example.com",
                filename="viewport.png",
            )

        assert result.url == "https://example.com"
        assert "viewport.png" in result.file_path
        assert result.metadata["full_page"] is False

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_viewport_overrides_full_page(self, temp_output_dir, mock_async_playwright):
        """Test that capture_viewport overrides full_page in config."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))
        config = ScreenshotConfig(full_page=True)  # Will be overridden

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            result = await capture.capture_viewport(
                url="https://example.com",
                filename="viewport.png",
                config=config,
            )

        assert result.metadata["full_page"] is False


# =============================================================================
# Test capture_element
# =============================================================================

class TestCaptureElement:
    """Tests for capture_element method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_element_basic(self, temp_output_dir, mock_async_playwright):
        """Test basic element screenshot capture."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=5000):

            result = await capture.capture_element(
                url="https://example.com",
                selector="#main-content",
                filename="element.png",
            )

        assert result.url == "https://example.com"
        assert "element.png" in result.file_path
        assert result.metadata["element_selector"] == "#main-content"

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_element_auto_filename(self, temp_output_dir, mock_async_playwright):
        """Test element capture with auto-generated filename."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=5000):

            result = await capture.capture_element(
                url="https://example.com",
                selector=".test-class",
            )

        assert "element_" in result.file_path
        assert ".png" in result.file_path

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_element_calls_wait_for_selector(self, temp_output_dir, mock_async_playwright, mock_page):
        """Test that capture_element waits for selector."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=5000):

            await capture.capture_element(
                url="https://example.com",
                selector="#target",
                filename="element.png",
            )

        mock_page.wait_for_selector.assert_called()
        assert "#target" in str(mock_page.wait_for_selector.call_args)

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_element_raises_on_not_found(self, temp_output_dir, mock_async_playwright, mock_page):
        """Test that capture_element raises error when element not found."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))

        # Configure mock to return None for element
        mock_page.wait_for_selector.return_value = None

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright):
            with pytest.raises(ValueError, match="Element not found"):
                await capture.capture_element(
                    url="https://example.com",
                    selector="#missing",
                    filename="element.png",
                )


# =============================================================================
# Test capture_with_devices
# =============================================================================

class TestCaptureWithDevices:
    """Tests for capture_with_devices method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_with_devices_single(self, temp_output_dir, mock_async_playwright):
        """Test capturing with single device."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            results = await capture.capture_with_devices(
                url="https://example.com",
                devices=["desktop-1080p"],
            )

        assert len(results) == 1
        assert results[0].url == "https://example.com"
        assert "desktop-1080p" in results[0].file_path

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_with_devices_multiple(self, temp_output_dir, mock_async_playwright):
        """Test capturing with multiple devices."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            results = await capture.capture_with_devices(
                url="https://example.com",
                devices=["desktop-1080p", "iphone-14", "ipad"],
            )

        assert len(results) == 3
        device_names = [r.device for r in results]
        assert "desktop-1080p" in device_names
        assert "iphone-14" in device_names
        assert "ipad" in device_names

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_with_devices_invalid_device_skipped(self, temp_output_dir, mock_async_playwright):
        """Test that invalid device names are skipped."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            results = await capture.capture_with_devices(
                url="https://example.com",
                devices=["desktop-1080p", "invalid-device", "iphone-14"],
            )

        assert len(results) == 2

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_with_devices_custom_prefix(self, temp_output_dir, mock_async_playwright):
        """Test capturing with custom filename prefix."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            results = await capture.capture_with_devices(
                url="https://example.com",
                devices=["desktop-1080p"],
                filename_prefix="homepage",
            )

        assert len(results) == 1
        assert "homepage_desktop-1080p" in results[0].file_path


# =============================================================================
# Test _capture Internal Method
# =============================================================================

class TestCaptureInternal:
    """Tests for _capture internal method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_with_device_emulation(self, temp_output_dir, mock_async_playwright, mock_browser):
        """Test capture with device emulation."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))
        config = ScreenshotConfig(device="iphone-14")

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            result = await capture._capture(
                url="https://example.com",
                filename="test.png",
                config=config,
            )

        # Verify browser context was created with device settings
        mock_browser.new_context.assert_called_once()
        context_args = mock_browser.new_context.call_args[1]
        assert "viewport" in context_args
        assert context_args["viewport"]["width"] == 390
        assert context_args["viewport"]["height"] == 844

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_with_custom_device(self, temp_output_dir, mock_async_playwright, mock_browser):
        """Test capture with custom device config."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))
        custom_device = DeviceConfig(
            name="Custom",
            width=800,
            height=600,
            device_scale_factor=1.5,
            is_mobile=True,
            has_touch=True,
            user_agent="Custom UA",
        )
        config = ScreenshotConfig(custom_device=custom_device)

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            result = await capture._capture(
                url="https://example.com",
                filename="test.png",
                config=config,
            )

        # Verify custom device settings were used
        mock_browser.new_context.assert_called_once()
        context_args = mock_browser.new_context.call_args[1]
        assert context_args["viewport"]["width"] == 800
        assert context_args["viewport"]["height"] == 600
        assert context_args["device_scale_factor"] == 1.5
        assert context_args["user_agent"] == "Custom UA"

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_waits_for_selector(self, temp_output_dir, mock_async_playwright, mock_page):
        """Test capture waits for selector when configured."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))
        config = ScreenshotConfig(wait_for_selector="#content")

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            await capture._capture(
                url="https://example.com",
                filename="test.png",
                config=config,
            )

        mock_page.wait_for_selector.assert_called()
        assert "#content" in str(mock_page.wait_for_selector.call_args)

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_hides_selectors(self, temp_output_dir, mock_async_playwright, mock_page):
        """Test capture hides specified selectors."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))
        config = ScreenshotConfig(hide_selectors=[".ad", ".cookie-banner"])

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            await capture._capture(
                url="https://example.com",
                filename="test.png",
                config=config,
            )

        # Should have called evaluate twice (once for each selector)
        assert mock_page.evaluate.call_count >= 2

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_with_clip_region(self, temp_output_dir, mock_async_playwright, mock_page):
        """Test capture with clip region."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))
        config = ScreenshotConfig(clip={"x": 0, "y": 0, "width": 800, "height": 600})

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            await capture._capture(
                url="https://example.com",
                filename="test.png",
                config=config,
            )

        # Verify screenshot was called with clip
        mock_page.screenshot.assert_called_once()
        screenshot_args = mock_page.screenshot.call_args[1]
        assert screenshot_args["clip"] == {"x": 0, "y": 0, "width": 800, "height": 600}

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_jpeg_quality(self, temp_output_dir, mock_async_playwright, mock_page):
        """Test capture with JPEG quality setting."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))
        config = ScreenshotConfig(format="jpeg", quality=85)

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            await capture._capture(
                url="https://example.com",
                filename="test.jpeg",
                config=config,
            )

        # Verify screenshot was called with quality
        mock_page.screenshot.assert_called_once()
        screenshot_args = mock_page.screenshot.call_args[1]
        assert screenshot_args["quality"] == 85
        assert screenshot_args["type"] == "jpeg"


# =============================================================================
# Test _url_to_filename Helper
# =============================================================================

class TestUrlToFilename:
    """Tests for _url_to_filename helper method."""

    @pytest.mark.L0
    def test_url_to_filename_basic(self):
        """Test converting basic URL to filename."""
        capture = ScreenshotCapture()

        filename = capture._url_to_filename("https://example.com")

        assert filename == "example.com"
        assert "/" not in filename
        assert ":" not in filename

    @pytest.mark.L0
    def test_url_to_filename_with_path(self):
        """Test converting URL with path to filename."""
        capture = ScreenshotCapture()

        filename = capture._url_to_filename("https://example.com/page/subpage")

        assert filename == "example.com_page_subpage"

    @pytest.mark.L0
    def test_url_to_filename_with_query(self):
        """Test converting URL with query parameters to filename."""
        capture = ScreenshotCapture()

        filename = capture._url_to_filename("https://example.com/page?id=123&name=test")

        assert "?" not in filename
        assert "&" not in filename
        assert "=" not in filename
        assert "_" in filename

    @pytest.mark.L0
    def test_url_to_filename_truncation(self):
        """Test that long URLs are truncated."""
        capture = ScreenshotCapture()

        long_url = "https://example.com/" + "a" * 100

        filename = capture._url_to_filename(long_url)

        assert len(filename) <= 50

    @pytest.mark.L0
    def test_url_to_filename_http(self):
        """Test converting HTTP URL to filename."""
        capture = ScreenshotCapture()

        filename = capture._url_to_filename("http://example.com")

        assert filename == "example.com"


# =============================================================================
# Test Error Handling
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in ScreenshotCapture."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_browser_closes_on_success(self, temp_output_dir, mock_async_playwright, mock_browser):
        """Test that browser is closed after successful capture."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright), \
             patch("os.path.getsize", return_value=12345):

            await capture.capture_full_page(
                url="https://example.com",
                filename="test.png",
            )

        mock_browser.close.assert_called_once()

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_capture_browser_closes_on_error(self, temp_output_dir, mock_async_playwright, mock_browser, mock_page):
        """Test that browser is closed even when error occurs."""
        capture = ScreenshotCapture(output_directory=str(temp_output_dir))

        # Make screenshot raise an error
        mock_page.screenshot.side_effect = Exception("Screenshot failed")

        with patch("Asgard.Freya.Visual.services._screenshot_capture_helpers.async_playwright", mock_async_playwright):
            with pytest.raises(Exception, match="Screenshot failed"):
                await capture.capture_full_page(
                    url="https://example.com",
                    filename="test.png",
                )

        # Browser should still be closed
        mock_browser.close.assert_called_once()
