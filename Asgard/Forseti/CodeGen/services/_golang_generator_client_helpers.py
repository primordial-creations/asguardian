"""
Golang Generator Client Helpers.

Client file generation helpers for GolangGeneratorService.
"""

from typing import Any

from Asgard.Forseti.CodeGen.models.codegen_models import (
    CodeGenConfig,
    GeneratedFile,
    MethodDefinition,
    TargetLanguage,
    TypeDefinition,
)


def generate_do_request_method() -> list[str]:
    """Generate the doRequest helper method."""
    lines: list[str] = []

    lines.append("func (c *Client) doRequest(method, path string, query url.Values, body interface{}, result interface{}) error {")
    lines.append('\tfullURL := c.baseURL + path')
    lines.append('\tif len(query) > 0 {')
    lines.append('\t\tfullURL += "?" + query.Encode()')
    lines.append("\t}")
    lines.append("")
    lines.append("\tvar bodyReader io.Reader")
    lines.append("\tif body != nil {")
    lines.append("\t\tjsonBody, err := json.Marshal(body)")
    lines.append("\t\tif err != nil {")
    lines.append("\t\t\treturn err")
    lines.append("\t\t}")
    lines.append("\t\tbodyReader = bytes.NewReader(jsonBody)")
    lines.append("\t}")
    lines.append("")
    lines.append("\treq, err := http.NewRequest(method, fullURL, bodyReader)")
    lines.append("\tif err != nil {")
    lines.append("\t\treturn err")
    lines.append("\t}")
    lines.append("")
    lines.append("\tfor key, value := range c.headers {")
    lines.append("\t\treq.Header.Set(key, value)")
    lines.append("\t}")
    lines.append("")
    lines.append("\tresp, err := c.httpClient.Do(req)")
    lines.append("\tif err != nil {")
    lines.append("\t\treturn err")
    lines.append("\t}")
    lines.append("\tdefer resp.Body.Close()")
    lines.append("")
    lines.append("\tif resp.StatusCode >= 400 {")
    lines.append("\t\trespBody, _ := io.ReadAll(resp.Body)")
    lines.append("\t\treturn &ApiError{")
    lines.append("\t\t\tStatusCode: resp.StatusCode,")
    lines.append('\t\t\tMessage:    fmt.Sprintf("request failed: %s", resp.Status),')
    lines.append("\t\t\tBody:       string(respBody),")
    lines.append("\t\t}")
    lines.append("\t}")
    lines.append("")
    lines.append("\tif resp.StatusCode == http.StatusNoContent || result == nil {")
    lines.append("\t\treturn nil")
    lines.append("\t}")
    lines.append("")
    lines.append("\treturn json.NewDecoder(resp.Body).Decode(result)")
    lines.append("}")

    return lines


def generate_go_api_method(method: MethodDefinition, config: CodeGenConfig, to_camel_case_fn: Any, to_pascal_case_fn: Any) -> list[str]:
    """Generate a single Go API method."""
    lines: list[str] = []

    if config.include_documentation and method.description:
        lines.append(f"// {method.name} {method.description}")
        if method.deprecated:
            lines.append("// Deprecated: This method is deprecated")

    params_str = _go_method_params(method, to_camel_case_fn)
    return_type = f"{method.response_type}, error" if method.response_type else "error"

    lines.append(f"func (c *Client) {method.name}({params_str}) ({return_type}) {{")

    path = method.path
    path_params = [p for p in method.parameters if p.location == "path"]
    query_params = [p for p in method.parameters if p.location == "query"]

    for param in path_params:
        go_name = to_camel_case_fn(param.name)
        path = path.replace(f"{{{param.name}}}", "%v")
        if path.count("%v") > 0:
            lines.append(f'\tpath := fmt.Sprintf("{path}", {go_name})')
            break
    else:
        lines.append(f'\tpath := "{path}"')

    if query_params:
        lines.append("\tquery := url.Values{}")
        for param in query_params:
            go_name = to_camel_case_fn(param.name)
            if "*" in param.type_name:
                lines.append(f"\tif {go_name} != nil {{")
                lines.append(f'\t\tquery.Set("{param.name}", fmt.Sprintf("%v", *{go_name}))')
                lines.append("\t}")
            else:
                lines.append(f'\tquery.Set("{param.name}", fmt.Sprintf("%v", {go_name}))')
    else:
        lines.append("\tquery := url.Values{}")

    body_arg = "body" if method.request_body_type else "nil"
    result_arg = "nil"
    if method.response_type and method.response_type != "":
        lines.append(f"\tvar result {method.response_type}")
        result_arg = "&result"

    lines.append(f'\terr := c.doRequest("{method.http_method}", path, query, {body_arg}, {result_arg})')

    if method.response_type:
        lines.append("\treturn result, err")
    else:
        lines.append("\treturn err")

    lines.append("}")

    return lines


