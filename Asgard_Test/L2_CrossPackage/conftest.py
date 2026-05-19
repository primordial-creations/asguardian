"""
L2 Cross-Package Integration Test Configuration

Shared pytest configuration and fixtures for cross-package integration tests
that validate interactions between multiple Asgard packages.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Add Asgard packages to path
asgard_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(asgard_root))


def pytest_configure(config):
    """Configure pytest markers for L2 cross-package tests."""
    config.addinivalue_line(
        "markers", "cross_package: marks tests that span multiple Asgard packages"
    )
    config.addinivalue_line(
        "markers", "heimdall_volundr: Heimdall to Volundr integration"
    )
    config.addinivalue_line(
        "markers", "forseti_verdandi: Forseti to Verdandi integration"
    )
    config.addinivalue_line(
        "markers", "freya_volundr: Freya to Volundr integration"
    )
    config.addinivalue_line(
        "markers", "full_pipeline: Complete multi-package workflow"
    )
    config.addinivalue_line(
        "markers", "heimdall_forseti: Heimdall to Forseti integration"
    )


@pytest.fixture(scope="session")
def project_root_fixture() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent.parent.parent


@pytest.fixture(scope="session")
def asgard_root_fixture() -> Path:
    """Return the Asgard package root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture
def temp_workspace(tmp_path) -> Generator[Path, None, None]:
    """
    Provide a temporary workspace directory for integration tests.

    Creates subdirectories for:
    - source: Sample source code to analyze
    - output: Generated artifacts
    - reports: Test reports and analysis results
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create subdirectories
    (workspace / "source").mkdir()
    (workspace / "output").mkdir()
    (workspace / "reports").mkdir()

    yield workspace

    # Cleanup
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)


@pytest.fixture
def sample_python_project(temp_workspace: Path) -> Path:
    """
    Create a sample Python project for analysis.

    Returns the path to the project root containing:
    - Multiple Python files with varying complexity
    - A requirements.txt file
    - Package structure
    """
    project_root = temp_workspace / "source" / "sample_project"
    project_root.mkdir(parents=True)

    # Create package structure
    (project_root / "src").mkdir()
    (project_root / "src" / "app").mkdir()

    # Create __init__ files
    (project_root / "src" / "__init__.py").write_text("")
    (project_root / "src" / "app" / "__init__.py").write_text("")

    # Create a simple module
    simple_module = project_root / "src" / "app" / "simple.py"
    simple_module.write_text("""
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
""")

    # Create a complex module with higher complexity
    complex_module = project_root / "src" / "app" / "complex.py"
    complex_module.write_text("""
from typing import List, Optional

class DataProcessor:
    def __init__(self, data: List[int]):
        self.data = data

    def process(self) -> Optional[int]:
        if not self.data:
            return None

        result = 0
        for item in self.data:
            if item > 10:
                result += item * 2
            elif item > 5:
                result += item
            else:
                result -= item

        return result

    def filter_data(self, threshold: int) -> List[int]:
        filtered = []
        for item in self.data:
            if item > threshold:
                filtered.append(item)
        return filtered

def calculate_statistics(numbers: List[int]) -> dict:
    if not numbers:
        return {"mean": 0, "max": 0, "min": 0}

    total = sum(numbers)
    mean = total / len(numbers)
    max_val = max(numbers)
    min_val = min(numbers)

    return {
        "mean": mean,
        "max": max_val,
        "min": min_val,
        "count": len(numbers)
    }
""")

    # Create module with dependencies
    service_module = project_root / "src" / "app" / "service.py"
    service_module.write_text("""
from src.app.complex import DataProcessor, calculate_statistics
from src.app.simple import add, multiply

class DataService:
    def __init__(self):
        self.processor = None

    def initialize(self, data):
        self.processor = DataProcessor(data)

    def get_results(self):
        if not self.processor:
            return None
        return self.processor.process()
