"""
Probe Planner Service - spec -> dependency-ordered ProbePlan.

Pure/offline: no network access. Turns an OpenAPI document into an
ordered request plan (RESTler-style, RESEARCH_15 simplified subset).
"""

from typing import Any

from Asgard.Forseti.LiveContract.models.live_contract_models import ProbePlan
from Asgard.Forseti.LiveContract.services._dependency_helpers import (
    extract_operations,
    topological_order,
)


class ProbePlannerService:
    """Builds a `ProbePlan` from a parsed OpenAPI document. No I/O."""

    def plan(self, openapi_doc: dict[str, Any]) -> ProbePlan:
        """Extract operations and order them producers-before-consumers."""
        operations = extract_operations(openapi_doc)
        ordered, dropped = topological_order(operations)
        return ProbePlan(operations=ordered, ignored_cycle_edges=dropped)
