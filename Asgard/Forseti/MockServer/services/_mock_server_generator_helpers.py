"""
Mock Server Generator Helpers.

Code generation helper functions for MockServerGeneratorService.
"""

import json
import re

from Asgard.Forseti.MockServer.models.mock_models import (
    MockEndpoint,
    MockServerConfig,
    MockServerDefinition,
)

_TRAILING_PARAM_RE = re.compile(r"/\{([^/{}]+)\}$")


def collection_key(path: str) -> tuple[str, bool]:
    """Split a path template into (collection_base_path, has_id_param).

    `/users` -> ("/users", False); `/users/{id}` -> ("/users", True).
    Nested params beyond the trailing one keep the collection distinct per
    parent, e.g. `/users/{userId}/orders/{id}` -> ("/users/{userId}/orders", True).
    """
    match = _TRAILING_PARAM_RE.search(path)
    if match:
        return path[: match.start()], True
    return path, False


def stateful_endpoints_by_collection(
    endpoints: list[MockEndpoint],
) -> dict[str, list[MockEndpoint]]:
    """Group endpoints that look like collection CRUD (POST base / GET,PUT,DELETE {id})."""
    grouped: dict[str, list[MockEndpoint]] = {}
    for endpoint in endpoints:
        base, _has_id = collection_key(endpoint.path)
        grouped.setdefault(base, []).append(endpoint)
    return grouped


def _method_str(endpoint: MockEndpoint) -> str:
    """Endpoint HTTP method as a plain string.

    `MockEndpoint.Config.use_enum_values=True` stores `.method` as a plain
    str at validation time, but callers (and this module, historically)
    sometimes still hold an `HttpMethod` enum instance - handle both.
    """
    method = endpoint.method
    return method.value if hasattr(method, "value") else str(method)


def endpoint_to_function_name(endpoint: MockEndpoint) -> str:
    """Convert an endpoint to a valid function name."""
    if endpoint.operation_id:
        name = str(endpoint.operation_id).replace("-", "_").replace(".", "_")
        return name
    path_parts = endpoint.path.strip("/").replace("{", "").replace("}", "")
    path_parts = path_parts.replace("/", "_").replace("-", "_")
    return f"{_method_str(endpoint).lower()}_{path_parts}"


def generate_flask_route(endpoint: MockEndpoint, config: MockServerConfig) -> str:
    """Generate a single Flask route."""
    flask_path = endpoint.path.replace("{", "<").replace("}", ">")
    func_name = endpoint_to_function_name(endpoint)
    default_status = endpoint.default_response or "200"
    method_str = _method_str(endpoint)
    response_key = f"{method_str}_{endpoint.path}_{default_status}"
    delay_code = ""
    if config.response_delay_ms > 0:
        delay_code = f"\n        time.sleep({config.response_delay_ms / 1000})"
    return f'''    @app.route("{flask_path}", methods=["{method_str}"])
    def {func_name}(**kwargs):
        """{endpoint.summary or endpoint.description or f"Mock {method_str} {endpoint.path}"}"""{delay_code}
        response_data = MOCK_RESPONSES.get("{response_key}", {{}})
        return jsonify(response_data), {default_status}'''


def generate_flask_route_stateful(endpoint: MockEndpoint, config: MockServerConfig) -> str:
    """Generate a single Flask route backed by the in-memory `_STORE` (WireMock-style).

    POST on a bare collection path stores the JSON body under a generated
    id; GET on `{id}` returns it (404 if absent); PUT replaces it; DELETE
    removes it (subsequent GET then 404s). Non-CRUD-shaped routes
    (methods other than GET/POST/PUT/PATCH/DELETE, or paths that aren't a
    plain collection/id pair) fall back to the static MOCK_RESPONSES path.
    """
    flask_path = endpoint.path.replace("{", "<").replace("}", ">")
    func_name = endpoint_to_function_name(endpoint)
    base, has_id = collection_key(endpoint.path)
    method = _method_str(endpoint)
    delay_code = ""
    if config.response_delay_ms > 0:
        delay_code = f"\n        time.sleep({config.response_delay_ms / 1000})"

    if method == "POST" and not has_id:
        return f'''    @app.route("{flask_path}", methods=["POST"])
    def {func_name}(**kwargs):
        """{endpoint.summary or f"Create under {endpoint.path}"}"""{delay_code}
        payload = request.get_json(silent=True) or {{}}
        new_id = str(_STORE.setdefault("_next_id", [1])[0])
        _STORE.setdefault("_next_id", [1])[0] += 1
        record = dict(payload)
        record["id"] = new_id
        _STORE.setdefault("{base}", {{}})[new_id] = record
        return jsonify(record), 201'''

    if method == "GET" and not has_id:
        return f'''    @app.route("{flask_path}", methods=["GET"])
    def {func_name}(**kwargs):
        """{endpoint.summary or f"List {endpoint.path}"}"""{delay_code}
        return jsonify(list(_STORE.get("{base}", {{}}).values())), 200'''

    if method == "GET" and has_id:
        return f'''    @app.route("{flask_path}", methods=["GET"])
    def {func_name}(**kwargs):
        """{endpoint.summary or f"Get one from {endpoint.path}"}"""{delay_code}
        item_id = str(list(kwargs.values())[-1]) if kwargs else None
        record = _STORE.get("{base}", {{}}).get(item_id)
        if record is None:
            return jsonify({{"error": "not found"}}), 404
        return jsonify(record), 200'''

    if method in ("PUT", "PATCH") and has_id:
        return f'''    @app.route("{flask_path}", methods=["{method}"])
    def {func_name}(**kwargs):
        """{endpoint.summary or f"Update {endpoint.path}"}"""{delay_code}
        item_id = str(list(kwargs.values())[-1]) if kwargs else None
        collection = _STORE.setdefault("{base}", {{}})
        if item_id not in collection:
            return jsonify({{"error": "not found"}}), 404
        payload = request.get_json(silent=True) or {{}}
        record = dict(payload)
        record["id"] = item_id
        collection[item_id] = record
        return jsonify(record), 200'''

    if method == "DELETE" and has_id:
        return f'''    @app.route("{flask_path}", methods=["DELETE"])
    def {func_name}(**kwargs):
        """{endpoint.summary or f"Delete {endpoint.path}"}"""{delay_code}
        item_id = str(list(kwargs.values())[-1]) if kwargs else None
        collection = _STORE.setdefault("{base}", {{}})
        if item_id not in collection:
            return jsonify({{"error": "not found"}}), 404
        del collection[item_id]
        return "", 204'''

    # Fallback: non-CRUD-shaped route, serve the static example response.
    return generate_flask_route(endpoint, config)


