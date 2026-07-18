"""
Portfolio posture roll-up — Graph-Weighted Posture Index (DEEPTHINK_01).

For multi-artifact projects: per-resource risk is compounded from finding
probabilities with an epistemic floor, resources are weighted by graph
centrality (PageRank over declared cross-references; uniform when no
edges are known — zero-edge resources get near-zero weight as a dilution
defense), and system risk uses an L3-norm so the weakest link dominates:

    rho = (sum_i w_i * R_i^3) ** (1/3);   Posture = 100 * (1 - rho)

The three invalidating assumptions (ClickOps divergence, cross-domain
linkage, independence fallacy — DEEPTHINK_01 §3) are carried in the
result model; the temporal multiplier tau(t) is out of scope until
Volundr persists finding history.
"""

from typing import Dict, Iterable, List, Optional, Tuple

from Asgard.Volundr.Validation.models.rule_registry import (
    RuleRegistry,
    RuleSeverity,
    default_registry,
)
from Asgard.Volundr.Validation.models.score_models import PostureIndex
from Asgard.Volundr.Validation.models.validation_models import ValidationResult
from Asgard.Volundr.Validation.services.scoring_engine import ScoringEngine

#: Severity -> exploit-probability prior (CIS lateral-movement style).
SEVERITY_RISK: Dict[RuleSeverity, float] = {
    RuleSeverity.CRITICAL: 0.85,
    RuleSeverity.HIGH: 0.60,
    RuleSeverity.MEDIUM: 0.40,
    RuleSeverity.LOW: 0.15,
    RuleSeverity.INFO: 0.0,
}

#: Epistemic floor when only Volundr's static rules ran (DEEPTHINK_01 §1C).
DEFAULT_EPISTEMIC_FLOOR = 0.4
#: Floor when external tools (kubeconform/hadolint/...) also ran.
EXTERNAL_TOOLS_FLOOR = 0.2

#: Dilution defense: weight for resources with no graph edges.
ZERO_EDGE_WEIGHT = 0.05


def _pagerank(
    nodes: List[str], edges: List[Tuple[str, str]],
    damping: float = 0.85, iterations: int = 50,
) -> Dict[str, float]:
    """Simple PageRank over a directed reference graph."""
    n = len(nodes)
    rank = {node: 1.0 / n for node in nodes}
    out_links: Dict[str, List[str]] = {node: [] for node in nodes}
    for src, dst in edges:
        if src in out_links and dst in rank:
            out_links[src].append(dst)
    for _ in range(iterations):
        new_rank = {node: (1.0 - damping) / n for node in nodes}
        for src, targets in out_links.items():
            if not targets:
                continue
            share = damping * rank[src] / len(targets)
            for dst in targets:
                new_rank[dst] += share
        # Dangling mass distributed uniformly.
        dangling = damping * sum(
            rank[node] for node, targets in out_links.items() if not targets
        ) / n
        for node in nodes:
            new_rank[node] += dangling
        rank = new_rank
    return rank


def compute_posture_index(
    findings_by_resource: Dict[str, Iterable[ValidationResult]],
    edges: Optional[List[Tuple[str, str]]] = None,
    external_tools_ran: bool = False,
    registry: Optional[RuleRegistry] = None,
) -> PostureIndex:
    """Compute the GWPI over a set of logical resources.

    Args:
        findings_by_resource: resource name -> its surviving findings.
        edges: (from, to) declared cross-references (Service->Deployment
            selectors, Compose depends_on, TF depends_on, job needs).
        external_tools_ran: lowers the epistemic floor (uncertainty
            was bought down by independent tooling).
    """
    engine = ScoringEngine(registry=registry or default_registry())
    floor = EXTERNAL_TOOLS_FLOOR if external_tools_ran else DEFAULT_EPISTEMIC_FLOOR
    nodes = sorted(findings_by_resource)
    if not nodes:
        return PostureIndex(
            posture=100.0 * (1.0 - floor), system_risk=floor,
            epistemic_floor=floor,
        )

    # Resource risk: R_i = max(U, 1 - prod(1 - p_ij)).
    risks: Dict[str, float] = {}
    for name in nodes:
        survive = 1.0
        for result in findings_by_resource[name]:
            survive *= 1.0 - SEVERITY_RISK[engine.severity_of(result)]
        risks[name] = max(floor, 1.0 - survive)

    # Centrality weights; dilution defense for zero-edge resources.
    edges = edges or []
    connected = sorted(
        {node for edge in edges for node in edge if node in set(nodes)}
    )
    if connected:
        # PageRank ONLY over the connected subgraph (its ranks sum to 1);
        # disconnected resources get a fixed near-zero share so padding
        # the portfolio with clean, unreferenced resources cannot shift
        # weight away from the load-bearing ones (dilution defense).
        rank = _pagerank(connected, edges)
        raw = {
            node: (rank[node] if node in rank else ZERO_EDGE_WEIGHT / len(nodes))
            for node in nodes
        }
    else:
        raw = {node: 1.0 for node in nodes}
    total = sum(raw.values()) or 1.0
    weights = {node: value / total for node, value in raw.items()}

    # L3-norm weakest-link dominance.
    rho = sum(weights[n] * risks[n] ** 3 for n in nodes) ** (1.0 / 3.0)
    rho = min(1.0, max(0.0, rho))
    return PostureIndex(
        posture=round(100.0 * (1.0 - rho), 2),
        system_risk=round(rho, 4),
        resource_risks={k: round(v, 4) for k, v in risks.items()},
        resource_weights={k: round(v, 4) for k, v in weights.items()},
        epistemic_floor=floor,
    )
