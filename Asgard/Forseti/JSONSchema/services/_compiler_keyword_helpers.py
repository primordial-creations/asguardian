"""
Compiler Keyword Helpers.

Per-dialect keyword -> checker-factory registry for the compile-then-run
JSON Schema validation engine. Each factory receives the raw subschema, the
compile context and the current base URI, and returns a checker closure
(or None when the keyword contributes nothing).

Checker signature:
    check(value, path, errors, scope, ann) -> None

- ``scope`` is the per-run RunScope (dynamic $dynamicRef stack).
- ``ann`` is the Annotations object shared by all in-place applicators at the
  same instance location (needed for unevaluatedProperties/unevaluatedItems).
"""

import re
from enum import Enum
from typing import Any, Callable, Optional

from Asgard.Forseti.JSONSchema.models.jsonschema_models import JSONSchemaValidationError
from Asgard.Forseti.JSONSchema.services._ref_resolver_helpers import RefResolutionError


class SchemaDialect(str, Enum):
    """Supported JSON Schema dialects."""

    DRAFT4 = "draft-04"
    DRAFT6 = "draft-06"
    DRAFT7 = "draft-07"
    DRAFT2019 = "2019-09"
    DRAFT2020 = "2020-12"


def detect_dialect(schema: Any, default: "SchemaDialect" = SchemaDialect.DRAFT2020) -> SchemaDialect:
    """Detect the dialect from a schema's $schema URI, falling back to default."""
    if isinstance(schema, dict):
        uri = schema.get("$schema", "")
        if isinstance(uri, str) and uri:
            return dialect_from_uri(uri, default)
    return default


def dialect_from_uri(uri: str, default: SchemaDialect = SchemaDialect.DRAFT2020) -> SchemaDialect:
    """Map a $schema URI (or shorthand) to a SchemaDialect."""
    lowered = uri.lower()
    if "2020-12" in lowered:
        return SchemaDialect.DRAFT2020
    if "2019-09" in lowered:
        return SchemaDialect.DRAFT2019
    if "draft-07" in lowered or lowered == "draft7":
        return SchemaDialect.DRAFT7
    if "draft-06" in lowered or lowered == "draft6":
        return SchemaDialect.DRAFT6
    if "draft-04" in lowered or lowered == "draft4":
        return SchemaDialect.DRAFT4
    return default


class RunScope:
    """Per-validation-run state: dynamic scope stack for $dynamicRef."""

    __slots__ = ("dynamic_stack", "depth")

    def __init__(self) -> None:
        self.dynamic_stack: list[str] = []
        self.depth = 0


class Annotations:
    """Evaluated-property / evaluated-item annotations at one instance location."""

    __slots__ = ("props", "items")

    def __init__(self) -> None:
        self.props: set[str] = set()
        self.items: set[int] = set()

    def merge(self, other: "Annotations") -> None:
        self.props |= other.props
        self.items |= other.items


class CompiledNode:
    """A compiled subschema: an ordered list of keyword checkers."""

    __slots__ = ("checkers", "boolean", "resource_uri")

    def __init__(self, resource_uri: str = "") -> None:
        self.checkers: list[tuple[str, Callable]] = []
        self.boolean: Optional[bool] = None  # set for boolean schemas
        self.resource_uri = resource_uri

    def run(
        self,
        value: Any,
        path: str,
        errors: list,
        scope: RunScope,
        ann: Optional[Annotations] = None,
    ) -> bool:
        """Validate value; append errors; return True when valid."""
        if self.boolean is not None:
            if self.boolean:
                return True
            errors.append(JSONSchemaValidationError(
                path=path, message="Schema is false, no value is valid", constraint="false_schema"))
            return False
        if ann is None:
            ann = Annotations()
        scope.depth += 1
        if scope.depth > 150:
            scope.depth -= 1
            errors.append(JSONSchemaValidationError(
                path=path, message="Maximum validation depth exceeded (possible unresolvable cycle)",
                constraint="max_depth"))
            return False
        pushed = False
        if self.resource_uri and (not scope.dynamic_stack or scope.dynamic_stack[-1] != self.resource_uri):
            scope.dynamic_stack.append(self.resource_uri)
            pushed = True
        before = len(errors)
        try:
            for _keyword, checker in self.checkers:
                checker(value, path, errors, scope, ann)
        finally:
            if pushed:
                scope.dynamic_stack.pop()
            scope.depth -= 1
        return len(errors) == before


