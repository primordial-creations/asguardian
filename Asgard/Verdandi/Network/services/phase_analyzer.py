"""
TTFB Phase Decomposition Analyzer

TTFB is composite: DNS -> TCP (1 RTT) -> TLS (2-RTT for 1.2, 1-RTT for 1.3,
0-RTT resumption/QUIC) -> request -> response. Diagnosis requires splitting
it into these phases and checking each against protocol-specific
expectations, rather than treating TTFB as a single number (RESEARCH_11).
"""

from typing import Dict, List, Optional, Sequence, Union

from Asgard.Verdandi.Analysis import PercentileCalculator
from Asgard.Verdandi.Network.models.network_models import (
    HANDSHAKE_OVERHEAD,
    ConnectionPhases,
    NetworkOutcome,
    PhaseAnalysisResult,
    PhaseStats,
)

_PHASE_NAMES = ("dns_ms", "tcp_ms", "tls_ms", "request_ms", "response_ms")

#: TLS handshake RTT budget by version: 2-RTT for TLS 1.2, 1-RTT for TLS 1.3,
#: 0-RTT for a resumed session or QUIC/HTTP-3 (which folds the handshake in).
_TLS_HANDSHAKE_RTTS = {"1.2": 2, "1.3": 1}
_HANDSHAKE_OVERHEAD_FACTOR = 1.5


class PhaseAnalyzer:
    """
    Decomposes TTFB into DNS/TCP/TLS/request/response phases and checks
    each against protocol-specific expectations.

    Example:
        analyzer = PhaseAnalyzer()
        result = analyzer.analyze([
            {"dns_ms": 5, "tcp_ms": 20, "tls_ms": 300, "request_ms": 2,
             "response_ms": 40, "tls_version": "1.2"},
        ])
        print(result.ttfb_dominant_phase)
    """

    def __init__(self) -> None:
        self._percentile_calc = PercentileCalculator()

    def analyze(
        self,
        samples: Sequence[Union[ConnectionPhases, Dict]],
    ) -> PhaseAnalysisResult:
        """
        Decompose a batch of per-request phase timings.

        Args:
            samples: Sequence of ConnectionPhases (or equivalent dicts)

        Returns:
            PhaseAnalysisResult; INSUFFICIENT_DATA when samples is empty.
        """
        if not samples:
            return PhaseAnalysisResult(
                outcome=NetworkOutcome.INSUFFICIENT_DATA,
                notes=["Need >= 1 phase sample for decomposition."],
            )

        parsed = [
            s if isinstance(s, ConnectionPhases) else ConnectionPhases(**s)
            for s in samples
        ]

        phase_values: Dict[str, List[float]] = {name: [] for name in _PHASE_NAMES}
        ttfb_values: List[float] = []
        shares: Dict[str, List[float]] = {name: [] for name in _PHASE_NAMES}

        for sample in parsed:
            values = {name: getattr(sample, name) for name in _PHASE_NAMES}
            for name in _PHASE_NAMES:
                phase_values[name].append(values[name])

            ttfb = sample.ttfb_ms if sample.ttfb_ms is not None else sum(values.values())
            ttfb_values.append(ttfb)
            if ttfb > 0:
                for name in _PHASE_NAMES:
                    shares[name].append(values[name] / ttfb * 100.0)

        phase_stats: Dict[str, PhaseStats] = {}
        for name in _PHASE_NAMES:
            values = phase_values[name]
            pct = self._percentile_calc.calculate(values) if values else None
            mean_share = sum(shares[name]) / len(shares[name]) if shares[name] else 0.0
            phase_stats[name] = PhaseStats(
                p50_ms=round(pct.median, 3) if pct else 0.0,
                p75_ms=round(pct.p75, 3) if pct else 0.0,
                p95_ms=round(pct.p95, 3) if pct else 0.0,
                mean_ms=round(pct.mean, 3) if pct else 0.0,
                share_of_ttfb_percent=round(mean_share, 2),
            )

        dominant_phase = max(
            _PHASE_NAMES, key=lambda name: phase_stats[name].share_of_ttfb_percent
        ).replace("_ms", "")

        ttfb_pct = self._percentile_calc.calculate(ttfb_values)

        protocol_flags: List[str] = []
        recommendations: List[str] = []
        for sample in parsed:
            flag = self._check_handshake_overhead(sample)
            if flag and flag not in protocol_flags:
                protocol_flags.append(flag)
                recommendations.append(
                    "TLS handshake overhead exceeds the protocol-expected RTT "
                    "budget. Consider TLS 1.3, 0-RTT session resumption, or "
                    "HTTP/3 (QUIC) to fold the handshake into transport setup."
                )

        return PhaseAnalysisResult(
            outcome=NetworkOutcome.OK,
            sample_count=len(parsed),
            dns=phase_stats["dns_ms"],
            tcp=phase_stats["tcp_ms"],
            tls=phase_stats["tls_ms"],
            request=phase_stats["request_ms"],
            response=phase_stats["response_ms"],
            ttfb_p50_ms=round(ttfb_pct.median, 3),
            ttfb_p95_ms=round(ttfb_pct.p95, 3),
            ttfb_dominant_phase=dominant_phase,
            protocol_flags=protocol_flags,
            recommendations=recommendations,
        )

    def _check_handshake_overhead(self, sample: ConnectionPhases) -> Optional[str]:
        """
        Flag HANDSHAKE_OVERHEAD when tls_ms exceeds 1.5x the protocol-expected
        handshake budget: expected_rtts x rtt_est, where rtt_est is estimated
        from tcp_ms (the TCP connect phase is ~1 RTT) and expected_rtts is
        2 for TLS 1.2, 1 for TLS 1.3, 0 for a resumed session or QUIC/HTTP-3.
        """
        if sample.resumed or (sample.protocol or "").lower() in ("h3", "http/3", "quic"):
            return None
        if not sample.tls_version or sample.tcp_ms <= 0:
            return None

        expected_rtts = _TLS_HANDSHAKE_RTTS.get(sample.tls_version)
        if expected_rtts is None:
            return None
        if expected_rtts == 0:
            return None

        rtt_est = sample.tcp_ms
        expected_tls_ms = expected_rtts * rtt_est
        if sample.tls_ms > expected_tls_ms * _HANDSHAKE_OVERHEAD_FACTOR:
            return HANDSHAKE_OVERHEAD
        return None
