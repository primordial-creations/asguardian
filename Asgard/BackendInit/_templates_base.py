"""
Templates for backend project initialization - Base templates.
"""

APIS_INIT = """\
\"\"\"
API route definitions for this service.
\"\"\"
"""

MODELS_INIT = """\
\"\"\"
Data models for this service.
\"\"\"
"""

MODELS_ENUMS = """\
\"\"\"
Enumeration types for this service.
\"\"\"

from enum import Enum
"""

SERVICES_INIT = """\
\"\"\"
Business logic services for this service.
\"\"\"
"""

PROMPTS_INIT = """\
\"\"\"
Prompt templates and definitions for AI/LLM interactions.
\"\"\"
"""

TESTS_INIT = """\
\"\"\"
Test suite for this service.
\"\"\"
"""

UTILITIES_INIT = """\
\"\"\"
Shared utility functions and helpers for this service.
\"\"\"
"""

README = """\
# Service Name

## Overview

Brief description of what this service does.

## Getting Started

### Prerequisites

- Python 3.11+
- Dependencies listed in requirements.txt or pyproject.toml

### Installation

```bash
pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and fill in the required values.

```bash
cp .env.example .env
```

## Structure

```
apis/         - API route definitions
models/       - Data models and enums
services/     - Business logic
prompts/      - AI/LLM prompt templates
tests/        - Test suite
utilities/    - Shared helpers and utilities
```

## Running Tests

```bash
pytest tests/
```
"""

ENV_EXAMPLE = """\
# Environment variable definitions for this service.
# Copy this file to .env and fill in the required values.
# Do NOT commit .env to version control.

# Application
# APP_ENV=
# APP_PORT=

# Database
# DB_HOST=
# DB_PORT=
# DB_NAME=
# DB_USER=
# DB_PASSWORD=
"""
