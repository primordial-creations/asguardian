"""
TypeScript Generator Request Helpers.

HTTP request method generation helpers for TypeScriptGeneratorService.
"""

from Asgard.Forseti.CodeGen.models.codegen_models import (
    CodeGenConfig,
    HttpClientType,
    MethodDefinition,
)


def generate_method_params(method: MethodDefinition) -> str:
    """Generate method parameter list string."""
    params: list[str] = []

    for param in method.parameters:
        optional = "" if param.required else "?"
        params.append(f"{param.name}{optional}: {param.type_name}")

    if method.request_body_type:
        params.append(f"data: {method.request_body_type}")

    return ", ".join(params)


def generate_ts_request_method(config: CodeGenConfig) -> list[str]:
    """Generate the private request method for TypeScript."""
    lines: list[str] = []

    if config.http_client == HttpClientType.FETCH:
        lines.append("  private async request<T>(")
        lines.append("    method: string,")
        lines.append("    path: string,")
        lines.append("    options: {")
        lines.append("      query?: Record<string, string | number | boolean | undefined>;")
        lines.append("      body?: unknown;")
        lines.append("      headers?: Record<string, string>;")
        lines.append("    } = {}")
        lines.append("  ): Promise<T> {")
        lines.append("    let url = `${this.baseUrl}${path}`;")
        lines.append("")
        lines.append("    if (options.query) {")
        lines.append("      const params = new URLSearchParams();")
        lines.append("      for (const [key, value] of Object.entries(options.query)) {")
        lines.append("        if (value !== undefined) {")
        lines.append("          params.append(key, String(value));")
        lines.append("        }")
        lines.append("      }")
        lines.append("      const queryString = params.toString();")
        lines.append("      if (queryString) {")
        lines.append("        url += `?${queryString}`;")
        lines.append("      }")
        lines.append("    }")
        lines.append("")
        lines.append("    const response = await this.fetchFn(url, {")
        lines.append("      method,")
        lines.append("      headers: { ...this.headers, ...options.headers },")
        lines.append("      body: options.body ? JSON.stringify(options.body) : undefined,")
        lines.append("    });")
        lines.append("")
        lines.append("    if (!response.ok) {")
        lines.append("      const errorBody = await response.text().catch(() => undefined);")
        lines.append("      throw new ApiError(")
        lines.append("        `Request failed: ${response.status} ${response.statusText}`,")
        lines.append("        response.status,")
        lines.append("        errorBody")
        lines.append("      );")
        lines.append("    }")
        lines.append("")
        lines.append("    if (response.status === 204) {")
        lines.append("      return undefined as T;")
        lines.append("    }")
        lines.append("")
        lines.append("    return response.json();")
        lines.append("  }")

    return lines
