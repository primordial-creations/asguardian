"""
Portfolio Health Scorer

Dual-axis cross-service scoring (DEEPTHINK_11): never multiply internal
SLOs bottom-up (a portfolio-wide "reliability score" built by multiplying
per-service SLI fractions collapses to ~0 for any large portfolio and is
meaningless). Instead report two independent axes:

    CXI (Customer/Composite Experience Index): business-weighted average of
        critical-journey SLIs, measured at the edge (what customers feel).
    SRI (Service Reliability Index): centrality-weighted burn-rate score
        across the internal service graph (which services matter most to
        the journeys, weighted by how central they are).

Also flags "sandbagged"/uncalibrated SLOs: services whose 90-day achieved
performance is far beyond their declared target (an easy target that never
gets tested rather than a genuinely reliable service).

Centrality weighting is pluggable: pass a `centrality: dict[str, float] | None`
mapping service name -> weight. When None, all services are weighted
uniformly. This is designed to be wired to the APM service-map centrality
export (Asgard/Verdandi/APM/service_map_builder.py, Plan 08.5) once that
work lands; this module has no dependency on it and degrades gracefully.
"""

import math
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class PortfolioHealthResult(BaseModel):
    """Dual-axis portfolio health score."""

    cxi: Optional[float] = Field(
        default=None, description="Customer/Composite Experience Index (0-100), edge-weighted"
    )
    sri: Optional[float] = Field(
        default=None, description="Service Reliability Index (0-100), centrality-weighted burn"
    )
    cxi_journey_scores: Dict[str, float] = Field(
        default_factory=dict, description="Per-journey success rate used in CXI"
    )
    sri_service_scores: Dict[str, float] = Field(
        default_factory=dict, description="Per-service burn-derived score used in SRI"
    )
    centrality_used: Dict[str, float] = Field(
        default_factory=dict,
        description="Effective weights used for SRI (uniform default if no centrality supplied)",
    )
    used_default_centrality: bool = Field(
        default=True,
        description="True when no external centrality mapping was supplied (uniform weights)",
    )
    recommendations: List[str] = Field(default_factory=list)


class UncalibratedSLOFlag(BaseModel):
    """A flagged sandbagged/uncalibrated SLO."""

    service_name: str = Field(...)
    declared_target: float = Field(..., description="Declared SLO target percentage")
    achieved_pct: float = Field(..., description="Achieved performance over the evaluation window")
    nines_declared: float = Field(..., description="Number of 'nines' in the declared target")
    nines_achieved: float = Field(..., description="Number of 'nines' in the achieved performance")
    reason: str = Field(...)


def _nines(pct: float) -> float:
    """Number of 'nines' of a percentage (99.9 -> 3.0). Handles 100 as +inf-safe cap."""
    failure_fraction = max(1e-12, (100.0 - pct) / 100.0)
    return -math.log10(failure_fraction)


