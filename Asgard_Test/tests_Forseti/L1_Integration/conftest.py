"""
Forseti L1 Integration Test Configuration

Fixtures for integration testing of Forseti services.
"""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


# SQLAlchemy Models for Database Testing
class UserModel(Base):
    """SQLAlchemy model for User table."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True)
    name = Column(String(100))
    created_at = Column(DateTime)

    posts = relationship("PostModel", back_populates="author", cascade="all, delete-orphan")


class PostModel(Base):
    """SQLAlchemy model for Post table."""
    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    created_at = Column(DateTime)

    author = relationship("UserModel", back_populates="posts")


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def sample_openapi_v3_1_spec():
    """Provide a sample OpenAPI 3.1 specification."""
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Advanced Test API",
            "version": "2.0.0",
            "description": "A comprehensive test API specification for 3.1 features",
            "contact": {
                "name": "API Support",
                "email": "support@test.com"
            }
        },
        "servers": [
            {"url": "https://api.test.com/v2"},
            {"url": "https://staging.test.com/v2"}
        ],
        "paths": {
            "/users": {
                "get": {
                    "summary": "List users",
                    "operationId": "listUsers",
                    "tags": ["users"],
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer", "default": 10}
                        },
                        {
                            "name": "offset",
                            "in": "query",
                            "schema": {"type": "integer", "default": 0}
                        }
                    ],
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
                                "schema": {"$ref": "#/components/schemas/UserInput"}
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
                        },
                        "400": {
                            "description": "Invalid input"
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
                        "name": {"type": ["string", "null"]},  # 3.1 feature
                        "createdAt": {"type": "string", "format": "date-time"}
                    }
                },
                "UserInput": {
                    "type": "object",
                    "required": ["email"],
                    "properties": {
                        "email": {"type": "string", "format": "email"},
                        "name": {"type": ["string", "null"]}
                    }
                }
            }
        }
    }


@pytest.fixture
def complex_graphql_schema():
    """Provide a complex GraphQL schema with directives and interfaces."""
    return '''
directive @deprecated(
    reason: String = "No longer supported"
) on FIELD_DEFINITION | ENUM_VALUE

directive @auth(
    requires: Role = USER
) on OBJECT | FIELD_DEFINITION

enum Role {
    ADMIN
    USER
    GUEST
}

interface Node {
    id: ID!
    createdAt: String!
}

type Query {
    user(id: ID!): User
    users(limit: Int = 10, offset: Int = 0): [User!]!
    post(id: ID!): Post
    posts(userId: ID): [Post!]!
    search(query: String!): [SearchResult!]!
}

type Mutation {
    createUser(input: UserInput!): User! @auth(requires: ADMIN)
    updateUser(id: ID!, input: UserInput!): User @auth(requires: ADMIN)
    deleteUser(id: ID!): Boolean! @auth(requires: ADMIN)
    createPost(input: PostInput!): Post! @auth(requires: USER)
}

type Subscription {
    userCreated: User!
    postPublished(userId: ID): Post!
}

type User implements Node {
    id: ID!
    email: String!
    name: String
    posts: [Post!]!
    createdAt: String!
    role: Role!
    legacyField: String @deprecated(reason: "Use name instead")
}

type Post implements Node {
    id: ID!
    title: String!
    content: String
    author: User!
    comments: [Comment!]!
    createdAt: String!
    published: Boolean!
}

type Comment {
    id: ID!
    content: String!
    author: User!
    post: Post!
    createdAt: String!
}

union SearchResult = User | Post | Comment

input UserInput {
    email: String!
    name: String
    role: Role = USER
}

input PostInput {
    title: String!
    content: String
    published: Boolean = false
}
'''


@pytest.fixture
def json_data_samples():
    """Provide JSON data samples for schema inference."""
    return {
        "simple_user": {
            "id": 1,
            "email": "user@example.com",
            "name": "John Doe"
        },
        "user_with_posts": {
            "id": 1,
            "email": "user@example.com",
            "name": "John Doe",
            "posts": [
                {
                    "id": 1,
                    "title": "First Post",
                    "content": "Hello World",
                    "published": True
                },
                {
                    "id": 2,
                    "title": "Second Post",
                    "content": "Another post",
                    "published": False
                }
            ]
        },
        "complex_nested": {
            "user": {
                "id": 1,
                "profile": {
                    "firstName": "John",
                    "lastName": "Doe",
                    "age": 30,
                    "addresses": [
                        {
                            "type": "home",
                            "street": "123 Main St",
                            "city": "Springfield",
                            "country": "USA"
                        }
                    ]
                }
            },
            "metadata": {
                "timestamp": "2024-01-01T00:00:00Z",
                "version": "1.0"
            }
        }
    }


@pytest.fixture
def jsonschema_draft_7():
    """Provide a JSON Schema draft 7 example."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "https://example.com/schemas/user.json",
        "title": "User",
        "description": "A user in the system",
        "type": "object",
        "required": ["id", "email"],
        "properties": {
            "id": {
                "type": "integer",
                "minimum": 1,
                "description": "Unique identifier"
            },
            "email": {
                "type": "string",
                "format": "email",
                "description": "User email address"
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
                "items": {
                    "type": "string",
                    "enum": ["admin", "user", "guest"]
                },
                "uniqueItems": True
            }
        },
        "additionalProperties": False
    }


