"""
Incremental Processing Infrastructure - Data Models

Data model classes for the incremental processing system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class HashEntry:
    """Cache entry for a single item."""
    item_id: str
    hash: str
    last_modified: Optional[float] = None
    size: Optional[int] = None
    last_processed: str = field(default_factory=lambda: datetime.now().isoformat())
    result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IncrementalConfig:
    """Configuration for incremental processing."""
    enabled: bool = False
    cache_path: str = ".asgard-cache.json"
    store_results: bool = True
    max_cache_age_days: int = 30
    hash_func: str = "sha256"  # sha256, sha1, md5
