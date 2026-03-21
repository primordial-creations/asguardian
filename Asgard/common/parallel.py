"""
Parallel Processing Infrastructure

Provides multiprocessing support for any task that can be parallelized.
Used by Heimdall for file analysis, Freya for URL testing, etc.
"""

import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Generic, List, Optional, TypeVar

from Asgard.common._parallel_types import (
    ChunkedResult,
    ParallelConfig,
    _process_item_wrapper,
    chunk_items,
)

T = TypeVar('T')  # Input type
R = TypeVar('R')  # Result type


class ParallelRunner(Generic[T, R]):
    """
    Generic parallel runner that distributes work across processes or threads.

    Usage:
        def process_item(item: Path, config: dict) -> Result:
            # Process a single item
            return result

        runner = ParallelRunner(process_item, config)
        results = runner.run(items)
    """

    def __init__(
        self,
        processor_func: Callable[[T, Dict], R],
        config: ParallelConfig,
        item_id_func: Optional[Callable[[T], str]] = None,
    ):
        """
        Initialize the parallel runner.

        Args:
            processor_func: Function to process a single item
            config: Parallel configuration
            item_id_func: Function to get ID from item (default: str)
        """
        self.processor_func = processor_func
        self.config = config
        self.item_id_func = item_id_func or str

    def run(
        self,
        items: List[T],
        config_dict: Optional[Dict] = None,
    ) -> ChunkedResult[R]:
        """
        Process items in parallel.

        Args:
            items: List of items to process
            config_dict: Configuration dictionary to pass to processor

        Returns:
            ChunkedResult containing all results and any errors
        """
        if not self.config.enabled or len(items) <= self.config.chunk_size:
            return self._run_sequential(items, config_dict or {})

        return self._run_parallel(items, config_dict or {})

    def _run_sequential(
        self,
        items: List[T],
        config_dict: Dict,
    ) -> ChunkedResult[R]:
        """Process items sequentially."""
        results = []
        errors = {}

        for item in items:
            item_id = self.item_id_func(item)
            try:
                result = self.processor_func(item, config_dict)
                if result is not None:
                    results.append(result)
            except Exception as e:
                errors[item_id] = str(e)

        return ChunkedResult(
            results=results,
            errors=errors,
            items_processed=len(items),
        )

    def _run_parallel(
        self,
        items: List[T],
        config_dict: Dict,
    ) -> ChunkedResult[R]:
        """Process items in parallel."""
        results = []
        errors = {}

        # Prepare work items
        work_items = [
            (item, self.processor_func, config_dict, self.item_id_func(item))
            for item in items
        ]

        # Choose executor based on config
        ExecutorClass = ThreadPoolExecutor if self.config.use_threads else ProcessPoolExecutor

        with ExecutorClass(max_workers=self.config.worker_count) as executor:
            futures = {
                executor.submit(_process_item_wrapper, item): item[3]
                for item in work_items
            }

            for future in as_completed(futures):
                item_id = futures[future]
                try:
                    _, result, error = future.result(timeout=self.config.timeout_per_item)
                    if error:
                        errors[item_id] = error
                    elif result is not None:
                        results.append(result)
                except Exception as e:
                    errors[item_id] = str(e)

        return ChunkedResult(
            results=results,
            errors=errors,
            items_processed=len(items),
        )


class ParallelRunnerMixin:
    """
    Mixin class to add parallel processing capabilities to any scanner/analyzer.

    Usage:
        class MyScanner(ParallelRunnerMixin):
            def __init__(self, config):
                self.parallel_config = ParallelConfig(
                    enabled=config.parallel,
                    workers=config.workers,
                )

            def _process_single_item(self, item, config_dict):
                # Return result for single item
                pass

            def analyze(self, items):
                if self.parallel_config.enabled:
                    return self._run_parallel(items, self._process_single_item)
                return self._run_sequential(items)
    """

    parallel_config: ParallelConfig

    def _run_parallel(
        self,
        items: List[T],
        processor_func: Callable[[T, Dict], R],
        config_dict: Optional[Dict] = None,
        item_id_func: Optional[Callable[[T], str]] = None,
    ) -> ChunkedResult[R]:
        """
        Run processing in parallel.

        Args:
            items: Items to process
            processor_func: Function to process each item
            config_dict: Configuration to pass to processor
            item_id_func: Function to get ID from item

        Returns:
            ChunkedResult with all results
        """
        runner = ParallelRunner(
            processor_func,
            self.parallel_config,
            item_id_func,
        )
        return runner.run(items, config_dict)


def get_optimal_worker_count(item_count: int, max_workers: Optional[int] = None) -> int:
    """
    Calculate the optimal number of workers based on item count and CPU cores.

    Args:
        item_count: Number of items to process
        max_workers: Maximum workers allowed (None = no limit)

    Returns:
        Optimal worker count
    """
    cpu_count = os.cpu_count() or 1
    optimal = min(item_count, cpu_count - 1)
    optimal = max(1, optimal)

    if max_workers is not None:
        optimal = min(optimal, max_workers)

    return optimal


def should_use_parallel(item_count: int, threshold: int = 20) -> bool:
    """
    Determine if parallel processing would be beneficial.

    Args:
        item_count: Number of items to process
        threshold: Minimum items to benefit from parallelization

    Returns:
        True if parallel processing is recommended
    """
    if item_count < threshold:
        return False

    cpu_count = os.cpu_count()
    if cpu_count is None or cpu_count < 2:
        return False

    return True
