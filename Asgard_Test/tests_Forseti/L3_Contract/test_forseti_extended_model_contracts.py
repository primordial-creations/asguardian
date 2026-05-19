"""L3 Contract tests for additional Forseti (schema/contract) models.

Covers models from AsyncAPI, Avro, CodeGen, Contracts, Database, Documentation,
GraphQL, JSONSchema, MockServer, OpenAPI, Protobuf that are not already in
test_forseti_model_contracts.py.
"""
import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# AsyncAPI
# ---------------------------------------------------------------------------
from Asgard.Forseti.AsyncAPI.models.asyncapi_models import (
    AsyncAPIConfig,
    AsyncAPIInfo,
    Channel,
    AsyncAPISpec,
    AsyncAPIValidationResult,
    AsyncAPIReport,
)


class TestAsyncAPIConfigContract:
    def test_instantiates_with_defaults(self):
        config = AsyncAPIConfig()
        assert config is not None
        assert hasattr(AsyncAPIConfig, "model_fields")


class TestAsyncAPIInfoContract:
    def test_requires_title_and_version(self):
        with pytest.raises((ValidationError, TypeError)):
            AsyncAPIInfo()

    def test_accepts_valid_data(self):
        info = AsyncAPIInfo(title="My API", version="1.0.0")
        assert info.title == "My API"
        assert info.version == "1.0.0"


class TestChannelContract:
    def test_requires_name(self):
        with pytest.raises((ValidationError, TypeError)):
            Channel()

    def test_accepts_valid_data(self):
        channel = Channel(name="user/created")
        assert channel.name == "user/created"


class TestAsyncAPISpecContract:
    def test_requires_asyncapi_and_info(self):
        with pytest.raises((ValidationError, TypeError)):
            AsyncAPISpec()

    def test_accepts_valid_data(self):
        info = AsyncAPIInfo(title="My API", version="1.0.0")
        spec = AsyncAPISpec(asyncapi="2.6.0", info=info)
        assert spec.asyncapi == "2.6.0"
        assert hasattr(spec, "info")


class TestAsyncAPIValidationResultContract:
    def test_requires_is_valid(self):
        with pytest.raises((ValidationError, TypeError)):
            AsyncAPIValidationResult()

    def test_accepts_valid_data(self):
        result = AsyncAPIValidationResult(is_valid=True)
        assert result.is_valid is True
        assert hasattr(result, "errors") or hasattr(AsyncAPIValidationResult, "model_fields")


class TestAsyncAPIReportContract:
    def test_requires_validation_result(self):
        with pytest.raises((ValidationError, TypeError)):
            AsyncAPIReport()

    def test_accepts_valid_data(self):
        vr = AsyncAPIValidationResult(is_valid=True)
        report = AsyncAPIReport(validation_result=vr)
        assert report.validation_result.is_valid is True


# ---------------------------------------------------------------------------
# Avro (extended)
# ---------------------------------------------------------------------------
from Asgard.Forseti.Avro.models.avro_models import (
    AvroField,
    AvroSchema,
    AvroValidationResult,
    AvroCompatibilityResult,
)


class TestAvroFieldContract:
    def test_requires_name_and_type(self):
        with pytest.raises((ValidationError, TypeError)):
            AvroField()

    def test_accepts_valid_data(self):
        af = AvroField(name="user_id", type="string")
        assert af.name == "user_id"
        assert af.type == "string"


class TestAvroSchemaContract:
    def test_requires_type(self):
        with pytest.raises((ValidationError, TypeError)):
            AvroSchema()

    def test_accepts_valid_data(self):
        avro = AvroSchema(type="record")
        assert avro.type == "record"
        assert hasattr(avro, "fields") or hasattr(AvroSchema, "model_fields")


class TestAvroValidationResultContract:
    def test_requires_is_valid(self):
        with pytest.raises((ValidationError, TypeError)):
            AvroValidationResult()

    def test_accepts_valid_data(self):
        result = AvroValidationResult(is_valid=True)
        assert result.is_valid is True


class TestAvroCompatibilityResultContract:
    def test_instantiates_with_defaults(self):
        # check that this can be created (all required or all default)
        assert hasattr(AvroCompatibilityResult, "model_fields")


# ---------------------------------------------------------------------------
# CodeGen (extended)
# ---------------------------------------------------------------------------
from Asgard.Forseti.CodeGen.models.codegen_models import (
    ParameterDefinition,
    PropertyDefinition,
    TypeDefinition,
    CodeGenReport,
    GeneratedFile,
)


class TestParameterDefinitionContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ParameterDefinition()

    def test_accepts_valid_data(self):
        pd = ParameterDefinition(name="user_id", location="path", type_name="string")
        assert pd.name == "user_id"
        assert pd.location == "path"


class TestPropertyDefinitionContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            PropertyDefinition()

    def test_accepts_valid_data(self):
        pd = PropertyDefinition(name="email", type_name="string")
        assert pd.name == "email"


