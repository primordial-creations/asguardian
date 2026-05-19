"""
Freya Visual L0 Tests - Module-Specific Fixtures

Contains fixtures specific to visual testing.
Shared Playwright mocks and PIL mocks are in the parent L0_Mocked/conftest.py.
"""

import json
import pytest
from unittest.mock import MagicMock


# =============================================================================
# Visual-Specific Model Fixtures
# =============================================================================

@pytest.fixture
def sample_device_config():
    """Sample DeviceConfig for testing."""
    from Asgard.Freya.Visual.models.visual_models import DeviceConfig

    return DeviceConfig(
        name="Test Device",
        width=1920,
        height=1080,
        device_scale_factor=2.0,
        is_mobile=False,
        has_touch=False,
    )


@pytest.fixture
def sample_screenshot_config():
    """Sample ScreenshotConfig for testing."""
    from Asgard.Freya.Visual.models.visual_models import ScreenshotConfig

    return ScreenshotConfig(
        full_page=True,
        device="desktop-1080p",
        wait_for_timeout=1000,
        format="png",
    )


@pytest.fixture
def sample_comparison_config():
    """Sample ComparisonConfig for testing."""
    from Asgard.Freya.Visual.models.visual_models import ComparisonConfig, ComparisonMethod

    return ComparisonConfig(
        threshold=0.95,
        method=ComparisonMethod.STRUCTURAL_SIMILARITY,
        color_tolerance=10,
    )


@pytest.fixture
def sample_regression_test_case():
    """Sample RegressionTestCase for testing."""
    from Asgard.Freya.Visual.models.visual_models import RegressionTestCase

    return RegressionTestCase(
        name="homepage_test",
        url="https://example.com",
        threshold=0.95,
    )


@pytest.fixture
def sample_regression_test_suite(temp_output_dir):
    """Sample RegressionTestSuite for testing."""
    from Asgard.Freya.Visual.models.visual_models import RegressionTestSuite, RegressionTestCase

    baseline_dir = temp_output_dir / "baselines"
    baseline_dir.mkdir(exist_ok=True)
    output_dir = temp_output_dir / "output"
    output_dir.mkdir(exist_ok=True)

    return RegressionTestSuite(
        name="Test Suite",
        baseline_directory=str(baseline_dir),
        output_directory=str(output_dir),
        test_cases=[
            RegressionTestCase(
                name="test1",
                url="https://example.com/page1",
                threshold=0.95,
            ),
            RegressionTestCase(
                name="test2",
                url="https://example.com/page2",
                threshold=0.90,
            ),
        ],
    )


@pytest.fixture
def sample_layout_issue():
    """Sample LayoutIssue for testing."""
    from Asgard.Freya.Visual.models.visual_models import LayoutIssue, LayoutIssueType, ElementBox

    return LayoutIssue(
        issue_type=LayoutIssueType.OVERFLOW,
        element_selector=".test-element",
        description="Element overflows container",
        severity="moderate",
        affected_area=ElementBox(x=10, y=20, width=100, height=50, selector=".test-element"),
        suggested_fix="Add overflow: hidden or adjust width",
    )


@pytest.fixture
def sample_style_issue():
    """Sample StyleIssue for testing."""
    from Asgard.Freya.Visual.models.visual_models import StyleIssue, StyleIssueType

    return StyleIssue(
        issue_type=StyleIssueType.UNKNOWN_COLOR,
        element_selector=".test-element",
        property_name="color",
        actual_value="#ff0000",
        description="Color not in theme",
        severity="minor",
    )


# =============================================================================
# Visual-Specific File Fixtures
# =============================================================================

@pytest.fixture
def temp_theme_file(temp_output_dir):
    """Temporary theme JSON file for style validation testing."""
    theme_file = temp_output_dir / "theme.json"
    theme_data = {
        "colors": {
            "primary": "#007bff",
            "secondary": "#6c757d",
            "success": "#28a745",
            "text": "#212529",
            "background": "#ffffff"
        },
        "fonts": {
            "primary": "Roboto",
            "secondary": "Arial",
            "heading": {"family": "Montserrat"}
        }
    }
    theme_file.write_text(json.dumps(theme_data))
    return theme_file


@pytest.fixture
def temp_baseline_file(temp_output_dir):
    """Temporary baseline image file for regression testing."""
    baseline_file = temp_output_dir / "baseline.png"
    baseline_file.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
    return baseline_file


@pytest.fixture
def temp_comparison_file(temp_output_dir):
    """Temporary comparison image file for regression testing."""
    comparison_file = temp_output_dir / "comparison.png"
    comparison_file.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
    return comparison_file


@pytest.fixture
def mock_page(mock_page):
    """Override mock_page.evaluate to return appropriate values for Visual tests."""
    from unittest.mock import AsyncMock, DEFAULT

    _SENTINEL = object()
    evaluate_mock = AsyncMock()
    evaluate_mock._test_return_value = _SENTINEL  # track explicit test overrides

    _orig_setattr = evaluate_mock.__class__.__setattr__

    async def evaluate_side_effect(expr, *args, **kwargs):
        expr_str = str(expr)
        # Always return an int for the total elements query used in validate()
        if "querySelectorAll('*').length" in expr_str:
            return 42
        # If the test explicitly set return_value (stored in _test_return_value), use it
        if evaluate_mock._test_return_value is not _SENTINEL:
            return evaluate_mock._test_return_value
        # Return dimensions dict when the script is specifically fetching page scroll dimensions
        if "document.documentElement.scrollWidth" in expr_str and "document.documentElement.scrollHeight" in expr_str:
            return {"width": 1920, "height": 1080}
        # Default: return empty list
        return []

    evaluate_mock.side_effect = evaluate_side_effect

    # Intercept return_value assignments so tests can set mock_page.evaluate.return_value
    class _EvaluateMockProxy:
        """Proxy that forwards return_value sets to _test_return_value."""
        def __init__(self, mock):
            object.__setattr__(self, '_mock', mock)

        def __getattr__(self, name):
            return getattr(object.__getattribute__(self, '_mock'), name)

        def __setattr__(self, name, value):
            if name == 'return_value':
                object.__getattribute__(self, '_mock')._test_return_value = value
            elif name == 'side_effect':
                object.__getattribute__(self, '_mock').side_effect = value
            else:
                setattr(object.__getattribute__(self, '_mock'), name, value)

        def __call__(self, *args, **kwargs):
            return object.__getattribute__(self, '_mock')(*args, **kwargs)

    proxy = _EvaluateMockProxy(evaluate_mock)
    mock_page.evaluate = proxy
    return mock_page


@pytest.fixture
def mock_image_draw():
    """Mock PIL ImageDraw module for drawing annotations."""
    draw = MagicMock()
    mock_draw_obj = MagicMock()
    mock_draw_obj.rectangle = MagicMock()
    mock_draw_obj.text = MagicMock()
    draw.Draw = MagicMock(return_value=mock_draw_obj)
    return draw
