"""
USE Method Analyzer for Cloud NICs and DNS Quotas

Applies Brendan Gregg's USE method (Utilization / Saturation / Errors) to
virtualized cloud networking: NIC bandwidth/PPS quotas, TCP-stack queueing,
and the DNS resolver's link-local rate limit. Errors trump utilization -- a
single non-zero allowance-exceeded counter is a definitive signal even at
low reported utilization (RESEARCH_11).
"""

from typing import List, Optional, Sequence

from Asgard.Verdandi.Network.models.network_models import (
    NetworkOutcome,
    UseCounterSnapshot,
    UseResourceColumn,
    USEReport,
)

#: AWS's silent link-local DNS resolver quota (169.254.169.253), in queries/sec.
LINKLOCAL_DNS_QUOTA_PPS = 1024

_CORRELATION_SATURATION_THRESHOLD = 0.7


class UseAnalyzer:
    """
    USE-method analyzer for cloud NICs, the TCP stack, and the DNS resolver.

    Example:
        analyzer = UseAnalyzer()
        report = analyzer.analyze(UseCounterSnapshot(linklocal_allowance_exceeded=3))
        print(report.dns_resolver.severity)  # "critical"
    """

    def analyze(
        self,
        snapshot: Optional[UseCounterSnapshot],
        retransmit_series: Optional[Sequence[float]] = None,
        utilization_series: Optional[Sequence[float]] = None,
    ) -> USEReport:
        """
        Run the USE method against a counter snapshot.

        Args:
            snapshot: Point-in-time counter snapshot
            retransmit_series: Optional retransmit-rate series for
                correlation against utilization (saturation vs path loss)
            utilization_series: Optional utilization series aligned to
                retransmit_series

        Returns:
            USEReport; INSUFFICIENT_DATA when snapshot is None.
        """
        if snapshot is None:
            return USEReport(
                outcome=NetworkOutcome.INSUFFICIENT_DATA,
                notes=["No counter snapshot provided."],
            )

        nic = self._analyze_nic(snapshot, retransmit_series, utilization_series)
        tcp_stack = self._analyze_tcp_stack(snapshot)
        dns_resolver = self._analyze_dns_resolver(snapshot)

        columns = [nic, tcp_stack, dns_resolver]
        overall_severity = self._max_severity([c.severity for c in columns])
        recommendations: List[str] = []
        for column in columns:
            recommendations.extend(column.remediation)

        return USEReport(
            outcome=NetworkOutcome.OK,
            nic=nic,
            tcp_stack=tcp_stack,
            dns_resolver=dns_resolver,
            overall_severity=overall_severity,
            recommendations=recommendations,
        )

    def _analyze_nic(
        self,
        snapshot: UseCounterSnapshot,
        retransmit_series: Optional[Sequence[float]],
        utilization_series: Optional[Sequence[float]],
    ) -> UseResourceColumn:
        errors: List[str] = []
        remediation: List[str] = []
        severity = "ok"

        utilization_percent = None
        if snapshot.instance_bw_limit_mbps:
            sent_mbps = snapshot.sent_bytes_ps * 8 / 1_000_000
            recv_mbps = snapshot.recv_bytes_ps * 8 / 1_000_000
            utilization_percent = round(
                (sent_mbps + recv_mbps) / snapshot.instance_bw_limit_mbps * 100, 2
            )
        elif snapshot.instance_pps_limit:
            utilization_percent = round(
                snapshot.pps / snapshot.instance_pps_limit * 100, 2
            )

        saturated = snapshot.listen_overflows > 0
        saturation_notes = []
        if snapshot.listen_overflows > 0:
            saturation_notes.append(
                f"Listen-queue overflows: {snapshot.listen_overflows}."
            )

        if snapshot.pps_allowance_exceeded > 0:
            errors.append("pps_allowance_exceeded")
            remediation.append(
                "PPS allowance exceeded: reduce packet rate or move to a "
                "larger instance/ENA-optimized type with a higher PPS quota."
            )
        if snapshot.bw_in_allowance_exceeded > 0:
            errors.append("bw_in_allowance_exceeded")
            remediation.append(
                "Bandwidth allowance exceeded: throttle traffic or upgrade "
                "the instance's network bandwidth tier."
            )
        if snapshot.conntrack_allowance_exceeded > 0:
            errors.append("conntrack_allowance_exceeded")
            saturated = True
            remediation.append(
                "Conntrack table filling: shorten connection TTLs, enable "
                "connection reuse, or raise the conntrack allowance."
            )

        if snapshot.tcp_retransmits > 0:
            if (
                retransmit_series
                and utilization_series
                and len(retransmit_series) >= 3
                and len(retransmit_series) == len(utilization_series)
            ):
                r = self._pearson_r(list(retransmit_series), list(utilization_series))
                if r is not None and r > _CORRELATION_SATURATION_THRESHOLD:
                    saturation_notes.append(
                        f"Retransmits correlate with utilization (r={r:.2f}): "
                        "link saturation, not path loss."
                    )
                    saturated = True
                elif r is not None:
                    saturation_notes.append(
                        f"Retransmits uncorrelated with utilization (r={r:.2f}): "
                        "likely path/upstream packet loss, not local saturation."
                    )

        if errors:
            severity = "critical"
        elif saturated:
            severity = "warning"

        return UseResourceColumn(
            resource="nic",
            utilization_percent=utilization_percent,
            saturated=saturated,
            saturation_notes=saturation_notes,
            errors=errors,
            severity=severity,
            remediation=remediation,
        )

    def _analyze_tcp_stack(self, snapshot: UseCounterSnapshot) -> UseResourceColumn:
        errors: List[str] = []
        remediation: List[str] = []
        saturation_notes: List[str] = []
        saturated = False

        utilization_percent = None
        if snapshot.ephemeral_port_range and snapshot.ephemeral_port_range > 0:
            utilization_percent = round(
                snapshot.active_connections / snapshot.ephemeral_port_range * 100, 2
            )

        if snapshot.listen_overflows > 0:
            saturated = True
            saturation_notes.append(
                f"Listen-queue overflows: {snapshot.listen_overflows}; "
                "backlog is too small or accept() is too slow."
            )
        if snapshot.conntrack_allowance_exceeded > 0:
            errors.append("conntrack_allowance_exceeded")
            saturated = True
            remediation.append(
                "Conntrack allowance exceeded: reduce connection churn or "
                "raise the conntrack table size."
            )

        severity = "critical" if errors else ("warning" if saturated else "ok")

        return UseResourceColumn(
            resource="tcp_stack",
            utilization_percent=utilization_percent,
            saturated=saturated,
            saturation_notes=saturation_notes,
            errors=errors,
            severity=severity,
            remediation=remediation,
        )

    def _analyze_dns_resolver(self, snapshot: UseCounterSnapshot) -> UseResourceColumn:
        errors: List[str] = []
        remediation: List[str] = []
        severity = "ok"

        dns_qps = snapshot.dns_qps if snapshot.dns_qps is not None else snapshot.pps
        utilization_percent = round(dns_qps / LINKLOCAL_DNS_QUOTA_PPS * 100, 2)

        if snapshot.linklocal_allowance_exceeded > 0:
            errors.append("linklocal_allowance_exceeded")
            remediation.append(
                f"Link-local DNS quota (1,024 PPS) exceeded "
                f"({snapshot.linklocal_allowance_exceeded} drops observed): "
                "deploy a node-local DNS cache (e.g. NodeLocal DNSCache) so "
                "queries stop hitting the VPC's link-local resolver directly."
            )

        # Errors trump utilization: a low utilization_percent must not mask
        # a non-zero allowance-exceeded counter.
        severity = "critical" if errors else severity

        return UseResourceColumn(
            resource="dns_resolver",
            utilization_percent=utilization_percent,
            saturated=False,
            errors=errors,
            severity=severity,
            remediation=remediation,
        )

    @staticmethod
    def _pearson_r(x: List[float], y: List[float]) -> Optional[float]:
        n = len(x)
        if n < 2:
            return None
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        var_x = sum((v - mean_x) ** 2 for v in x)
        var_y = sum((v - mean_y) ** 2 for v in y)
        denom = (var_x * var_y) ** 0.5
        if denom == 0:
            return None
        return cov / denom

    @staticmethod
    def _max_severity(severities: List[str]) -> str:
        order = {"ok": 0, "warning": 1, "critical": 2}
        return max(severities, key=lambda s: order.get(s, 0), default="ok")
