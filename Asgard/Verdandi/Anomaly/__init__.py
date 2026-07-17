"""
Verdandi Anomaly - Anomaly Detection for Performance Metrics

This module provides anomaly detection capabilities including:
- Statistical anomaly detection (z-score, IQR)
- Baseline comparison for performance metrics
- Regression detection for performance changes

Usage:
    from Asgard.Verdandi.Anomaly import StatisticalDetector, BaselineComparator, RegressionDetector

    # Detect statistical anomalies
    detector = StatisticalDetector()
    anomalies = detector.detect(data)

    # Compare against baseline
    comparator = BaselineComparator()
    comparison = comparator.compare(current_data, baseline)

    # Detect regressions
    regression_detector = RegressionDetector()
    regressions = regression_detector.detect(before_data, after_data)
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Verdandi.Anomaly.models.anomaly_models import (
    AnomalyType,
    AnomalySeverity,
    AnomalyDetection,
    BaselineMetrics,
    BaselineComparison,
    RegressionResult,
    AnomalyReport,
    BimodalityResult,
    StepChangeResult,
    DriftResult,
    MethodRecommendation,
    MetricClass,
    SensitivityProfile,
    BaselineStrategy,
    BaselineStrategyAssessment,
    DiffInDiffResult,
    DetectionOutcome,
    ModeStats,
)
from Asgard.Verdandi.Anomaly.services.statistical_detector import StatisticalDetector
from Asgard.Verdandi.Anomaly.services.baseline_comparator import BaselineComparator
from Asgard.Verdandi.Anomaly.services.regression_detector import RegressionDetector

__all__ = [
    # Models
    "AnomalyType",
    "AnomalySeverity",
    "AnomalyDetection",
    "BaselineMetrics",
    "BaselineComparison",
    "RegressionResult",
    "AnomalyReport",
    "BimodalityResult",
    "StepChangeResult",
    "DriftResult",
    "MethodRecommendation",
    "MetricClass",
    "SensitivityProfile",
    "BaselineStrategy",
    "BaselineStrategyAssessment",
    "DiffInDiffResult",
    "DetectionOutcome",
    "ModeStats",
    # Services
    "StatisticalDetector",
    "BaselineComparator",
    "RegressionDetector",
]
