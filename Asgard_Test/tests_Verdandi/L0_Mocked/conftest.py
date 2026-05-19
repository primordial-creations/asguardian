"""
Pytest configuration and shared fixtures for Verdandi L0 unit tests.

This file provides common fixtures used across multiple test files.
"""

import pytest
from datetime import datetime, timedelta


@pytest.fixture
def sample_response_times():
    """Sample response times for testing."""
    return [100, 150, 200, 250, 300, 350, 400, 450, 500, 550]


@pytest.fixture
def sample_response_times_with_outliers():
    """Sample response times with outliers for anomaly testing."""
    return [100, 105, 98, 102, 99, 500, 101, 97, 103, 5000]


@pytest.fixture
def current_timestamp():
    """Current timestamp fixture."""
    return datetime.now()


@pytest.fixture
def timestamp_range_30_days(current_timestamp):
    """Generate timestamps for 30 days."""
    return [
        current_timestamp - timedelta(days=i)
        for i in range(30)
    ]


@pytest.fixture
def timestamp_range_7_days(current_timestamp):
    """Generate timestamps for 7 days."""
    return [
        current_timestamp - timedelta(days=i)
        for i in range(7)
    ]


@pytest.fixture
def large_dataset():
    """Large dataset for performance testing."""
    return list(range(1, 10001))


@pytest.fixture
def normal_distribution_data():
    """Normally distributed data for statistical testing."""
    # Approximate normal distribution
    mean = 150.0
    std_dev = 30.0

    # Generate values using simple approximation
    values = []
    for i in range(100):
        # Simple pseudo-random generation for testing
        value = mean + std_dev * (i % 10 - 5) / 2.5
        values.append(value)

    return values


@pytest.fixture
def bimodal_distribution_data():
    """Bimodal distribution data (e.g., cache hits/misses)."""
    # Two distinct modes
    return [50] * 70 + [200] * 30


@pytest.fixture
def uniform_distribution_data():
    """Uniformly distributed data."""
    return list(range(100, 201))
