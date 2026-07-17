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


def register_compat_rules() -> None:
    """Idempotently register all compat rules in the default registry."""
    for rule_id, (violation, structural, semantic, base_severity, desc) in \
            COMPAT_RULE_TABLE.items():
        if default_registry.get(rule_id) is not None:
            continue
        prefix = rule_id.split("-", 1)[0]
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
        ))


register_compat_rules()
