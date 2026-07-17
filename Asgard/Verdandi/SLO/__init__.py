"""
Verdandi SLO - Service Level Objective Management

This module provides SLO capabilities including:
- Error budget calculation and tracking
- SLI metric tracking over time
- Burn rate analysis for alerting

Usage:
    from Asgard.Verdandi.SLO import ErrorBudgetCalculator, SLITracker, BurnRateAnalyzer

    # Calculate error budget
    calculator = ErrorBudgetCalculator()
    budget = calculator.calculate(slo_definition, metrics)

    # Track SLI over time
    tracker = SLITracker()
    tracker.record(metric)
    history = tracker.get_history()

    # Analyze burn rate
    analyzer = BurnRateAnalyzer()
    burn_rate = analyzer.analyze(error_budget_history)
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Verdandi.SLO.models.slo_models import (
    SLODefinition,
    SLOType,
    SLIMetric,
    ErrorBudget,
    BurnRate,
    BurnRateAlert,
    ThresholdDerivation,
    SLOReport,
    SLOComplianceStatus,
)
from Asgard.Verdandi.SLO.services.error_budget_calculator import ErrorBudgetCalculator
from Asgard.Verdandi.SLO.services.sli_tracker import SLITracker
from Asgard.Verdandi.SLO.services.burn_rate_analyzer import BurnRateAnalyzer

__all__ = [
    # Models
    "SLODefinition",
    "SLOType",
    "SLIMetric",
    "ErrorBudget",
    "BurnRate",
    "BurnRateAlert",
    "ThresholdDerivation",
    "SLOReport",
    "SLOComplianceStatus",
    # Services
    "ErrorBudgetCalculator",
    "SLITracker",
    "BurnRateAnalyzer",
]
