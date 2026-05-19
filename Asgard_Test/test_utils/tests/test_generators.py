"""
Tests for Test Data Generators

Unit tests for test data generation utilities including Python code,
OpenAPI specs, GraphQL schemas, and performance metrics.
"""

import pytest

from Asgard_Test.test_utils.generators import (
    generate_graphql_schema,
    generate_metrics_data,
    generate_openapi_spec,
    generate_python_class,
    generate_python_module,
    generate_web_vitals_data,
)


class TestGeneratePythonClass:
    """Tests for generate_python_class function."""

    def test_generates_class_with_name(self):
        """Test that generated code contains class name."""
        code = generate_python_class("UserService")
        assert "class UserService:" in code

    def test_generates_default_number_of_methods(self):
        """Test that default number of methods is generated."""
        code = generate_python_class("TestClass")
        for i in range(1, 6):
            assert f"def method_{i}" in code

    def test_generates_custom_number_of_methods(self):
        """Test that custom number of methods is generated."""
        code = generate_python_class("TestClass", methods=3)
        assert "def method_1" in code
        assert "def method_2" in code
        assert "def method_3" in code
        assert "def method_4" not in code

    def test_includes_init_method(self):
        """Test that __init__ method is included."""
        code = generate_python_class("TestClass")
        assert "def __init__(self):" in code

    def test_includes_docstrings(self):
        """Test that docstrings are included."""
        code = generate_python_class("TestClass")
        assert '"""' in code

    def test_methods_have_parameters(self):
        """Test that methods have parameters."""
        code = generate_python_class("TestClass", methods=1)
        assert "param1" in code
        assert "param2" in code

    def test_methods_have_return_statements(self):
        """Test that methods have return statements."""
        code = generate_python_class("TestClass", methods=1)
        assert "return result" in code

    def test_generates_valid_python_syntax(self):
        """Test that generated code is valid Python."""
        code = generate_python_class("TestClass", methods=2)
        try:
            compile(code, "<string>", "exec")
        except SyntaxError:
            pytest.fail("Generated code has invalid Python syntax")

    def test_zero_methods(self):
        """Test generating class with zero methods."""
        code = generate_python_class("EmptyClass", methods=0)
        assert "class EmptyClass:" in code
        assert "def __init__(self):" in code
        assert "def method_1" not in code

    def test_many_methods(self):
        """Test generating class with many methods."""
        code = generate_python_class("LargeClass", methods=20)
        assert "def method_1" in code
        assert "def method_20" in code


class TestGeneratePythonModule:
    """Tests for generate_python_module function."""

    def test_generates_module_docstring(self):
        """Test that module docstring is included."""
        code = generate_python_module()
        assert '"""Generated test module."""' in code

    def test_includes_imports(self):
        """Test that imports are included."""
        code = generate_python_module()
        assert "from typing import" in code

    def test_generates_default_functions(self):
        """Test that default number of functions is generated."""
        code = generate_python_module()
        for i in range(1, 6):
            assert f"def function_{i}" in code

    def test_generates_default_classes(self):
        """Test that default number of classes is generated."""
        code = generate_python_module()
        assert "class Class1:" in code
        assert "class Class2:" in code
        assert "class Class3:" in code

    def test_custom_number_of_functions(self):
        """Test custom number of functions."""
        code = generate_python_module(classes=1, functions=2)
        assert "def function_1" in code
        assert "def function_2" in code
        assert "def function_3" not in code

    def test_custom_number_of_classes(self):
        """Test custom number of classes."""
        code = generate_python_module(classes=2, functions=1)
        assert "class Class1:" in code
        assert "class Class2:" in code
        assert "class Class3:" not in code

    def test_functions_have_type_hints(self):
        """Test that functions have type hints."""
        code = generate_python_module(functions=1)
        assert "-> Dict[str, Any]:" in code

    def test_functions_return_dicts(self):
        """Test that functions return dictionaries."""
        code = generate_python_module(functions=1)
        assert "return {" in code

    def test_generates_valid_python_syntax(self):
        """Test that generated module is valid Python."""
        code = generate_python_module(classes=2, functions=3)
        try:
            compile(code, "<string>", "exec")
        except SyntaxError:
            pytest.fail("Generated module has invalid Python syntax")

    def test_zero_functions_and_classes(self):
        """Test generating module with no functions or classes."""
        code = generate_python_module(classes=0, functions=0)
        assert "from typing import" in code
        assert "def function_" not in code
        assert "class Class" not in code


