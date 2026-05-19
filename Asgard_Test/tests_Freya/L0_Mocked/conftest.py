"""
Freya L0 Mocked Tests - Shared Fixtures

Consolidated pytest fixtures for all L0 mocked tests across Accessibility, Visual, and Responsive modules.
This conftest provides common Playwright mocks and shared utilities.

Submodule-specific fixtures are in their respective conftest.py files.
"""

import sys
from pathlib import Path
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


# =============================================================================
# Playwright Mock Fixtures - Shared across all submodules
# =============================================================================

@pytest.fixture
def mock_page():
    """
    Create a mock Playwright Page object.

    Used by: Accessibility, Visual, Responsive

    Returns:
        AsyncMock: Mocked Playwright page with common methods
    """
    page = AsyncMock()
    page.goto = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[])
    page.query_selector = AsyncMock(return_value=None)
    page.wait_for_selector = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.evaluate = AsyncMock(return_value=None)
    page.screenshot = AsyncMock()
    page.title = AsyncMock(return_value="Test Page")
    page.keyboard = AsyncMock()
    page.keyboard.press = AsyncMock()
    page.viewport_size = {"width": 1920, "height": 1080}
    return page


@pytest.fixture
def mock_element():
    """
    Create a mock Playwright ElementHandle object.

    Used by: Accessibility, Visual, Responsive

    Returns:
        AsyncMock: Mocked Playwright element with common methods
    """
    element = AsyncMock()
    element.get_attribute = AsyncMock(return_value=None)
    element.evaluate = AsyncMock(return_value=None)
    element.inner_text = AsyncMock(return_value="")
    element.bounding_box = AsyncMock(return_value={"x": 0, "y": 0, "width": 100, "height": 50})
    element.focus = AsyncMock()
    element.screenshot = AsyncMock()
    element.query_selector = AsyncMock(return_value=None)
    element.query_selector_all = AsyncMock(return_value=[])
    return element


@pytest.fixture
def mock_browser():
    """
    Create a mock Playwright Browser object.

    Used by: Accessibility, Visual, Responsive

    Returns:
        AsyncMock: Mocked Playwright browser
    """
    browser = AsyncMock()
    browser.new_page = AsyncMock()
    browser.new_context = AsyncMock()
    browser.close = AsyncMock()
    browser.is_connected = MagicMock(return_value=True)
    return browser


@pytest.fixture
def mock_context(mock_page):
    """
    Create a mock Playwright browser context.

    Used by: Visual, Responsive

    Returns:
        AsyncMock: Mocked browser context
    """
    context = AsyncMock()
    context.new_page = AsyncMock(return_value=mock_page)
    context.close = AsyncMock()
    return context


@pytest.fixture
def mock_playwright(mock_browser, mock_context, mock_page):
    """
    Create a mock Playwright async context manager.

    Used by: Accessibility, Visual, Responsive

    Returns:
        Callable: Factory function that returns a mock playwright instance
    """
    async def mock_playwright_context():
        playwright = MagicMock()
        playwright.chromium = AsyncMock()
        playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        return playwright

    return mock_playwright_context


@pytest.fixture
def mock_async_playwright(mock_playwright):
    """
    Mock async_playwright function for use with async context managers.

    Used by: Visual, Responsive

    Returns:
        Callable: Factory function for async playwright context manager
    """
    class AsyncPlaywrightContext:
        def __init__(self, mock_pw):
            self.mock_pw = mock_pw

        async def __aenter__(self):
            return await self.mock_pw()

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    def _async_playwright():
        return AsyncPlaywrightContext(mock_playwright)

    return _async_playwright


# =============================================================================
# PIL/Image Mock Fixtures - Used by Visual module
# =============================================================================

@pytest.fixture
def mock_pil_image():
    """
    Mock PIL Image for visual testing.

    Used by: Visual

    Returns:
        MagicMock: Mocked PIL Image object
    """
    image = MagicMock()
    image.size = (1920, 1080)
    image.width = 1920
    image.height = 1080
    image.convert = MagicMock(return_value=image)
    image.resize = MagicMock(return_value=image)
    image.filter = MagicMock(return_value=image)
    image.save = MagicMock()
    image.copy = MagicMock(return_value=image)
    image.histogram = MagicMock(return_value=[0] * 768)
    return image


