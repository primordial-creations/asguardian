"""L0 tests for stateful mock server generation (plan 06-B.1).

Flask itself is not a project dependency (stdlib+pydantic+yaml only), so
these tests validate the *generated* Python source: syntactic validity
(`ast.parse`) plus the WireMock-style CRUD shape (POST 201/create, GET
list, GET-by-id 404-if-absent, PUT replace, DELETE 204/then-404), and the
pure routing-shape helpers (`collection_key`,
`stateful_endpoints_by_collection`) directly.
"""

import ast

from Asgard.Forseti.MockServer.models._mock_base_models import HttpMethod, MockResponse, MockServerConfig
from Asgard.Forseti.MockServer.models.mock_models import MockEndpoint, MockServerDefinition
from Asgard.Forseti.MockServer.services._mock_server_generator_helpers import (
    collection_key,
    generate_flask_route_stateful,
    generate_flask_routes,
    stateful_endpoints_by_collection,
)

USERS_ENDPOINTS = [
    MockEndpoint(path="/users", method=HttpMethod.POST, operation_id="createUser",
                 responses={"201": MockResponse(status_code=201, body={})}),
    MockEndpoint(path="/users", method=HttpMethod.GET, operation_id="listUsers",
                 responses={"200": MockResponse(status_code=200, body=[])}),
    MockEndpoint(path="/users/{id}", method=HttpMethod.GET, operation_id="getUser",
                 responses={"200": MockResponse(status_code=200, body={})}),
    MockEndpoint(path="/users/{id}", method=HttpMethod.PUT, operation_id="updateUser",
                 responses={"200": MockResponse(status_code=200, body={})}),
    MockEndpoint(path="/users/{id}", method=HttpMethod.DELETE, operation_id="deleteUser",
                 responses={"204": MockResponse(status_code=204, body=None)}),
]


class TestCollectionKey:
    def test_bare_collection(self):
        assert collection_key("/users") == ("/users", False)

    def test_collection_with_id(self):
        assert collection_key("/users/{id}") == ("/users", True)

    def test_nested_collection_with_id(self):
        assert collection_key("/users/{userId}/orders/{id}") == ("/users/{userId}/orders", True)


class TestStatefulGrouping:
    def test_groups_by_collection_base(self):
        grouped = stateful_endpoints_by_collection(USERS_ENDPOINTS)
        assert set(grouped.keys()) == {"/users"}
        assert len(grouped["/users"]) == 5


class TestStatefulRouteGeneration:
    def test_post_creates_and_returns_201(self):
        config = MockServerConfig(stateful=True)
        code = generate_flask_route_stateful(USERS_ENDPOINTS[0], config)
        assert "_STORE" in code
        assert "201" in code
        ast.parse(_wrap(code))  # syntactically valid Python

    def test_get_by_id_returns_404_when_absent(self):
        config = MockServerConfig(stateful=True)
        code = generate_flask_route_stateful(USERS_ENDPOINTS[2], config)
        assert "404" in code
        ast.parse(_wrap(code))

    def test_delete_returns_204(self):
        config = MockServerConfig(stateful=True)
        code = generate_flask_route_stateful(USERS_ENDPOINTS[4], config)
        assert "204" in code
        ast.parse(_wrap(code))

    def test_full_routes_file_declares_store_when_stateful(self):
        server_def = MockServerDefinition(title="Users API", endpoints=USERS_ENDPOINTS)
        config = MockServerConfig(stateful=True)
        code = generate_flask_routes(server_def, config)
        assert "_STORE" in code
        compile(code, "<generated>", "exec")

    def test_full_routes_file_omits_store_when_not_stateful(self):
        server_def = MockServerDefinition(title="Users API", endpoints=USERS_ENDPOINTS)
        config = MockServerConfig(stateful=False)
        code = generate_flask_routes(server_def, config)
        assert "_STORE" not in code
        compile(code, "<generated>", "exec")


def _wrap(route_code: str) -> str:
    """Wrap a bare route snippet (uses `@app.route` and `request`/`jsonify`
    names that only exist inside `register_routes`) in a syntactically
    valid enclosing function so ast.parse succeeds."""
    indented = "\n".join("    " + line if line.strip() else line for line in route_code.splitlines())
    return f"def register_routes(app):\n{indented}\n"
