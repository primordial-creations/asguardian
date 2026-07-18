"""
Rule Base Models - Core enums for the Forseti rule registry.

Severity is fixed and objective (DEEPTHINK_09): profiles and audiences may
filter *display*, but a rule's severity never changes per-audience.
"""

from enum import Enum


class Severity(str, Enum):
    """Fixed, objective severity for a finding (ERROR/WARNING/INFO/HINT)."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"

    @property
    def rank(self) -> int:
        """Numeric rank, higher = more severe."""
        return {"hint": 0, "info": 1, "warning": 2, "error": 3}[self.value]


class Target(str, Enum):
    """What a rule inspects."""

    SCHEMA = "schema"
    PAYLOAD = "payload"


class Cost(str, Enum):
    """Execution-cost class of a rule (DEEPTHINK_05)."""

    O1 = "O(1)"
    ON = "O(N)"
    NETWORK = "network"

    @property
    def rank(self) -> int:
        """Numeric rank, higher = more expensive."""
        return {"O(1)": 0, "O(N)": 1, "network": 2}[self.value]


class Confidence(str, Enum):
    """Whether a rule is exact or a heuristic guess."""

    DETERMINISTIC = "deterministic"
    HEURISTIC = "heuristic"


class SchemaFormat(str, Enum):
    """Schema/spec formats Forseti understands."""

    OPENAPI = "openapi"
    ASYNCAPI = "asyncapi"
    GRAPHQL = "graphql"
    JSONSCHEMA = "jsonschema"
    AVRO = "avro"
    PROTOBUF = "protobuf"
    SQL = "sql"
    CONTRACT = "contract"


class RuleCategory(str, Enum):
    """Rule category taxonomy."""

    STRUCTURE = "structure"
    SECURITY = "security"
    DOCS = "docs"
    STYLE = "style"
    COMPATIBILITY = "compatibility"
    SEMANTICS = "semantics"
    LIFECYCLE = "lifecycle"
