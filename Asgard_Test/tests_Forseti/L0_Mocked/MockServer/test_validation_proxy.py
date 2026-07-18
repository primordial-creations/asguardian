"""L0 tests for the validation proxy (plan 06-B.2, Prism-style).

Exercises `ValidationProxyService.handle_request` directly with an
injected fake `fetcher` so no real socket/network call is made - these
tests must remain fast and hermetic. The `--stateful`-style opt-in
network behaviour (`run_proxy_server`) is exercised only by CLI wiring,
never implicitly.
"""

import json

from Asgard.Forseti.MockServer.services._validation_proxy_helpers import (
    match_operation,
    path_template_to_regex,
)
from Asgard.Forseti.MockServer.services.validation_proxy_service import ValidationProxyService

SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Users API", "version": "1.0.0"},
    "paths": {
        "/users/{id}": {
            "get": {
                "operationId": "getUser",
                "parameters": [{"name": "id", "in": "path"}],
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["id", "name"],
                                    "properties": {
                                        "id": {"type": "string"},
                                        "name": {"type": "string"},
                                    },
                                }
                            }
                        }
                    }
                },
            }
        },
        "/users": {
            "post": {
                "operationId": "createUser",
                "responses": {
                    "201": {
                        "content": {
                            "application/json": {
                                "schema": {"type": "object", "properties": {"id": {"type": "string"}}}
                            }
                        }
                    }
                },
            }
        },
    },
}


class TestPathMatching:
    def test_templated_path_matches(self):
        regex = path_template_to_regex("/users/{id}")
        m = regex.match("/users/42")
        assert m is not None
        assert m.group("id") == "42"

    def test_literal_preferred_over_templated(self):
        from Asgard.Forseti.LiveContract.services._dependency_helpers import extract_operations

        ops = extract_operations(SPEC)
        op = match_operation(ops, "GET", "/users/42")
        assert op is not None
        assert op.operation_id == "getUser"

    def test_no_match_returns_none(self):
        from Asgard.Forseti.LiveContract.services._dependency_helpers import extract_operations

        ops = extract_operations(SPEC)
        assert match_operation(ops, "DELETE", "/nope") is None


def _fake_fetcher(status, headers, body):
    def fetch(method, url, req_headers, req_body, timeout_s):
        return status, headers, body
    return fetch


class TestValidationProxyService:
    def test_valid_response_produces_no_findings(self):
        body = json.dumps({"id": "1", "name": "Ada"}).encode()
        service = ValidationProxyService(
            SPEC, upstream="http://upstream.example", fetcher=_fake_fetcher(200, {}, body)
        )
        status, _headers, resp_body, findings = service.handle_request("GET", "/users/1", {}, b"")
        assert status == 200
        assert resp_body == body
        assert findings == []
        assert service.report().operations_attempted == 1
        assert service.report().has_errors is False

    def test_schema_mismatch_produces_finding(self):
        body = json.dumps({"id": "1"}).encode()  # missing required "name"
        service = ValidationProxyService(
            SPEC, upstream="http://upstream.example", fetcher=_fake_fetcher(200, {}, body)
        )
        _status, _headers, _resp_body, findings = service.handle_request("GET", "/users/1", {}, b"")
        assert len(findings) == 1
        assert findings[0].rule_id == "drift.schema-mismatch"
        assert service.report().has_errors is True

    def test_undocumented_status_produces_finding(self):
        service = ValidationProxyService(
            SPEC, upstream="http://upstream.example", fetcher=_fake_fetcher(500, {}, b"{}")
        )
        _status, _headers, _resp_body, findings = service.handle_request("GET", "/users/1", {}, b"")
        assert len(findings) == 1
        assert findings[0].rule_id == "drift.undocumented-status"

    def test_unmatched_operation_forwards_without_validation(self):
        service = ValidationProxyService(
            SPEC, upstream="http://upstream.example", fetcher=_fake_fetcher(200, {}, b"ok")
        )
        status, _headers, resp_body, findings = service.handle_request("GET", "/unknown", {}, b"")
        assert status == 200
        assert resp_body == b"ok"
        assert findings == []
        assert service.report().operations_attempted == 0

    def test_report_accumulates_across_requests(self):
        service = ValidationProxyService(
            SPEC, upstream="http://upstream.example", fetcher=_fake_fetcher(201, {}, b'{"id": "1"}')
        )
        service.handle_request("POST", "/users", {}, b"{}")
        service.handle_request("POST", "/users", {}, b"{}")
        assert service.report().operations_attempted == 2
