"""
LLM Profile Service.

Lints a JSON Schema against LLM structured-output subsets (RESEARCH_05 §7).
Providers accept only restricted schema subsets for constrained decoding;
schemas outside the subset are rejected at request time or silently degraded.

Rule ids are stable and metadata-friendly (`llm.<provider>.<rule>`) so they
can be registered with the Forseti rule registry when that foundation lands.

Severity discipline: 'error' = the provider documents rejection of the
construct; 'warning' = the construct is ignored/degraded or close to a
documented limit (heuristic findings are never errors).
"""

from typing import Any, Callable, Optional

from Asgard.Forseti.JSONSchema.models.jsonschema_models import (
    LLMCompatibilityIssue,
    LLMCompatibilityResult,
)


class _ProviderProfile:
    """Declarative constraints for one provider's structured-output subset."""

    def __init__(
        self,
        name: str,
        require_root_object: bool,
        require_all_required: bool,
        require_closed_objects: bool,
        unsupported_keywords: dict[str, str],  # keyword -> severity
        max_nesting_depth: Optional[int],
        max_total_properties: Optional[int],
        max_enum_values: Optional[int],
        max_string_enum_chars: Optional[int] = None,
    ):
        self.name = name
        self.require_root_object = require_root_object
        self.require_all_required = require_all_required
        self.require_closed_objects = require_closed_objects
        self.unsupported_keywords = unsupported_keywords
        self.max_nesting_depth = max_nesting_depth
        self.max_total_properties = max_total_properties
        self.max_enum_values = max_enum_values
        self.max_string_enum_chars = max_string_enum_chars


_PROFILES: dict[str, _ProviderProfile] = {
    # OpenAI strict structured outputs: root object, every property required,
    # additionalProperties: false mandatory, limited keyword set, 5 nesting
    # levels / 100 properties / 500 enum values / 7500 enum chars documented.
    "openai": _ProviderProfile(
        name="openai",
        require_root_object=True,
        require_all_required=True,
        require_closed_objects=True,
        unsupported_keywords={
            "not": "error",
            "if": "error",
            "then": "error",
            "else": "error",
            "dependentRequired": "error",
            "dependentSchemas": "error",
            "patternProperties": "error",
            "unevaluatedProperties": "error",
            "unevaluatedItems": "error",
            "propertyNames": "error",
            "contains": "error",
            "minProperties": "warning",
            "maxProperties": "warning",
            "oneOf": "warning",  # anyOf is the supported union form
        },
        max_nesting_depth=5,
        max_total_properties=100,
        max_enum_values=500,
        max_string_enum_chars=7500,
    ),
    # Anthropic tool input schemas: permissive JSON Schema, but complex
    # conditional/negation constructs are not enforced by the model and
    # open objects invite hallucinated keys.
    "anthropic": _ProviderProfile(
        name="anthropic",
        require_root_object=True,
        require_all_required=False,
        require_closed_objects=False,
        unsupported_keywords={
            "not": "warning",
            "if": "warning",
            "then": "warning",
            "else": "warning",
            "unevaluatedProperties": "warning",
            "unevaluatedItems": "warning",
            "$dynamicRef": "warning",
        },
        max_nesting_depth=10,
        max_total_properties=None,
        max_enum_values=None,
    ),
    # Gemini responseSchema (OpenAPI 3.0 subset): no $ref/$defs, no
    # patternProperties, no conditional keywords, no additionalProperties.
    "gemini": _ProviderProfile(
        name="gemini",
        require_root_object=False,
        require_all_required=False,
        require_closed_objects=False,
        unsupported_keywords={
            "$ref": "error",
            "$defs": "error",
            "definitions": "error",
            "patternProperties": "error",
            "additionalProperties": "warning",
            "pattern": "warning",
            "not": "error",
            "if": "error",
            "then": "error",
            "else": "error",
            "oneOf": "warning",
            "allOf": "warning",
            "unevaluatedProperties": "error",
            "unevaluatedItems": "error",
            "prefixItems": "warning",
        },
        max_nesting_depth=None,
        max_total_properties=None,
        max_enum_values=None,
    ),
}

_SUBSCHEMA_MAP_KEYS = ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas")
_SUBSCHEMA_LIST_KEYS = ("allOf", "anyOf", "oneOf", "prefixItems")
_SUBSCHEMA_VALUE_KEYS = ("items", "additionalProperties", "contains", "not", "if", "then", "else",
                         "propertyNames", "unevaluatedProperties", "unevaluatedItems")


