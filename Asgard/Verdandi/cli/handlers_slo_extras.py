"""
CLI handlers for the extended `slo` command-group surface:

- slo portfolio        cross-journey/service portfolio health scoring (CXI/SRI)
- slo budget-policy     error-budget policy tier evaluation
- slo dynamic-budget    complexity-aware dynamic latency budget evaluation

And `analyze self-slo` (Verdandi's own tool-quality self-SLIs).

All are thin wrappers over Asgard.Verdandi.SLO.services.*: JSON metrics file
in, JSON or human-readable text out.
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


def run_slo_portfolio(args, output_format: str = "text") -> int:
    """`verdandi slo portfolio <input.json>`.

    Input: {"journey_success_rates": {name: rate}, "business_weights": {}?,
            "service_burn_rates": {name: rate}, "centrality": {}?}
    Computes CXI if only journey data is given, SRI if only service data is
    given, or the combined portfolio score if both are present.
    """
    from Asgard.Verdandi.SLO.services.portfolio_scorer import PortfolioScorer

    data = _load_json(args.metrics_file)
    if data is None:
        return 1
    if not isinstance(data, dict):
        print("Error: Expected a JSON object.")
        return 1

    journeys = data.get("journey_success_rates")
    services = data.get("service_burn_rates")
    scorer = PortfolioScorer()
    try:
        if journeys and services:
            result = scorer.score_portfolio(
                journeys, services,
                business_weights=data.get("business_weights"),
                centrality=data.get("centrality"),
            )
        elif journeys:
            result = scorer.compute_cxi(
                journeys, business_weights=data.get("business_weights")
            )
        elif services:
            result = scorer.compute_sri(
                services, centrality=data.get("centrality")
            )
        else:
            print(
                "Error: Provide 'journey_success_rates' and/or "
                "'service_burn_rates'."
            )
            return 1
    except (TypeError, ValueError) as e:
        print(f"Error: {e}")
        return 1

    if output_format == "json":
        print(json.dumps(_dump(result), indent=2, default=str))
    else:
        lines = ["", "SLO PORTFOLIO HEALTH", "=" * 60]
        for field in ("cxi", "sri", "portfolio_score", "status"):
            if hasattr(result, field):
                lines.append(f"  {field}: {getattr(result, field)}")
        for note in getattr(result, "notes", []):
            lines.append(f"  - {note}")
        print("\n".join(lines))

    status = str(getattr(result, "status", "")).lower()
    return 1 if status in ("critical", "unhealthy") else 0


def run_slo_budget_policy(args, output_format: str = "text") -> int:
    """`verdandi slo budget-policy <input.json>`.

    Input: {"budget": {...ErrorBudget fields...},
            "incidents": [...]?, "slo": {...SLODefinition fields...}?}
    """
    from Asgard.Verdandi.SLO.models.slo_models import ErrorBudget, SLODefinition
    from Asgard.Verdandi.SLO.services.budget_policy import BudgetPolicyEngine

    data = _load_json(args.metrics_file)
    if data is None:
        return 1
    if not isinstance(data, dict) or "budget" not in data:
        print("Error: Expected a JSON object with a 'budget' field.")
        return 1

    try:
        budget = ErrorBudget.model_validate(data["budget"])
        slo = (
            SLODefinition.model_validate(data["slo"])
            if data.get("slo") else None
        )
    except (TypeError, ValueError) as e:
        print(f"Error: Invalid budget-policy input: {e}")
        return 1

    state = BudgetPolicyEngine().evaluate(
        budget, incidents=data.get("incidents"), slo=slo
    )

    if output_format == "json":
        print(json.dumps(_dump(state), indent=2, default=str))
    else:
        tier = getattr(state, "tier", None)
        tier_val = getattr(tier, "value", tier)
        lines = ["", "ERROR-BUDGET POLICY STATE", "=" * 60,
                 f"  Tier: {tier_val}"]
        for note in getattr(state, "notes", []):
            lines.append(f"  - {note}")
        print("\n".join(lines))

    tier_val = str(getattr(getattr(state, "tier", ""), "value", state))
    return 1 if "freeze" in tier_val.lower() or "exhaust" in tier_val.lower() else 0


def run_slo_dynamic_budget(args, output_format: str = "text") -> int:
    """`verdandi slo dynamic-budget <input.json>`.

    Input: {"base_ms": 50, "cost_per_unit_ms": 0.1, "cost_function": "linear"
            | "nlogn", "durations_ms": [...], "complexity_units": [...]}
    """
    from Asgard.Verdandi.SLO.services.dynamic_budget import (
        DynamicLatencyBudget,
        linear_cost,
        nlogn_cost,
    )

    data = _load_json(args.metrics_file)
    if data is None:
        return 1
    if not isinstance(data, dict):
        print("Error: Expected a JSON object.")
        return 1

    durations = data.get("durations_ms")
    units = data.get("complexity_units")
    if not isinstance(durations, list) or not isinstance(units, list):
        print("Error: 'durations_ms' and 'complexity_units' arrays are required.")
        return 1

    cost_fn = nlogn_cost if data.get("cost_function") == "nlogn" else linear_cost
    try:
        budget = DynamicLatencyBudget(
            base_ms=float(data.get("base_ms", 50.0)),
            cost_per_unit_ms=float(data.get("cost_per_unit_ms", 0.1)),
            cost_function=cost_fn,
        )
        results = budget.evaluate_batch(durations, units)
    except (TypeError, ValueError, ZeroDivisionError) as e:
        print(f"Error: {e}")
        return 1

    passed = sum(1 for r in results if r)
    total = len(results)

    if output_format == "json":
        print(json.dumps({
            "passed": passed, "total": total, "results": results,
        }, indent=2, default=str))
    else:
        lines = ["", "DYNAMIC LATENCY BUDGET EVALUATION", "=" * 60,
                 f"  Passed: {passed}/{total}"]
        print("\n".join(lines))

    return 0 if passed == total else 1


def run_self_slo(args, output_format: str = "text") -> int:
    """`verdandi analyze self-slo <run.json>`.

    Input: {...RunRecord fields...} (entities_submitted, entities_scored,
    valid_rejections, entities_failed, ...).
    """
    from Asgard.Verdandi.SLO.services.tool_slo import RunRecord, ToolSelfSLOCalculator

    data = _load_json(args.metrics_file)
    if data is None:
        return 1
    if not isinstance(data, dict):
        print("Error: Expected a JSON object of run-record fields.")
        return 1

    try:
        run = RunRecord.model_validate(data)
    except (TypeError, ValueError) as e:
        print(f"Error: Invalid run-record input: {e}")
        return 1

    result = ToolSelfSLOCalculator().analytical_yield(run)

    if output_format == "json":
        print(json.dumps(_dump(result), indent=2, default=str))
    else:
        lines = ["", "TOOL SELF-SLO: ANALYTICAL YIELD", "=" * 60,
                 f"  Value:  {result.value}",
                 f"  Target: {result.target}",
                 f"  Meets target: {result.meets_target}"]
        for e in result.integrity_errors:
            lines.append(f"  ! {e}")
        for note in result.notes:
            lines.append(f"  - {note}")
        print("\n".join(lines))

    if result.insufficient_data:
        return 0
    return 0 if result.meets_target else 1
