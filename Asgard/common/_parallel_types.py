"""
Parallel Processing Infrastructure - Types

Configuration dataclass, result dataclass, and utility functions
for the parallel processing system.
"""

import os
from dataclasses import dataclass
from typing import Dict, Generic, Iterator, List, Optional, TypeVar

T = TypeVar('T')
R = TypeVar('R')


@dataclass
class ParallelConfig:
    """Configuration for parallel processing."""
    enabled: bool = False
    workers: Optional[int] = None  # None = CPU count - 1
    chunk_size: int = 10
    timeout_per_item: float = 30.0
    use_threads: bool = False  # Use threads instead of processes (for I/O bound)

    @property
    def worker_count(self) -> int:
        """Get the actual number of workers to use."""
        if self.workers is not None:
            return max(1, self.workers)
        return max(1, (os.cpu_count() or 1) - 1)


@dataclass
class ChunkedResult(Generic[R]):
    """Result from processing a batch of items."""
    results: List[R]
    errors: Dict[str, str]
    items_processed: int
    items_skipped: int = 0

    @property
    def success_count(self) -> int:
        """Number of successfully processed items."""
        return len(self.results)

    @property
    def error_count(self) -> int:
        """Number of items that failed."""
        return len(self.errors)

    @property
    def success_rate(self) -> float:
        """Success rate as a percentage."""
        total = self.items_processed
        if total == 0:
            return 100.0
        return (self.success_count / total) * 100


def chunk_items(items: List[T], chunk_size: int) -> Iterator[List[T]]:
    """
    Split a list of items into chunks for parallel processing.

    Args:
        items: List of items to chunk
        chunk_size: Number of items per chunk

    Yields:
        Chunks of items
    """
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


def _process_item_wrapper(args: tuple) -> tuple:
    """
    Wrapper function for processing a single item in a subprocess.

    Args:
        args: Tuple of (item, processor_func, config_dict)

    Returns:
        Tuple of (item_id, result, error)
    """
    item, processor_func, config_dict, item_id = args
    try:
        result = processor_func(item, config_dict)
        return (item_id, result, None)
    except Exception as e:
        return (item_id, None, str(e))