def generate_flask_routes(server_def: MockServerDefinition, config: MockServerConfig) -> str:
    """Generate Flask routes file."""
    routes = []
    for endpoint in server_def.endpoints:
        if config.stateful:
            route_code = generate_flask_route_stateful(endpoint, config)
        else:
            route_code = generate_flask_route(endpoint, config)
        routes.append(route_code)
    routes_str = "\n\n".join(routes)
    store_init = '\n_STORE: dict = {}  # WireMock-style in-memory resource store (--stateful)\n' if config.stateful else ""
    return f'''"""
API Routes for {server_def.title}
"""

import time
from flask import Flask, jsonify, request
from mock_data import MOCK_RESPONSES
{store_init}

def register_routes(app: Flask):
    """Register all mock routes with the Flask app."""

{routes_str}
'''


def generate_flask_main(server_def: MockServerDefinition, config: MockServerConfig) -> str:
    """Generate Flask main server file."""
    cors_import = "from flask_cors import CORS" if config.enable_cors else ""
    cors_init = "CORS(app)" if config.enable_cors else ""
    return f'''"""
{server_def.title} - Mock Server
Generated by Forseti MockServer

{server_def.description or ""}
"""

from flask import Flask, jsonify
{cors_import}
from routes import register_routes

app = Flask(__name__)
{cors_init}

# Register all routes
register_routes(app)


@app.errorhandler(404)
def not_found(e):
    return jsonify({{"error": "Not found"}}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({{"error": "Internal server error"}}), 500


if __name__ == "__main__":
    app.run(
        host="{config.host}",
        port={config.port},
        debug=True
    )
'''


def generate_response_data(server_def: MockServerDefinition) -> str:
    """Generate Python mock data file."""
    mock_data = {}
    for endpoint in server_def.endpoints:
        for status_code, response in endpoint.responses.items():
            response_key = f"{_method_str(endpoint)}_{endpoint.path}_{status_code}"
            mock_data[response_key] = response.body
    data_json = json.dumps(mock_data, indent=4, default=str)
    return f'''"""
Mock response data for {server_def.title}
"""

MOCK_RESPONSES = {data_json}
'''


def generate_fastapi_route(endpoint: MockEndpoint, config: MockServerConfig) -> str:
    """Generate a single FastAPI route."""
    method_str = _method_str(endpoint)
    method_lower = method_str.lower()
    func_name = endpoint_to_function_name(endpoint)
    default_status = endpoint.default_response or "200"
    response_key = f"{method_str}_{endpoint.path}_{default_status}"
    delay_code = ""
    if config.response_delay_ms > 0:
        delay_code = f"\n    time.sleep({config.response_delay_ms / 1000})"
    return f'''@app.{method_lower}("{endpoint.path}")
async def {func_name}():{delay_code}
    """{endpoint.summary or endpoint.description or f"Mock {method_str} {endpoint.path}"}"""
    return MOCK_RESPONSES.get("{response_key}", {{}})'''


def generate_express_route(endpoint: MockEndpoint, config: MockServerConfig) -> str:
    """Generate a single Express.js route."""
    express_path = endpoint.path
    for param in endpoint.path_parameters:
        express_path = express_path.replace(f"{{{param.name}}}", f":{param.name}")
    method_str = _method_str(endpoint)
    method_lower = method_str.lower()
    default_status = endpoint.default_response or "200"
    response_key = f"{method_str}_{endpoint.path}_{default_status}"
    delay_code = ""
    if config.response_delay_ms > 0:
        delay_code = f'''
    await new Promise(resolve => setTimeout(resolve, {config.response_delay_ms}));'''
    return f'''// {endpoint.summary or f"{endpoint.method.value} {endpoint.path}"}
app.{method_lower}('{express_path}', {"async " if delay_code else ""}(req, res) => {{{delay_code}
    const response = mockData['{response_key}'] || {{}};
    res.status({default_status}).json(response);
}});'''
