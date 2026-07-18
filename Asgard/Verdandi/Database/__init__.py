"""
Verdandi Database - Database Performance Metrics

This module provides database performance metric calculations including:
- Query execution time analysis
- Throughput calculations (queries per second)
- Connection pool metrics
- Transaction performance

Usage:
    from Asgard.Verdandi.Database import QueryMetricsCalculator

    calc = QueryMetricsCalculator()
    result = calc.analyze([query1, query2, ...])
    print(f"Avg Query Time: {result.average_execution_ms}ms")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Verdandi.Database.models.database_models import (
    QueryMetricsInput,
    QueryMetricsResult,
    ConnectionPoolMetrics,
    TransactionMetrics,
    DatabaseHealthResult,
    PoolModeStats,
    PoolSignature,
    PoolSignatureClass,
    QueryBudgetConfig,
    QueryBudgetResult,
    QueryClassStats,
)
from Asgard.Verdandi.Database.services.query_metrics import (
    QueryMetricsCalculator,
    fingerprint_query,
)
from Asgard.Verdandi.Database.services.throughput_calculator import ThroughputCalculator
from Asgard.Verdandi.Database.services.connection_analyzer import ConnectionAnalyzer
from Asgard.Verdandi.Database.services.pool_signature_detector import PoolSignatureDetector
from Asgard.Verdandi.Database.services.query_budget import QueryBudgetAnalyzer

__all__ = [
    "ConnectionAnalyzer",
    "ConnectionPoolMetrics",
    "DatabaseHealthResult",
    "PoolModeStats",
    "PoolSignature",
    "PoolSignatureClass",
    "PoolSignatureDetector",
    "QueryBudgetAnalyzer",
    "QueryBudgetConfig",
    "QueryBudgetResult",
    "QueryClassStats",
    "QueryMetricsCalculator",
    "QueryMetricsInput",
    "QueryMetricsResult",
    "ThroughputCalculator",
    "TransactionMetrics",
    "fingerprint_query",
]
