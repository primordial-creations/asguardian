"""
Reified Suppression Models.

Suppressions are the ONLY sanctioned way to relax a Volundr rule.
Each suppression is scoped (rule x target), justified (non-empty reason),
and optionally time-boxed (expires). Suppressed rules emit ZERO warnings
(warning-annihilation contract) and the rendered artifact carries a
machine-readable receipt.
"""

from datetime import date
from typing import List, Optional

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field, field_validator


class Suppression(BaseModel):
    """A single scoped, justified rule suppression."""

    rule: str = Field(description="Rule ID being suppressed (must match a known rule)")
    target: str = Field(description="Container/resource/step name or glob pattern")
    reason: str = Field(description="Non-empty human justification (ticket ref etc.)")
    expires: Optional[date] = Field(
        default=None, description="Expiry date; expired suppressions are hard errors"
    )

    @field_validator("rule", "target")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be a non-empty string")
        return v.strip()

    @field_validator("reason")
    @classmethod
    def _reason_required(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "suppression requires a non-empty reason (justification is mandatory)"
            )
        return v.strip()

    def is_expired(self, today: Optional[date] = None) -> bool:
        if self.expires is None:
            return False
        return (today or date.today()) > self.expires

    def receipt_annotation_key(self) -> str:
        """K8s annotation key receipt: volundr.asgard/suppress-<rule>."""
        return f"volundr.asgard/suppress-{self.rule}"

    def receipt_comment(self) -> str:
        """Comment receipt for Dockerfile/HCL/pipeline YAML."""
        return f"# volundr:suppress={self.rule} {self.reason}"


class SuppressionSet(BaseModel):
    """A collection of suppressions, loadable from YAML."""

    suppressions: List[Suppression] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, text: str) -> "SuppressionSet":
        """Parse a suppressions YAML document.

        Accepts either a top-level ``suppressions:`` list or a bare list.
        Missing rule/target/reason refuses to compile (ValidationError).
        """
        data = yaml.safe_load(text) or {}
        if isinstance(data, list):
            data = {"suppressions": data}
        return cls.model_validate(data)

    @classmethod
    def from_file(cls, path: str) -> "SuppressionSet":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_yaml(f.read())

    def __iter__(self):
        return iter(self.suppressions)

    def __len__(self) -> int:
        return len(self.suppressions)