class PortfolioScorer:
    """
    Computes CXI/SRI dual-axis portfolio health and detects sandbagged SLOs.
    """

    #: Achieved performance must exceed the declared target by at least this
    #: many additional "nines" to be flagged as sandbagged (RESEARCH_13 /
    #: DEEPTHINK_11: an order of magnitude fewer failures than promised).
    SANDBAGGING_NINES_MARGIN = 1.0

    def compute_cxi(
        self,
        journey_success_rates: Dict[str, float],
        business_weights: Optional[Dict[str, float]] = None,
    ) -> PortfolioHealthResult:
        """
        Business-weighted average of critical-journey success rates
        (fractions in [0, 1]), measured at the edge.

        Args:
            journey_success_rates: journey name -> success rate fraction
            business_weights: Optional journey name -> business importance
                weight; defaults to uniform weighting when None or when a
                journey is missing a weight

        Returns:
            PortfolioHealthResult with cxi populated (sri left None)
        """
        if not journey_success_rates:
            return PortfolioHealthResult(
                recommendations=["No journeys supplied; CXI is undefined."]
            )

        weights = {
            name: (business_weights or {}).get(name, 1.0) for name in journey_success_rates
        }
        total_weight = sum(weights.values())
        if total_weight <= 0:
            total_weight = float(len(journey_success_rates))
            weights = {name: 1.0 for name in journey_success_rates}

        cxi = sum(
            journey_success_rates[name] * weights[name] for name in journey_success_rates
        ) / total_weight * 100.0

        return PortfolioHealthResult(
            cxi=round(cxi, 4),
            cxi_journey_scores={k: round(v * 100.0, 4) for k, v in journey_success_rates.items()},
        )

    def compute_sri(
        self,
        service_burn_rates: Dict[str, float],
        centrality: Optional[Dict[str, float]] = None,
    ) -> PortfolioHealthResult:
        """
        Centrality-weighted burn-rate score across the service graph.

        Each service's burn rate is converted to a bounded per-service score
        (100 = burning at the sustainable rate or better, decaying toward 0
        as burn rate increases), then averaged with centrality weights.

        Args:
            service_burn_rates: service name -> current burn rate (1.0 =
                sustainable)
            centrality: Optional service name -> centrality weight (e.g.
                from APM's service-map centrality export, Plan 08.5). When
                None, all services are weighted uniformly -- this is the
                pluggable hook for future APM wiring; SRI degrades
                gracefully to an unweighted average without it.

        Returns:
            PortfolioHealthResult with sri populated (cxi left None)
        """
        if not service_burn_rates:
            return PortfolioHealthResult(
                recommendations=["No services supplied; SRI is undefined."]
            )

        used_default = centrality is None
        weights = {
            name: (centrality or {}).get(name, 1.0) for name in service_burn_rates
        }
        total_weight = sum(weights.values())
        if total_weight <= 0:
            total_weight = float(len(service_burn_rates))
            weights = {name: 1.0 for name in service_burn_rates}
            used_default = True

        # Score decays as 100 / burn_rate for burn_rate >= 1.0 (sustainable
        # or better scores 100); burn_rate < 1.0 (under-spending budget)
        # also scores 100 -- we only penalize over-burning.
        per_service_scores = {
            name: (100.0 if br <= 1.0 else 100.0 / br)
            for name, br in service_burn_rates.items()
        }

        sri = sum(
            per_service_scores[name] * weights[name] for name in service_burn_rates
        ) / total_weight

        recommendations = []
        if used_default:
            recommendations.append(
                "No centrality mapping supplied; SRI uses uniform service weights. "
                "Wire APM's service-map centrality export (Plan 08.5) for "
                "topology-aware weighting."
            )

        return PortfolioHealthResult(
            sri=round(sri, 4),
            sri_service_scores={k: round(v, 4) for k, v in per_service_scores.items()},
            centrality_used={k: round(v, 6) for k, v in weights.items()},
            used_default_centrality=used_default,
            recommendations=recommendations,
        )

    def score_portfolio(
        self,
        journey_success_rates: Dict[str, float],
        service_burn_rates: Dict[str, float],
        business_weights: Optional[Dict[str, float]] = None,
        centrality: Optional[Dict[str, float]] = None,
    ) -> PortfolioHealthResult:
        """Combine compute_cxi() and compute_sri() into one dual-axis result."""
        cxi_result = self.compute_cxi(journey_success_rates, business_weights)
        sri_result = self.compute_sri(service_burn_rates, centrality)

        return PortfolioHealthResult(
            cxi=cxi_result.cxi,
            sri=sri_result.sri,
            cxi_journey_scores=cxi_result.cxi_journey_scores,
            sri_service_scores=sri_result.sri_service_scores,
            centrality_used=sri_result.centrality_used,
            used_default_centrality=sri_result.used_default_centrality,
            recommendations=cxi_result.recommendations + sri_result.recommendations,
        )

    def detect_uncalibrated_slos(
        self,
        declared_targets: Dict[str, float],
        achieved_pct_90d: Dict[str, float],
    ) -> List[UncalibratedSLOFlag]:
        """
        Flag sandbagged/uncalibrated SLOs: services whose 90-day achieved
        performance exceeds their declared target by >= 1 full order of
        magnitude of "nines" (e.g. declared 99% but achieving 99.99%+ --
        the target is too loose to ever be tested).

        Args:
            declared_targets: service name -> declared SLO target percentage
            achieved_pct_90d: service name -> achieved percentage over the
                trailing 90-day window

        Returns:
            List of UncalibratedSLOFlag for flagged services
        """
        flags: List[UncalibratedSLOFlag] = []
        for name, target in declared_targets.items():
            if name not in achieved_pct_90d:
                continue
            achieved = achieved_pct_90d[name]
            nines_declared = _nines(target)
            nines_achieved = _nines(achieved)
            if nines_achieved >= nines_declared + self.SANDBAGGING_NINES_MARGIN:
                flags.append(
                    UncalibratedSLOFlag(
                        service_name=name,
                        declared_target=target,
                        achieved_pct=achieved,
                        nines_declared=round(nines_declared, 4),
                        nines_achieved=round(nines_achieved, 4),
                        reason=(
                            f"Declared {target:g}% ({nines_declared:.2f} nines) but "
                            f"achieved {achieved:g}% ({nines_achieved:.2f} nines) over "
                            "90 days -- target may be sandbagged/uncalibrated."
                        ),
                    )
                )
        return flags
