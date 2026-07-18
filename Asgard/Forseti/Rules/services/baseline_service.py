"""
Baseline Service - `.forseti-baseline.json` read/write/match.

A baseline accepts pre-existing lint findings so only net-new findings
are reported. Editing a baselined node revokes its exemption (Boy-Scout
rule) via a content hash of the offending node. Baselines apply to
static lint only — compatibility breaks use waivers instead ("you
cannot baseline away a runtime exception", DEEPTHINK_02).
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from Asgard.Forseti.Reporting.models.finding_models import Finding
from Asgard.Forseti.Rules.models.rule_models import BaselineEntry
from Asgard.Forseti.Rules.utilities.rule_utils import (
    compute_node_hash,
    finding_fingerprint,
    normalize_location,
)

BASELINE_FILENAME = ".forseti-baseline.json"


class BaselineService:
    """Create, load and apply finding baselines."""

    def __init__(self, baseline_path: Optional[str | Path] = None):
        self.baseline_path = Path(baseline_path) if baseline_path else Path(BASELINE_FILENAME)

    def load(self) -> list[BaselineEntry]:
        """Load baseline entries; empty when the file does not exist."""
        if not self.baseline_path.is_file():
            return []
        raw = json.loads(self.baseline_path.read_text(encoding="utf-8"))
        return [BaselineEntry(**entry) for entry in raw.get("entries", [])]

    def update(self, findings: list[Finding], document: Optional[Any] = None) -> int:
        """Write a baseline accepting all current active findings."""
        entries = [
            self._entry_for(finding, document)
            for finding in findings
            if not finding.suppressed
        ]
        payload = {
            "version": 1,
            "created": datetime.now(timezone.utc).isoformat(),
            "entries": [entry.model_dump() for entry in entries],
        }
        self.baseline_path.write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        return len(entries)

    def apply(
        self,
        findings: list[Finding],
        document: Optional[Any] = None,
    ) -> list[Finding]:
        """
        Mark baselined findings as suppressed (status preserved in output).

        A finding matches when its fingerprint is baselined AND, when a
        content hash was recorded, the node is unedited.
        """
        entries = {entry.fingerprint: entry for entry in self.load()}
        if not entries:
            return findings
        for finding in findings:
            fp = self._fingerprint(finding)
            entry = entries.get(fp)
            if entry is None:
                continue
            if entry.content_hash and document is not None:
                current = compute_node_hash(document, finding.coordinates.json_path)
                if current != entry.content_hash:
                    continue  # node edited -> exemption revoked
            finding.suppressed = True
            finding.suppression_reason = "baseline"
        return findings

    @staticmethod
    def _fingerprint(finding: Finding) -> str:
        return finding_fingerprint(
            finding.rule_id,
            finding.coordinates.file,
            finding.coordinates.json_path,
            finding.message,
        )

    def _entry_for(self, finding: Finding, document: Optional[Any]) -> BaselineEntry:
        content_hash = ""
        if document is not None:
            content_hash = compute_node_hash(document, finding.coordinates.json_path)
        return BaselineEntry(
            fingerprint=self._fingerprint(finding),
            rule_id=finding.rule_id,
            location=normalize_location(
                finding.coordinates.file, finding.coordinates.json_path
            ),
            content_hash=content_hash,
        )
