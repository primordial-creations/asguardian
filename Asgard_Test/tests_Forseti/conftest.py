"""
Forseti Test Configuration

Shared pytest fixtures for Forseti package tests.
"""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def sample_openapi_v3_spec():
    """Provide a sample OpenAPI 3.0 specification."""
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Test API",
            "version": "1.0.0",
            "description": "A test API specification"
        },
        "servers": [
            {"url": "https://api.test.com/v1"}
        ],
        "paths": {
            "/users": {
                "get": {
                    "summary": "List users",
                    "operationId": "listUsers",
                    "tags": ["users"],
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/User"}
                                    }
                                }
                            }
                        }
                    }
                },
                "post": {
                    "summary": "Create user",
                    "operationId": "createUser",
                    "tags": ["users"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/User"}
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "User created",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"}
                                }
                            }
                        }
                    }
                }
            },
            "/users/{userId}": {
                "get": {
                    "summary": "Get user",
                    "operationId": "getUser",
                    "tags": ["users"],
                    "parameters": [
                        {
                            "name": "userId",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"}
                                }
                            }
                        },
                        "404": {
                            "description": "User not found"
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "required": ["id", "email"],
                    "properties": {
                        "id": {"type": "integer"},
                        "email": {"type": "string", "format": "email"},
                        "name": {"type": "string"},
                        "createdAt": {"type": "string", "format": "date-time"}
                    }
                }
            }
        }
    }


@pytest.fixture
def sample_openapi_v2_spec():
    """Provide a sample Swagger 2.0 specification."""
    return {
        "swagger": "2.0",
        "info": {
            "title": "Test API",
            "version": "1.0.0"
        },
        "host": "api.test.com",
        "basePath": "/v1",
        "schemes": ["https"],
        "paths": {
            "/users": {
                "get": {
                    "summary": "List users",
                    "produces": ["application/json"],
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "schema": {
                                "type": "array",
                                "items": {"$ref": "#/definitions/User"}
                            }
                        }
                    }
                }
            }
        },
        "definitions": {
            "User": {
                "type": "object",
                "required": ["id", "email"],
                "properties": {
                    "id": {"type": "integer"},
                    "email": {"type": "string", "format": "email"}
                }
            }
        }
    }


@pytest.fixture
def sample_graphql_schema():
    """Provide a sample GraphQL schema."""
    return '''
type Query {
    user(id: ID!): User
    users(limit: Int = 10): [User!]!
}

type Mutation {
    createUser(input: UserInput!): User!
    updateUser(id: ID!, input: UserInput!): User
    deleteUser(id: ID!): Boolean!
}

type User {
    id: ID!
    email: String!
    name: String
    posts: [Post!]!
    createdAt: String!
}

type Post {
    id: ID!
    title: String!
    content: String
    author: User!
    createdAt: String!
}

input UserInput {
    email: String!
    name: String
}
'''


@pytest.fixture
def sample_json_schema():
    """Provide a sample JSON schema."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "User",
        "type": "object",
        "required": ["id", "email"],
        "properties": {
            "id": {
                "type": "integer",
                "minimum": 1
            },
            "email": {
                "type": "string",
                "format": "email",
                "maxLength": 255
            },
            "name": {
                "type": "string",
                "minLength": 1,
                "maxLength": 100
            },
            "age": {
                "type": "integer",
                "minimum": 0,
                "maximum": 150
            },
            "roles": {
                "type": "array",
                "items": {"type": "string"},
                "uniqueItems": True
            },
            "metadata": {
                "type": "object",
                "additionalProperties": {"type": "string"}
            }
        },
        "additionalProperties": False
    }


@pytest.fixture
def sample_sql_schema():
    """Provide a sample SQL schema."""
    return '''
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_users_email UNIQUE (email)
);

CREATE TABLE posts (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    user_id INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_created_at ON posts(created_at);
'''


@pytest.fixture
def sample_valid_data():
    """Provide sample valid data for validation."""
    return {
        "id": 123,
        "email": "test@example.com",
        "name": "Test User",
        "age": 30,
        "roles": ["admin", "user"],
        "metadata": {
            "department": "Engineering",
            "location": "Remote"
        }
    }


@pytest.fixture
def sample_invalid_data():
    """Provide sample invalid data for validation."""
    return {
        "email": "not-an-email",
        "age": -5,
        "roles": ["admin", "admin"],
        "extra_field": "not allowed"
    }


@pytest.fixture
def openapi_spec_file(tmp_path, sample_openapi_v3_spec):
    """Create a temporary OpenAPI spec file."""
    spec_file = tmp_path / "openapi.yaml"
    with open(spec_file, "w") as f:
        yaml.dump(sample_openapi_v3_spec, f)
    return spec_file


@pytest.fixture
def graphql_schema_file(tmp_path, sample_graphql_schema):
    """Create a temporary GraphQL schema file."""
    schema_file = tmp_path / "schema.graphql"
    schema_file.write_text(sample_graphql_schema)
    return schema_file


@pytest.fixture
def json_schema_file(tmp_path, sample_json_schema):
    """Create a temporary JSON schema file."""
    schema_file = tmp_path / "schema.json"
    with open(schema_file, "w") as f:
        json.dump(sample_json_schema, f, indent=2)
    return schema_file


@pytest.fixture
def sql_schema_file(tmp_path, sample_sql_schema):
    """Create a temporary SQL schema file."""
    schema_file = tmp_path / "schema.sql"
    schema_file.write_text(sample_sql_schema)
    return schema_file


@pytest.fixture
def invalid_openapi_spec():
    """Provide an invalid OpenAPI specification."""
    return {
        "openapi": "3.0.0",
        # Missing required "info" field
        "paths": {
            "/test": {
                "get": {
                    # Missing required "responses" field
                    "summary": "Test endpoint"
                }
            }
        }
    }


@pytest.fixture
def invalid_graphql_schema():
    """Provide an invalid GraphQL schema."""
    return '''
type Query {
    user(id: ID!): UndefinedType
}

type User {
    id: ID!
    email String!  # Missing colon
}
'''


@pytest.fixture
def mock_fastapi_source(tmp_path):
    """Create a mock FastAPI source directory."""
    source_dir = tmp_path / "api"
    source_dir.mkdir()

    routes_file = source_dir / "routes.py"
    routes_file.write_text('''
from fastapi import APIRouter

router = APIRouter()

@router.get("/users")
def list_users():
    """Get all users.

    Returns a list of users.
    """
    pass

@router.post("/users", tags=["users"])
def create_user(email: str, name: str = None):
    """Create a new user."""
    pass
''')

    return source_dir
