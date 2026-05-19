"""conftest.py — mock optional heavy dependencies before any Freya import."""
import sys
from unittest.mock import MagicMock

for mod in ("playwright", "playwright.async_api", "playwright.sync_api", "httpx"):
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()
