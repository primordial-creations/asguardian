"""
Rule Registration - registers every compat rule id from the classification
table into the rule registry (metadata-only, stable ids, plan 02 contract).
"""

from Asgard.Forseti.Compatibility.models._compat_base_models import TierVerdict
from Asgard.Forseti.Compatibility.services._classification_helpers import COMPAT_RULE_TABLE
from Asgard.Forseti.Rules.models._rule_base_models import (
    RuleCategory,
    SchemaFormat,
    Severity,
)
from Asgard.Forseti.Rules.models.rule_models import RuleMeta
from Asgard.Forseti.Rules.services.rule_registry_service import default_registry

_PREFIX_FORMATS: dict[str, set[SchemaFormat]] = {
    "OAS": {SchemaFormat.OPENAPI},
    "AVRO": {SchemaFormat.AVRO},
    "PROTO": {SchemaFormat.PROTOBUF},
    "GQL": {SchemaFormat.GRAPHQL},
    "ASYNC": {SchemaFormat.ASYNCAPI},
    "JSON": {SchemaFormat.JSONSCHEMA},
    "COMPAT": {SchemaFormat.CONTRACT},
}


_PREFIX_NAMES: dict[str, str] = {
    "OAS": "oas",
    "AVRO": "avro",
    "PROTO": "proto",
    "GQL": "graphql",
    "ASYNC": "asyncapi",
    "JSON": "jsonschema",
    "COMPAT": "compat",
}


def registry_rule_id(change_rule_id: str) -> str:
    """Map a compat change rule id to its dotted registry id.

    'AVRO-FIELD-REMOVED' -> 'avro.compat.field-removed'
    """
    prefix, _, rest = change_rule_id.partition("-")
    name = _PREFIX_NAMES.get(prefix, prefix.lower())
    return f"{name}.compat.{rest.lower()}"


def register_compat_rules() -> None:
    """Idempotently register all compat rules in the default registry."""
    for change_rule_id, (violation, structural, semantic, base_severity, desc) in \
            COMPAT_RULE_TABLE.items():
        rule_id = registry_rule_id(change_rule_id)
        if default_registry.get(rule_id) is not None:
            continue
        prefix = change_rule_id.split("-", 1)[0]
        formats = _PREFIX_FORMATS.get(prefix, {SchemaFormat.CONTRACT})
        if structural == TierVerdict.FAIL:
            severity = Severity.ERROR
        elif TierVerdict.HAZARD in (structural, semantic) or \
                semantic == TierVerdict.FAIL:
            severity = Severity.WARNING
        else:
            severity = Severity.INFO
        default_registry.register(RuleMeta(
            rule_id=rule_id,
            formats=formats,
            severity=severity,
            category=RuleCategory.COMPATIBILITY,
            description=desc,
            rationale=f"Abstract violation: {violation.value}",
            core=structural == TierVerdict.FAIL,
            legacy_ids={change_rule_id},
        ))


register_compat_rules()
