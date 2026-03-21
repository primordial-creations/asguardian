"""
Docs Generator Helpers.

HTML and Markdown generation helper functions for DocsGeneratorService.
"""

import html
import json

from Asgard.Forseti.Documentation.models.docs_models import (
    DocumentationStructure,
    EndpointInfo,
    SchemaInfo,
    TagGroup,
)


def get_css() -> str:
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


def generate_html_header(doc: DocumentationStructure) -> str:
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


def generate_html_overview(doc: DocumentationStructure) -> str:
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


def generate_html_authentication(doc: DocumentationStructure) -> str:
    """Generate HTML authentication section."""
    parts = ["    <section class=\"auth-section\">", "      <h2>Authentication</h2>"]
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


def generate_html_endpoint(endpoint: EndpointInfo) -> str:
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
    parts.extend(["        </div>", "        <div class=\"endpoint-body\">"])
    if endpoint.description:
        parts.append(f"          <p>{html.escape(endpoint.description)}</p>")
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
    if endpoint.request_body:
        parts.append("          <h4>Request Body</h4>")
        content = endpoint.request_body.get("content", {})
        for content_type, media in content.items():
            parts.append(f"          <p><strong>Content-Type:</strong> <code>{html.escape(content_type)}</code></p>")
            if media.get("schema"):
                parts.append(f"          <pre><code>{html.escape(json.dumps(media['schema'], indent=2))}</code></pre>")
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
    parts.extend(["        </div>", "      </div>"])
    return "\n".join(parts)


def generate_html_tag_section(tag_group: TagGroup) -> str:
    """Generate HTML section for a tag group."""
    parts = [
        f"    <section class=\"tag-section\" id=\"{html.escape(tag_group.name.lower().replace(' ', '-'))}\">",
        f"      <h2>{html.escape(tag_group.name)}</h2>",
    ]
    if tag_group.description:
        parts.append(f"      <p class=\"description\">{html.escape(tag_group.description)}</p>")
    for endpoint in tag_group.endpoints:
        parts.append(generate_html_endpoint(endpoint))
    parts.append("    </section>")
    return "\n".join(parts)


def generate_html_schemas(schemas: list[SchemaInfo]) -> str:
    """Generate HTML schemas section."""
    parts = ["    <section class=\"schemas-section\">", "      <h2>Schemas</h2>"]
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


def generate_markdown_endpoint(endpoint: EndpointInfo) -> list[str]:
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
    if endpoint.responses:
        lines.append("**Responses:**")
        lines.append("")
        for status_code, response in endpoint.responses.items():
            lines.append(f"- **{status_code}**: {response.get('description', '')}")
        lines.append("")
    return lines