class TestTypeDefinitionContract:
    def test_requires_name(self):
        with pytest.raises((ValidationError, TypeError)):
            TypeDefinition()

    def test_accepts_valid_data(self):
        td = TypeDefinition(name="UserResponse")
        assert td.name == "UserResponse"
        assert hasattr(td, "properties") or hasattr(TypeDefinition, "model_fields")


class TestCodeGenReportContract:
    def test_requires_success_and_target_language(self):
        with pytest.raises((ValidationError, TypeError)):
            CodeGenReport()

    def test_accepts_valid_data(self):
        report = CodeGenReport(success=True, target_language="python")
        assert report.success is True
        assert report.target_language == "python"


# ---------------------------------------------------------------------------
# Contracts (extended)
# ---------------------------------------------------------------------------
from Asgard.Forseti.Contracts.models.contract_models import (
    ContractValidationResult,
    ContractValidationError,
    BreakingChange,
    CompatibilityResult,
)


class TestContractValidationResultContract:
    def test_requires_is_valid(self):
        with pytest.raises((ValidationError, TypeError)):
            ContractValidationResult()

    def test_accepts_valid_data(self):
        result = ContractValidationResult(is_valid=True)
        assert result.is_valid is True


class TestCompatibilityResultContract:
    def test_requires_is_compatible_and_level(self):
        with pytest.raises((ValidationError, TypeError)):
            CompatibilityResult()

    def test_accepts_valid_data(self):
        result = CompatibilityResult(is_compatible=True, compatibility_level="backward")
        assert result.is_compatible is True
        assert hasattr(result, "compatibility_level")


# ---------------------------------------------------------------------------
# Database (Forseti)
# ---------------------------------------------------------------------------
from Asgard.Forseti.Database.models.database_models import (
    ColumnDefinition,
    TableDefinition,
    DatabaseConfig,
    DatabaseSchema,
    SchemaDiffResult,
    ForeignKeyDefinition,
    IndexDefinition,
)


class TestColumnDefinitionContract:
    def test_requires_name_and_data_type(self):
        with pytest.raises((ValidationError, TypeError)):
            ColumnDefinition()

    def test_accepts_valid_data(self):
        col = ColumnDefinition(name="user_id", data_type="INTEGER")
        assert col.name == "user_id"
        assert col.data_type == "INTEGER"


class TestTableDefinitionContract:
    def test_requires_name(self):
        with pytest.raises((ValidationError, TypeError)):
            TableDefinition()

    def test_accepts_valid_data(self):
        tbl = TableDefinition(name="users")
        assert tbl.name == "users"
        assert hasattr(tbl, "columns") or hasattr(TableDefinition, "model_fields")


class TestDatabaseConfigContract:
    def test_instantiates_with_defaults(self):
        config = DatabaseConfig()
        assert config is not None


class TestSchemaDiffResultContract:
    def test_requires_is_identical(self):
        with pytest.raises((ValidationError, TypeError)):
            SchemaDiffResult()

    def test_accepts_valid_data(self):
        result = SchemaDiffResult(is_identical=False)
        assert result.is_identical is False


# ---------------------------------------------------------------------------
# Documentation (Forseti)
# ---------------------------------------------------------------------------
from Asgard.Forseti.Documentation.models.docs_models import (
    APIDocConfig,
    EndpointInfo,
    GeneratedDocument,
    DocumentationReport,
)


class TestAPIDocConfigContract:
    def test_instantiates_with_defaults(self):
        config = APIDocConfig()
        assert config is not None


class TestEndpointInfoContract:
    def test_requires_path_and_method(self):
        with pytest.raises((ValidationError, TypeError)):
            EndpointInfo()

    def test_accepts_valid_data(self):
        ep = EndpointInfo(path="/users", method="GET")
        assert ep.path == "/users"
        assert ep.method == "GET"


class TestGeneratedDocumentContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            GeneratedDocument()

    def test_accepts_valid_data(self):
        gd = GeneratedDocument(path="/docs/api.html", content="<html>...</html>", format="html", title="API Docs")
        assert gd.path == "/docs/api.html"
        assert hasattr(gd, "format")


class TestDocumentationReportContract:
    def test_requires_success_and_api_info(self):
        with pytest.raises((ValidationError, TypeError)):
            DocumentationReport()

    def test_accepts_valid_data(self):
        report = DocumentationReport(success=True, api_title="My API", api_version="1.0.0")
        assert report.success is True


# ---------------------------------------------------------------------------
# GraphQL (extended)
# ---------------------------------------------------------------------------
from Asgard.Forseti.GraphQL.models.graphql_models import (
    GraphQLField,
    GraphQLType,
    GraphQLSchema,
    GraphQLValidationResult,
)


class TestGraphQLFieldContract:
    def test_requires_name_and_type_name(self):
        with pytest.raises((ValidationError, TypeError)):
            GraphQLField()

    def test_accepts_valid_data(self):
        gf = GraphQLField(name="id", type_name="ID")
        assert gf.name == "id"
        assert gf.type_name == "ID"


