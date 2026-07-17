"""
Navigation Timing Calculator

Calculates page load timing breakdown from Navigation Timing API data.
"""

from typing import Dict, List, Sequence

from Asgard.Verdandi.Web.models.web_models import (
    NavigationTimingInput,
    NavigationTimingResult,
)


class NavigationTimingCalculator:
    """
    Calculator for Navigation Timing metrics.

    Breaks down page load time into component phases and identifies bottlenecks.

    Example:
        calc = NavigationTimingCalculator()
        result = calc.calculate(input_data)
        print(f"Page Load: {result.page_load_ms}ms")
        print(f"Bottleneck: {result.bottleneck}")
    """

    def calculate(self, input_data: NavigationTimingInput) -> NavigationTimingResult:
        """
        Calculate navigation timing breakdown.

        Args:
            input_data: Navigation timing input data

        Returns:
            NavigationTimingResult with timing breakdown
        """
        dns_lookup = input_data.dns_end_ms - input_data.dns_start_ms
        tcp_connection = input_data.connect_end_ms - input_data.connect_start_ms

        ssl_handshake = None
        if input_data.ssl_start_ms is not None and input_data.ssl_end_ms is not None:
            ssl_handshake = input_data.ssl_end_ms - input_data.ssl_start_ms

        ttfb = input_data.response_start_ms - input_data.request_start_ms
        content_download = input_data.response_end_ms - input_data.response_start_ms
        dom_processing = input_data.dom_complete_ms - input_data.dom_interactive_ms
        page_load = input_data.load_event_end_ms

        backend_time = ttfb + dns_lookup + tcp_connection
        if ssl_handshake:
            backend_time += ssl_handshake

        frontend_time = page_load - input_data.response_end_ms

        bottleneck = self._identify_bottleneck(
            dns_lookup, tcp_connection, ssl_handshake, ttfb,
            content_download, dom_processing, frontend_time
        )

        recommendations = self._generate_recommendations(
            dns_lookup, tcp_connection, ssl_handshake, ttfb,
            content_download, dom_processing, frontend_time
        )

        return NavigationTimingResult(
            dns_lookup_ms=round(dns_lookup, 2),
            tcp_connection_ms=round(tcp_connection, 2),
            ssl_handshake_ms=round(ssl_handshake, 2) if ssl_handshake else None,
            ttfb_ms=round(ttfb, 2),
            content_download_ms=round(content_download, 2),
            dom_processing_ms=round(dom_processing, 2),
            page_load_ms=round(page_load, 2),
            frontend_time_ms=round(frontend_time, 2),
            backend_time_ms=round(backend_time, 2),
            bottleneck=bottleneck,
            recommendations=recommendations,
        )

    def analyze_batch(
        self,
        inputs: Sequence[NavigationTimingInput],
    ) -> Dict[str, Dict[str, float]]:
        """
        Fleet aggregation: per-phase p50/p75/p95 across many page loads.

        Lets TTFB regressions be attributed to a specific phase
        (DNS / TCP / TLS / request-response / DOM) instead of a single
        opaque number.

        Args:
            inputs: Navigation timing records from many page loads

        Returns:
            {phase: {"p50": ..., "p75": ..., "p95": ..., "count": n}} for
            phases dns_lookup, tcp_connection, ssl_handshake, ttfb,
            content_download, dom_processing, page_load. Empty dict for no
            input (insufficient data, not zeros).
        """
        from Asgard.Verdandi.Analysis.services.percentile_calculator import (
            PercentileCalculator,
        )

        if not inputs:
            return {}

        phases: Dict[str, List[float]] = {
            "dns_lookup": [],
            "tcp_connection": [],
            "ssl_handshake": [],
            "ttfb": [],
            "content_download": [],
            "dom_processing": [],
            "page_load": [],
        }
        for item in inputs:
            result = self.calculate(item)
            phases["dns_lookup"].append(result.dns_lookup_ms)
            phases["tcp_connection"].append(result.tcp_connection_ms)
            if result.ssl_handshake_ms is not None:
                phases["ssl_handshake"].append(result.ssl_handshake_ms)
            phases["ttfb"].append(result.ttfb_ms)
            phases["content_download"].append(result.content_download_ms)
            phases["dom_processing"].append(result.dom_processing_ms)
            phases["page_load"].append(result.page_load_ms)

        calc = PercentileCalculator()
        aggregated: Dict[str, Dict[str, float]] = {}
        for phase, values in phases.items():
            if not values:
                continue
            ordered = sorted(values)
            aggregated[phase] = {
                "p50": calc.calculate_percentile(ordered, 50, presorted=True),
                "p75": calc.calculate_percentile(ordered, 75, presorted=True),
                "p95": calc.calculate_percentile(ordered, 95, presorted=True),
                "count": float(len(values)),
            }
        return aggregated

    def _identify_bottleneck(
        self,
        dns: float,
        tcp: float,
        ssl: float | None,
        ttfb: float,
        download: float,
        dom: float,
        frontend: float,
    ) -> str:
        """Identify the primary bottleneck."""
        metrics = {
            "DNS Lookup": dns,
            "TCP Connection": tcp,
            "TTFB (Server Response)": ttfb,
            "Content Download": download,
            "DOM Processing": dom,
            "Frontend Rendering": frontend,
        }

        if ssl:
            metrics["SSL Handshake"] = ssl

        max_metric = max(metrics.items(), key=lambda x: x[1])
        return max_metric[0]

    def _generate_recommendations(
        self,
        dns: float,
        tcp: float,
        ssl: float | None,
        ttfb: float,
        download: float,
        dom: float,
        frontend: float,
    ) -> List[str]:
        """Generate recommendations based on timing data."""
        recommendations = []

        if dns > 50:
            recommendations.append(
                f"DNS lookup ({dns:.0f}ms) is slow. Consider DNS prefetching or faster DNS provider."
            )

        if tcp > 100:
            recommendations.append(
                f"TCP connection ({tcp:.0f}ms) is slow. Enable connection keep-alive and use HTTP/2."
            )

        if ssl and ssl > 100:
            recommendations.append(
                f"SSL handshake ({ssl:.0f}ms) is slow. Consider TLS 1.3 and session resumption."
            )

        if ttfb > 600:
            recommendations.append(
                f"TTFB ({ttfb:.0f}ms) is high. Optimize server-side processing and use caching."
            )

        if download > 500:
            recommendations.append(
                f"Content download ({download:.0f}ms) is slow. Enable compression and use a CDN."
            )

        if dom > 500:
            recommendations.append(
                f"DOM processing ({dom:.0f}ms) is slow. Reduce DOM size and optimize JavaScript."
            )

        if frontend > 1000:
            recommendations.append(
                f"Frontend rendering ({frontend:.0f}ms) is slow. Defer non-critical resources."
            )

        return recommendations
