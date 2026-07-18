# 05 — Network: TTFB Phase Decomposition, USE for Cloud NICs, Anomaly Signatures, Baselines

## Research-Backed Rationale

All from **RESEARCH_11** unless noted:

- TTFB is composite; diagnosis requires splitting into **DNS → TCP (1 RTT) → TLS (2-RTT for 1.2, 1-RTT for 1.3, 0-RTT resumption) → request → response**. TLS 1.2→1.3 alone shifts p95 TTFB ~40% (318→194 ms in production LB data) — phase attribution is where the actionability lives.
- **Cloud latency baselines**: intra-AZ RTT 0.1–0.6 ms (p99.99 can hit 0.77–2.79 ms), inter-AZ 1–2 ms (sync replication breaks past 3–5 ms), cross-region governed by distance (≥ 200 ms US↔APAC), backbone packet loss < 0.01%, managed DNS < 100 ms public / < 2 ms in-VPC. These become named baseline profiles instead of the current one-size health bands.
- **USE method for virtualized networking**: utilization = bytes/pps vs instance quota; saturation = tx queue stops, `TcpExt_ListenOverflows`, conntrack fill; errors = retransmits, `pps_allowance_exceeded`, `bw_in_allowance_exceeded`, `linklocal_allowance_exceeded` (the silent 1,024-PPS AWS link-local DNS quota), `conntrack_allowance_exceeded`. Error baseline is zero.
- **Anomaly signatures**: packet loss/congestion → isolated retransmission-rate spike (throughput-correlated ⇒ link saturation); **BGP route change** → sustained step-function RTT shift (+ hop-count change); **DNS poisoning** → resolved-IP change to anomalous ASN + TLS handshake/cert failure spike.
- **Clock-skew guard** (also RESEARCH_14): one-way latency from span timestamps is corrupted by NTP drift; negative computed latency is the definitive skew signature, not a network anomaly.
- **RESEARCH_11 (pooling)**: bimodal latency with equal-variance peaks = connection-pool queueing; peak separation = mean queue wait (detection itself lives in Plans 03/07; Network exposes the transit-vs-queue split).

## Current State (`Asgard/Verdandi/Network/`)

- `latency_calculator.py`: RTT stats, jitter (mean absolute successive difference), packet loss, static health bands.
- `bandwidth_calculator.py`: Mbps + utilization vs capacity.
- `dns_calculator.py`: resolution stats, cache hit rate, per-hostname/server comparison.
- Nothing on phases, USE, retransmissions, step-change signatures, or baseline profiles.

## Target State

### A. Connection phase decomposition (`Network/services/phase_analyzer.py`, new)
Input: per-request phase timings (same shape as `Web/navigation_timing`; reuse): `{dns_ms, tcp_ms, tls_ms, request_ms, response_ms, ttfb_ms, protocol?, tls_version?}`.
- Per-phase p50/p75/p95 and share-of-TTFB attribution; dominant-phase verdict (`ttfb_dominant_phase`).
- Protocol expectation model: expected handshake RTTs = `1 (TCP) + {2 if TLS1.2, 1 if TLS1.3, 0 if resumed/QUIC}`; estimate base RTT from `tcp_ms`; flag `HANDSHAKE_OVERHEAD` when `tls_ms > expected_rtts × rtt_est × 1.5` and recommend TLS 1.3 / 0-RTT / HTTP/3 per RESEARCH_11's protocol table.
- Regression mode: phase-wise Welch+HL comparison vs baseline (delegates to Plan 03) so "TTFB regressed" resolves to "TLS phase regressed".

### B. Baseline topology profiles (`Network/models/network_models.py`)
`TopologyProfile` enum with expected-RTT envelopes:
| Profile | Expected RTT | Degraded above |
|---|---|---|
| INTRA_AZ | 0.1–0.6 ms | 1 ms (p99: 3 ms) |
| INTER_AZ | 1–2 ms | 3–5 ms (sync-replication risk note) |
| SAME_REGION_PUBLIC | 2–10 ms | 20 ms |
| CROSS_REGION | distance-based, user-supplied | 1.3× declared |
| INTERNET_EDGE | 20–150 ms | user percentile baseline |
`LatencyCalculator.analyze(samples, profile=...)` rates against the profile instead of the current absolute EXCELLENT/GOOD bands (kept as `LEGACY_DEFAULT`). Packet-loss baseline: backbone profiles expect < 0.01%; INTERNET_EDGE tolerates ≤ 1%.

