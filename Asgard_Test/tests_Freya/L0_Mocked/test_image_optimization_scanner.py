"""
L0 Unit Tests for Freya ImageOptimizationScanner

Tests the externally-observable surface of the scanner:
- Initialization with custom configs
- HTTP client lifecycle
- High-level alt-text / performance entry points

Note: many low-level helpers (_detect_format, _build_image_info,
_check_*, _calculate_score, _generate_suggestions) were refactored
into in-browser JS evaluation inside scan_page(), and are no longer
Python-callable methods on the scanner. Those tests have been removed.
"""

import pytest
import sys
import os
from unittest.mock import AsyncMock, patch

# Add the Freya directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..', 'Asgard', 'Freya'))

try:
    from Images.services.image_optimization_scanner import ImageOptimizationScanner
    from Images.models.image_models import (
        ImageConfig,
        ImageReport,
    )
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False


@pytest.mark.L0
@pytest.mark.freya
@pytest.mark.unit
class TestImageOptimizationScannerInit:
    """Test ImageOptimizationScanner initialization"""

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_scanner_init_with_default_config(self):
        scanner = ImageOptimizationScanner()
        assert scanner.config is not None
        assert scanner.config.__class__.__name__ == "ImageConfig"
        assert scanner.config.check_alt_text is True
        assert scanner._http_client is None

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_scanner_init_with_custom_config(self):
        custom_config = ImageConfig(
            check_alt_text=True,
            check_lazy_loading=False,
            oversized_threshold=2.0,
        )
        scanner = ImageOptimizationScanner(config=custom_config)
        assert scanner.config == custom_config
        assert scanner.config.check_alt_text is True
        assert scanner.config.check_lazy_loading is False
        assert scanner.config.oversized_threshold == 2.0

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_scanner_init_accessibility_only_config(self):
        config = ImageConfig(
            check_alt_text=True,
            check_lazy_loading=False,
            check_formats=False,
            check_dimensions=False,
            check_oversized=False,
            check_srcset=False,
        )
        scanner = ImageOptimizationScanner(config=config)
        assert scanner.config.check_alt_text is True
        assert scanner.config.check_lazy_loading is False
        assert scanner.config.check_formats is False


@pytest.mark.L0
@pytest.mark.freya
@pytest.mark.unit
@pytest.mark.asyncio
class TestImageOptimizationScannerHTTPClient:
    """Test HTTP client management"""

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    async def test_get_client_creates_client_on_first_call(self):
        scanner = ImageOptimizationScanner()
        assert scanner._http_client is None
        client = await scanner._get_client()
        assert client is not None
        assert scanner._http_client is not None

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    async def test_get_client_reuses_existing_client(self):
        scanner = ImageOptimizationScanner()
        client1 = await scanner._get_client()
        client2 = await scanner._get_client()
        assert client1 is client2

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    async def test_close_closes_http_client(self):
        scanner = ImageOptimizationScanner()
        await scanner._get_client()
        assert scanner._http_client is not None
        await scanner.close()
        assert scanner._http_client is None


@pytest.mark.L0
@pytest.mark.freya
@pytest.mark.unit
@pytest.mark.asyncio
class TestScannerHighLevelMethods:
    """Test high-level scanner methods"""

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    async def test_check_alt_text_method_sets_config(self):
        scanner = ImageOptimizationScanner()
        with patch.object(scanner, 'scan', new_callable=AsyncMock) as mock_scan:
            mock_scan.return_value = ImageReport(url="https://example.com")
            await scanner.check_alt_text("https://example.com")
            assert scanner.config.check_alt_text is True

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    async def test_check_performance_method_sets_config(self):
        scanner = ImageOptimizationScanner()
        with patch.object(scanner, 'scan', new_callable=AsyncMock) as mock_scan:
            mock_scan.return_value = ImageReport(url="https://example.com")
            await scanner.check_performance("https://example.com")
            assert scanner.config.check_alt_text is True