class LLMProfileService:
    """
    Checks JSON Schemas against LLM structured-output subsets.

    Usage:
        service = LLMProfileService()
        result = service.check(schema, provider="openai")
        if not result.is_compatible:
            for issue in result.issues:
                print(f"{issue.rule_id}: {issue.message}")
    """

    PROVIDERS = tuple(_PROFILES.keys())

    def check(self, schema: dict[str, Any], provider: str = "openai") -> LLMCompatibilityResult:
        """
        Check a schema against a provider's structured-output subset.

        Args:
            schema: Schema to lint.
            provider: One of 'openai', 'anthropic', 'gemini'.

        Returns:
            LLMCompatibilityResult; is_compatible is False when any
            error-severity issue was found.
        """
        profile = _PROFILES.get(provider.lower())
        if profile is None:
            raise ValueError(f"Unknown provider '{provider}'. Supported: {', '.join(_PROFILES)}")

        issues: list[LLMCompatibilityIssue] = []
        stats = {"total_properties": 0, "enum_values": 0, "enum_chars": 0}

        if profile.require_root_object and schema.get("type") != "object":
            issues.append(LLMCompatibilityIssue(
                rule_id=f"llm.{profile.name}.root-object",
                path="$",
                message=f"{profile.name} structured outputs require a root schema of type 'object' "
                        f"(got {schema.get('type')!r})",
                severity="error",
            ))

        self._walk(schema, "$", 1, profile, issues, stats)

        if profile.max_total_properties is not None and stats["total_properties"] > profile.max_total_properties:
            issues.append(LLMCompatibilityIssue(
                rule_id=f"llm.{profile.name}.max-properties",
                path="$",
                message=f"Schema declares {stats['total_properties']} properties; "
                        f"{profile.name} limit is {profile.max_total_properties}",
                severity="error",
            ))
        if profile.max_enum_values is not None and stats["enum_values"] > profile.max_enum_values:
            issues.append(LLMCompatibilityIssue(
                rule_id=f"llm.{profile.name}.max-enum-values",
                path="$",
                message=f"Schema declares {stats['enum_values']} enum values across all enums; "
                        f"{profile.name} limit is {profile.max_enum_values}",
                severity="error",
            ))
        if profile.max_string_enum_chars is not None and stats["enum_chars"] > profile.max_string_enum_chars:
            issues.append(LLMCompatibilityIssue(
                rule_id=f"llm.{profile.name}.max-enum-chars",
                path="$",
                message=f"String enum values total {stats['enum_chars']} characters; "
                        f"{profile.name} limit is {profile.max_string_enum_chars}",
                severity="warning",
            ))

        return LLMCompatibilityResult(
            provider=profile.name,
            is_compatible=not any(issue.severity == "error" for issue in issues),
            issues=issues,
        )

    def _walk(
        self,
        node: Any,
        path: str,
        depth: int,
        profile: _ProviderProfile,
        issues: list[LLMCompatibilityIssue],
        stats: dict[str, int],
    ) -> None:
        if not isinstance(node, dict):
            return

        if profile.max_nesting_depth is not None and depth > profile.max_nesting_depth:
            issues.append(LLMCompatibilityIssue(
                rule_id=f"llm.{profile.name}.max-nesting",
                path=path,
                message=f"Nesting depth {depth} exceeds {profile.name} limit of {profile.max_nesting_depth}",
                severity="error",
            ))
            return  # deeper findings would be redundant

        for keyword, severity in profile.unsupported_keywords.items():
            if keyword in node:
                issues.append(LLMCompatibilityIssue(
                    rule_id=f"llm.{profile.name}.{self._slug(keyword)}",
                    path=path,
                    message=f"Keyword '{keyword}' is not supported by {profile.name} structured outputs",
                    severity=severity,
                ))

        properties = node.get("properties")
        if isinstance(properties, dict):
            stats["total_properties"] += len(properties)
            if profile.require_all_required:
                required = set(node.get("required", []) or [])
                optional = [name for name in properties if name not in required]
                if optional:
                    issues.append(LLMCompatibilityIssue(
                        rule_id=f"llm.{profile.name}.all-required",
                        path=path,
                        message=f"All properties must be listed in 'required' for {profile.name} "
                                f"strict mode; optional: {sorted(optional)}",
                        severity="error",
                    ))
            if profile.require_closed_objects and node.get("additionalProperties") is not False:
                issues.append(LLMCompatibilityIssue(
                    rule_id=f"llm.{profile.name}.additional-properties",
                    path=path,
                    message=f"'additionalProperties: false' is required on every object for "
                            f"{profile.name} strict mode",
                    severity="error",
                ))

        enum = node.get("enum")
        if isinstance(enum, list):
            stats["enum_values"] += len(enum)
            stats["enum_chars"] += sum(len(v) for v in enum if isinstance(v, str))

        for key in _SUBSCHEMA_MAP_KEYS:
            if isinstance(node.get(key), dict):
                for name, sub in node[key].items():
                    child_depth = depth + 1 if key == "properties" else depth
                    self._walk(sub, f"{path}.{key}.{name}", child_depth, profile, issues, stats)
        for key in _SUBSCHEMA_LIST_KEYS:
            if isinstance(node.get(key), list):
                for i, sub in enumerate(node[key]):
                    self._walk(sub, f"{path}.{key}[{i}]", depth, profile, issues, stats)
        for key in _SUBSCHEMA_VALUE_KEYS:
            sub = node.get(key)
            if isinstance(sub, dict):
                child_depth = depth + 1 if key == "items" else depth
                self._walk(sub, f"{path}.{key}", child_depth, profile, issues, stats)
        if isinstance(node.get("items"), list):
            for i, sub in enumerate(node["items"]):
                self._walk(sub, f"{path}.items[{i}]", depth + 1, profile, issues, stats)

    @staticmethod
    def _slug(keyword: str) -> str:
        return keyword.replace("$", "").replace("_", "-").lower()


__all__ = ["LLMProfileService"]
