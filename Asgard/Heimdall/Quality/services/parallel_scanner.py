"""
Parallel Scanner Infrastructure

Provides multiprocessing support for file analysis to improve performance
on large codebases.
"""

import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Generic, Iterator, List, Optional, TypeVar

# Type variables
T = TypeVar('T')  # Input type
R = TypeVar('R')  # Result type


@dataclass
class ParallelConfig:
    """Configuration for parallel scanning."""
    enabled: bool = False
    workers: Optional[int] = None  # None = CPU count - 1
    chunk_size: int = 10
    timeout_per_file: float = 30.0

    @property
    def worker_count(self) -> int:
        """Get the actual number of workers to use."""
        if self.workers is not None:
            return max(1, self.workers)
        return max(1, (os.cpu_count() or 1) - 1)


@dataclass
class ChunkedResult(Generic[R]):
    """Result from processing a chunk of files."""
    results: List[R]
    errors: Dict[str, str]
    files_processed: int


def chunk_files(files: List[Path], chunk_size: int) -> Iterator[List[Path]]:
    """
    Split a list of files into chunks for parallel processing.

    Args:
        files: List of file paths
        chunk_size: Number of files per chunk

    Yields:
        Chunks of file paths
    """
    for i in range(0, len(files), chunk_size):
        yield files[i:i + chunk_size]


def _process_file_wrapper(args: tuple) -> tuple:
    """
    Wrapper function for processing a single file in a subprocess.

    This is a module-level function required for multiprocessing.

    Args:
        args: Tuple of (file_path, analyzer_func, config_dict)

    Returns:
        Tuple of (file_path, result, error)
    """
    file_path, analyzer_func, config_dict = args
    try:
        result = analyzer_func(file_path, config_dict)
        return (str(file_path), result, None)
    except Exception as e:
        return (str(file_path), None, str(e))


class ParallelScanner(Generic[T, R]):
    """
    Generic parallel scanner that distributes file analysis across processes.

    Usage:
        def analyze_file(file_path: Path, config: dict) -> Result:
            # Analyze a single file
            return result

        scanner = ParallelScanner(analyze_file, config)
        results = scanner.scan(files)
    """

    def __init__(
        self,
        analyze_func: Callable[[Path, Dict], R],
        config: ParallelConfig,
    ):
        """
        Initialize the parallel scanner.

        Args:
            analyze_func: Function to analyze a single file
            config: Parallel configuration
        """
        self.analyze_func = analyze_func
        self.config = config

    def scan(
        self,
        files: List[Path],
        config_dict: Optional[Dict] = None,
    ) -> ChunkedResult[R]:
        """
        Scan files in parallel.

        Args:
            files: List of file paths to analyze
            config_dict: Configuration dictionary to pass to analyzer

        Returns:
            ChunkedResult containing all results and any errors
        """
        if not self.config.enabled or len(files) <= self.config.chunk_size:
            # Fall back to sequential processing for small file sets
            return self._scan_sequential(files, config_dict or {})

        return self._scan_parallel(files, config_dict or {})

    def _scan_sequential(
        self,
        files: List[Path],
        config_dict: Dict,
    ) -> ChunkedResult[R]:
        """Process files sequentially."""
        results = []
        errors = {}

        for file_path in files:
            try:
                result = self.analyze_func(file_path, config_dict)
                if result is not None:
                    results.append(result)
            except Exception as e:
                errors[str(file_path)] = str(e)

        return ChunkedResult(
            results=results,
            errors=errors,
            files_processed=len(files),
        )

    def _scan_parallel(
        self,
        files: List[Path],
        config_dict: Dict,
    ) -> ChunkedResult[R]:
        """Process files in parallel using ProcessPoolExecutor."""
        results = []
        errors = {}

        # Prepare arguments for each file
        work_items = [
            (file_path, self.analyze_func, config_dict)
            for file_path in files
        ]

        with ProcessPoolExecutor(max_workers=self.config.worker_count) as executor:
            # Submit all work
            futures = {
                executor.submit(_process_file_wrapper, item): item[0]
                for item in work_items
            }

            # Collect results as they complete
            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    path, result, error = future.result(timeout=self.config.timeout_per_file)
                    if error:
                        errors[path] = error
                    elif result is not None:
                        results.append(result)
                except Exception as e:
                    errors[str(file_path)] = str(e)

        return ChunkedResult(
            results=results,
            errors=errors,
            files_processed=len(files),
        )


class ParallelScannerMixin:
    """
    Mixin class to add parallel scanning capabilities to existing scanners.

    Usage:
        class MyScanner(ParallelScannerMixin):
            def __init__(self, config):
                self.config = config
                self.parallel_config = ParallelConfig(
                    enabled=config.parallel,
                    workers=config.workers,
                )

            def _analyze_single_file(self, file_path: Path, config_dict: dict):
                # Return analysis result for single file
                pass

            def analyze(self, path: Path):
                files = self._discover_files(path)
                if self.parallel_config.enabled:
                    return self._analyze_parallel(files)
                return self._analyze_sequential(files)
    """

    parallel_config: ParallelConfig

    def _analyze_parallel(
        self,
        files: List[Path],
        analyze_func: Callable[[Path, Dict], R],
        config_dict: Optional[Dict] = None,
    ) -> ChunkedResult[R]:
        """
        Analyze files in parallel.

        Args:
            files: Files to analyze
            analyze_func: Function to analyze each file
            config_dict: Configuration to pass to analyzer

        Returns:
            ChunkedResult with all results
        """
        scanner: ParallelScanner = ParallelScanner(analyze_func, self.parallel_config)
        return scanner.scan(files, config_dict)


def get_optimal_worker_count(file_count: int, max_workers: Optional[int] = None) -> int:
    """
    Calculate the optimal number of workers based on file count and CPU cores.

    Args:
        file_count: Number of files to process
        max_workers: Maximum workers allowed (None = no limit)

    Returns:
        Optimal worker count
    """
    cpu_count = os.cpu_count() or 1

    # Don't use more workers than files
    optimal = min(file_count, cpu_count - 1)

    # Ensure at least 1 worker
    optimal = max(1, optimal)

    # Apply max limit if specified
    if max_workers is not None:
        optimal = min(optimal, max_workers)

    return optimal


def should_use_parallel(file_count: int, threshold: int = 20) -> bool:
    """
    Determine if parallel processing would be beneficial.

    Args:
        file_count: Number of files to process
        threshold: Minimum files to benefit from parallelization

    Returns:
        True if parallel processing is recommended
    """
    # Don't parallelize for small file counts due to overhead
    if file_count < threshold:
        return False

    # Check if multiprocessing is available
    cpu_count = os.cpu_count()
    if cpu_count is None or cpu_count < 2:
        return False

    return True