class TestGenerateOpenApiSpec:
    """Tests for generate_openapi_spec function."""

    def test_generates_valid_openapi_structure(self):
        """Test that valid OpenAPI structure is generated."""
        spec = generate_openapi_spec()
        assert "openapi" in spec
        assert "info" in spec
        assert "paths" in spec

    def test_default_openapi_version(self):
        """Test that default OpenAPI version is 3.0."""
        spec = generate_openapi_spec()
        assert spec["openapi"].startswith("3.0")

    def test_custom_openapi_version(self):
        """Test custom OpenAPI version."""
        spec = generate_openapi_spec(version="3.1")
        assert spec["openapi"] == "3.1"

    def test_includes_info_section(self):
        """Test that info section is included."""
        spec = generate_openapi_spec()
        assert "title" in spec["info"]
        assert "description" in spec["info"]
        assert "version" in spec["info"]

    def test_includes_servers_section(self):
        """Test that servers section is included."""
        spec = generate_openapi_spec()
        assert "servers" in spec
        assert len(spec["servers"]) > 0

    def test_generates_default_number_of_endpoints(self):
        """Test that default number of endpoints is generated."""
        spec = generate_openapi_spec()
        assert len(spec["paths"]) == 3

    def test_generates_custom_number_of_endpoints(self):
        """Test custom number of endpoints."""
        spec = generate_openapi_spec(endpoints=5)
        assert len(spec["paths"]) == 5

    def test_endpoints_have_get_method(self):
        """Test that endpoints have GET method."""
        spec = generate_openapi_spec(endpoints=1)
        first_path = list(spec["paths"].keys())[0]
        assert "get" in spec["paths"][first_path]

    def test_endpoints_have_post_method(self):
        """Test that endpoints have POST method."""
        spec = generate_openapi_spec(endpoints=1)
        first_path = list(spec["paths"].keys())[0]
        assert "post" in spec["paths"][first_path]

    def test_get_has_responses(self):
        """Test that GET method has responses."""
        spec = generate_openapi_spec(endpoints=1)
        first_path = list(spec["paths"].keys())[0]
        get_op = spec["paths"][first_path]["get"]
        assert "responses" in get_op
        assert "200" in get_op["responses"]

    def test_post_has_request_body(self):
        """Test that POST method has request body."""
        spec = generate_openapi_spec(endpoints=1)
        first_path = list(spec["paths"].keys())[0]
        post_op = spec["paths"][first_path]["post"]
        assert "requestBody" in post_op

    def test_includes_components_section(self):
        """Test that components section is included."""
        spec = generate_openapi_spec()
        assert "components" in spec
        assert "schemas" in spec["components"]

    def test_has_error_schema(self):
        """Test that Error schema is defined."""
        spec = generate_openapi_spec()
        assert "Error" in spec["components"]["schemas"]

    def test_endpoints_have_operation_ids(self):
        """Test that endpoints have operation IDs."""
        spec = generate_openapi_spec(endpoints=1)
        first_path = list(spec["paths"].keys())[0]
        assert "operationId" in spec["paths"][first_path]["get"]

    def test_zero_endpoints(self):
        """Test generating spec with zero endpoints."""
        spec = generate_openapi_spec(endpoints=0)
        assert len(spec["paths"]) == 0