### C. USE analyzer (`Network/services/use_analyzer.py`, new)
Input: counter snapshot(s) `{sent_bytes_ps, recv_bytes_ps, pps, instance_bw_limit, instance_pps_limit, tcp_retransmits, listen_overflows, conntrack_allowance_exceeded, pps_allowance_exceeded, bw_allowance_exceeded, linklocal_allowance_exceeded, active_connections, ephemeral_port_range}`.
Output `USEReport` with the three columns per resource (NIC / TCP stack / DNS resolver):
- Utilization: `bytes_ps / bw_limit`, `pps / pps_limit`, `active_conns / port_range`, `dns_qps / 1024` (AWS link-local quota).
- Saturation: listen overflows > 0, tx queue stops, conntrack table filling.
- Errors: **any** non-zero allowance-exceeded counter → CRITICAL with the RESEARCH_11 remediation text (e.g., linklocal → deploy node-local DNS cache); retransmit-rate spike correlated with utilization (r > 0.7) → link saturation, uncorrelated → path loss.

### D. Anomaly signature classifier (`Network/services/signature_classifier.py`, new)
Input: RTT series, optional `{hop_count, resolved_ip/asn, tls_failures}` series. Rules:
- `ROUTE_CHANGE`: CUSUM step in RTT (Plan 03) sustained ≥ 15 min, optionally hop-count delta → "BGP/path change".
- `DNS_HIJACK_SUSPECT`: resolved-IP/ASN change + TLS failure spike within 5 min.
- `CONGESTION`: retransmit spike + RTT variance growth, no step.
- `CLOCK_SKEW`: any negative one-way latency → data-quality flag, never an anomaly.

### E. DNS calculator upgrade (`dns_calculator.py`)
Add quota awareness (`queries_ps` vs 1024 link-local), NXDOMAIN/SERVFAIL/timeout rate columns (USE "errors"), and in-VPC vs public expectation bands (2 ms / 100 ms).

## Concrete File/Module Changes

| File | Change |
|---|---|
| `Network/models/network_models.py` | `ConnectionPhases`, `PhaseAnalysisResult`, `TopologyProfile`, `USEReport`, `NetworkSignature`. |
| `Network/services/phase_analyzer.py` (new) | §A. |
| `Network/services/use_analyzer.py` (new) | §C. |
| `Network/services/signature_classifier.py` (new) | §D. |
| `Network/services/latency_calculator.py` | Profile-relative rating; keep legacy bands. |
| `Network/services/dns_calculator.py` | Quota/error-rate columns, environment bands. |
| `cli/` | `verdandi network phases`, `verdandi network use`, `verdandi network classify`. |

## Phased Steps

1. Topology profiles + profile-relative latency rating.
2. Phase analyzer (reuse navigation-timing parsing; share model with Web plan 01 batch mode).
3. USE analyzer.
4. Signature classifier (depends on Plan 03 CUSUM).
5. DNS upgrade.

## Testing Notes

- L0 phases: TLS1.2 profile with rtt≈50 ms → tls_ms≈100 ms expected; 300 ms observed → `HANDSHAKE_OVERHEAD`; TLS1.3 equivalent passes.
- L0 profiles: 1.8 ms inter-AZ → GOOD; 4 ms → DEGRADED with sync-replication warning; same series under INTERNET_EDGE → GOOD.
- L0 USE: `linklocal_allowance_exceeded=3` → CRITICAL + DNS-cache remediation even with 5% utilization (errors trump utilization).
- L0 signatures: step series 20→45 ms sustained → ROUTE_CHANGE; negative one-way latency → CLOCK_SKEW flag only.
