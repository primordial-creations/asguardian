"""
Classification Helpers - per-rule metadata table for the compat engine.

Every compat rule id maps to an abstract violation, tier verdicts and a
base severity (0-100, DEEPTHINK_04). The table is also the source for
registering compat rules in the rule registry with stable ids.
"""

from typing import Optional

from Asgard.Forseti.Compatibility.models._compat_base_models import (
    AbstractViolation,
    Direction,
    TierVerdict,
)
from Asgard.Forseti.Compatibility.models.compat_models import ImpactAssessment, UnifiedChange
from Asgard.Forseti.Rules.models._rule_base_models import SchemaFormat

_V = AbstractViolation
_T = TierVerdict

# rule_id -> (violation, structural, semantic, base_severity, description)
COMPAT_RULE_TABLE: dict[str, tuple[AbstractViolation, TierVerdict, TierVerdict, int, str]] = {
    # ---- OpenAPI ----
    "OAS-PATH-REMOVED": (_V.ROUTING_BREAK, _T.FAIL, _T.FAIL, 25, "Endpoint removed"),
    "OAS-METHOD-REMOVED": (_V.ROUTING_BREAK, _T.FAIL, _T.FAIL, 25, "HTTP method removed"),
    "OAS-PARAM-REMOVED": (_V.INPUT_CONTRAVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 15,
                          "Request parameter removed"),
    "OAS-PARAM-REQUIRED-ADDED": (_V.INPUT_CONTRAVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 20,
                                 "Required parameter added"),
    "OAS-REQBODY-REMOVED": (_V.INPUT_CONTRAVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 15,
                            "Request body removed"),
    "OAS-REQBODY-REQUIRED-ADDED": (_V.INPUT_CONTRAVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 20,
                                   "Required request body added"),
    "OAS-REQ-FIELD-REQUIRED-ADDED": (_V.INPUT_CONTRAVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 15,
                                     "Request property became required"),
    "OAS-REQ-FIELD-REMOVED": (_V.OUTPUT_COVARIANCE_MODIFIED, _T.PASS, _T.HAZARD, 5,
                              "Optional request property removed (now ignored/rejected)"),
    "OAS-REQ-TYPE-CHANGED": (_V.TYPE_CONTRADICTION, _T.FAIL, _T.FAIL, 20,
                             "Request property type changed"),
    "OAS-REQ-ENUM-NARROWED": (_V.INPUT_CONTRAVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 15,
                              "Accepted enum value removed from request"),
    "OAS-RES-FIELD-REMOVED": (_V.OUTPUT_COVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 15,
                              "Response property removed"),
    "OAS-RES-FIELD-REQUIRED-REMOVED": (_V.OUTPUT_COVARIANCE_MODIFIED, _T.PASS, _T.HAZARD, 5,
                                       "Response property no longer guaranteed"),
    "OAS-RES-TYPE-CHANGED": (_V.TYPE_CONTRADICTION, _T.FAIL, _T.FAIL, 20,
                             "Response property type changed"),
    "OAS-RES-ENUM-EXTENDED": (_V.OUTPUT_COVARIANCE_MODIFIED, _T.PASS, _T.HAZARD, 5,
                              "New enum value emitted that old consumers never saw"),
    "OAS-RESPONSE-REMOVED": (_V.OUTPUT_COVARIANCE_VIOLATION, _T.HAZARD, _T.HAZARD, 8,
                             "Response status code removed"),
    "OAS-SCHEMA-REMOVED": (_V.OUTPUT_COVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 15,
                           "Component schema removed"),
    # ---- Avro ----
    "AVRO-TYPE-INCOMPATIBLE": (_V.TYPE_CONTRADICTION, _T.FAIL, _T.FAIL, 20,
                               "Reader/writer types not resolvable"),
    "AVRO-FIELD-REMOVED": (_V.OUTPUT_COVARIANCE_MODIFIED, _T.PASS, _T.HAZARD, 5,
                           "Writer field absent from reader (silently ignored)"),
    "AVRO-FIELD-ADDED-NO-DEFAULT": (_V.INPUT_CONTRAVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 20,
                                    "Reader field added without default"),
    "AVRO-FIELD-ADDED-DEFAULT": (_V.OUTPUT_COVARIANCE_MODIFIED, _T.PASS, _T.HAZARD, 4,
                                 "Field added with default: structural bridge, semantic hazard"),
    "AVRO-ENUM-SYMBOL-REMOVED": (_V.OUTPUT_COVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 15,
                                 "Enum symbol removed without enum default"),
    "AVRO-ENUM-SYMBOL-REMOVED-DEFAULT": (_V.OUTPUT_COVARIANCE_MODIFIED, _T.PASS, _T.HAZARD, 5,
                                         "Enum symbol removed; resolved by enum default"),
    "AVRO-ENUM-ORDER-CHANGED": (_V.OUTPUT_COVARIANCE_MODIFIED, _T.PASS, _T.HAZARD, 3,
                                "Enum symbol order changed"),
    "AVRO-NAME-CHANGED": (_V.TYPE_CONTRADICTION, _T.FAIL, _T.FAIL, 20,
                          "Named type renamed without alias"),
    "AVRO-FIXED-SIZE-CHANGED": (_V.TYPE_CONTRADICTION, _T.FAIL, _T.FAIL, 20,
                                "Fixed size changed"),
    "AVRO-UNION-INCOMPATIBLE": (_V.TYPE_CONTRADICTION, _T.FAIL, _T.FAIL, 20,
                                "Writer union branch has no compatible reader branch"),
    # ---- Protobuf ----
    "PROTO-MESSAGE-REMOVED": (_V.ROUTING_BREAK, _T.FAIL, _T.FAIL, 20, "Message removed"),
    "PROTO-FIELD-REMOVED-UNRESERVED": (_V.OUTPUT_COVARIANCE_MODIFIED, _T.PASS, _T.FAIL, 12,
                                       "Field removed without reserving its tag"),
    "PROTO-FIELD-REMOVED-RESERVED": (_V.OUTPUT_COVARIANCE_MODIFIED, _T.PASS, _T.HAZARD, 4,
                                     "Field removed with tag properly reserved"),
    "PROTO-FIELD-TYPE-CHANGED": (_V.TYPE_CONTRADICTION, _T.FAIL, _T.FAIL, 20,
                                 "Field type changed across wire-type groups"),
    "PROTO-FIELD-TYPE-WIRE-COMPATIBLE": (_V.OUTPUT_COVARIANCE_MODIFIED, _T.PASS, _T.HAZARD, 6,
                                         "Field type changed within a wire-type group"),
    "PROTO-FIELD-RENAMED": (_V.OUTPUT_COVARIANCE_MODIFIED, _T.PASS, _T.HAZARD, 5,
                            "Field renamed: wire-safe, breaks source/JSON mapping"),
    "PROTO-FIELD-LABEL-CHANGED": (_V.TYPE_CONTRADICTION, _T.FAIL, _T.FAIL, 15,
                                  "Field label changed (repeated <-> singular)"),
    "PROTO-FIELD-LABEL-MODIFIED": (_V.OUTPUT_COVARIANCE_MODIFIED, _T.PASS, _T.HAZARD, 5,
                                   "Field label changed (optional <-> required)"),
    "PROTO-FIELD-NUMBER-CHANGED": (_V.TYPE_CONTRADICTION, _T.FAIL, _T.FAIL, 25,
                                   "Field number changed (tag anchoring violated)"),
    "PROTO-RESERVED-REUSED": (_V.TYPE_CONTRADICTION, _T.FAIL, _T.FAIL, 25,
                              "Reserved tag/name reused"),
    "PROTO-ENUM-REMOVED": (_V.ROUTING_BREAK, _T.FAIL, _T.FAIL, 20, "Enum removed"),
    "PROTO-ENUM-VALUE-REMOVED": (_V.OUTPUT_COVARIANCE_VIOLATION, _T.PASS, _T.FAIL, 12,
                                 "Enum value removed without reservation"),
    "PROTO-ENUM-VALUE-REMOVED-RESERVED": (_V.OUTPUT_COVARIANCE_MODIFIED, _T.PASS, _T.HAZARD, 4,
                                          "Enum value removed with reservation"),
    "PROTO-ENUM-VALUE-NUMBER-CHANGED": (_V.TYPE_CONTRADICTION, _T.FAIL, _T.FAIL, 20,
                                        "Enum value number changed"),
    "PROTO-SERVICE-REMOVED": (_V.ROUTING_BREAK, _T.FAIL, _T.FAIL, 25, "Service removed"),
    "PROTO-RPC-REMOVED": (_V.ROUTING_BREAK, _T.FAIL, _T.FAIL, 25,
                          "RPC removed (12 UNIMPLEMENTED)"),
    "PROTO-RPC-TYPE-CHANGED": (_V.TYPE_CONTRADICTION, _T.FAIL, _T.FAIL, 20,
                               "RPC input/output type changed"),
    "PROTO-RPC-STREAMING-CHANGED": (_V.ROUTING_BREAK, _T.FAIL, _T.FAIL, 25,
                                    "RPC streaming mode changed (irrecoverable)"),
    # ---- GraphQL ----
    "GQL-TYPE-REMOVED": (_V.ROUTING_BREAK, _T.FAIL, _T.FAIL, 20, "Type removed"),
    "GQL-FIELD-REMOVED": (_V.INPUT_CONTRAVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 15,
                          "Field removed: previously valid queries now rejected"),
    "GQL-FIELD-TYPE-CHANGED": (_V.TYPE_CONTRADICTION, _T.FAIL, _T.FAIL, 15,
                               "Field type changed"),
    "GQL-ENUM-VALUE-REMOVED": (_V.INPUT_CONTRAVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 12,
                               "Enum value removed"),
    "GQL-ENUM-VALUE-ADDED": (_V.OUTPUT_COVARIANCE_MODIFIED, _T.PASS, _T.HAZARD, 3,
                             "Enum value added: old consumers never saw it"),
    "GQL-ARG-REMOVED": (_V.INPUT_CONTRAVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 12,
                        "Field argument removed"),
    "GQL-ARG-REQUIRED-ADDED": (_V.INPUT_CONTRAVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 15,
                               "Required argument added"),
    "GQL-INPUT-FIELD-REMOVED": (_V.INPUT_CONTRAVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 12,
                                "Input field removed"),
    "GQL-INPUT-FIELD-REQUIRED-ADDED": (_V.INPUT_CONTRAVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 15,
                                       "Required input field added"),
    "GQL-UNION-MEMBER-REMOVED": (_V.OUTPUT_COVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 12,
                                 "Union member removed"),
    # ---- AsyncAPI ----
    "ASYNC-CHANNEL-REMOVED": (_V.ROUTING_BREAK, _T.FAIL, _T.FAIL, 25, "Channel removed"),
    "ASYNC-OPERATION-REMOVED": (_V.ROUTING_BREAK, _T.FAIL, _T.FAIL, 20,
                                "Publish/subscribe operation removed"),
    "ASYNC-MSG-FIELD-REMOVED": (_V.OUTPUT_COVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 15,
                                "Published message property removed"),
    "ASYNC-MSG-FIELD-REQUIRED-ADDED": (_V.INPUT_CONTRAVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 15,
                                       "Subscribed message property became required"),
    "ASYNC-MSG-TYPE-CHANGED": (_V.TYPE_CONTRADICTION, _T.FAIL, _T.FAIL, 20,
                               "Message payload property type changed"),
    # ---- JSON Schema (generic) ----
    "JSON-FIELD-REMOVED": (_V.OUTPUT_COVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 15,
                           "Schema property removed"),
    "JSON-FIELD-REQUIRED-ADDED": (_V.INPUT_CONTRAVARIANCE_VIOLATION, _T.FAIL, _T.FAIL, 15,
                                  "Schema property became required"),
    "JSON-TYPE-CHANGED": (_V.TYPE_CONTRADICTION, _T.FAIL, _T.FAIL, 20,
                          "Schema property type changed"),
    # ---- Engine-level ----
    "COMPAT-PARSE-ERROR": (_V.TYPE_CONTRADICTION, _T.FAIL, _T.FAIL, 100,
                           "Specification could not be parsed"),
}


def make_change(
    rule_id: str,
    fmt: SchemaFormat,
    direction: Direction,
    location: str,
    message: str,
    *,
    old_value: Optional[object] = None,
    new_value: Optional[object] = None,
    blast_radius: int = 1,
    mitigation: Optional[str] = None,
) -> UnifiedChange:
    """Build a UnifiedChange with classification looked up from the table."""
    violation, structural, semantic, base_severity, _desc = COMPAT_RULE_TABLE[rule_id]
    return UnifiedChange(
        rule_id=rule_id,
        format=fmt,
        direction=direction,
        abstract_violation=violation,
        location=location,
        message=message,
        old_value=old_value,
        new_value=new_value,
        impact=ImpactAssessment(structural=structural, semantic=semantic),
        base_severity=base_severity,
        blast_radius=max(1, blast_radius),
        mitigation=mitigation,
    )