def _go_method_params(method: MethodDefinition, to_camel_case_fn: Any) -> str:
    """Generate Go method parameter list string."""
    params: list[str] = []

    for param in method.parameters:
        go_name = to_camel_case_fn(param.name)
        params.append(f"{go_name} {param.type_name}")

    if method.request_body_type:
        params.append(f"body {method.request_body_type}")

    return ", ".join(params)


def generate_go_client_file(methods: list[MethodDefinition], types: dict[str, TypeDefinition], spec_data: dict[str, Any], config: CodeGenConfig, to_camel_case_fn: Any, to_pascal_case_fn: Any) -> GeneratedFile:
    """Generate the client.go file."""
    lines: list[str] = []
    info = spec_data.get("info", {})

    lines.append(f"// {info.get('title', 'API')} - API Client")
    lines.append("//")
    lines.append("// Generated by Forseti CodeGen")
    lines.append("")
    lines.append(f"package {config.package_name}")
    lines.append("")

    lines.extend([
        'import (', '\t"bytes"', '\t"encoding/json"', '\t"fmt"',
        '\t"io"', '\t"net/http"', '\t"net/url"', '\t"strings"', ')', "",
        "// ApiError represents an API error response",
        "type ApiError struct {",
        "\tStatusCode int", "\tMessage    string", "\tBody       string", "}", "",
        "func (e *ApiError) Error() string {",
        '\treturn fmt.Sprintf("API error %d: %s", e.StatusCode, e.Message)',
        "}", "",
        "// Client is the API client",
        "type Client struct {",
        "\tbaseURL    string", "\thttpClient *http.Client", "\theaders    map[string]string", "}", "",
        "// ClientOption configures the client",
        "type ClientOption func(*Client)", "",
        "// WithHTTPClient sets a custom HTTP client",
        "func WithHTTPClient(client *http.Client) ClientOption {",
        "\treturn func(c *Client) {", "\t\tc.httpClient = client", "\t}", "}", "",
        "// WithHeader adds a custom header",
        "func WithHeader(key, value string) ClientOption {",
        "\treturn func(c *Client) {", "\t\tc.headers[key] = value", "\t}", "}", "",
        "// NewClient creates a new API client",
        "func NewClient(baseURL string, opts ...ClientOption) *Client {",
        "\tc := &Client{",
        '\t\tbaseURL:    strings.TrimSuffix(baseURL, "/"),',
        "\t\thttpClient: http.DefaultClient,",
        "\t\theaders: map[string]string{",
        '\t\t\t"Content-Type": "application/json",',
        "\t\t},",
        "\t}",
        "\tfor _, opt := range opts {",
        "\t\topt(c)",
        "\t}",
        "\treturn c",
        "}", "",
    ])

    lines.extend(generate_do_request_method())
    lines.append("")

    for method in methods:
        lines.extend(generate_go_api_method(method, config, to_camel_case_fn, to_pascal_case_fn))
        lines.append("")

    content = "\n".join(lines)

    return GeneratedFile(
        path="client.go",
        content=content,
        language=TargetLanguage.GOLANG,
        file_type="client",
        line_count=len(lines),
    )
