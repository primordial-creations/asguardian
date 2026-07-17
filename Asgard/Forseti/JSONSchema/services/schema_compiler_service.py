"""
Schema Compiler Service.

Compile-then-run JSON Schema validation engine. A schema dict is compiled
once into a tree of checker closures (CompiledSchema) and can then be run
against any number of instances. Compilation results are cached in a
class-level LRU keyed by schema content hash + config, giving large speedups
for repeat validation (mock-data generation, example checking, test loops).

Supports draft-04/06/07, 2019-09 and 2020-12 dialects, $defs / definitions,
$id / $anchor / $dynamicAnchor resolution, JSON Pointer refs, cyclic $refs
(lazy thunks) and relative file references when the schema was loaded from
a file.
"""

import hashlib
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any, Optional

from Asgard.Forseti.JSONSchema.models.jsonschema_models import (
    JSONSchemaConfig,
    JSONSchemaValidationError,
    JSONSchemaValidationResult,
)
from Asgard.Forseti.JSONSchema.services._compiler_keyword_helpers import (
    Annotations,
    CompiledNode,
    DIALECT_REGISTRIES,
    REF_EXCLUSIVE_DIALECTS,
    RunScope,
    SchemaDialect,
    detect_dialect,
    dialect_from_uri,
)
from Asgard.Forseti.JSONSchema.services._ref_resolver_helpers import SchemaRegistry

# Default format regexes (assertion set); shared with SchemaValidatorService.
DEFAULT_FORMAT_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
    "uri": re.compile(r"^https?://[^\s/$.?#].[^\s]*$"),
    "uuid": re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE),
    "date": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "date-time": re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$"),
    "time": re.compile(r"^\d{2}:\d{2}:\d{2}(\.\d+)?$"),
    "ipv4": re.compile(r"^(\d{1,3}\.){3}\d{1,3}$"),
    "ipv6": re.compile(r"^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$"),
    "hostname": re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$"),
}


class _CompileContext:
    """Shared state during a single compilation: registry, memo, config."""

    def __init__(
        self,
        registry: SchemaRegistry,
        dialect: SchemaDialect,
        config: JSONSchemaConfig,
        format_patterns: dict[str, re.Pattern],
    ):
        self.registry = registry
        self.dialect = dialect
        self.config = config
        self.format_patterns = format_patterns
        self._memo: dict[tuple[int, str], CompiledNode] = {}

    def compile(self, schema: Any, base_uri: str) -> CompiledNode:
        """Compile a (sub)schema into a CompiledNode. Cycle-safe via memoization."""
        if isinstance(schema, bool):
            node = CompiledNode()
            node.boolean = schema
            return node
        if not isinstance(schema, dict):
            node = CompiledNode()
            node.boolean = True
            return node
        if not schema:
            node = CompiledNode()
            node.boolean = True
            return node

        # honor a $schema switch inside embedded resources
        dialect = self.dialect
        if "$schema" in schema and isinstance(schema["$schema"], str):
            dialect = dialect_from_uri(schema["$schema"], dialect)

        raw_id = schema.get("$id")
        if isinstance(raw_id, str) and not raw_id.startswith("#"):
            from urllib.parse import urljoin, urldefrag
            base_uri, _ = urldefrag(urljoin(base_uri or raw_id, raw_id))

        key = (id(schema), base_uri)
        if key in self._memo:
            return self._memo[key]
        node = CompiledNode(resource_uri=base_uri)
        self._memo[key] = node  # register before compiling children (cycles)

        registry = DIALECT_REGISTRIES[dialect]
        keywords = schema.keys()
        if "$ref" in schema and dialect in REF_EXCLUSIVE_DIALECTS:
            keywords = ["$ref"]  # draft-07 and earlier: $ref siblings are ignored

        entries = []
        for keyword in keywords:
            spec = registry.get(keyword)
            if spec is None:
                continue
            order, factory = spec
            checker = factory(schema, self, base_uri)
            if checker is not None:
                entries.append((order, keyword, checker))
        entries.sort(key=lambda e: e[0])
        node.checkers = [(kw, fn) for _o, kw, fn in entries]
        return node


class CompiledSchema:
    """A schema compiled for repeated validation runs."""

    def __init__(self, root: CompiledNode, dialect: SchemaDialect):
        self._root = root
        self.dialect = dialect

    def validate(self, data: Any) -> list[JSONSchemaValidationError]:
        """Validate an instance; returns the list of errors (empty when valid)."""
        errors: list[JSONSchemaValidationError] = []
        scope = RunScope()
        self._root.run(data, "$", errors, scope, Annotations())
        return errors

    def is_valid(self, data: Any) -> bool:
        return not self.validate(data)


