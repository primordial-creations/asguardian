# 06 — Security Scoring & Severity Normalization

**Sources:** `_Docs/Research/Heimdall/Completed/DEEPTHINK_02` (aggregate scoring math), `DEEPTHINK_11` (cross-module severity normalization), `RESEARCH_13` (industry scoring: Veracode/SonarQube/Snyk, SAVD trending).

## Rationale

`Asgard/Heimdall/Security/models/security_models_findings.py::_calculate_security_score` is linear-subtractive (`100 − 25c − 10h − 5m − 1l`, floored at 0). DEEPTHINK_02 shows why this fails: it's size-blind (5 findings score the same in 10k and 500k LOC), gameable (fix cheap LOWs to offset a CRITICAL), saturates at 0 (score starvation kills motivation), and lets one noisy category (200 container LOWs from one Dockerfile) eclipse everything. Separately, each of ~30 security sub-modules picks its own severity labels — DEEPTHINK_11's "severity oracle drift" — and severity currently conflates impact with detection certainty.

## Target State

### A. Multiplicative Decay Score (replaces `_calculate_security_score`)

```
S        = max(1, sqrt(LOC / 1000))                       # size factor
N_crit   = Σ_c critical_c                                 # absolute — NOT normalized/capped
N_high   = Σ_c high_c
N_med_eff = (1/S) · Σ_c (medium_c)^0.8                    # per-category soft cap + size norm
N_low_eff = (1/S) · Σ_c (low_c)^0.8

Score = floor(100 · 0.40^N_crit · 0.80^N_high · 0.90^N_med_eff · 0.95^N_low_eff)
```

Design properties (DEEPTHINK_02 walkthroughs): 1 CRITICAL → 40 (failing but recoverable); 50 LOWs in one category @10k LOC → 69; same 50 spread across 10 categories → 56 (breadth punished more than depth); 50 LOWs in 1M LOC → 96. Score never reaches exactly 0 — every fix moves the number.

Rules bound to the formula:
- **Do not weight by scanner FP rates** ("discounted devastation" — a confirmed SQLi must never cost less than a leaked staging token). FP-proneness is a UI concern (triage queues), not math.
- Un-triaged findings count as TPs; marking false-positive in `Shared/Issues` immediately restores score (deliberate triage incentive).
- Findings suppressed by test-context (plan 08) or with bucket *Unlikely* are excluded from the score entirely; *Possible* findings count at 50% weight in the effective-count sums (severity itself never diluted — only aggregate hygiene counts).
- Documented accepted failure modes: score shock on first scan, LOC-inflation exploit, no exploit-chain modeling (verbatim list from DEEPTHINK_02 §"Deliberately Accepted").

Category set `c` = the Security sub-packages (Secrets, Injection/Taint, Crypto, Deps, Container, TLS, Headers, Auth, Access, Deserialization, SSRF, ReDoS, …) as registered in the Normalization Engine below.

### B. Central Severity Normalization Engine (DEEPTHINK_11)

New `Asgard/Heimdall/Security/normalization/`:
- `impact_matrix.py` — modules stop assigning free-text severities; they report `(mechanism_id, confidence, context_tags)` and the engine maps mechanism → severity via the universal CIA-impact criteria:
  - CRITICAL: unauthenticated host/database takeover, RCE, total auth bypass, validated cloud-admin credential.
  - HIGH: PII exfiltration, authenticated SQLi, stored XSS, path traversal read, scoped live 3rd-party token, container root+privileged.
  - MEDIUM: defense-in-depth bypass, reflected XSS, DoS, missing CSP in web context, internal test credentials.
  - LOW: hygiene, fingerprinting, missing header in API context, dummy keys.
- `equivalency.py` — the cross-module matrix (Secrets/SAST/SCA/Container-IaC/Auth-Headers rows) transcribed from DEEPTHINK_11 §Step 2 as data, unit-tested so a "HIGH" means the same blast radius everywhere.
- Severity/confidence are orthogonal: a low-confidence RCE stays CRITICAL severity with LOW confidence and is routed to review, not downgraded (DEEPTHINK_11 §2).
- **Context modifiers** (progressive contextualization): heuristic `is_api` inference (JSON responses/gRPC configs → downgrade browser-only header findings); repo-level declarations in `.heimdall.yml` (`tier: internal-service`, `data: non-sensitive`) scale context 0.5–1.0.
- **Effort tag, not severity input**: findings gain `estimated_effort: trivial|moderate|complex` for Return-on-Remediation sorting; never touches severity (DEEPTHINK_11 §4).

### C. Actionable Priority (report ordering)

```
priority = impact_points(severity) × confidence × context_modifier
           impact_points: CRITICAL 100, HIGH 80, MEDIUM 50, LOW 20
```
Reports/PR comments sort by priority; the DEEPTHINK_11 worked example (validated Twilio key P=80 outranks tentative RCE P=40) becomes a regression test.

### D. Trend metrics (RESEARCH_13)

`Reporting/History` snapshots add **SAVD** (findings per KLOC by severity) and store the new score; trend rendering emphasizes normalized density direction over absolute counts (time-series > snapshot).

## Concrete Changes

| File | Change |
|---|---|
| `Security/models/security_models_findings.py` | new `_calculate_security_score` (multiplicative); keep old value as `legacy_score` for one minor version |
| `Security/normalization/impact_matrix.py`, `equivalency.py`, `priority.py` | NEW engine |
| every `Security/*/services/*` scanner | emit `mechanism_id` + confidence; stop hardcoding severity strings (mechanical, per-module sweep) |
| `Bragi/Ratings/services/` | Security rating consumes normalized severities (mapping unchanged: worst-severity → letter) |
| `Bragi/QualityGate` | new optional condition `SECURITY_SCORE >= threshold` |
| `Reporting/History` | SAVD + score fields in `AnalysisSnapshot` |

## Phases & Testing

1. Engine + formula behind a feature flag (`--scoring=v2`), dual-report both scores for one release.
2. Module sweep to mechanism IDs (can proceed incrementally — unmapped modules pass through their legacy severity with a `normalized=false` marker).
3. Flip default; delete legacy after a deprecation cycle.

Tests: formula golden values (the four DEEPTHINK_02 walkthroughs, exact integers); monotonicity property tests (adding any finding never raises the score; fixing any finding never lowers it); equivalency-matrix consistency tests; priority-ordering regression (Twilio-vs-RCE); score-exclusion tests for test-context/Unlikely findings.
