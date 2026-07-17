"""
Ref Resolver Helpers.

Builds a registry of addressable subschemas ($id / $anchor / $dynamicAnchor /
$defs / definitions) and resolves $ref targets, including JSON Pointer
fragments, anchor fragments, and file: / relative-path references.

Cycle safety is achieved by resolving to *schema dicts* (not inlined copies);
the compiler turns references into lazy thunks.
"""

from pathlib import Path
from typing import Any, Optional
from urllib.parse import urldefrag, urljoin, urlparse, unquote


class RefResolutionError(Exception):
    """Raised when a $ref cannot be resolved."""


def _pointer_unescape(token: str) -> str:
    return unquote(token).replace("~1", "/").replace("~0", "~")


def resolve_json_pointer(document: Any, pointer: str) -> Any:
    """Resolve a JSON Pointer (RFC 6901) against a document."""
    if pointer in ("", "#"):
        return document
    if pointer.startswith("/"):
        pointer = pointer[1:]
    current = document
    for raw_token in pointer.split("/"):
        token = _pointer_unescape(raw_token)
        if isinstance(current, dict):
            if token not in current:
                raise RefResolutionError(f"JSON Pointer token not found: '{token}'")
            current = current[token]
        elif isinstance(current, list):
            try:
                index = int(token)
            except ValueError:
                raise RefResolutionError(f"Invalid array index in pointer: '{token}'")
            if index < 0 or index >= len(current):
                raise RefResolutionError(f"Array index out of range: {index}")
            current = current[index]
        else:
            raise RefResolutionError(f"Cannot traverse into scalar at token: '{token}'")
    return current


class SchemaRegistry:
    """
    Registry of addressable subschemas within a schema document tree.

    Maps canonical URIs (from $id), anchors ($anchor, $dynamicAnchor) and
    supports JSON Pointer fragments relative to any registered resource.
    """

    def __init__(self, root_schema: Any, base_uri: str = "", root_path: Optional[Path] = None):
        self.root_schema = root_schema
        self.base_uri = base_uri or ""
        self.root_path = root_path
        # resource uri -> schema dict at that $id boundary
        self.resources: dict[str, Any] = {}
        # (resource_uri, anchor_name) -> schema dict
        self.anchors: dict[tuple[str, str], Any] = {}
        # (resource_uri, anchor_name) -> schema dict, for $dynamicAnchor
        self.dynamic_anchors: dict[tuple[str, str], Any] = {}
        # cache of externally loaded documents: absolute path -> SchemaRegistry
        self._external: dict[str, "SchemaRegistry"] = {}
        self.resources[self.base_uri] = root_schema
        self._index(root_schema, self.base_uri)

    def _index(self, node: Any, current_base: str) -> None:
        if isinstance(node, dict):
            new_base = current_base
            raw_id = node.get("$id")
            if isinstance(raw_id, str) and not raw_id.startswith("#"):
                new_base = urljoin(current_base or raw_id, raw_id)
                new_base, _frag = urldefrag(new_base)
                self.resources[new_base] = node
            anchor = node.get("$anchor")
            if isinstance(anchor, str):
                self.anchors[(new_base, anchor)] = node
            dyn = node.get("$dynamicAnchor")
            if isinstance(dyn, str):
                self.dynamic_anchors[(new_base, dyn)] = node
                # a $dynamicAnchor is also addressable as a plain anchor
                self.anchors.setdefault((new_base, dyn), node)
            # draft-07 style: $id: "#name" acts as an anchor
            if isinstance(raw_id, str) and raw_id.startswith("#") and len(raw_id) > 1:
                self.anchors[(current_base, raw_id[1:])] = node
            for value in node.values():
                self._index(value, new_base)
        elif isinstance(node, list):
            for item in node:
                self._index(item, current_base)

    def resource_dynamic_anchor(self, resource_uri: str, name: str) -> Optional[Any]:
        return self.dynamic_anchors.get((resource_uri, name))

    def resolve(self, ref: str, current_base: str) -> tuple[Any, str]:
        """
        Resolve a $ref string against the current base URI.

        Returns:
            (subschema, new_base_uri) tuple.

        Raises:
            RefResolutionError: If the reference cannot be resolved.
        """
        uri, fragment = urldefrag(urljoin(current_base or self.base_uri, ref))
        target_doc: Any = None
        registry: "SchemaRegistry" = self

        if uri in self.resources:
            target_doc = self.resources[uri]
        elif uri in ("", self.base_uri):
            target_doc = self.root_schema
            uri = self.base_uri
        else:
            parsed = urlparse(uri)
            if parsed.scheme in ("", "file") and self.root_path is not None:
                registry = self._load_external(parsed.path or uri)
                target_doc = registry.root_schema
            else:
                raise RefResolutionError(f"Cannot resolve external reference: {ref}")

        if not fragment:
            return target_doc, uri
        if fragment.startswith("/"):
            return resolve_json_pointer(target_doc, fragment), uri
        # anchor fragment
        anchored = registry.anchors.get((uri, fragment))
        if anchored is None and registry is not self:
            anchored = registry.anchors.get((registry.base_uri, fragment))
        if anchored is None:
            # fall back to plain-name lookup in definitions / $defs
            for defs_key in ("$defs", "definitions"):
                defs = target_doc.get(defs_key, {}) if isinstance(target_doc, dict) else {}
                if fragment in defs:
                    return defs[fragment], uri
            raise RefResolutionError(f"Anchor not found: '#{fragment}' in '{uri or '<root>'}'")
        return anchored, uri

    def _load_external(self, path_str: str) -> "SchemaRegistry":
        from Asgard.Forseti.JSONSchema.utilities.jsonschema_utils import load_schema_file

        base_dir = self.root_path.parent if self.root_path else Path(".")
        candidate = Path(path_str)
        if not candidate.is_absolute():
            candidate = base_dir / candidate
        key = str(candidate.resolve())
        if key not in self._external:
            try:
                document = load_schema_file(candidate)
            except Exception as e:
                raise RefResolutionError(f"Failed to load referenced file '{path_str}': {e}")
            self._external[key] = SchemaRegistry(document, base_uri=f"file://{key}", root_path=candidate)
        return self._external[key]


__all__ = ["RefResolutionError", "SchemaRegistry", "resolve_json_pointer"]
