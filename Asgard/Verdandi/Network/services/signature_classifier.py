"""
Network Anomaly Signature Classifier

Classifies RTT/hop-count/DNS-resolution series into named signature shapes
(RESEARCH_11):

- ROUTE_CHANGE: a sustained CUSUM step in RTT (optionally corroborated by a
  hop-count delta) -- a BGP/path change.
- DNS_HIJACK_SUSPECT: resolved-IP/ASN change coincident with a TLS-failure
  spike.
- CONGESTION: a retransmit spike plus growing RTT variance with no step --
  ordinary link congestion, not a route change.
- CLOCK_SKEW: any negative one-way latency. This is a data-quality guard,
  never an anomaly: NTP drift corrupts one-way latency computed from span
  timestamps, and the correct response is to flag the measurement, not the
  network (RESEARCH_14's coordinated-omission chapter makes the same
  argument for closed-loop timers).

Detectors emit annotations, not alerts (anomalies are not alerts).
"""

from typing import Optional, Sequence

from Asgard.Verdandi.Anomaly.services._batch_detectors import cusum
from Asgard.Verdandi.Network.models.network_models import (
    NetworkSignature,
    NetworkSignatureType,
)

#: Minimum sustained duration (minutes) after a CUSUM alarm for ROUTE_CHANGE.
_ROUTE_CHANGE_SUSTAINED_MINUTES = 15.0
#: Window (minutes) within which a resolved-IP/ASN change + TLS failure spike
#: is treated as coincident for DNS_HIJACK_SUSPECT.
_DNS_HIJACK_WINDOW_MINUTES = 5.0


def detect_clock_skew(one_way_latencies_ms: Sequence[float]) -> NetworkSignature:
    """
    The definitive clock-skew signature: any negative one-way latency.

    Negative computed latency is physically impossible for a real network
    event; it is the fingerprint of NTP drift between the timestamping
    clocks, not a network anomaly.
    """
    negatives = [v for v in one_way_latencies_ms if v < 0]
    if not negatives:
        return NetworkSignature(signature=NetworkSignatureType.NONE)

    return NetworkSignature(
        signature=NetworkSignatureType.CLOCK_SKEW,
        confidence=1.0,
        is_data_quality_issue=True,
        details=(
            f"{len(negatives)} negative one-way latency sample(s) "
            f"(min={min(negatives):.2f} ms): clock skew, not a network anomaly."
        ),
    )