@pytest.fixture
def mock_image_module(mock_pil_image):
    """
    Mock PIL Image module.

    Used by: Visual

    Returns:
        MagicMock: Mocked PIL Image module
    """
    image_module = MagicMock()
    image_module.open = MagicMock(return_value=mock_pil_image)
    image_module.Resampling.LANCZOS = 1
    return image_module


@pytest.fixture
def mock_image_chops():
    """
    Mock PIL ImageChops module.

    Used by: Visual

    Returns:
        MagicMock: Mocked PIL ImageChops module
    """
    chops = MagicMock()
    mock_diff = MagicMock()
    mock_diff.convert = MagicMock(return_value=MagicMock())
    chops.difference = MagicMock(return_value=mock_diff)
    return chops


@pytest.fixture
def mock_numpy():
    """
    Mock numpy for image processing.

    Used by: Visual

    Returns:
        MagicMock: Mocked numpy module
    """
    numpy = MagicMock()
    numpy.array = MagicMock(return_value=MagicMock())
    numpy.sum = MagicMock(return_value=100)
    numpy.any = MagicMock(return_value=True)
    numpy.where = MagicMock(return_value=([10, 20, 30], [15, 25, 35]))
    return numpy


# =============================================================================
# File System Fixtures - Shared temporary directories and files
# =============================================================================

@pytest.fixture
def temp_output_dir(tmp_path):
    """
    Temporary output directory for tests.

    Used by: Visual, Integration

    Returns:
        Path: Temporary output directory
    """
    output_dir = tmp_path / "test_output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def temp_screenshot_file(temp_output_dir):
    """
    Temporary screenshot file.

    Used by: Visual

    Returns:
        Path: Temporary screenshot file path
    """
    screenshot_file = temp_output_dir / "test_screenshot.png"
    screenshot_file.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)  # Minimal PNG header
    return screenshot_file


@pytest.fixture
def temp_baseline_dir(temp_output_dir):
    """
    Temporary baseline directory for visual regression tests.

    Used by: Visual, Integration

    Returns:
        Path: Temporary baseline directory
    """
    baseline_dir = temp_output_dir / "baselines"
    baseline_dir.mkdir()
    return baseline_dir


# =============================================================================
# Common Test Data Fixtures
# =============================================================================

@pytest.fixture
def test_url():
    """
    Standard test URL.

    Used by: Accessibility, Visual, Responsive

    Returns:
        str: Test URL
    """
    return "https://test.example.com"


@pytest.fixture
def mock_element_with_text(mock_element):
    """
    Create a mock element with text content.

    Used by: Accessibility

    Returns:
        AsyncMock: Element mock with text content
    """
    mock_element.inner_text = AsyncMock(return_value="Sample Text")
    mock_element.evaluate = AsyncMock(return_value=True)
    return mock_element


@pytest.fixture
def mock_element_styles():
    """
    Standard element styles for testing.

    Used by: Accessibility, Visual

    Returns:
        Dict: CSS style properties
    """
    return {
        "color": "rgb(0, 0, 0)",
        "backgroundColor": "rgb(255, 255, 255)",
        "fontSize": "16px",
        "fontWeight": "400",
        "lineHeight": "1.5",
        "outline": "none",
        "outlineColor": "rgb(0, 0, 0)",
        "outlineWidth": "0px",
        "outlineStyle": "none",
        "boxShadow": "none",
        "border": "none",
    }


@pytest.fixture
def sample_html_content():
    """
    Sample HTML content for testing.

    Used by: Accessibility, Responsive

    Returns:
        str: HTML content
    """
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Test Page</title>
    </head>
    <body>
        <header>
            <h1>Test Page</h1>
            <nav aria-label="Main navigation">
                <ul>
                    <li><a href="/">Home</a></li>
                    <li><a href="/about">About</a></li>
                </ul>
            </nav>
        </header>
        <main>
            <article>
                <h2>Article Title</h2>
                <p>Sample paragraph text.</p>
                <button type="button">Click Me</button>
            </article>
        </main>
        <footer>
            <p>Footer content</p>
        </footer>
    </body>
    </html>
    """