def _err(path: str, message: str, constraint: str, value: Any = None, expected: Any = None) -> JSONSchemaValidationError:
    return JSONSchemaValidationError(path=path, message=message, constraint=constraint, value=value, expected=expected)


def json_equal(a: Any, b: Any) -> bool:
    """JSON-value equality: bools are distinct from numbers, 1 == 1.0."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(json_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(json_equal(x, y) for x, y in zip(a, b))
    return bool(a == b)


def check_json_type(value: Any, expected_type: str) -> bool:
    """Spec-correct JSON type check (1.0 is a valid integer; bools are not numbers)."""
    if expected_type == "null":
        return value is None
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "integer":
        if isinstance(value, bool):
            return False
        return isinstance(value, int) or (isinstance(value, float) and value.is_integer())
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    return False


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# Keyword factories. Signature: factory(schema, ctx, base_uri) -> checker|None
# ``ctx`` is a SchemaCompilerContext (see schema_compiler_service).
# ---------------------------------------------------------------------------

def _f_type(schema, ctx, base_uri):
    expected = schema["type"]
    if isinstance(expected, list):
        def check(value, path, errors, scope, ann):
            if not any(check_json_type(value, t) for t in expected):
                errors.append(_err(path, f"Value type must be one of: {expected}", "type", value, expected))
        return check

    def check(value, path, errors, scope, ann):
        if not check_json_type(value, expected):
            errors.append(_err(path, f"Expected type '{expected}', got '{type(value).__name__}'", "type", value, expected))
    return check


def _f_enum(schema, ctx, base_uri):
    allowed = schema["enum"]

    def check(value, path, errors, scope, ann):
        if not any(json_equal(value, item) for item in allowed):
            errors.append(_err(path, f"Value must be one of: {allowed}", "enum", value, allowed))
    return check


def _f_const(schema, ctx, base_uri):
    expected = schema["const"]

    def check(value, path, errors, scope, ann):
        if not json_equal(value, expected):
            errors.append(_err(path, f"Value must be {expected}", "const", value, expected))
    return check


def _f_multiple_of(schema, ctx, base_uri):
    factor = schema["multipleOf"]

    def check(value, path, errors, scope, ann):
        if not _is_number(value):
            return
        try:
            quotient = value / factor
        except (ZeroDivisionError, OverflowError):
            return
        if abs(quotient - round(quotient)) > 1e-9:
            errors.append(_err(path, f"Value {value} is not a multiple of {factor}", "multipleOf", value, factor))
    return check


def _f_minimum(schema, ctx, base_uri):
    limit = schema["minimum"]
    exclusive = schema.get("exclusiveMinimum") is True  # draft-04 boolean form

    def check(value, path, errors, scope, ann):
        if not _is_number(value):
            return
        if exclusive:
            if value <= limit:
                errors.append(_err(path, f"Value {value} must be greater than {limit}", "exclusiveMinimum", value, limit))
        elif value < limit:
            errors.append(_err(path, f"Value {value} is less than minimum {limit}", "minimum", value, limit))
    return check


def _f_maximum(schema, ctx, base_uri):
    limit = schema["maximum"]
    exclusive = schema.get("exclusiveMaximum") is True

    def check(value, path, errors, scope, ann):
        if not _is_number(value):
            return
        if exclusive:
            if value >= limit:
                errors.append(_err(path, f"Value {value} must be less than {limit}", "exclusiveMaximum", value, limit))
        elif value > limit:
            errors.append(_err(path, f"Value {value} exceeds maximum {limit}", "maximum", value, limit))
    return check


def _f_exclusive_minimum(schema, ctx, base_uri):
    limit = schema["exclusiveMinimum"]
    if isinstance(limit, bool):
        return None  # draft-04 form handled by _f_minimum

    def check(value, path, errors, scope, ann):
        if _is_number(value) and value <= limit:
            errors.append(_err(path, f"Value {value} must be greater than {limit}", "exclusiveMinimum", value, limit))
    return check


def _f_exclusive_maximum(schema, ctx, base_uri):
    limit = schema["exclusiveMaximum"]
    if isinstance(limit, bool):
        return None

    def check(value, path, errors, scope, ann):
        if _is_number(value) and value >= limit:
            errors.append(_err(path, f"Value {value} must be less than {limit}", "exclusiveMaximum", value, limit))
    return check


def _f_min_length(schema, ctx, base_uri):
    limit = schema["minLength"]

    def check(value, path, errors, scope, ann):
        if isinstance(value, str) and len(value) < limit:
            errors.append(_err(path, f"String length {len(value)} is less than minimum {limit}", "minLength", value, limit))
    return check


def _f_max_length(schema, ctx, base_uri):
    limit = schema["maxLength"]

    def check(value, path, errors, scope, ann):
        if isinstance(value, str) and len(value) > limit:
            errors.append(_err(path, f"String length {len(value)} exceeds maximum {limit}", "maxLength", value, limit))
    return check


def _f_pattern(schema, ctx, base_uri):
    try:
        regex = re.compile(schema["pattern"])
    except re.error:
        return None

    def check(value, path, errors, scope, ann):
        if isinstance(value, str) and not regex.search(value):
            errors.append(_err(path, f"String does not match pattern: {schema['pattern']}", "pattern", value, schema["pattern"]))
    return check


def _f_format(schema, ctx, base_uri):
    fmt = schema["format"]
    pattern = ctx.format_patterns.get(fmt)
    if pattern is None or not ctx.config.check_formats:
        return None  # unknown formats and annotation-mode: no assertion

    def check(value, path, errors, scope, ann):
        if isinstance(value, str) and not pattern.match(value):
            errors.append(_err(path, f"String does not match format: {fmt}", "format", value, fmt))
    return check


def _f_required(schema, ctx, base_uri):
    required = schema["required"]
    if not isinstance(required, list):
        return None

    def check(value, path, errors, scope, ann):
        if not isinstance(value, dict):
            return
        for name in required:
            if name not in value:
                errors.append(_err(f"{path}.{name}", f"Required property '{name}' is missing", "required", expected=name))
    return check


def _f_properties(schema, ctx, base_uri):
    compiled = {name: ctx.compile(sub, base_uri) for name, sub in schema["properties"].items()}

    def check(value, path, errors, scope, ann):
        if not isinstance(value, dict):
            return
        for name, node in compiled.items():
            if name in value:
                node.run(value[name], f"{path}.{name}", errors, scope)
                ann.props.add(name)
    return check


def _f_pattern_properties(schema, ctx, base_uri):
    compiled = []
    for pattern, sub in schema["patternProperties"].items():
        try:
            compiled.append((re.compile(pattern), ctx.compile(sub, base_uri)))
        except re.error:
            continue

    def check(value, path, errors, scope, ann):
        if not isinstance(value, dict):
            return
        for name in value:
            for regex, node in compiled:
                if regex.search(name):
                    node.run(value[name], f"{path}.{name}", errors, scope)
                    ann.props.add(name)
    return check


def _f_additional_properties(schema, ctx, base_uri):
    sub = schema["additionalProperties"]
    declared = set(schema.get("properties", {}).keys()) if isinstance(schema.get("properties"), dict) else set()
    patterns = []
    if isinstance(schema.get("patternProperties"), dict):
        for pattern in schema["patternProperties"]:
            try:
                patterns.append(re.compile(pattern))
            except re.error:
                continue
    node = None if isinstance(sub, bool) else ctx.compile(sub, base_uri)
    enforce_false = ctx.config.strict_mode  # legacy behavior: only error in strict mode

    def check(value, path, errors, scope, ann):
        if not isinstance(value, dict):
            return
        for name in value:
            if name in declared or any(r.search(name) for r in patterns):
                continue
            ann.props.add(name)
            if sub is False:
                if enforce_false:
                    errors.append(_err(f"{path}.{name}", f"Additional property '{name}' is not allowed", "additionalProperties"))
            elif node is not None:
                node.run(value[name], f"{path}.{name}", errors, scope)
    return check


def _f_property_names(schema, ctx, base_uri):
    node = ctx.compile(schema["propertyNames"], base_uri)

    def check(value, path, errors, scope, ann):
        if not isinstance(value, dict):
            return
        for name in value:
            node.run(name, f"{path}[propertyName:{name}]", errors, scope)
    return check


def _f_min_properties(schema, ctx, base_uri):
    limit = schema["minProperties"]

    def check(value, path, errors, scope, ann):
        if isinstance(value, dict) and len(value) < limit:
            errors.append(_err(path, f"Object has {len(value)} properties, minimum is {limit}", "minProperties", value, limit))
    return check


def _f_max_properties(schema, ctx, base_uri):
    limit = schema["maxProperties"]

    def check(value, path, errors, scope, ann):
        if isinstance(value, dict) and len(value) > limit:
            errors.append(_err(path, f"Object has {len(value)} properties, maximum is {limit}", "maxProperties", value, limit))
    return check


def _f_min_items(schema, ctx, base_uri):
    limit = schema["minItems"]

    def check(value, path, errors, scope, ann):
        if isinstance(value, list) and len(value) < limit:
            errors.append(_err(path, f"Array has {len(value)} items, minimum is {limit}", "minItems", value, limit))
    return check


def _f_max_items(schema, ctx, base_uri):
    limit = schema["maxItems"]

    def check(value, path, errors, scope, ann):
        if isinstance(value, list) and len(value) > limit:
            errors.append(_err(path, f"Array has {len(value)} items, maximum is {limit}", "maxItems", value, limit))
    return check


def _f_unique_items(schema, ctx, base_uri):
    if not schema.get("uniqueItems"):
        return None

    def check(value, path, errors, scope, ann):
        if not isinstance(value, list):
            return
        for i, item in enumerate(value):
            for prior in value[:i]:
                if json_equal(item, prior):
                    errors.append(_err(f"{path}[{i}]", "Duplicate item in array", "uniqueItems", item))
                    break
    return check


def _make_items_checker(ctx, base_uri, prefix_schemas, rest_schema):
    """Shared positional + rest items checker builder."""
    prefix_nodes = [ctx.compile(s, base_uri) for s in prefix_schemas]
    rest_node = None
    rest_false = rest_schema is False
    if isinstance(rest_schema, (dict, bool)) and not rest_false and rest_schema is not True and rest_schema is not None:
        rest_node = ctx.compile(rest_schema, base_uri)

    def check(value, path, errors, scope, ann):
        if not isinstance(value, list):
            return
        for i, item in enumerate(value):
            if i < len(prefix_nodes):
                prefix_nodes[i].run(item, f"{path}[{i}]", errors, scope)
                ann.items.add(i)
            elif rest_false:
                errors.append(_err(f"{path}[{i}]", "Additional items not allowed", "additionalItems", item))
                ann.items.add(i)
            elif rest_node is not None:
                rest_node.run(item, f"{path}[{i}]", errors, scope)
                ann.items.add(i)
            elif rest_schema is True:
                ann.items.add(i)
    return check


def _f_items_draft7(schema, ctx, base_uri):
    items = schema["items"]
    if isinstance(items, list):
        return _make_items_checker(ctx, base_uri, items, schema.get("additionalItems"))
    return _make_items_checker(ctx, base_uri, [], items)


def _f_items_2020(schema, ctx, base_uri):
    items = schema["items"]
    if isinstance(items, list):
        # tolerated draft-07 form under 2020-12 (treated as prefixItems)
        return _make_items_checker(ctx, base_uri, items, None)
    if "prefixItems" in schema:
        return None  # handled by _f_prefix_items (which reads items as the rest schema)
    return _make_items_checker(ctx, base_uri, [], items)


def _f_prefix_items(schema, ctx, base_uri):
    return _make_items_checker(ctx, base_uri, schema["prefixItems"], schema.get("items"))


def _f_contains(schema, ctx, base_uri):
    node = ctx.compile(schema["contains"], base_uri)
    min_contains = schema.get("minContains", 1)
    max_contains = schema.get("maxContains")

    def check(value, path, errors, scope, ann):
        if not isinstance(value, list):
            return
        match_count = 0
        for i, item in enumerate(value):
            scratch: list = []
            if node.run(item, f"{path}[{i}]", scratch, scope):
                match_count += 1
                ann.items.add(i)
        if match_count < min_contains:
            errors.append(_err(path, f"Array contains {match_count} matching items, minimum is {min_contains}", "contains", value, min_contains))
        if max_contains is not None and match_count > max_contains:
            errors.append(_err(path, f"Array contains {match_count} matching items, maximum is {max_contains}", "maxContains", value, max_contains))
    return check


def _f_all_of(schema, ctx, base_uri):
    nodes = [ctx.compile(sub, base_uri) for sub in schema["allOf"]]

    def check(value, path, errors, scope, ann):
        for node in nodes:
            node.run(value, path, errors, scope, ann)
    return check


def _f_any_of(schema, ctx, base_uri):
    nodes = [ctx.compile(sub, base_uri) for sub in schema["anyOf"]]

    def check(value, path, errors, scope, ann):
        matched = False
        for node in nodes:
            scratch: list = []
            branch_ann = Annotations()
            if node.run(value, path, scratch, scope, branch_ann):
                ann.merge(branch_ann)
                matched = True
        if not matched:
            errors.append(_err(path, "Value does not match any of the allowed schemas", "anyOf", value))
    return check


def _f_one_of(schema, ctx, base_uri):
    nodes = [ctx.compile(sub, base_uri) for sub in schema["oneOf"]]

    def check(value, path, errors, scope, ann):
        matches = 0
        matched_ann = None
        for node in nodes:
            scratch: list = []
            branch_ann = Annotations()
            if node.run(value, path, scratch, scope, branch_ann):
                matches += 1
                matched_ann = branch_ann
        if matches != 1:
            errors.append(_err(path, f"Value must match exactly one schema, but matched {matches}", "oneOf", value))
        elif matched_ann is not None:
            ann.merge(matched_ann)
    return check


def _f_not(schema, ctx, base_uri):
    node = ctx.compile(schema["not"], base_uri)

    def check(value, path, errors, scope, ann):
        scratch: list = []
        if node.run(value, path, scratch, scope):
            errors.append(_err(path, "Value must not match the schema", "not", value))
    return check


def _f_conditional(schema, ctx, base_uri):
    if_node = ctx.compile(schema["if"], base_uri)
    then_node = ctx.compile(schema["then"], base_uri) if "then" in schema else None
    else_node = ctx.compile(schema["else"], base_uri) if "else" in schema else None

    def check(value, path, errors, scope, ann):
        scratch: list = []
        if_ann = Annotations()
        if if_node.run(value, path, scratch, scope, if_ann):
            ann.merge(if_ann)
            if then_node is not None:
                then_node.run(value, path, errors, scope, ann)
        elif else_node is not None:
            else_node.run(value, path, errors, scope, ann)
    return check


def _f_dependencies(schema, ctx, base_uri):
    schema_deps = {}
    required_deps = {}
    for name, dep in schema["dependencies"].items():
        if isinstance(dep, list):
            required_deps[name] = dep
        else:
            schema_deps[name] = ctx.compile(dep, base_uri)
    return _make_dependency_checker(required_deps, schema_deps)


def _f_dependent_required(schema, ctx, base_uri):
    return _make_dependency_checker(dict(schema["dependentRequired"]), {})


def _f_dependent_schemas(schema, ctx, base_uri):
    compiled = {name: ctx.compile(sub, base_uri) for name, sub in schema["dependentSchemas"].items()}
    return _make_dependency_checker({}, compiled)


def _make_dependency_checker(required_deps, schema_deps):
    def check(value, path, errors, scope, ann):
        if not isinstance(value, dict):
            return
        for name, needed in required_deps.items():
            if name in value:
                for req in needed:
                    if req not in value:
                        errors.append(_err(f"{path}.{req}", f"Property '{req}' is required when '{name}' is present", "dependentRequired", expected=req))
        for name, node in schema_deps.items():
            if name in value:
                node.run(value, path, errors, scope, ann)
    return check


def _f_ref(schema, ctx, base_uri):
    ref = schema["$ref"]
    if not ctx.config.resolve_references:
        return None
    holder: dict = {}

    def check(value, path, errors, scope, ann):
        node = holder.get("node")
        if node is None and "error" not in holder:
            try:
                target, new_base = ctx.registry.resolve(ref, base_uri)
                node = ctx.compile(target, new_base)
                holder["node"] = node
            except RefResolutionError as e:
                holder["error"] = str(e)
        if "error" in holder:
            errors.append(_err(path, f"Unresolvable $ref '{ref}': {holder['error']}", "ref", expected=ref))
            return
        node.run(value, path, errors, scope, ann)
    return check


def _f_dynamic_ref(schema, ctx, base_uri):
    ref = schema["$dynamicRef"]
    if not ctx.config.resolve_references:
        return None
    anchor_name = ref[1:] if ref.startswith("#") and "/" not in ref else None
    holder: dict = {}

    def check(value, path, errors, scope, ann):
        node = None
        if anchor_name is not None:
            for resource_uri in scope.dynamic_stack:  # outermost first
                target = ctx.registry.resource_dynamic_anchor(resource_uri, anchor_name)
                if target is not None:
                    node = ctx.compile(target, resource_uri)
                    break
        if node is None:
            if "node" not in holder and "error" not in holder:
                try:
                    target, new_base = ctx.registry.resolve(ref, base_uri)
                    holder["node"] = ctx.compile(target, new_base)
                except RefResolutionError as e:
                    holder["error"] = str(e)
            if "error" in holder:
                errors.append(_err(path, f"Unresolvable $dynamicRef '{ref}': {holder['error']}", "dynamicRef", expected=ref))
                return
            node = holder["node"]
        node.run(value, path, errors, scope, ann)
    return check


def _f_unevaluated_properties(schema, ctx, base_uri):
    sub = schema["unevaluatedProperties"]
    node = None if isinstance(sub, bool) else ctx.compile(sub, base_uri)

    def check(value, path, errors, scope, ann):
        if not isinstance(value, dict):
            return
        for name in value:
            if name in ann.props:
                continue
            if sub is False:
                errors.append(_err(f"{path}.{name}", f"Unevaluated property '{name}' is not allowed", "unevaluatedProperties"))
            elif node is not None:
                node.run(value[name], f"{path}.{name}", errors, scope)
            ann.props.add(name)
    return check


def _f_unevaluated_items(schema, ctx, base_uri):
    sub = schema["unevaluatedItems"]
    node = None if isinstance(sub, bool) else ctx.compile(sub, base_uri)

    def check(value, path, errors, scope, ann):
        if not isinstance(value, list):
            return
        for i, item in enumerate(value):
            if i in ann.items:
                continue
            if sub is False:
                errors.append(_err(f"{path}[{i}]", f"Unevaluated item at index {i} is not allowed", "unevaluatedItems", item))
            elif node is not None:
                node.run(item, f"{path}[{i}]", errors, scope)
            ann.items.add(i)
    return check


# ---------------------------------------------------------------------------
# Dialect registries: keyword -> (order, factory). Lower order runs first.
# ``unevaluated*`` must run last (they read annotations from all applicators).
# ---------------------------------------------------------------------------

_COMMON: dict[str, tuple[int, Callable]] = {
    "$ref": (0, _f_ref),
    "type": (10, _f_type),
    "enum": (10, _f_enum),
    "const": (10, _f_const),
    "multipleOf": (20, _f_multiple_of),
    "minimum": (20, _f_minimum),
    "maximum": (20, _f_maximum),
    "exclusiveMinimum": (20, _f_exclusive_minimum),
    "exclusiveMaximum": (20, _f_exclusive_maximum),
    "minLength": (20, _f_min_length),
    "maxLength": (20, _f_max_length),
    "pattern": (20, _f_pattern),
    "format": (20, _f_format),
    "required": (30, _f_required),
    "properties": (40, _f_properties),
    "patternProperties": (41, _f_pattern_properties),
    "additionalProperties": (42, _f_additional_properties),
    "propertyNames": (43, _f_property_names),
    "minProperties": (30, _f_min_properties),
    "maxProperties": (30, _f_max_properties),
    "minItems": (30, _f_min_items),
    "maxItems": (30, _f_max_items),
    "uniqueItems": (30, _f_unique_items),
    "contains": (45, _f_contains),
    "allOf": (50, _f_all_of),
    "anyOf": (50, _f_any_of),
    "oneOf": (50, _f_one_of),
    "not": (50, _f_not),
    "if": (55, _f_conditional),
}

DRAFT7_REGISTRY: dict[str, tuple[int, Callable]] = {
    **_COMMON,
    "items": (44, _f_items_draft7),
    "dependencies": (35, _f_dependencies),
}

DRAFT2020_REGISTRY: dict[str, tuple[int, Callable]] = {
    **_COMMON,
    "prefixItems": (44, _f_prefix_items),
    "items": (44, _f_items_2020),
    "dependencies": (35, _f_dependencies),        # tolerated legacy form
    "dependentRequired": (35, _f_dependent_required),
    "dependentSchemas": (36, _f_dependent_schemas),
    "$dynamicRef": (0, _f_dynamic_ref),
    "unevaluatedItems": (90, _f_unevaluated_items),
    "unevaluatedProperties": (91, _f_unevaluated_properties),
}

DIALECT_REGISTRIES: dict[SchemaDialect, dict[str, tuple[int, Callable]]] = {
    SchemaDialect.DRAFT4: DRAFT7_REGISTRY,
    SchemaDialect.DRAFT6: DRAFT7_REGISTRY,
    SchemaDialect.DRAFT7: DRAFT7_REGISTRY,
    SchemaDialect.DRAFT2019: DRAFT2020_REGISTRY,
    SchemaDialect.DRAFT2020: DRAFT2020_REGISTRY,
}

# Keywords whose presence next to $ref is ignored in draft-07 and earlier
REF_EXCLUSIVE_DIALECTS = {SchemaDialect.DRAFT4, SchemaDialect.DRAFT6, SchemaDialect.DRAFT7}


__all__ = [
    "Annotations",
    "CompiledNode",
    "DIALECT_REGISTRIES",
    "DRAFT7_REGISTRY",
    "DRAFT2020_REGISTRY",
    "REF_EXCLUSIVE_DIALECTS",
    "RunScope",
    "SchemaDialect",
    "check_json_type",
    "detect_dialect",
    "dialect_from_uri",
    "json_equal",
]