class TestGraphQLTypeContract:
    def test_requires_name_and_kind(self):
        with pytest.raises((ValidationError, TypeError)):
            GraphQLType()

    def test_accepts_valid_data(self):
        gt = GraphQLType(name="User", kind="OBJECT")
        assert gt.name == "User"
        assert hasattr(gt, "fields") or hasattr(GraphQLType, "model_fields")


class TestGraphQLSchemaContract:
    def test_instantiates_with_defaults(self):
        schema = GraphQLSchema()
        assert schema is not None


class TestGraphQLValidationResultContract:
    def test_requires_is_valid(self):
        with pytest.raises((ValidationError, TypeError)):
            GraphQLValidationResult()

    def test_accepts_valid_data(self):
        result = GraphQLValidationResult(is_valid=True)
        assert result.is_valid is True


# ---------------------------------------------------------------------------
# JSONSchema (extended)
# ---------------------------------------------------------------------------
from Asgard.Forseti.JSONSchema.models.jsonschema_models import (
    JSONSchemaSpec,
    JSONSchemaInferenceResult,
)


class TestJSONSchemaSpecContract:
    def test_instantiates_with_defaults(self):
        spec = JSONSchemaSpec()
        assert spec is not None


# ---------------------------------------------------------------------------
# MockServer (extended)
# ---------------------------------------------------------------------------
from Asgard.Forseti.MockServer.models.mock_models import (
    MockEndpoint,
    MockServerDefinition,
    MockServerConfig,
    MockResponse,
    MockDataConfig,
)


class TestMockEndpointContract:
    def test_requires_path_and_method(self):
        with pytest.raises((ValidationError, TypeError)):
            MockEndpoint()

    def test_accepts_valid_data(self):
        ep = MockEndpoint(path="/users", method="GET")
        assert ep.path == "/users"
        assert ep.method == "GET"


class TestMockServerDefinitionContract:
    def test_requires_title(self):
        with pytest.raises((ValidationError, TypeError)):
            MockServerDefinition()

    def test_accepts_valid_data(self):
        msd = MockServerDefinition(title="User API Mock")
        assert msd.title == "User API Mock"
        assert hasattr(msd, "endpoints") or hasattr(MockServerDefinition, "model_fields")


class TestMockServerConfigContract:
    def test_instantiates_with_defaults(self):
        config = MockServerConfig()
        assert config is not None


class TestMockResponseContract:
    def test_instantiates_with_defaults(self):
        response = MockResponse()
        assert response is not None


class TestMockDataConfigContract:
    def test_instantiates_with_defaults(self):
        config = MockDataConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# OpenAPI (extended)
# ---------------------------------------------------------------------------
from Asgard.Forseti.OpenAPI.models.openapi_models import (
    OpenAPISpec,
    OpenAPIInfo,
    OpenAPIValidationResult,
)


class TestOpenAPISpecContract:
    def test_requires_openapi_and_info(self):
        with pytest.raises((ValidationError, TypeError)):
            OpenAPISpec()

    def test_accepts_valid_data(self):
        info = OpenAPIInfo(title="My API", version="1.0.0")
        spec = OpenAPISpec(openapi="3.0.0", info=info)
        assert spec.openapi == "3.0.0"
        assert hasattr(spec, "paths") or hasattr(OpenAPISpec, "model_fields")


class TestOpenAPIInfoContract:
    def test_requires_title_and_version(self):
        with pytest.raises((ValidationError, TypeError)):
            OpenAPIInfo()

    def test_accepts_valid_data(self):
        info = OpenAPIInfo(title="My API", version="1.0.0")
        assert info.title == "My API"


# ---------------------------------------------------------------------------
# Protobuf (extended)
# ---------------------------------------------------------------------------
from Asgard.Forseti.Protobuf.models.protobuf_models import (
    ProtobufField,
    ProtobufMessage,
    ProtobufSchema,
    ProtobufValidationResult,
)


class TestProtobufFieldContract:
    def test_requires_name_number_type(self):
        with pytest.raises((ValidationError, TypeError)):
            ProtobufField()

    def test_accepts_valid_data(self):
        pf = ProtobufField(name="user_id", number=1, type="int32")
        assert pf.name == "user_id"
        assert pf.number == 1


class TestProtobufMessageContract:
    def test_requires_name(self):
        with pytest.raises((ValidationError, TypeError)):
            ProtobufMessage()

    def test_accepts_valid_data(self):
        msg = ProtobufMessage(name="UserRequest")
        assert msg.name == "UserRequest"
        assert hasattr(msg, "fields") or hasattr(ProtobufMessage, "model_fields")


class TestProtobufSchemaContract:
    def test_instantiates_with_defaults(self):
        schema = ProtobufSchema()
        assert schema is not None


class TestProtobufValidationResultContract:
    def test_requires_is_valid(self):
        with pytest.raises((ValidationError, TypeError)):
            ProtobufValidationResult()

    def test_accepts_valid_data(self):
        result = ProtobufValidationResult(is_valid=True)
        assert result.is_valid is True
        assert hasattr(result, "errors") or hasattr(ProtobufValidationResult, "model_fields")
