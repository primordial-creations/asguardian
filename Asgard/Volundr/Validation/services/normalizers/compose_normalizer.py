"""Tier 3 normalizer: Compose Specification dicts -> canonical Compose services."""

from typing import Any, Dict, List, Optional

from Asgard.Volundr.Validation.models.canonical_models import (
    CanonicalComposeService,
    CanonicalNetworkRule,
)


def _parse_port(entry: Any) -> CanonicalNetworkRule:
    if isinstance(entry, dict):
        # long syntax
        return CanonicalNetworkRule(
            source="compose",
            host_interface=entry.get("host_ip"),
            host_port=entry.get("published"),
            container_port=entry.get("target"),
        )
    text = str(entry)
    parts = text.split(":")
    if len(parts) == 3:
        return CanonicalNetworkRule(
            source="compose", host_interface=parts[0],
            host_port=parts[1], container_port=parts[2],
        )
    if len(parts) == 2:
        return CanonicalNetworkRule(
            source="compose", host_interface=None,
            host_port=parts[0], container_port=parts[1],
        )
    return CanonicalNetworkRule(source="compose", container_port=text)


def normalize_compose(
    compose: Dict[str, Any],
    file_path: Optional[str] = None,
) -> List[CanonicalComposeService]:
    """Normalize a compose dict into canonical services."""
    services: List[CanonicalComposeService] = []
    for name, svc in (compose.get("services") or {}).items():
        if not isinstance(svc, dict):
            continue
        services.append(CanonicalComposeService(
            name=name,
            image=svc.get("image"),
            privileged=svc.get("privileged"),
            network_mode=svc.get("network_mode"),
            ports=[_parse_port(p) for p in (svc.get("ports") or [])],
            read_only=svc.get("read_only"),
            cap_drop=svc.get("cap_drop"),
        ))
    return services


def has_obsolete_version_key(compose: Dict[str, Any]) -> bool:
    """The Compose Specification obsoleted the top-level version key."""
    return "version" in compose
