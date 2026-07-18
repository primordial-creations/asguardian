"""
CLI handlers for the `network` command group (first CLI surface for the
Network module):

- network phases      connection-phase breakdown analysis (DNS/TCP/TLS/...)
- network use         USE-method analysis of NIC/TCP-stack/DNS-resolver
- network signature   signature classification (route change / congestion /
                       DNS hijack / clock skew) from RTT and related series

All are thin wrappers over Asgard.Verdandi.Network.services.*: JSON metrics
file in, JSON or human-readable text out.
"""

import json
from pathlib import Path
from typing import Any, Optional


def _load_json(path: str) -> Optional[Any]:
    file_path = Path(path)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return None
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error: Could not parse JSON from {file_path}: {e}")
        return None


def _dump(model: Any) -> Any:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def run_network_phases(args, output_format: str = "text") -> int:
    """`verdandi network phases <samples.json>`.

    Input: JSON array of {dns_ms, tcp_ms, tls_ms, request_ms, response_ms,
    ttfb_ms?, protocol?, tls_version?, resumed?} connection-phase samples.
    """
    from Asgard.Verdandi.Network.services.phase_analyzer import PhaseAnalyzer

    data = _load_json(args.metrics_file)
    if data is None:
        return 1
    samples = data.get("samples", data) if isinstance(data, dict) else data
    if not isinstance(samples, list):
        print("Error: Expected a JSON array of connection-phase samples.")
        return 1

    result = PhaseAnalyzer().analyze(samples)

    if output_format == "json":
        print(json.dumps(_dump(result), indent=2, default=str))
    else:
        outcome = getattr(result.outcome, "value", result.outcome)
        lines = ["", "NETWORK CONNECTION-PHASE ANALYSIS", "=" * 60,
                 f"  Outcome: {outcome}",
                 f"  Samples: {result.sample_count}",
                 f"  TTFB-dominant phase: {result.ttfb_dominant_phase}"]
        for rec in result.recommendations:
            lines.append(f"  ! {rec}")
        for note in result.notes:
            lines.append(f"  - {note}")
        print("\n".join(lines))

    outcome = str(getattr(result.outcome, "value", result.outcome))
    return 1 if outcome not in ("ok", "insufficient_data") else 0


def run_network_use(args, output_format: str = "text") -> int:
    """`verdandi network use <snapshot.json>`.

    Input: {"snapshot": {...UseCounterSnapshot fields...},
            "retransmit_series": [...]?, "utilization_series": [...]?}
    """
    from Asgard.Verdandi.Network.models.network_models import UseCounterSnapshot
    from Asgard.Verdandi.Network.services.use_analyzer import UseAnalyzer

    data = _load_json(args.metrics_file)
    if data is None:
        return 1
    if not isinstance(data, dict):
        print("Error: Expected a JSON object.")
        return 1

    snapshot_data = data.get("snapshot", data)
    try:
        snapshot = (
            UseCounterSnapshot.model_validate(snapshot_data)
            if snapshot_data else None
        )
    except (TypeError, ValueError) as e:
        print(f"Error: Invalid snapshot input: {e}")
        return 1

    result = UseAnalyzer().analyze(
        snapshot,
        retransmit_series=data.get("retransmit_series"),
        utilization_series=data.get("utilization_series"),
    )

    if output_format == "json":
        print(json.dumps(_dump(result), indent=2, default=str))
    else:
        outcome = getattr(result.outcome, "value", result.outcome)
        lines = ["", "NETWORK USE-METHOD ANALYSIS", "=" * 60,
                 f"  Outcome: {outcome}",
                 f"  Overall severity: {result.overall_severity}"]
        for label, col in (("NIC", result.nic), ("TCP stack", result.tcp_stack),
                            ("DNS resolver", result.dns_resolver)):
            lines.append(
                f"  {label:12}: severity={col.severity} "
                f"saturated={col.saturated}"
            )
        for rec in result.recommendations:
            lines.append(f"  ! {rec}")
        print("\n".join(lines))

    return 1 if result.overall_severity in ("warning", "critical") else 0


def run_network_signature(args, output_format: str = "text") -> int:
    """`verdandi network signature <series.json>`.

    Input: {"rtt_series": [...], "hop_count_series": [...]?,
            "resolved_asn_series": [...]?, "tls_failure_series": [...]?,
            "one_way_latencies_ms": [...]?, "sample_interval_seconds": 60}
    """
    from Asgard.Verdandi.Network.services.signature_classifier import (
        SignatureClassifier,
    )

    data = _load_json(args.metrics_file)
    if data is None:
        return 1
    if not isinstance(data, dict):
        print("Error: Expected a JSON object.")
        return 1

    rtt_series = data.get("rtt_series")
    if not isinstance(rtt_series, list):
        print("Error: 'rtt_series' array is required.")
        return 1

    try:
        signature = SignatureClassifier().classify(
            rtt_series,
            hop_count_series=data.get("hop_count_series"),
            resolved_asn_series=data.get("resolved_asn_series"),
            tls_failure_series=data.get("tls_failure_series"),
            one_way_latencies_ms=data.get("one_way_latencies_ms"),
            sample_interval_seconds=float(
                data.get("sample_interval_seconds", 60.0)
            ),
        )
    except (TypeError, ValueError) as e:
        print(f"Error: {e}")
        return 1

    if output_format == "json":
        print(json.dumps(_dump(signature), indent=2, default=str))
    else:
        sig_type = getattr(signature.signature, "value", signature.signature)
        lines = ["", "NETWORK SIGNATURE CLASSIFICATION", "=" * 60,
                 f"  Signature:  {sig_type}",
                 f"  Confidence: {signature.confidence}",
                 f"  Details:    {signature.details}"]
        for note in signature.notes:
            lines.append(f"  - {note}")
        print("\n".join(lines))

    sig_type = str(getattr(signature.signature, "value", signature.signature))
    return 1 if sig_type not in ("none", "") else 0
