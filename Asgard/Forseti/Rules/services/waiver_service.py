"""
Waiver Service - `.forseti-waivers.yaml` epoch waivers for compatibility rules.

Waivers apply ONLY to compatibility findings and are scoped to an exact
old->new version pair; once the epoch passes (or the waiver expires),
strict enforcement resumes (DEEPTHINK_02 Epoch Waiver Model).
"""

import fnmatch
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

from Asgard.Forseti.Rules.models.rule_models import WaiverEntry

WAIVERS_FILENAME = ".forseti-waivers.yaml"


class WaiverService:
    """Load and match compatibility waivers."""

    def __init__(self, waivers_path: Optional[str | Path] = None):
        self.waivers_path = Path(waivers_path) if waivers_path else Path(WAIVERS_FILENAME)

    def load(self) -> list[WaiverEntry]:
        """Load waiver entries; empty when the file does not exist."""
        if not self.waivers_path.is_file():
            return []
        raw = yaml.safe_load(self.waivers_path.read_text(encoding="utf-8")) or {}
        entries = raw.get("waivers", raw if isinstance(raw, list) else [])
        return [WaiverEntry(**entry) for entry in entries or []]

    def is_waived(
        self,
        rule: str,
        location: str,
        from_version: str,
        to_version: str,
        today: Optional[date] = None,
        waivers: Optional[list[WaiverEntry]] = None,
    ) -> Optional[WaiverEntry]:
        """
        Return the matching, unexpired waiver or None.

        A waiver matches only the exact from/to version pair it was
        granted for; rule and location support glob patterns.
        """
        today = today or date.today()
        for waiver in waivers if waivers is not None else self.load():
            if waiver.is_expired(today):
                continue
            if waiver.from_version != from_version or waiver.to_version != to_version:
                continue
            if not fnmatch.fnmatch(rule.lower(), waiver.rule.lower()):
                continue
            if not fnmatch.fnmatch(location, waiver.location):
                continue
            return waiver
        return None
