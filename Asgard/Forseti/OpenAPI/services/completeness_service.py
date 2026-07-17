"""
Completeness Service - 4-vector completeness matrix with gated maturity
tiers for OpenAPI specifications (plan 03, DEEPTHINK_08 / RESEARCH_09).
"""

import json
from pathlib import Path
from typing import Any

from Asgard.Forseti.OpenAPI.models.completeness_models import (
    CompletenessReport,
    MaturityTier,
)
from Asgard.Forseti.OpenAPI.services._completeness_helpers import (
    assign_tier,
    collect_signals,
    compute_vector,
    evaluate_gates,
)
from Asgard.Forseti.OpenAPI.utilities.openapi_utils import load_spec_file


class CompletenessService:
    """
    Assess OpenAPI spec completeness as a capability vector + maturity tier.

    Usage:
        service = CompletenessService()
        report = service.assess("openapi.yaml")
        print(report.tier, report.vector.experiential)
    """

    def assess(
        self,
        spec_path: str | Path,
        *,
        profile: str = "dx",
    ) -> CompletenessReport:
        """Assess a spec file. profile: 'dx' (default) or 'secops'."""
        spec_data = load_spec_file(Path(spec_path))
        report = self.assess_spec_data(spec_data, profile=profile)
        report.spec_path = str(spec_path)
        return report

    def assess_spec_data(
        self,
        spec_data: dict[str, Any],
        *,
        profile: str = "dx",
    ) -> CompletenessReport:
        """Assess parsed spec data."""
        if profile not in ("dx", "secops"):
            raise ValueError(f"Unknown completeness profile: {profile}")
        signals = collect_signals(spec_data)
        vector = compute_vector(spec_data, signals)
        gates = evaluate_gates(vector, signals, profile)
        tier, missing = assign_tier(gates)
        return CompletenessReport(
            profile=profile,
            vector=vector,
            tier=tier,
            gates=gates,
            signals=signals,
            missing_for_next_tier=missing,
        )

    def meets_tier(self, report: CompletenessReport, minimum: MaturityTier) -> bool:
        """Whether the report's tier meets a minimum tier."""
        return report.tier.rank >= minimum.rank

    def generate_report(
        self,
        report: CompletenessReport,
        format: str = "text",
    ) -> str:
        """Render a completeness report (text / json / markdown)."""
        if format == "json":
            return json.dumps(report.model_dump(mode="json"), indent=2)
        lines = self._text_lines(report, markdown=(format == "markdown"))
        return "\n".join(lines)

    @staticmethod
    def _text_lines(report: CompletenessReport, markdown: bool = False) -> list[str]:
        bullet = "- " if markdown else "  "
        header = "## " if markdown else ""
        lines = [
            f"{header}OpenAPI Completeness ({report.profile} profile)",
            f"{bullet}File: {report.spec_path or 'N/A'}",
            f"{bullet}Maturity tier: {report.tier.value.upper()}",
            "",
            f"{header}Vectors" if markdown else "Vectors:",
            f"{bullet}experiential: {report.vector.experiential:.0%}",
            f"{bullet}precision:    {report.vector.precision:.0%}",
            f"{bullet}operational:  {report.vector.operational:.0%}",
            f"{bullet}structural:   {report.vector.structural:.0%}",
            "",
            f"{header}Gates" if markdown else "Gates:",
        ]
        for gate in report.gates:
            mark = "PASS" if gate.passed else "FAIL"
            lines.append(f"{bullet}[{mark}] ({gate.tier.value}) {gate.name} "
                         f"— {gate.detail}")
        if report.missing_for_next_tier:
            lines.append("")
            lines.append("To reach the next tier:" if not markdown
                         else f"{header}To reach the next tier")
            for item in report.missing_for_next_tier:
                lines.append(f"{bullet}{item}")
        return lines