""")

    # Create requirements.txt
    requirements = project_root / "requirements.txt"
    requirements.write_text("""
requests>=2.28.0
pydantic>=2.0.0
fastapi>=0.100.0
uvicorn>=0.23.0
""")

    return project_root


@pytest.fixture
def sample_openapi_spec(temp_workspace: Path) -> Path:
    """
    Create a sample OpenAPI specification file.

    Returns path to an OpenAPI 3.0 YAML file.
    """
    spec_file = temp_workspace / "source" / "openapi.yaml"
    spec_content = """
openapi: 3.0.0
info:
  title: Sample API
  version: 1.0.0
  description: A sample API for integration testing
  contact:
    name: API Support
    email: support@example.com

servers:
  - url: https://api.example.com/v1
    description: Production server

paths:
  /users:
    get:
      summary: List all users
      operationId: listUsers
      tags:
        - users
      parameters:
        - name: limit
          in: query
          description: Maximum number of users to return
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 20
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/User'
        '400':
          description: Bad request
        '500':
          description: Internal server error

    post:
      summary: Create a new user
      operationId: createUser
      tags:
        - users
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UserCreate'
      responses:
        '201':
          description: User created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/User'
        '400':
          description: Bad request

  /users/{userId}:
    get:
      summary: Get a user by ID
      operationId: getUser
      tags:
        - users
      parameters:
        - name: userId
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/User'
        '404':
          description: User not found

components:
  schemas:
    User:
      type: object
      required:
        - id
        - username
        - email
      properties:
        id:
          type: string
        username:
          type: string
        email:
          type: string
          format: email
        created_at:
          type: string
          format: date-time

    UserCreate:
      type: object
      required:
        - username
        - email
      properties:
        username:
          type: string
          minLength: 3
          maxLength: 50
        email:
          type: string
          format: email
        password:
          type: string
          minLength: 8
"""
    spec_file.write_text(spec_content)
    return spec_file


@pytest.fixture
def sample_html_page(temp_workspace: Path) -> Path:
    """
    Create a sample HTML page for accessibility testing.

    Returns path to an HTML file with various elements.
    """
    html_file = temp_workspace / "source" / "sample.html"
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sample Page</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            line-height: 1.6;
        }
        .header {
            background-color: #333;
            color: white;
            padding: 15px;
        }
        .content {
            padding: 20px;
        }
        button {
            padding: 10px 20px;
            font-size: 16px;
            cursor: pointer;
        }
        img {
            max-width: 100%;
            height: auto;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
        }
        input[type="text"],
        input[type="email"] {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Welcome to Sample Page</h1>
        <nav aria-label="Main navigation">
            <ul>
                <li><a href="#home">Home</a></li>
                <li><a href="#about">About</a></li>
                <li><a href="#contact">Contact</a></li>
            </ul>
        </nav>
    </div>

    <main class="content">
        <h2>Contact Form</h2>
        <form>
            <div class="form-group">
                <label for="name">Name:</label>
                <input type="text" id="name" name="name" required aria-required="true">
            </div>

            <div class="form-group">
                <label for="email">Email:</label>
                <input type="email" id="email" name="email" required aria-required="true">
            </div>

            <button type="submit">Submit</button>
        </form>

        <section aria-labelledby="features-heading">
            <h2 id="features-heading">Features</h2>
            <ul>
                <li>Feature 1: Fast and responsive</li>
                <li>Feature 2: Secure and reliable</li>
                <li>Feature 3: Easy to use</li>
            </ul>
        </section>
    </main>
</body>
</html>
"""
    html_file.write_text(html_content)
    return html_file


@pytest.fixture
def output_dir(temp_workspace: Path) -> Path:
    """Return the output directory for generated artifacts."""
    return temp_workspace / "output"


@pytest.fixture
def reports_dir(temp_workspace: Path) -> Path:
    """Return the reports directory for test results."""
    return temp_workspace / "reports"
