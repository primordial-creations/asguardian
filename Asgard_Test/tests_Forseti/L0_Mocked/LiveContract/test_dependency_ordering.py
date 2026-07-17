"""
L0 Unit Tests for RESTler-style producer/consumer dependency ordering.

Pure/offline - no network. Petstore-style fixture asserts that
`POST /pets` orders before `GET /pets/{petId}`, which orders before
`DELETE /pets/{petId}`.
"""

import pytest

from Asgard.Forseti.LiveContract.services._dependency_helpers import (
    build_dependency_edges,
    extract_operations,
    topological_order,
)
from Asgard.Forseti.LiveContract.services.probe_planner_service import (
    ProbePlannerService,
)

PETSTORE_SPEC = {
    "paths": {
        "/pets/{petId}": {
            "get": {
                "operationId": "getPet",
                "parameters": [{"name": "petId", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {"type": "object", "properties": {"id": {"type": "string"}, "name": {"type": "string"}}}
                            }
                        }
                    }
                },
            },
            "delete": {
                "operationId": "deletePet",
                "parameters": [{"name": "petId", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"204": {}},
            },
        },
        "/pets": {
            "post": {
                "operationId": "createPet",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}
                        }
                    }
                },
                "responses": {
                    "201": {
                        "content": {
                            "application/json": {
                                "schema": {"type": "object", "properties": {"id": {"type": "string"}, "name": {"type": "string"}}}
                            }
                        }
                    }
                },
            }
        },
    }
}


class TestExtractOperations:
    def test_extracts_all_operations(self):
        ops = extract_operations(PETSTORE_SPEC)
        ids = {op.operation_id for op in ops}
        assert ids == {"getPet", "deletePet", "createPet"}

    def test_produced_fields_captured(self):
        ops = {op.operation_id: op for op in extract_operations(PETSTORE_SPEC)}
        assert "id" in ops["createPet"].produced_fields

    def test_path_params_captured(self):
        ops = {op.operation_id: op for op in extract_operations(PETSTORE_SPEC)}
        assert ops["getPet"].path_params == ["petId"]


class TestDependencyEdges:
    def test_producer_consumer_edge_detected(self):
        ops = extract_operations(PETSTORE_SPEC)
        edges = build_dependency_edges(ops)
        assert ("createPet", "getPet") in edges
        assert ("createPet", "deletePet") in edges


class TestTopologicalOrder:
    def test_create_before_get_and_delete(self):
        ops = extract_operations(PETSTORE_SPEC)
        ordered, dropped = topological_order(ops)
        order_ids = [op.operation_id for op in ordered]
        assert order_ids.index("createPet") < order_ids.index("getPet")
        assert order_ids.index("createPet") < order_ids.index("deletePet")
        assert dropped == []

    def test_no_dependency_case_preserves_declared_order(self):
        spec = {
            "paths": {
                "/a": {"get": {"operationId": "opA", "responses": {}}},
                "/b": {"get": {"operationId": "opB", "responses": {}}},
            }
        }
        ops = extract_operations(spec)
        ordered, dropped = topological_order(ops)
        assert [op.operation_id for op in ordered] == ["opA", "opB"]
        assert dropped == []

    def test_cycle_is_broken_not_raised(self):
        # A produces field consumed by B; B produces field consumed by A -> cycle.
        spec = {
            "paths": {
                "/a/{bId}": {
                    "get": {
                        "operationId": "opA",
                        "parameters": [{"name": "bId", "in": "path"}],
                        "responses": {"200": {"content": {"application/json": {"schema": {"type": "object", "properties": {"aId": {"type": "string"}}}}}}},
                    }
                },
                "/b/{aId}": {
                    "get": {
                        "operationId": "opB",
                        "parameters": [{"name": "aId", "in": "path"}],
                        "responses": {"200": {"content": {"application/json": {"schema": {"type": "object", "properties": {"bId": {"type": "string"}}}}}}},
                    }
                },
            }
        }
        ops = extract_operations(spec)
        ordered, dropped = topological_order(ops)
        assert {op.operation_id for op in ordered} == {"opA", "opB"}
        assert len(dropped) >= 1


class TestProbePlannerService:
    def test_plan_orders_operations(self):
        plan = ProbePlannerService().plan(PETSTORE_SPEC)
        ids = [op.operation_id for op in plan.operations]
        assert ids.index("createPet") < ids.index("getPet")
        assert plan.ignored_cycle_edges == []
