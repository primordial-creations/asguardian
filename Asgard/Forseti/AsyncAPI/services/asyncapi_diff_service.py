"""
AsyncAPI Diff Service - channel/operation/payload compatibility diffing
(plan 01, phase 3). AsyncAPI previously had no compatibility checking.

Direction semantics per DEEPTHINK_01: publish operations describe what the
application emits (OUTPUT, covariant); subscribe operations describe what
it accepts (INPUT, contravariant).
"""

from pathlib import Path
from typing import Any

from Asgard.Forseti.Compatibility.models._compat_base_models import Direction
from Asgard.Forseti.Compatibility.models.compat_models import UnifiedChange
from Asgard.Forseti.Compatibility.services._classification_helpers import make_change
from Asgard.Forseti.Compatibility.utilities.compat_utils import (
    dedup_changes,
    diff_schema_pair,
    load_document,
    make_ref_resolver,
)
from Asgard.Forseti.Rules.models._rule_base_models import SchemaFormat

FMT = SchemaFormat.ASYNCAPI

_OPERATION_DIRECTIONS = {
    "publish": Direction.OUTPUT,
    "subscribe": Direction.INPUT,
}


class AsyncAPIDiffService:
    """
    Service for diffing two AsyncAPI documents for breaking changes.

    Usage:
        service = AsyncAPIDiffService()
        changes = service.diff("old.yaml", "new.yaml")
    """

    def diff(self, old_path: str | Path, new_path: str | Path) -> list[UnifiedChange]:
        """Diff two AsyncAPI spec files."""
        old_spec = load_document(old_path)
        new_spec = load_document(new_path)
        return self.diff_specs(old_spec or {}, new_spec or {})

    def diff_specs(self, old_spec: dict[str, Any],
                   new_spec: dict[str, Any]) -> list[UnifiedChange]:
        """Diff two parsed AsyncAPI documents."""
        changes: list[UnifiedChange] = []
        old_resolver = make_ref_resolver(old_spec)
        new_resolver = make_ref_resolver(new_spec)
        old_channels = old_spec.get("channels") or {}
        new_channels = new_spec.get("channels") or {}

        for channel in sorted(set(old_channels) - set(new_channels)):
            changes.append(make_change(
                "ASYNC-CHANNEL-REMOVED", FMT, Direction.OUTPUT,
                f"channels/{channel}",
                f"Channel '{channel}' was removed", old_value=channel,
                mitigation="Immutable event logs outlive schemas: keep the "
                           "channel or drain all consumers first",
            ))

        for channel in sorted(set(old_channels) & set(new_channels)):
            old_channel = old_channels[channel] or {}
            new_channel = new_channels[channel] or {}
            for op_name, direction in _OPERATION_DIRECTIONS.items():
                if op_name in old_channel and op_name not in new_channel:
                    changes.append(make_change(
                        "ASYNC-OPERATION-REMOVED", FMT, direction,
                        f"channels/{channel}/{op_name}",
                        f"Operation '{op_name}' removed from channel '{channel}'",
                        old_value=op_name,
                    ))
                    continue
                if op_name in old_channel and op_name in new_channel:
                    old_payload = self._payload(old_channel[op_name], old_resolver)
                    new_payload = self._payload(new_channel[op_name], new_resolver)
                    if isinstance(old_payload, dict) and isinstance(new_payload, dict):
                        changes.extend(diff_schema_pair(
                            f"channels/{channel}/{op_name}/message/payload",
                            old_payload, new_payload, direction, FMT,
                            old_resolver=old_resolver, new_resolver=new_resolver,
                        ))
        return dedup_changes(changes)

    @staticmethod
    def _payload(operation: dict[str, Any], resolver: Any) -> Any:
        message = (operation or {}).get("message") or {}
        ref = message.get("$ref")
        if isinstance(ref, str):
            message = resolver(ref) or {}
        payload = message.get("payload") or {}
        ref = payload.get("$ref") if isinstance(payload, dict) else None
        if isinstance(ref, str):
            payload = resolver(ref) or {}
        return payload