class SchemaCompilerService:
    """
    Service that compiles JSON Schemas into reusable validators.

    Usage:
        compiler = SchemaCompilerService()
        compiled = compiler.compile(schema)
        errors = compiled.validate(data)
    """

    _CACHE_MAX = 128
    _cache: OrderedDict[str, CompiledSchema] = OrderedDict()
    # identity fast path: id(schema) -> (schema strong-ref, cfg key, CompiledSchema)
    _identity_cache: OrderedDict[tuple[int, str], tuple[Any, CompiledSchema]] = OrderedDict()

    def __init__(self, config: Optional[JSONSchemaConfig] = None):
        self.config = config or JSONSchemaConfig()

    def compile(
        self,
        schema: dict[str, Any] | bool,
        dialect: Optional[str | SchemaDialect] = None,
        schema_path: Optional[str | Path] = None,
        use_cache: bool = True,
    ) -> CompiledSchema:
        """
        Compile a schema for validation.

        Args:
            schema: Schema dict (or boolean schema).
            dialect: Optional dialect override ("draft-07", "2020-12", or a
                $schema URI). When omitted, detected from $schema, falling
                back to the configured schema_version.
            schema_path: Path the schema was loaded from (enables relative
                file $refs).
            use_cache: Reuse a cached compilation when available.

        Returns:
            CompiledSchema ready for repeated validate() calls.
        """
        identity_key = None
        if use_cache and isinstance(schema, dict):
            cfg = self.config
            identity_key = (
                id(schema),
                f"{dialect}|{schema_path}|{cfg.strict_mode}|{cfg.check_formats}|{cfg.resolve_references}|{cfg.schema_version}",
            )
            hit = self._identity_cache.get(identity_key)
            if hit is not None and hit[0] is schema:
                self._identity_cache.move_to_end(identity_key)
                return hit[1]

        resolved_dialect = self._resolve_dialect(schema, dialect)
        cache_key = self._cache_key(schema, resolved_dialect, schema_path) if use_cache else None
        if cache_key is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._cache.move_to_end(cache_key)
                if identity_key is not None:
                    self._store_identity(identity_key, schema, cached)
                return cached

        base_uri = ""
        root_path = Path(schema_path) if schema_path else None
        if isinstance(schema, dict):
            raw_id = schema.get("$id")
            if isinstance(raw_id, str) and not raw_id.startswith("#"):
                base_uri = raw_id
        registry = SchemaRegistry(schema, base_uri=base_uri, root_path=root_path)
        ctx = _CompileContext(registry, resolved_dialect, self.config, DEFAULT_FORMAT_PATTERNS)
        root = ctx.compile(schema, registry.base_uri)
        compiled = CompiledSchema(root, resolved_dialect)

        if cache_key is not None:
            self._cache[cache_key] = compiled
            while len(self._cache) > self._CACHE_MAX:
                self._cache.popitem(last=False)
        if identity_key is not None:
            self._store_identity(identity_key, schema, compiled)
        return compiled

    def validate(self, data: Any, schema: dict[str, Any] | bool, **kwargs) -> JSONSchemaValidationResult:
        """Compile (cached) and validate in one call."""
        import time
        start = time.time()
        compiled = self.compile(schema, **kwargs)
        errors = compiled.validate(data)
        return JSONSchemaValidationResult(
            is_valid=not errors,
            errors=errors,
            dialect=compiled.dialect.value,
            validation_time_ms=(time.time() - start) * 1000,
        )

    @classmethod
    def _store_identity(cls, identity_key: tuple, schema, compiled: CompiledSchema) -> None:
        cls._identity_cache[identity_key] = (schema, compiled)
        while len(cls._identity_cache) > cls._CACHE_MAX:
            cls._identity_cache.popitem(last=False)

    @classmethod
    def clear_cache(cls) -> None:
        cls._cache.clear()
        cls._identity_cache.clear()

    def _resolve_dialect(self, schema: Any, override: Optional[str | SchemaDialect]) -> SchemaDialect:
        if override is not None:
            if isinstance(override, SchemaDialect):
                return override
            return dialect_from_uri(str(override))
        default = dialect_from_uri(self.config.schema_version, SchemaDialect.DRAFT7)
        return detect_dialect(schema, default)

    def _cache_key(self, schema: Any, dialect: SchemaDialect, schema_path: Optional[str | Path]) -> Optional[str]:
        try:
            content = json.dumps(schema, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError):
            return None
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        cfg = self.config
        return "|".join([
            digest,
            dialect.value,
            str(schema_path or ""),
            f"{cfg.strict_mode}|{cfg.check_formats}|{cfg.resolve_references}",
        ])


__all__ = ["CompiledSchema", "SchemaCompilerService", "SchemaDialect", "DEFAULT_FORMAT_PATTERNS"]