class TestGenerateGraphqlSchema:
    """Tests for generate_graphql_schema function."""

    def test_generates_schema_string(self):
        """Test that schema string is generated."""
        schema = generate_graphql_schema()
        assert isinstance(schema, str)
        assert len(schema) > 0

    def test_includes_docstring(self):
        """Test that docstring is included."""
        schema = generate_graphql_schema()
        assert '"""' in schema

    def test_includes_scalar_datetime(self):
        """Test that DateTime scalar is included."""
        schema = generate_graphql_schema()
        assert "scalar DateTime" in schema

    def test_generates_default_number_of_types(self):
        """Test that default number of types is generated."""
        schema = generate_graphql_schema()
        assert "type Type1" in schema
        assert "type Type2" in schema
        assert "type Type3" in schema

    def test_generates_custom_number_of_types(self):
        """Test custom number of types."""
        schema = generate_graphql_schema(types=2)
        assert "type Type1" in schema
        assert "type Type2" in schema
        assert "type Type3" not in schema

    def test_types_have_id_field(self):
        """Test that types have ID field."""
        schema = generate_graphql_schema(types=1)
        assert "id: ID!" in schema

    def test_types_have_name_field(self):
        """Test that types have name field."""
        schema = generate_graphql_schema(types=1)
        assert "name: String!" in schema

    def test_types_have_datetime_field(self):
        """Test that types have DateTime field."""
        schema = generate_graphql_schema(types=1)
        assert "createdAt: DateTime!" in schema

    def test_includes_query_type(self):
        """Test that Query type is included."""
        schema = generate_graphql_schema()
        assert "type Query {" in schema

    def test_includes_mutation_type(self):
        """Test that Mutation type is included."""
        schema = generate_graphql_schema()
        assert "type Mutation {" in schema

    def test_query_has_single_queries(self):
        """Test that Query type has single item queries."""
        schema = generate_graphql_schema(types=1)
        assert "type1(id: ID!): Type1" in schema

    def test_query_has_list_queries(self):
        """Test that Query type has list queries."""
        schema = generate_graphql_schema(types=1)
        assert "allType1s: [Type1!]!" in schema

    def test_mutation_has_create(self):
        """Test that Mutation type has create operations."""
        schema = generate_graphql_schema(types=1)
        assert "createType1" in schema

    def test_mutation_has_update(self):
        """Test that Mutation type has update operations."""
        schema = generate_graphql_schema(types=1)
        assert "updateType1" in schema

    def test_mutation_has_delete(self):
        """Test that Mutation type has delete operations."""
        schema = generate_graphql_schema(types=1)
        assert "deleteType1" in schema


class TestGenerateMetricsData:
    """Tests for generate_metrics_data function."""

    def test_generates_default_number_of_points(self):
        """Test that default number of points is generated."""
        data = generate_metrics_data()
        assert len(data) == 100

    def test_generates_custom_number_of_points(self):
        """Test custom number of points."""
        data = generate_metrics_data(points=50)
        assert len(data) == 50

    def test_data_points_have_timestamp(self):
        """Test that data points have timestamp."""
        data = generate_metrics_data(points=5)
        for point in data:
            assert "timestamp" in point
            assert isinstance(point["timestamp"], int)

    def test_data_points_have_value(self):
        """Test that data points have value."""
        data = generate_metrics_data(points=5)
        for point in data:
            assert "value" in point
            assert isinstance(point["value"], (int, float))

    def test_data_points_have_metric_type(self):
        """Test that data points have metric_type."""
        data = generate_metrics_data(points=5)
        for point in data:
            assert "metric_type" in point

    def test_data_points_have_labels(self):
        """Test that data points have labels."""
        data = generate_metrics_data(points=5)
        for point in data:
            assert "labels" in point
            assert isinstance(point["labels"], dict)

    def test_latency_metric_type(self):
        """Test latency metric type."""
        data = generate_metrics_data(points=10, metric_type="latency")
        assert all(point["metric_type"] == "latency" for point in data)

    def test_throughput_metric_type(self):
        """Test throughput metric type."""
        data = generate_metrics_data(points=10, metric_type="throughput")
        assert all(point["metric_type"] == "throughput" for point in data)

    def test_memory_metric_type(self):
        """Test memory metric type."""
        data = generate_metrics_data(points=10, metric_type="memory")
        assert all(point["metric_type"] == "memory" for point in data)

    def test_cpu_metric_type(self):
        """Test CPU metric type."""
        data = generate_metrics_data(points=10, metric_type="cpu")
        assert all(point["metric_type"] == "cpu" for point in data)

    def test_values_have_variance(self):
        """Test that values have variance."""
        data = generate_metrics_data(points=50, metric_type="latency")
        values = [point["value"] for point in data]
        unique_values = set(values)
        assert len(unique_values) > 1

    def test_timestamps_are_sequential(self):
        """Test that timestamps are sequential."""
        data = generate_metrics_data(points=10)
        timestamps = [point["timestamp"] for point in data]
        for i in range(len(timestamps) - 1):
            assert timestamps[i] < timestamps[i + 1]