class SignatureClassifier:
    """
    Classifies network telemetry series into named anomaly signatures.

    Example:
        classifier = SignatureClassifier()
        sig = classifier.classify(rtt_series=[20] * 20 + [45] * 20)
        print(sig.signature)  # NetworkSignatureType.ROUTE_CHANGE
    """

    def classify(
        self,
        rtt_series: Sequence[float],
        hop_count_series: Optional[Sequence[float]] = None,
        resolved_asn_series: Optional[Sequence[str]] = None,
        tls_failure_series: Optional[Sequence[int]] = None,
        one_way_latencies_ms: Optional[Sequence[float]] = None,
        sample_interval_seconds: float = 60.0,
    ) -> NetworkSignature:
        """
        Classify a batch of network telemetry into a single dominant
        signature. Priority: CLOCK_SKEW > DNS_HIJACK_SUSPECT > ROUTE_CHANGE
        > CONGESTION > NONE -- a data-quality flag always wins because every
        other classification is unreliable once the clock is untrustworthy.
        """
        if one_way_latencies_ms:
            skew = detect_clock_skew(one_way_latencies_ms)
            if skew.signature == NetworkSignatureType.CLOCK_SKEW:
                return skew

        hijack = self.classify_dns_hijack(resolved_asn_series, tls_failure_series)
        if hijack.signature == NetworkSignatureType.DNS_HIJACK_SUSPECT:
            return hijack

        route = self.classify_route_change(
            rtt_series, hop_count_series, sample_interval_seconds
        )
        if route.signature == NetworkSignatureType.ROUTE_CHANGE:
            return route

        congestion = self.classify_congestion(rtt_series)
        if congestion.signature == NetworkSignatureType.CONGESTION:
            return congestion

        if route.signature == NetworkSignatureType.INSUFFICIENT_DATA:
            return route

        return NetworkSignature(signature=NetworkSignatureType.NONE)

    def classify_route_change(
        self,
        rtt_series: Sequence[float],
        hop_count_series: Optional[Sequence[float]] = None,
        sample_interval_seconds: float = 60.0,
    ) -> NetworkSignature:
        """
        A BGP/path change shows up as a sustained step-function RTT shift,
        optionally corroborated by a hop-count delta.
        """
        n = len(rtt_series)
        if n < 15:
            return NetworkSignature(
                signature=NetworkSignatureType.INSUFFICIENT_DATA,
                notes=[f"Need >= 15 points for route-change detection; got {n}."],
            )

        step = cusum(list(rtt_series))
        if not step.detected or step.change_index is None:
            return NetworkSignature(signature=NetworkSignatureType.NONE)

        sustained_points = n - step.change_index
        sustained_minutes = sustained_points * sample_interval_seconds / 60.0
        if sustained_minutes < _ROUTE_CHANGE_SUSTAINED_MINUTES:
            return NetworkSignature(
                signature=NetworkSignatureType.NONE,
                notes=[
                    f"CUSUM step detected but sustained only "
                    f"{sustained_minutes:.1f} min "
                    f"(< {_ROUTE_CHANGE_SUSTAINED_MINUTES} min threshold)."
                ],
            )

        hop_delta = None
        if hop_count_series and len(hop_count_series) == n:
            before = hop_count_series[: step.change_index]
            after = hop_count_series[step.change_index :]
            if before and after:
                hop_delta = (sum(after) / len(after)) - (sum(before) / len(before))

        details = f"Sustained RTT step of {step.magnitude:.2f} ms at index {step.change_index}"
        if hop_delta is not None and abs(hop_delta) >= 1:
            details += f" with a hop-count change of {hop_delta:+.1f}"
        details += ": BGP/path change suspected."

        return NetworkSignature(
            signature=NetworkSignatureType.ROUTE_CHANGE,
            confidence=0.8 if hop_delta and abs(hop_delta) >= 1 else 0.6,
            change_index=step.change_index,
            details=details,
        )

    def classify_dns_hijack(
        self,
        resolved_asn_series: Optional[Sequence[str]],
        tls_failure_series: Optional[Sequence[int]],
    ) -> NetworkSignature:
        """
        Resolved-IP/ASN change to an anomalous ASN coincident with a
        TLS handshake/cert failure spike is a DNS-poisoning signature.
        """
        if not resolved_asn_series or not tls_failure_series:
            return NetworkSignature(signature=NetworkSignatureType.NONE)
        if len(resolved_asn_series) < 2 or len(resolved_asn_series) != len(
            tls_failure_series
        ):
            return NetworkSignature(signature=NetworkSignatureType.NONE)

        baseline_asn = resolved_asn_series[0]
        for i in range(1, len(resolved_asn_series)):
            if resolved_asn_series[i] != baseline_asn:
                window = tls_failure_series[max(0, i - 5) : i + 5]
                if window and max(window) - (window[0] if window else 0) > 0 and sum(window) > 0:
                    return NetworkSignature(
                        signature=NetworkSignatureType.DNS_HIJACK_SUSPECT,
                        confidence=0.7,
                        change_index=i,
                        details=(
                            f"Resolved ASN changed from {baseline_asn} to "
                            f"{resolved_asn_series[i]} with a coincident TLS "
                            "failure spike: possible DNS hijack/poisoning."
                        ),
                    )
        return NetworkSignature(signature=NetworkSignatureType.NONE)

    def classify_congestion(self, rtt_series: Sequence[float]) -> NetworkSignature:
        """
        Retransmit-correlated packet loss shows up as isolated retransmission
        spikes plus growing RTT variance with no sustained step -- ordinary
        congestion rather than a route change.
        """
        n = len(rtt_series)
        if n < 10:
            return NetworkSignature(signature=NetworkSignatureType.NONE)

        step = cusum(list(rtt_series))
        if step.detected and abs(step.magnitude or 0.0) > 5.0:
            # A genuine location shift (not just variance growth) is
            # route-change territory, not congestion.
            return NetworkSignature(signature=NetworkSignatureType.NONE)

        mid = n // 2
        first_half, second_half = rtt_series[:mid], rtt_series[mid:]
        var_first = _variance(first_half)
        var_second = _variance(second_half)

        if var_first > 0 and var_second > var_first * 1.5:
            return NetworkSignature(
                signature=NetworkSignatureType.CONGESTION,
                confidence=0.5,
                details=(
                    f"RTT variance grew from {var_first:.2f} to {var_second:.2f} "
                    "with no sustained step: congestion, not a route change."
                ),
            )
        return NetworkSignature(signature=NetworkSignatureType.NONE)


def _variance(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return sum((v - mean) ** 2 for v in values) / (n - 1)
