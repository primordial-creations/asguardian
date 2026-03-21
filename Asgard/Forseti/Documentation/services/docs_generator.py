"""
API Documentation Generator Service.

Generates comprehensive API documentation from OpenAPI specifications.
"""

import json
import time
from pathlib import Path
from typing import Any, Optional, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Forseti.Documentation.models.docs_models import (
    APIDocConfig,
    DocumentationFormat,
    DocumentationReport,
    DocumentationStructure,
    EndpointInfo,
    GeneratedDocument,
    SchemaInfo,
    TagGroup,
)
from Asgard.Forseti.Documentation.services._docs_generator_helpers import (
    generate_html_authentication,
    generate_html_header,
    generate_html_overview,
    generate_html_schemas,
    generate_html_tag_section,
    generate_markdown_endpoint,
    get_css,
)


class DocsGeneratorService:
    """
    Service for generating API documentation from OpenAPI specifications.

    Generates comprehensive documentation in HTML, Markdown, or other formats.

    Usage:
        generator = DocsGeneratorService()
        result = generator.generate("api.yaml")
        for doc in result.generated_documents:
            print(f"Generated: {doc.path}")
    """

    def __init__(self, config: Optional[APIDocConfig] = None):
        self.config = config or APIDocConfig()

    def generate(self, spec_path: str | Path, output_dir: Optional[str | Path] = None) -> DocumentationReport:
        start_time = time.time()
        spec_path = Path(spec_path)
        warnings: list[str] = []
        errors: list[str] = []
        try:
            spec_data = self._load_spec_file(spec_path)
        except Exception as e:
            errors.append(f"Failed to load specification: {e}")
            return DocumentationReport(success=False, source_spec=str(spec_path), api_title="Unknown", api_version="Unknown", errors=errors, generation_time_ms=(time.time() - start_time) * 1000)
        doc_structure = self._parse_spec(spec_data, warnings)
        generated_docs = self._generate_docs(doc_structure)
        if output_dir:
            self._write_files(generated_docs, Path(output_dir))
        return DocumentationReport(
            success=len(errors) == 0,
            source_spec=str(spec_path),
            api_title=doc_structure.title,
            api_version=doc_structure.version,
            generated_documents=generated_docs,
            endpoint_count=sum(len(tg.endpoints) for tg in doc_structure.tag_groups),
            schema_count=len(doc_structure.schemas),
            tag_count=len(doc_structure.tag_groups),
            warnings=warnings,
            errors=errors,
            generation_time_ms=(time.time() - start_time) * 1000,
        )

    def generate_from_spec_data(self, spec_data: dict[str, Any], output_dir: Optional[str | Path] = None) -> DocumentationReport:
        start_time = time.time()
        warnings: list[str] = []
        errors: list[str] = []
        doc_structure = self._parse_spec(spec_data, warnings)
        generated_docs = self._generate_docs(doc_structure)
        if output_dir:
            self._write_files(generated_docs, Path(output_dir))
        return DocumentationReport(
            success=len(errors) == 0,
            api_title=doc_structure.title,
            api_version=doc_structure.version,
            generated_documents=generated_docs,
            endpoint_count=sum(len(tg.endpoints) for tg in doc_structure.tag_groups),
            schema_count=len(doc_structure.schemas),
            tag_count=len(doc_structure.tag_groups),
            warnings=warnings,
            errors=errors,
            generation_time_ms=(time.time() - start_time) * 1000,
        )

    def _load_spec_file(self, spec_path: Path) -> dict[str, Any]:
        content = spec_path.read_text(encoding="utf-8")
        try:
            return cast(dict[str, Any], yaml.safe_load(content))
        except yaml.YAMLError:
            return cast(dict[str, Any], json.loads(content))

    def _generate_docs(self, doc_structure: DocumentationStructure) -> list[GeneratedDocument]:
        if self.config.output_format == DocumentationFormat.MARKDOWN:
            return [self._generate_markdown(doc_structure)]
        return [self._generate_html(doc_structure)]

    def _parse_spec(self, spec_data: dict[str, Any], warnings: list[str]) -> DocumentationStructure:
        info = spec_data.get("info", {})
        tag_groups = self._parse_endpoints_by_tag(spec_data, warnings)
        schemas = self._parse_schemas(spec_data, warnings)
        security_schemes = spec_data.get("components", {}).get("securitySchemes", {})
        return DocumentationStructure(
            title=self.config.title or info.get("title", "API Documentation"),
            version=info.get("version", "1.0.0"),
            description=self.config.description or info.get("description"),
            base_url=self.config.base_url or self._get_base_url(spec_data),
            contact=info.get("contact"),
            license=info.get("license"),
            servers=spec_data.get("servers", []),
            security_schemes=security_schemes,
            tag_groups=tag_groups,
            schemas=schemas,
            external_docs=spec_data.get("externalDocs"),
        )

    def _get_base_url(self, spec_data: dict[str, Any]) -> Optional[str]:
        servers = spec_data.get("servers", [])
        if servers:
            return cast(Optional[str], servers[0].get("url"))
        return None

    def _parse_endpoints_by_tag(self, spec_data: dict[str, Any], warnings: list[str]) -> list[TagGroup]:
        paths = spec_data.get("paths", {})
        http_methods = ["get", "post", "put", "patch", "delete", "options", "head"]
        endpoints_by_tag: dict[str, list[EndpointInfo]] = {}
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method in http_methods:
                if method not in path_item:
                    continue
                operation = path_item[method]
                if not isinstance(operation, dict):
                    continue
                if not self.config.show_deprecated and operation.get("deprecated", False):
                    continue
                endpoint = EndpointInfo(
                    path=path, method=method.upper(),
                    summary=operation.get("summary"), description=operation.get("description"),
                    operation_id=operation.get("operationId"), tags=operation.get("tags", ["Other"]),
                    parameters=operation.get("parameters", []), request_body=operation.get("requestBody"),
                    responses=operation.get("responses", {}), deprecated=operation.get("deprecated", False),
                    security=operation.get("security", []),
                )
                for tag in endpoint.tags:
                    if tag not in endpoints_by_tag:
                        endpoints_by_tag[tag] = []
                    endpoints_by_tag[tag].append(endpoint)
        tag_descriptions = {t["name"]: t.get("description") for t in spec_data.get("tags", [])}
        return [TagGroup(name=tag_name, description=tag_descriptions.get(tag_name), endpoints=endpoints) for tag_name, endpoints in sorted(endpoints_by_tag.items())]

    def _parse_schemas(self, spec_data: dict[str, Any], warnings: list[str]) -> list[SchemaInfo]:
        schemas = []
        schema_defs = spec_data.get("components", {}).get("schemas", {})
        for name, schema in schema_defs.items():
            if not isinstance(schema, dict):
                continue
            schemas.append(SchemaInfo(
                name=name, description=schema.get("description"),
                properties=schema.get("properties", {}), required=schema.get("required", []),
                is_enum="enum" in schema, enum_values=schema.get("enum", []),
                example=schema.get("example"),
            ))
        return schemas

    def _generate_html(self, doc_structure: DocumentationStructure) -> GeneratedDocument:
        css = get_css()
        html_parts = [
            "<!DOCTYPE html>", "<html lang=\"en\">", "<head>",
            f"  <title>{doc_structure.title}</title>",
            "  <meta charset=\"UTF-8\">",
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
            f"  <style>{css}</style>",
        ]
        if self.config.custom_css:
            html_parts.append(f"  <style>{self.config.custom_css}</style>")
        html_parts.extend(["</head>", "<body>", "  <div class=\"container\">",
            generate_html_header(doc_structure), generate_html_overview(doc_structure)])
        if self.config.include_authentication and doc_structure.security_schemes:
            html_parts.append(generate_html_authentication(doc_structure))
        for tag_group in doc_structure.tag_groups:
            html_parts.append(generate_html_tag_section(tag_group))
        if self.config.include_schemas and doc_structure.schemas:
            html_parts.append(generate_html_schemas(doc_structure.schemas))
        html_parts.extend(["  </div>", "</body>", "</html>"])
        content = "\n".join(html_parts)
        return GeneratedDocument(path="index.html", content=content, format=DocumentationFormat.HTML, title=doc_structure.title, size_bytes=len(content.encode("utf-8")))

    def _generate_markdown(self, doc_structure: DocumentationStructure) -> GeneratedDocument:
        lines = [f"# {doc_structure.title}", "", f"**Version:** {doc_structure.version}", ""]
        if doc_structure.description:
            lines.extend([doc_structure.description, ""])
        lines.extend(["## Overview", ""])
        if doc_structure.base_url:
            lines.extend([f"**Base URL:** `{doc_structure.base_url}`", ""])
        if doc_structure.servers:
            lines.extend(["### Servers", ""])
            for server in doc_structure.servers:
                lines.append(f"- `{server.get('url', '')}` - {server.get('description', '')}")
            lines.append("")
        if self.config.include_authentication and doc_structure.security_schemes:
            lines.extend(["## Authentication", ""])
            for scheme_name, scheme in doc_structure.security_schemes.items():
                lines.append(f"### {scheme_name}")
                lines.append(f"**Type:** {scheme.get('type', 'unknown')}")
                if scheme.get("description"):
                    lines.append(f"\n{scheme['description']}")
                lines.append("")
        for tag_group in doc_structure.tag_groups:
            lines.extend([f"## {tag_group.name}", ""])
            if tag_group.description:
                lines.extend([tag_group.description, ""])
            for endpoint in tag_group.endpoints:
                lines.extend(generate_markdown_endpoint(endpoint))
                lines.append("")
        if self.config.include_schemas and doc_structure.schemas:
            lines.extend(["## Schemas", ""])
            for schema in doc_structure.schemas:
                lines.extend([f"### {schema.name}", ""])
                if schema.description:
                    lines.extend([schema.description, ""])
                if schema.is_enum:
                    lines.extend(["**Type:** enum", "", "**Values:**"])
                    for value in schema.enum_values:
                        lines.append(f"- `{value}`")
                elif schema.properties:
                    lines.extend(["| Property | Type | Required | Description |", "|----------|------|----------|-------------|"])
                    for prop_name, prop_def in schema.properties.items():
                        prop_type = prop_def.get("type", "any")
                        is_required = "Yes" if prop_name in schema.required else "No"
                        desc = prop_def.get("description", "")
                        lines.append(f"| `{prop_name}` | {prop_type} | {is_required} | {desc} |")
                lines.append("")
        content = "\n".join(lines)
        return GeneratedDocument(path="README.md", content=content, format=DocumentationFormat.MARKDOWN, title=doc_structure.title, size_bytes=len(content.encode("utf-8")))

    def _write_files(self, docs: list[GeneratedDocument], output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        for doc in docs:
            file_path = output_dir / doc.path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(doc.content, encoding="utf-8")