class TestGenerateWebVitalsData:
    """Tests for generate_web_vitals_data function."""

    def test_generates_vitals_dict(self):
        """Test that vitals dictionary is generated."""
        vitals = generate_web_vitals_data()
        assert isinstance(vitals, dict)

    def test_includes_lcp(self):
        """Test that LCP is included."""
        vitals = generate_web_vitals_data()
        assert "lcp" in vitals

    def test_includes_fid(self):
        """Test that FID is included."""
        vitals = generate_web_vitals_data()
        assert "fid" in vitals

    def test_includes_cls(self):
        """Test that CLS is included."""
        vitals = generate_web_vitals_data()
        assert "cls" in vitals

    def test_includes_ttfb(self):
        """Test that TTFB is included."""
        vitals = generate_web_vitals_data()
        assert "ttfb" in vitals

    def test_includes_fcp(self):
        """Test that FCP is included."""
        vitals = generate_web_vitals_data()
        assert "fcp" in vitals

    def test_includes_metadata(self):
        """Test that metadata is included."""
        vitals = generate_web_vitals_data()
        assert "metadata" in vitals
        assert isinstance(vitals["metadata"], dict)

    def test_good_quality_lcp(self):
        """Test that good quality has good LCP."""
        vitals = generate_web_vitals_data(quality="good")
        assert vitals["lcp"] < 2500

    def test_poor_quality_lcp(self):
        """Test that poor quality has poor LCP."""
        vitals = generate_web_vitals_data(quality="poor")
        assert vitals["lcp"] > 4000

    def test_good_quality_fid(self):
        """Test that good quality has good FID."""
        vitals = generate_web_vitals_data(quality="good")
        assert vitals["fid"] < 100

    def test_poor_quality_fid(self):
        """Test that poor quality has poor FID."""
        vitals = generate_web_vitals_data(quality="poor")
        assert vitals["fid"] > 300

    def test_good_quality_cls(self):
        """Test that good quality has good CLS."""
        vitals = generate_web_vitals_data(quality="good")
        assert vitals["cls"] < 0.1

    def test_poor_quality_cls(self):
        """Test that poor quality has poor CLS."""
        vitals = generate_web_vitals_data(quality="poor")
        assert vitals["cls"] > 0.25

    def test_mixed_quality(self):
        """Test mixed quality vitals."""
        vitals = generate_web_vitals_data(quality="mixed")
        assert 2500 <= vitals["lcp"] <= 4000

    def test_metadata_has_timestamp(self):
        """Test that metadata has timestamp."""
        vitals = generate_web_vitals_data()
        assert "timestamp" in vitals["metadata"]

    def test_metadata_has_url(self):
        """Test that metadata has URL."""
        vitals = generate_web_vitals_data()
        assert "url" in vitals["metadata"]

    def test_metadata_has_quality_rating(self):
        """Test that metadata has quality rating."""
        vitals = generate_web_vitals_data(quality="good")
        assert vitals["metadata"]["quality_rating"] == "good"

    def test_all_vitals_are_numeric(self):
        """Test that all vital values are numeric."""
        vitals = generate_web_vitals_data()
        for key in ["lcp", "fid", "cls", "ttfb", "fcp", "tti", "tbt", "si"]:
            assert isinstance(vitals[key], (int, float))
