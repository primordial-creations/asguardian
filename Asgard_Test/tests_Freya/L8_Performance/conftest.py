"""
Freya L8 Performance Test Configuration

Stubs out the playwright module so that Freya submodule services can be
imported without playwright being installed (CSPAnalyzer and other
non-browser services have no runtime dependency on it).
"""

import sys
import types
from unittest.mock import MagicMock

# Inject a minimal playwright stub before any Freya imports happen.
# This allows the Freya package __init__ to load (which re-exports
# Accessibility classes that import playwright) without raising
# ModuleNotFoundError at collection time.
if "playwright" not in sys.modules:
    playwright_stub = types.ModuleType("playwright")
    async_api_stub = types.ModuleType("playwright.async_api")
    for name in ["async_playwright", "Browser", "BrowserContext", "Page",
                 "Playwright", "ElementHandle", "Locator", "Response", "Request",
                 "ViewportSize", "Cookie", "ConsoleMessage", "Error", "Dialog",
                 "FileChooser", "Frame", "JSHandle", "Route", "WebSocket",
                 "Worker", "Download", "Keyboard", "Mouse", "Touchscreen"]:
        setattr(async_api_stub, name, MagicMock)
    playwright_stub.async_api = async_api_stub
    sys.modules["playwright"] = playwright_stub
    sys.modules["playwright.async_api"] = async_api_stub
