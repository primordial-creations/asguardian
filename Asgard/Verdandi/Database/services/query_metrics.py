"""
Query Metrics Calculator

Calculates database query performance metrics.
"""

import re
import statistics
from typing import Dict, List, Optional

from Asgard.Verdandi.Analysis import PercentileCalculator
from Asgard.Verdandi.Database.models.database_models import (
    QueryClassStats,
    QueryMetricsInput,
    QueryMetricsResult,
    QueryType,
)

_STRING_LITERAL_RE = re.compile(r"'(?:[^'\\]|\\.)*'")
_NUMERIC_LITERAL_RE = re.compile(r"(?<![\w])-?\d+(\.\d+)?(?![\w])")
_IN_LIST_RE = re.compile(r"\bIN\s*\([^)]*\)", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


def fingerprint_query(query_text: str) -> str:
    """
    Normalize a raw SQL string into a fingerprint by collapsing literals
    and whitespace, so `SELECT * FROM t WHERE id = 1` and
    `SELECT * FROM t WHERE id = 2` share a fingerprint.

    Args:
        query_text: Raw SQL text

    Returns:
        Normalized fingerprint string
    """
    if not query_text:
        return ""
    text = _STRING_LITERAL_RE.sub("?", query_text)
    text = _IN_LIST_RE.sub("IN (?)", text)
    text = _NUMERIC_LITERAL_RE.sub("?", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text.upper()


class QueryMetricsCalculator:
    """
    Calculator for database query performance metrics.

    Analyzes query execution times, index usage, and identifies slow queries.

    Example:
        calc = QueryMetricsCalculator()
        result = calc.analyze([query1, query2, ...])
        print(f"P95: {result.p95_execution_ms}ms")
    """

    def __init__(self, slow_query_threshold_ms: float = 100.0):
        """
        Initialize the calculator.

        Args:
            slow_query_threshold_ms: Threshold for classifying slow queries
        """
        self.slow_query_threshold_ms = slow_query_threshold_ms
        self._percentile_calc = PercentileCalculator()

    def analyze(
        self,
        queries: List[QueryMetricsInput],
    ) -> QueryMetricsResult:
        """
        Analyze query metrics.

        Args:
            queries: List of query metrics to analyze

        Returns:
            QueryMetricsResult with analysis
        """
        if not queries:
            raise ValueError("Cannot analyze empty query list")

        execution_times = [q.execution_time_ms for q in queries]
        percentiles = self._percentile_calc.calculate(execution_times)

        by_type = self._group_by_type(queries)
        slow_count = sum(1 for q in queries if q.execution_time_ms > self.slow_query_threshold_ms)
        index_usage = sum(1 for q in queries if q.used_index) / len(queries) * 100

        total_examined = sum(q.rows_examined for q in queries)
        total_affected = sum(q.rows_affected for q in queries if q.rows_affected > 0)
        scan_rate = total_examined / total_affected if total_affected > 0 else 0

        recommendations = self._generate_recommendations(
            percentiles.p95, slow_count, index_usage, scan_rate, len(queries)
        )

        return QueryMetricsResult(
            total_queries=len(queries),
            average_execution_ms=round(percentiles.mean, 2),
            median_execution_ms=round(percentiles.median, 2),
            p95_execution_ms=round(percentiles.p95, 2),
            p99_execution_ms=round(percentiles.p99, 2),
            max_execution_ms=round(percentiles.max_value, 2),
            min_execution_ms=round(percentiles.min_value, 2),
            by_type=by_type,
            slow_query_count=slow_count,
            slow_query_threshold_ms=self.slow_query_threshold_ms,
            index_usage_rate=round(index_usage, 2),
            scan_rate=round(scan_rate, 2),
            recommendations=recommendations,
        )

    def analyze_by_fingerprint(
        self,
        queries: List[QueryMetricsInput],
        baseline: Optional[Dict[str, List[float]]] = None,
        shift_threshold: float = 3.0,
    ) -> List[QueryClassStats]:
        """
        Segment queries by normalized fingerprint and compute per-class
        percentiles. When a baseline (fingerprint -> durations) is supplied,
        flag classes whose median has shifted by more than
        `shift_threshold` baseline MADs (a robust Hodges-Lehmann-style shift
        test) — this replaces one blended P99 across heterogeneous query
        classes (DEEPTHINK_04) with per-class regression detection.

        Args:
            queries: Queries to segment (uses `query_text`; falls back to
                `query_id` or query_type when `query_text` is absent)
            baseline: Optional per-fingerprint baseline durations (ms)
            shift_threshold: MAD multiples defining a "shift"

        Returns:
            List of QueryClassStats, one per fingerprint, sorted by count desc
        """
        by_fp: Dict[str, List[float]] = {}
        for q in queries:
            fp = self._fingerprint_for(q)
            by_fp.setdefault(fp, []).append(q.execution_time_ms)

        results: List[QueryClassStats] = []
        for fp, durations in by_fp.items():
            sorted_d = sorted(durations)
            stats = QueryClassStats(
                fingerprint=fp,
                count=len(durations),
                p50_ms=round(self._pct(sorted_d, 50), 3),
                p95_ms=round(self._pct(sorted_d, 95), 3),
                p99_ms=round(self._pct(sorted_d, 99), 3),
                mean_ms=round(statistics.fmean(durations), 3),
                max_ms=round(max(durations), 3),
            )

            if baseline and fp in baseline and baseline[fp]:
                shift_detected, notes = self._shift_vs_baseline(
                    durations, baseline[fp], shift_threshold
                )
                stats.shift_detected = shift_detected
                stats.shift_notes = notes

            results.append(stats)

        results.sort(key=lambda s: s.count, reverse=True)
        return results

    @staticmethod
    def _fingerprint_for(q: QueryMetricsInput) -> str:
        if q.query_text:
            return fingerprint_query(q.query_text)
        if q.query_id:
            return q.query_id
        return q.query_type.value

    @staticmethod
    def _shift_vs_baseline(
        current: List[float],
        baseline: List[float],
        shift_threshold: float,
    ):
        cur_median = statistics.median(current)
        base_median = statistics.median(baseline)
        base_mad = statistics.median(
            [abs(v - base_median) for v in baseline]
        ) * 1.4826  # normal-consistent MAD
        if base_mad == 0:
            base_mad = 1e-9

        shift_mads = abs(cur_median - base_median) / base_mad
        shift_detected = shift_mads > shift_threshold
        notes = []
        if shift_detected:
            notes.append(
                f"Median shifted {cur_median - base_median:+.2f}ms "
                f"({shift_mads:.1f}x baseline MAD, threshold {shift_threshold}x)."
            )
        return shift_detected, notes

    @staticmethod
    def _pct(sorted_values: List[float], pct: float) -> float:
        if not sorted_values:
            return 0.0
        n = len(sorted_values)
        if n == 1:
            return float(sorted_values[0])
        rank = (pct / 100) * (n - 1)
        lower = int(rank)
        upper = min(lower + 1, n - 1)
        frac = rank - lower
        return sorted_values[lower] + frac * (sorted_values[upper] - sorted_values[lower])

    def _group_by_type(
        self,
        queries: List[QueryMetricsInput],
    ) -> Dict[str, Dict[str, float]]:
        """Group queries by type and calculate stats."""
        groups: Dict[str, List[float]] = {}

        for query in queries:
            query_type = query.query_type.value
            if query_type not in groups:
                groups[query_type] = []
            groups[query_type].append(query.execution_time_ms)

        result = {}
        for query_type, times in groups.items():
            result[query_type] = {
                "count": len(times),
                "avg_ms": round(sum(times) / len(times), 2),
                "max_ms": round(max(times), 2),
                "min_ms": round(min(times), 2),
            }

        return result

    def _generate_recommendations(
        self,
        p95: float,
        slow_count: int,
        index_usage: float,
        scan_rate: float,
        total: int,
    ) -> List[str]:
        """Generate performance recommendations."""
        recommendations = []

        if p95 > 500:
            recommendations.append(
                f"P95 query time ({p95:.0f}ms) is high. Review slow queries for optimization."
            )

        slow_pct = (slow_count / total) * 100 if total > 0 else 0
        if slow_pct > 10:
            recommendations.append(
                f"{slow_pct:.1f}% of queries are slow (>{self.slow_query_threshold_ms}ms). "
                "Consider adding indexes or query optimization."
            )

        if index_usage < 80:
            recommendations.append(
                f"Index usage is {index_usage:.1f}%. "
                "Review queries not using indexes and add appropriate indexes."
            )

        if scan_rate > 100:
            recommendations.append(
                f"Scan rate is {scan_rate:.0f} rows examined per row affected. "
                "Queries may be doing full table scans."
            )

        return recommendations
