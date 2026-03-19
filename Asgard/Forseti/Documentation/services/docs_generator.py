"""
API Documentation Generator Service.

Generates comprehensive API documentation from OpenAPI specifications.
"""

import html
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
    DocumentationTheme,
    EndpointInfo,
    GeneratedDocument,
    SchemaInfo,
    TagGroup,
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
        """
        Initialize the documentation generator.

        Args:
            config: Optional configuration for documentation generation.
        """
        self.config = config or APIDocConfig()

    def generate(
        self,
        spec_path: str | Path,
        output_dir: Optional[str | Path] = None
    ) -> DocumentationReport:
        """
        Generate documentation from an OpenAPI specification.

        Args:
            spec_path: Path to the OpenAPI specification file.
            output_dir: Optional output directory for generated files.

        Returns:
            DocumentationReport with generated documentation.
        """
        start_time = time.time()
        spec_path = Path(spec_path)
        warnings: list[str] = []
        errors: list[str] = []

        # Load specification
        try:
            spec_data = self._load_spec_file(spec_path)
        except Exception as e:
            errors.append(f"Failed to load specification: {e}")
            return DocumentationReport(
                success=False,
                source_spec=str(spec_path),
                api_title="Unknown",
                api_version="Unknown",
                errors=errors,
                generation_time_ms=(time.time() - start_time) * 1000,
            )

        # Parse documentation structure
        doc_structure = self._parse_spec(spec_data, warnings)

        # Generate documentation based on format
        generated_docs: list[GeneratedDocument] = []

        if self.config.output_format == DocumentationFormat.HTML:
            html_doc = self._generate_html(doc_structure)
            generated_docs.append(html_doc)
        elif self.config.output_format == DocumentationFormat.MARKDOWN:
            md_doc = self._generate_markdown(doc_structure)
            generated_docs.append(md_doc)
        else:
            # Default to HTML
            html_doc = self._generate_html(doc_structure)
            generated_docs.append(html_doc)

        # Write files if output directory specified
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

    def generate_from_spec_data(
        self,
        spec_data: dict[str, Any],
        output_dir: Optional[str | Path] = None
    ) -> DocumentationReport:
        """
        Generate documentation from parsed specification data.

        Args:
            spec_data: Parsed OpenAPI specification as a dictionary.
            output_dir: Optional output directory for generated files.

        Returns:
            DocumentationReport with generated documentation.
        """
        start_time = time.time()
        warnings: list[str] = []
        errors: list[str] = []

        # Parse documentation structure
        doc_structure = self._parse_spec(spec_data, warnings)

        # Generate documentation
        generated_docs: list[GeneratedDocument] = []

        if self.config.output_format == DocumentationFormat.HTML:
            html_doc = self._generate_html(doc_structure)
            generated_docs.append(html_doc)
        elif self.config.output_format == DocumentationFormat.MARKDOWN:
            md_doc = self._generate_markdown(doc_structure)
            generated_docs.append(md_doc)
        else:
            html_doc = self._generate_html(doc_structure)
            generated_docs.append(html_doc)

        # Write files if output directory specified
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
        """Load a specification file."""
        content = spec_path.read_text(encoding="utf-8")

        try:
            return cast(dict[str, Any], yaml.safe_load(content))
        except yaml.YAMLError:
            return cast(dict[str, Any], json.loads(content))

    def _parse_spec(
        self,
        spec_data: dict[str, Any],
        warnings: list[str]
    ) -> DocumentationStructure:
        """Parse OpenAPI spec into documentation structure."""
        info = spec_data.get("info", {})

        # Parse endpoints grouped by tags
        tag_groups = self._parse_endpoints_by_tag(spec_data, warnings)

        # Parse schemas
        schemas = self._parse_schemas(spec_data, warnings)

        # Parse security schemes
        security_schemes = {}
        components = spec_data.get("components", {})
        if "securitySchemes" in components:
            security_schemes = components["securitySchemes"]

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
        """Extract base URL from spec."""
        servers = spec_data.get("servers", [])
        if servers:
            return cast(Optional[str], servers[0].get("url"))
        return None

    def _parse_endpoints_by_tag(
        self,
        spec_data: dict[str, Any],
        warnings: list[str]
    ) -> list[TagGroup]:
        """Parse endpoints and group by tags."""
        paths = spec_data.get("paths", {})
        http_methods = ["get", "post", "put", "patch", "delete", "options", "head"]

        # Collect endpoints by tag
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

                # Skip deprecated if configured
                if not self.config.show_deprecated and operation.get("deprecated", False):
                    continue

                endpoint = EndpointInfo(
                    path=path,
                    method=method.upper(),
                    summary=operation.get("summary"),
                    description=operation.get("description"),
                    operation_id=operation.get("operationId"),
                    tags=operation.get("tags", ["Other"]),
                    parameters=operation.get("parameters", []),
                    request_body=operation.get("requestBody"),
                    responses=operation.get("responses", {}),
                    deprecated=operation.get("deprecated", False),
                    security=operation.get("security", []),
                )

                # Add to each tag
                for tag in endpoint.tags:
                    if tag not in endpoints_by_tag:
                        endpoints_by_tag[tag] = []
                    endpoints_by_tag[tag].append(endpoint)

        # Create tag groups
        tag_groups = []
        tag_descriptions = {t["name"]: t.get("description") for t in spec_data.get("tags", [])}

        for tag_name, endpoints in sorted(endpoints_by_tag.items()):
            tag_group = TagGroup(
                name=tag_name,
                description=tag_descriptions.get(tag_name),
                endpoints=endpoints,
            )
            tag_groups.append(tag_group)

        return tag_groups

    def _parse_schemas(
        self,
        spec_data: dict[str, Any],
        warnings: list[str]
    ) -> list[SchemaInfo]:
        """Parse schema definitions."""
        schemas = []
        components = spec_data.get("components", {})
        schema_defs = components.get("schemas", {})

        for name, schema in schema_defs.items():
            if not isinstance(schema, dict):
                continue

            is_enum = "enum" in schema
            schema_info = SchemaInfo(
                name=name,
                description=schema.get("description"),
                properties=schema.get("properties", {}),
                required=schema.get("required", []),
                is_enum=is_enum,
                enum_values=schema.get("enum", []),
                example=schema.get("example"),
            )
            schemas.append(schema_info)

        return schemas

    def _generate_html(self, doc_structure: DocumentationStructure) -> GeneratedDocument:
        """Generate HTML documentation."""
        css = self._get_css()

        html_parts = [
            "<!DOCTYPE html>",
            "<html lang=\"en\">",
            "<head>",
            f"  <title>{html.escape(doc_structure.title)}</title>",
            "  <meta charset=\"UTF-8\">",
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
            f"  <style>{css}</style>",
        ]

        if self.config.custom_css:
            html_parts.append(f"  <style>{self.config.custom_css}</style>")

        html_parts.extend([
            "</head>",
            "<body>",
            "  <div class=\"container\">",
            self._generate_html_header(doc_structure),
            self._generate_html_overview(doc_structure),
        ])

        # Authentication section
        if self.config.include_authentication and doc_structure.security_schemes:
            html_parts.append(self._generate_html_authentication(doc_structure))

        # Endpoints by tag
        for tag_group in doc_structure.tag_groups:
            html_parts.append(self._generate_html_tag_section(tag_group))

        # Schemas section
        if self.config.include_schemas and doc_structure.schemas:
            html_parts.append(self._generate_html_schemas(doc_structure.schemas))

        html_parts.extend([
            "  </div>",
            "</body>",
            "</html>",
        ])

        content = "\n".join(html_parts)

        return GeneratedDocument(
            path="index.html",
            content=content,
            format=DocumentationFormat.HTML,
            title=doc_structure.title,
            size_bytes=len(content.encode("utf-8")),
        )

    def _get_css(self) -> str:
        """Get CSS styles for documentation."""
        return """
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; background: white; min-height: 100vh; }
        h1 { color: #2c3e50; margin-bottom: 10px; }
        h2 { color: #34495e; margin: 30px 0 15px; padding-bottom: 10px; border-bottom: 2px solid #3498db; }
        h3 { color: #2c3e50; margin: 20px 0 10px; }
        h4 { color: #555; margin: 15px 0 8px; }
        p { margin-bottom: 10px; }
        code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-family: 'Monaco', 'Menlo', monospace; font-size: 0.9em; }
        pre { background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 5px; overflow-x: auto; margin: 10px 0; }
        pre code { background: none; padding: 0; }
        .endpoint { border: 1px solid #ddd; border-radius: 5px; margin: 15px 0; overflow: hidden; }
        .endpoint-header { padding: 12px 15px; cursor: pointer; display: flex; align-items: center; gap: 10px; }
        .endpoint-body { padding: 15px; border-top: 1px solid #ddd; display: block; }
        .method { font-weight: bold; padding: 4px 8px; border-radius: 3px; color: white; font-size: 0.85em; min-width: 70px; text-align: center; }
        .method-get { background: #61affe; }
        .method-post { background: #49cc90; }
        .method-put { background: #fca130; }
        .method-patch { background: #50e3c2; }
        .method-delete { background: #f93e3e; }
        .path { font-family: monospace; font-size: 0.95em; }
        .deprecated { opacity: 0.6; text-decoration: line-through; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 0.75em; margin-left: 10px; }
        .badge-deprecated { background: #e74c3c; color: white; }
        .parameters-table, .schema-table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        .parameters-table th, .parameters-table td, .schema-table th, .schema-table td { padding: 10px; border: 1px solid #ddd; text-align: left; }
        .parameters-table th, .schema-table th { background: #f8f9fa; }
        .required { color: #e74c3c; }
        .type { color: #3498db; font-family: monospace; }
        .tag-section { margin: 30px 0; }
        .schema-card { border: 1px solid #ddd; border-radius: 5px; margin: 15px 0; padding: 15px; }
        .schema-name { font-weight: bold; color: #2c3e50; }
        .response-code { padding: 2px 6px; border-radius: 3px; font-weight: bold; }
        .response-2xx { background: #d4edda; color: #155724; }
        .response-4xx { background: #f8d7da; color: #721c24; }
        .response-5xx { background: #fff3cd; color: #856404; }
        .version { color: #666; font-size: 0.9em; }
        .description { color: #666; margin: 10px 0; }
        .auth-section { background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0; }
        """

    def _generate_html_header(self, doc: DocumentationStructure) -> str:
        """Generate HTML header section."""
        parts = [
            "    <header>",
            f"      <h1>{html.escape(doc.title)}</h1>",
            f"      <span class=\"version\">Version: {html.escape(doc.version)}</span>",
        ]

        if doc.description:
            parts.append(f"      <p class=\"description\">{html.escape(doc.description)}</p>")

        parts.append("    </header>")
        return "\n".join(parts)

    def _generate_html_overview(self, doc: DocumentationStructure) -> str:
        """Generate HTML overview section."""
        parts = ["    <section class=\"overview\">", "      <h2>Overview</h2>"]

        if doc.base_url:
            parts.append(f"      <p><strong>Base URL:</strong> <code>{html.escape(doc.base_url)}</code></p>")

        if doc.servers:
            parts.append("      <h3>Servers</h3>")
            parts.append("      <ul>")
            for server in doc.servers:
                url = server.get("url", "")
                desc = server.get("description", "")
                parts.append(f"        <li><code>{html.escape(url)}</code> - {html.escape(desc)}</li>")
            parts.append("      </ul>")

        if doc.contact:
            parts.append("      <h3>Contact</h3>")
            if doc.contact.get("email"):
                parts.append(f"      <p>Email: <a href=\"mailto:{doc.contact['email']}\">{doc.contact['email']}</a></p>")
            if doc.contact.get("url"):
                parts.append(f"      <p>URL: <a href=\"{doc.contact['url']}\">{doc.contact['url']}</a></p>")

        parts.append("    </section>")
        return "\n".join(parts)

    def _generate_html_authentication(self, doc: DocumentationStructure) -> str:
        """Generate HTML authentication section."""
        parts = [
            "    <section class=\"auth-section\">",
            "      <h2>Authentication</h2>",
        ]

        for scheme_name, scheme in doc.security_schemes.items():
            scheme_type = scheme.get("type", "unknown")
            parts.append(f"      <h3>{html.escape(scheme_name)}</h3>")
            parts.append(f"      <p><strong>Type:</strong> {html.escape(scheme_type)}</p>")

            if scheme.get("description"):
                parts.append(f"      <p>{html.escape(scheme['description'])}</p>")

            if scheme_type == "apiKey":
                parts.append(f"      <p><strong>Name:</strong> {html.escape(scheme.get('name', ''))}</p>")
                parts.append(f"      <p><strong>In:</strong> {html.escape(scheme.get('in', ''))}</p>")
            elif scheme_type == "http":
                parts.append(f"      <p><strong>Scheme:</strong> {html.escape(scheme.get('scheme', ''))}</p>")

        parts.append("    </section>")
        return "\n".join(parts)

    def _generate_html_tag_section(self, tag_group: TagGroup) -> str:
        """Generate HTML section for a tag group."""
        parts = [
            f"    <section class=\"tag-section\" id=\"{html.escape(tag_group.name.lower().replace(' ', '-'))}\">",
            f"      <h2>{html.escape(tag_group.name)}</h2>",
        ]

        if tag_group.description:
            parts.append(f"      <p class=\"description\">{html.escape(tag_group.description)}</p>")

        for endpoint in tag_group.endpoints:
            parts.append(self._generate_html_endpoint(endpoint))

        parts.append("    </section>")
        return "\n".join(parts)

    def _generate_html_endpoint(self, endpoint: EndpointInfo) -> str:
        """Generate HTML for a single endpoint."""
        method_class = f"method-{endpoint.method.lower()}"
        deprecated_class = " deprecated" if endpoint.deprecated else ""

        parts = [
            f"      <div class=\"endpoint\">",
            f"        <div class=\"endpoint-header{deprecated_class}\">",
            f"          <span class=\"method {method_class}\">{endpoint.method}</span>",
            f"          <span class=\"path\">{html.escape(endpoint.path)}</span>",
        ]

        if endpoint.deprecated:
            parts.append("          <span class=\"badge badge-deprecated\">Deprecated</span>")

        if endpoint.summary:
            parts.append(f"          <span class=\"summary\"> - {html.escape(endpoint.summary)}</span>")

        parts.extend([
            "        </div>",
            "        <div class=\"endpoint-body\">",
        ])

        if endpoint.description:
            parts.append(f"          <p>{html.escape(endpoint.description)}</p>")

        # Parameters
        if endpoint.parameters:
            parts.append("          <h4>Parameters</h4>")
            parts.append("          <table class=\"parameters-table\">")
            parts.append("            <tr><th>Name</th><th>In</th><th>Type</th><th>Required</th><th>Description</th></tr>")

            for param in endpoint.parameters:
                name = param.get("name", "")
                location = param.get("in", "")
                schema = param.get("schema", {})
                param_type = schema.get("type", "string")
                required = "Yes" if param.get("required") else "No"
                desc = param.get("description", "")

                parts.append(f"            <tr>")
                parts.append(f"              <td><code>{html.escape(name)}</code></td>")
                parts.append(f"              <td>{html.escape(location)}</td>")
                parts.append(f"              <td class=\"type\">{html.escape(param_type)}</td>")
                parts.append(f"              <td>{required}</td>")
                parts.append(f"              <td>{html.escape(desc)}</td>")
                parts.append(f"            </tr>")

            parts.append("          </table>")

        # Request body
        if endpoint.request_body:
            parts.append("          <h4>Request Body</h4>")
            content = endpoint.request_body.get("content", {})
            for content_type, media in content.items():
                parts.append(f"          <p><strong>Content-Type:</strong> <code>{html.escape(content_type)}</code></p>")
                if media.get("schema"):
                    parts.append(f"          <pre><code>{html.escape(json.dumps(media['schema'], indent=2))}</code></pre>")

        # Responses
        if endpoint.responses:
            parts.append("          <h4>Responses</h4>")
            for status_code, response in endpoint.responses.items():
                if status_code.startswith("2"):
                    code_class = "response-2xx"
                elif status_code.startswith("4"):
                    code_class = "response-4xx"
                else:
                    code_class = "response-5xx"

                parts.append(f"          <p><span class=\"response-code {code_class}\">{status_code}</span> {html.escape(response.get('description', ''))}</p>")

        parts.extend([
            "        </div>",
            "      </div>",
        ])

        return "\n".join(parts)

    def _generate_html_schemas(self, schemas: list[SchemaInfo]) -> str:
        """Generate HTML schemas section."""
        parts = [
            "    <section class=\"schemas-section\">",
            "      <h2>Schemas</h2>",
        ]

        for schema in schemas:
            parts.append(f"      <div class=\"schema-card\" id=\"schema-{html.escape(schema.name.lower())}\">")
            parts.append(f"        <h3 class=\"schema-name\">{html.escape(schema.name)}</h3>")

            if schema.description:
                parts.append(f"        <p>{html.escape(schema.description)}</p>")

            if schema.is_enum:
                parts.append("        <p><strong>Type:</strong> enum</p>")
                parts.append("        <p><strong>Values:</strong> " + ", ".join(f"<code>{html.escape(str(v))}</code>" for v in schema.enum_values) + "</p>")
            elif schema.properties:
                parts.append("        <table class=\"schema-table\">")
                parts.append("          <tr><th>Property</th><th>Type</th><th>Required</th><th>Description</th></tr>")

                for prop_name, prop_def in schema.properties.items():
                    prop_type = prop_def.get("type", "any")
                    is_required = "Yes" if prop_name in schema.required else "No"
                    desc = prop_def.get("description", "")

                    parts.append(f"          <tr>")
                    parts.append(f"            <td><code>{html.escape(prop_name)}</code></td>")
                    parts.append(f"            <td class=\"type\">{html.escape(prop_type)}</td>")
                    parts.append(f"            <td>{is_required}</td>")
                    parts.append(f"            <td>{html.escape(desc)}</td>")
                    parts.append(f"          </tr>")

                parts.append("        </table>")

            parts.append("      </div>")

        parts.append("    </section>")
        return "\n".join(parts)

    def _generate_markdown(self, doc_structure: DocumentationStructure) -> GeneratedDocument:
        """Generate Markdown documentation."""
        lines = [
            f"# {doc_structure.title}",
            "",
            f"**Version:** {doc_structure.version}",
            "",
        ]

        if doc_structure.description:
            lines.extend([doc_structure.description, ""])

        # Overview
        lines.extend(["## Overview", ""])

        if doc_structure.base_url:
            lines.append(f"**Base URL:** `{doc_structure.base_url}`")
            lines.append("")

        if doc_structure.servers:
            lines.append("### Servers")
            lines.append("")
            for server in doc_structure.servers:
                url = server.get("url", "")
                desc = server.get("description", "")
                lines.append(f"- `{url}` - {desc}")
            lines.append("")

        # Authentication
        if self.config.include_authentication and doc_structure.security_schemes:
            lines.extend(["## Authentication", ""])
            for scheme_name, scheme in doc_structure.security_schemes.items():
                lines.append(f"### {scheme_name}")
                lines.append(f"**Type:** {scheme.get('type', 'unknown')}")
                if scheme.get("description"):
                    lines.append(f"\n{scheme['description']}")
                lines.append("")

        # Endpoints by tag
        for tag_group in doc_structure.tag_groups:
            lines.append(f"## {tag_group.name}")
            lines.append("")

            if tag_group.description:
                lines.extend([tag_group.description, ""])

            for endpoint in tag_group.endpoints:
                lines.extend(self._generate_markdown_endpoint(endpoint))
                lines.append("")

        # Schemas
        if self.config.include_schemas and doc_structure.schemas:
            lines.extend(["## Schemas", ""])

            for schema in doc_structure.schemas:
                lines.append(f"### {schema.name}")
                lines.append("")

                if schema.description:
                    lines.extend([schema.description, ""])

                if schema.is_enum:
                    lines.append("**Type:** enum")
                    lines.append("")
                    lines.append("**Values:**")
                    for value in schema.enum_values:
                        lines.append(f"- `{value}`")
                elif schema.properties:
                    lines.append("| Property | Type | Required | Description |")
                    lines.append("|----------|------|----------|-------------|")
                    for prop_name, prop_def in schema.properties.items():
                        prop_type = prop_def.get("type", "any")
                        is_required = "Yes" if prop_name in schema.required else "No"
                        desc = prop_def.get("description", "")
                        lines.append(f"| `{prop_name}` | {prop_type} | {is_required} | {desc} |")

                lines.append("")

        content = "\n".join(lines)

        return GeneratedDocument(
            path="README.md",
            content=content,
            format=DocumentationFormat.MARKDOWN,
            title=doc_structure.title,
            size_bytes=len(content.encode("utf-8")),
        )

    def _generate_markdown_endpoint(self, endpoint: EndpointInfo) -> list[str]:
        """Generate Markdown for a single endpoint."""
        lines = []

        deprecated_badge = " *(Deprecated)*" if endpoint.deprecated else ""
        lines.append(f"### `{endpoint.method}` {endpoint.path}{deprecated_badge}")
        lines.append("")

        if endpoint.summary:
            lines.append(f"**{endpoint.summary}**")
            lines.append("")

        if endpoint.description:
            lines.extend([endpoint.description, ""])

        # Parameters
        if endpoint.parameters:
            lines.append("**Parameters:**")
            lines.append("")
            lines.append("| Name | In | Type | Required | Description |")
            lines.append("|------|----|----|----------|-------------|")

            for param in endpoint.parameters:
                name = param.get("name", "")
                location = param.get("in", "")
                schema = param.get("schema", {})
                param_type = schema.get("type", "string")
                required = "Yes" if param.get("required") else "No"
                desc = param.get("description", "")
                lines.append(f"| `{name}` | {location} | {param_type} | {required} | {desc} |")

            lines.append("")

        # Responses
        if endpoint.responses:
            lines.append("**Responses:**")
            lines.append("")
            for status_code, response in endpoint.responses.items():
                lines.append(f"- **{status_code}**: {response.get('description', '')}")
            lines.append("")

        return lines

    def _write_files(self, docs: list[GeneratedDocument], output_dir: Path) -> None:
        """Write generated documentation to disk."""
        output_dir.mkdir(parents=True, exist_ok=True)

        for doc in docs:
            file_path = output_dir / doc.path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(doc.content, encoding="utf-8")
