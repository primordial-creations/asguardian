"""
Verdandi Network - Network Performance Metrics

This module provides network performance metric calculations including:
- Latency measurements and analysis (incl. topology-baseline-relative rating)
- Bandwidth utilization
- DNS timing metrics (incl. quota/environment-band analysis)
- Connection timing
- TTFB phase decomposition (DNS/TCP/TLS/request/response)
- USE-method analysis for cloud NICs and DNS quotas
- BGP/DNS-hijack/congestion/clock-skew anomaly signatures

Usage:
    from Asgard.Verdandi.Network import LatencyCalculator

    calc = LatencyCalculator()
    result = calc.analyze([10, 15, 12, 20, 18])
    print(f"P99 Latency: {result.p99_ms}ms")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Verdandi.Network.models.network_models import (
    BandwidthMetrics,
    ConnectionMetrics,
    ConnectionPhases,
    DnsMetrics,
    DnsQuotaResult,
    LatencyMetrics,
    NetworkOutcome,
    NetworkSignature,
    NetworkSignatureType,
    PhaseAnalysisResult,
    PhaseStats,
    ProfileLatencyResult,
    TopologyProfile,
    TopologyRating,
    UseCounterSnapshot,
    UseResourceColumn,
    USEReport,
)
from Asgard.Verdandi.Network.services.latency_calculator import LatencyCalculator
from Asgard.Verdandi.Network.services.bandwidth_calculator import BandwidthCalculator
from Asgard.Verdandi.Network.services.dns_calculator import DnsCalculator
from Asgard.Verdandi.Network.services.phase_analyzer import PhaseAnalyzer
from Asgard.Verdandi.Network.services.use_analyzer import UseAnalyzer
from Asgard.Verdandi.Network.services.signature_classifier import SignatureClassifier

__all__ = [
    "BandwidthCalculator",
    "BandwidthMetrics",
    "ConnectionMetrics",
    "ConnectionPhases",
    "DnsCalculator",
    "DnsMetrics",
    "DnsQuotaResult",
    "LatencyCalculator",
    "LatencyMetrics",
    "NetworkOutcome",
    "NetworkSignature",
    "NetworkSignatureType",
    "PhaseAnalysisResult",
    "PhaseAnalyzer",
    "PhaseStats",
    "ProfileLatencyResult",
    "SignatureClassifier",
    "TopologyProfile",
    "TopologyRating",
    "UseAnalyzer",
    "UseCounterSnapshot",
    "UseResourceColumn",
    "USEReport",
]
