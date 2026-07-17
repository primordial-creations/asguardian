"""
Freya Config Models

FreyaConfig is the root model for `.freyarc` / `freya.yaml`: a single
declarative source of truth for crawl behaviour, budgets, and the CI
quality gate (Plan 06 §3.1). It composes existing models rather than
duplicating their fields.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from Asgard.Freya.Integration.models.integration_models import CrawlConfig
from Asgard.Freya.Scoring.models.scoring_models import GateConfig


class RouteBudgetRef(BaseModel):
    """A lightweight route -> archetype/budget reference.

    Full RouteBudget evaluation lives with Plan 03's Performance budget
    models; this is deliberately a thin, forward-compatible reference so
    `.freyarc` can name an archetype per route glob without this
    subpackage having to duplicate or import ahead of that plan landing.
    """
    archetype: Optional[str] = Field(
        default=None,
        description='Named budget archetype, e.g. "document", "transactional"'
    )
    overrides: Dict[str, float] = Field(
        default_factory=dict,
        description="Per-metric budget overrides for this route"
    )


class VisualConfig(BaseModel):
    """Visual-comparison settings surfaced in config."""
    allow_env_mismatch: bool = Field(
        default=False,
        description="Allow baseline comparison despite an environment mismatch "
                    "(result is flagged and capped, see BaselineConfig)"
    )


class FreyaConfig(BaseModel):
    """Root configuration model for `.freyarc` / `freya.yaml`."""

    wcag_level: str = Field(default="AA", description="Target WCAG conformance level")
    output_format: str = Field(default="text", description="Default CLI output format")

    crawl: Optional[CrawlConfig] = Field(
        default=None,
        description="Crawl configuration (start_url is required only when crawling)"
    )
    categories: List[str] = Field(
        default_factory=lambda: ["accessibility", "visual", "responsive"],
        description="Test categories to run"
    )
    budgets: Dict[str, RouteBudgetRef] = Field(
        default_factory=dict,
        description="Route-glob -> budget archetype references"
    )
    gate: GateConfig = Field(
        default_factory=GateConfig,
        description="CI quality gate configuration"
    )
    visual: VisualConfig = Field(
        default_factory=VisualConfig,
        description="Visual-comparison settings"
    )