@pytest.fixture
def jsonschema_draft_2020_12():
    """Provide a JSON Schema draft 2020-12 example."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://example.com/schemas/user.json",
        "title": "User",
        "type": "object",
        "required": ["id", "email"],
        "properties": {
            "id": {"type": "integer"},
            "email": {"type": "string", "format": "email"},
            "name": {"type": "string"},
            "profile": {
                "$ref": "#/$defs/Profile"
            }
        },
        "$defs": {
            "Profile": {
                "type": "object",
                "properties": {
                    "firstName": {"type": "string"},
                    "lastName": {"type": "string"},
                    "age": {"type": "integer"}
                }
            }
        }
    }


@pytest.fixture
def breaking_change_specs(sample_openapi_v3_spec):
    """Provide two API specs with breaking changes between them."""
    v1_spec = sample_openapi_v3_spec.copy()

    v2_spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "Test API",
            "version": "2.0.0",
            "description": "Updated API with breaking changes"
        },
        "servers": [
            {"url": "https://api.test.com/v2"}
        ],
        "paths": {
            "/users": {
                "get": {
                    "summary": "List users",
                    "operationId": "listUsers",
                    "tags": ["users"],
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "required": True,  # Breaking: now required
                            "schema": {"type": "integer"}
                        }
                    ],
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
                }
                # Breaking: removed POST endpoint
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
                            "schema": {"type": "string"}  # Breaking: changed from integer
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
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "required": ["id", "email", "name"],  # Breaking: name now required
                    "properties": {
                        "id": {"type": "integer"},
                        "email": {"type": "string", "format": "email"},
                        "name": {"type": "string"},
                        # Breaking: removed createdAt field
                        "updatedAt": {"type": "string", "format": "date-time"}  # New field
                    }
                }
            }
        }
    }

    return {"v1": v1_spec, "v2": v2_spec}


@pytest.fixture
def compatible_specs(sample_openapi_v3_spec):
    """Provide two API specs that are backward compatible."""
    v1_spec = sample_openapi_v3_spec.copy()

    v2_spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "Test API",
            "version": "1.1.0",
            "description": "Updated API with backward compatible changes"
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
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer", "default": 10}
                        }
                    ],
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
                        "createdAt": {"type": "string", "format": "date-time"},
                        "updatedAt": {"type": "string", "format": "date-time"}  # New optional field
                    }
                }
            }
        }
    }

    return {"v1": v1_spec, "v2": v2_spec}


@pytest.fixture
def sqlalchemy_models():
    """Provide SQLAlchemy model classes for database testing."""
    return {
        "User": UserModel,
        "Post": PostModel
    }


@pytest.fixture
def database_versions(tmp_path):
    """Provide two database schema versions for migration testing."""
    v1_schema = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
"""

    v2_schema = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE user_profiles (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    user_id INTEGER NOT NULL,
    bio TEXT,
    avatar_url VARCHAR(500),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active);
CREATE INDEX idx_profiles_user_id ON user_profiles(user_id);
"""

    v1_file = tmp_path / "schema_v1.sql"
    v2_file = tmp_path / "schema_v2.sql"

    v1_file.write_text(v1_schema)
    v2_file.write_text(v2_schema)

    return {"v1": v1_file, "v2": v2_file}


@pytest.fixture
def fastapi_source_with_models(tmp_path):
    """Create a realistic FastAPI source directory with Pydantic models."""
    source_dir = tmp_path / "api"
    source_dir.mkdir()

    # Models file
    models_file = source_dir / "models.py"
    models_file.write_text('''
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    """Base user model."""
    email: EmailStr
    name: Optional[str] = None

class UserCreate(UserBase):
    """User creation model."""
    password: str = Field(..., min_length=8)

class User(UserBase):
    """User response model."""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class PostBase(BaseModel):
    """Base post model."""
    title: str = Field(..., max_length=200)
    content: Optional[str] = None
    published: bool = False

class Post(PostBase):
    """Post response model."""
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True
''')

    # Routes file
    routes_file = source_dir / "routes.py"
    routes_file.write_text('''
from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
from .models import User, UserCreate, Post, PostBase

router = APIRouter()

@router.get("/users", response_model=List[User], tags=["users"])
def list_users(limit: int = 10, offset: int = 0):
    """Get all users with pagination.

    Args:
        limit: Maximum number of users to return
        offset: Number of users to skip

    Returns:
        List of users
    """
    pass

@router.post("/users", response_model=User, status_code=status.HTTP_201_CREATED, tags=["users"])
def create_user(user: UserCreate):
    """Create a new user.

    Args:
        user: User data

    Returns:
        Created user
    """
    pass

@router.get("/users/{user_id}", response_model=User, tags=["users"])
def get_user(user_id: int):
    """Get a user by ID.

    Args:
        user_id: User identifier

    Returns:
        User data

    Raises:
        HTTPException: If user not found
    """
    pass

@router.get("/users/{user_id}/posts", response_model=List[Post], tags=["posts"])
def list_user_posts(user_id: int, published: Optional[bool] = None):
    """Get all posts for a user.

    Args:
        user_id: User identifier
        published: Filter by published status

    Returns:
        List of posts
    """
    pass
''')

    return source_dir
