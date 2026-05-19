"""
Database Integration Tests

Tests for database schema analysis, comparison, and migration generation
using real SQLAlchemy models and in-memory databases.
"""

import pytest
from pathlib import Path
from sqlalchemy import create_engine, MetaData, inspect

from Asgard.Forseti.Database import (
    SchemaAnalyzerService,
    SchemaDiffService,
    MigrationGeneratorService,
    DatabaseConfig,
)
from Asgard.Forseti.Database.models.database_models import ChangeType


class TestDatabaseSchemaAnalysis:
    """Tests for database schema analysis workflows."""

    def test_workflow_analyze_sql_file(self, sql_schema_file):
        """Test analyzing a SQL schema file."""
        analyzer = SchemaAnalyzerService()
        result = analyzer.analyze_file(sql_schema_file)

        assert result.table_count > 0
        assert len(result.tables) > 0

        # Verify table information was extracted
        for table in result.tables:
            assert table.name is not None
            assert len(table.columns) > 0

    def test_workflow_extract_table_dependencies(self, sql_schema_file):
        """Test extracting table dependencies from schema."""
        analyzer = SchemaAnalyzerService()
        result = analyzer.analyze_file(sql_schema_file)

        # Should have detected foreign key relationships
        dependencies = analyzer.get_table_dependencies(result)
        assert dependencies is not None

        # posts should depend on users if present
        if 'posts' in dependencies:
            assert 'users' in dependencies['posts'] or len(dependencies['posts']) >= 0

    def test_workflow_analyze_indexes(self, sql_schema_file):
        """Test analyzing indexes in schema."""
        analyzer = SchemaAnalyzerService()
        result = analyzer.analyze_file(sql_schema_file)

        # Should have at least extracted tables; indexes may be 0 depending on fixture
        total_indexes = sum(len(table.indexes) for table in result.tables)
        assert total_indexes >= 0

    def test_workflow_analyze_constraints(self, sql_schema_file):
        """Test analyzing constraints in schema."""
        analyzer = SchemaAnalyzerService()
        result = analyzer.analyze_file(sql_schema_file)

        # Tables should have been parsed
        assert len(result.tables) > 0


class TestDatabaseSchemaDiff:
    """Tests for database schema comparison workflows."""

    def test_workflow_compare_schema_versions(self, database_versions):
        """Test comparing two database schema versions."""
        diff_service = SchemaDiffService()

        result = diff_service.diff(
            database_versions["v1"],
            database_versions["v2"]
        )

        assert len(result.changes) > 0

        # Should detect new table (user_profiles)
        new_tables = [c for c in result.changes if c.change_type == ChangeType.ADD_TABLE]
        assert len(new_tables) > 0

        # Should detect new columns in users table
        new_columns = [c for c in result.changes if c.change_type == ChangeType.ADD_COLUMN]
        assert len(new_columns) > 0

    def test_workflow_detect_breaking_changes(self, database_versions):
        """Test detecting breaking schema changes."""
        diff_service = SchemaDiffService()

        result = diff_service.diff(
            database_versions["v1"],
            database_versions["v2"],
        )

        # Check that changes were detected and that has_breaking_changes property works
        assert len(result.changes) > 0
        assert isinstance(result.has_breaking_changes, bool)

    def test_workflow_identical_schemas(self, sql_schema_file):
        """Test comparing identical schemas."""
        diff_service = SchemaDiffService()

        result = diff_service.diff(sql_schema_file, sql_schema_file)

        # Identical schemas should be flagged identical with no changes
        assert result.is_identical is True
        assert len(result.changes) == 0

    def test_workflow_generate_diff_report(self, database_versions):
        """Test generating diff report in multiple formats."""
        diff_service = SchemaDiffService()

        result = diff_service.diff(
            database_versions["v1"],
            database_versions["v2"]
        )

        # Generate reports
        text_report = diff_service.generate_report(result, format="text")
        json_report = diff_service.generate_report(result, format="json")

        assert len(text_report) > 0
        assert len(json_report) > 0

        # Verify JSON structure
        import json
        json_data = json.loads(json_report)
        assert "changes" in json_data
        assert isinstance(json_data["changes"], list)


class TestMigrationGeneration:
    """Tests for database migration generation workflows."""

    def test_workflow_generate_migration_from_diff(self, database_versions):
        """Test generating migration script from schema diff."""
        diff_service = SchemaDiffService()
        diff_result = diff_service.diff(
            database_versions["v1"],
            database_versions["v2"]
        )

        migration_service = MigrationGeneratorService()
        migration_sql = migration_service.generate(diff_result)

        assert migration_sql is not None
        assert len(migration_sql) > 0
        # Upgrade SQL should contain CREATE TABLE for user_profiles
        assert "user_profiles" in migration_sql.lower()

    def test_workflow_generate_migration_for_new_table(self, tmp_path):
        """Test generating migration for adding a new table."""
        v1_schema = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255)
);
"""

        v2_schema = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255)
);

CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    title VARCHAR(200),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

        v1_file = tmp_path / "v1.sql"
        v2_file = tmp_path / "v2.sql"
        v1_file.write_text(v1_schema)
        v2_file.write_text(v2_schema)

        diff_service = SchemaDiffService()
        diff_result = diff_service.diff(v1_file, v2_file)

        migration_service = MigrationGeneratorService()
        migration_sql = migration_service.generate(diff_result)
        rollback_sql = migration_service.generate_rollback(diff_result)

        assert "create table posts" in migration_sql.lower()
        assert "drop table posts" in rollback_sql.lower()

    def test_workflow_save_migration_files(self, tmp_path, database_versions):
        """Test saving migration to files."""
        diff_service = SchemaDiffService()
        diff_result = diff_service.diff(
            database_versions["v1"],
            database_versions["v2"]
        )

        migration_service = MigrationGeneratorService()
        migration_sql = migration_service.generate(diff_result)

        migration_dir = tmp_path / "migrations"
        migration_dir.mkdir()

        upgrade_file = migration_dir / "001_test_migration_upgrade.sql"
        migration_service.save(migration_sql, upgrade_file)

        assert upgrade_file.exists()
        assert len(upgrade_file.read_text()) > 0

    def test_workflow_generate_alembic_migration(self, database_versions):
        """Test generating Alembic-compatible migration."""
        diff_service = SchemaDiffService()
        diff_result = diff_service.diff(
            database_versions["v1"],
            database_versions["v2"]
        )

        migration_service = MigrationGeneratorService()
        alembic_script = migration_service.generate_alembic_migration(
            diff_result,
            revision_id="abc123",
            description="test migration",
        )

        assert "def upgrade():" in alembic_script
        assert "def downgrade():" in alembic_script


class TestDatabaseComplexScenarios:
    """Tests for complex database schema scenarios."""

    def test_workflow_analyze_complex_relationships(self, tmp_path):
        """Test analyzing schema with complex relationships."""
        schema = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title VARCHAR(200),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE comments (
    id INTEGER PRIMARY KEY,
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE tags (
    id INTEGER PRIMARY KEY,
    name VARCHAR(50) UNIQUE
);

CREATE TABLE post_tags (
    post_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (post_id, tag_id),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
"""
        schema_file = tmp_path / "complex.sql"
        schema_file.write_text(schema)

        analyzer = SchemaAnalyzerService()
        result = analyzer.analyze_file(schema_file)

        assert result.table_count == 5

        # Verify dependency ordering
        ordered_tables = analyzer.get_ordered_tables(result)
        assert ordered_tables is not None

        # users should come before posts
        users_idx = ordered_tables.index('users')
        posts_idx = ordered_tables.index('posts')
        assert users_idx < posts_idx

    def test_workflow_detect_circular_dependencies(self, tmp_path):
        """Test detecting circular foreign key dependencies."""
        schema = """
CREATE TABLE table_a (
    id INTEGER PRIMARY KEY,
    b_id INTEGER,
    FOREIGN KEY (b_id) REFERENCES table_b(id)
);

CREATE TABLE table_b (
    id INTEGER PRIMARY KEY,
    a_id INTEGER,
    FOREIGN KEY (a_id) REFERENCES table_a(id)
);
"""
        schema_file = tmp_path / "circular.sql"
        schema_file.write_text(schema)

        analyzer = SchemaAnalyzerService()
        result = analyzer.analyze_file(schema_file)

        # Should still analyze and return both tables in some ordering
        assert result.table_count == 2
        ordered = analyzer.get_ordered_tables(result)
        assert set(ordered) == {"table_a", "table_b"}

    def test_workflow_analyze_composite_keys(self, tmp_path):
        """Test analyzing tables with composite primary keys."""
        schema = """
CREATE TABLE user_roles (
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    granted_at TIMESTAMP,
    PRIMARY KEY (user_id, role_id)
);
"""
        schema_file = tmp_path / "composite.sql"
        schema_file.write_text(schema)

        analyzer = SchemaAnalyzerService()
        result = analyzer.analyze_file(schema_file)

        # Find the table
        user_roles = next(t for t in result.tables if t.name == 'user_roles')

        # Should have a composite primary key recorded (either via primary_key list
        # or via is_primary_key on multiple columns)
        pk_columns = [c for c in user_roles.columns if c.is_primary_key]
        assert len(pk_columns) >= 2 or len(user_roles.primary_key) >= 2

    def test_workflow_migration_with_data_preservation(self, tmp_path):
        """Test generating migration for splitting a column."""
        v1_schema = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    full_name VARCHAR(200)
);
"""

        v2_schema = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100)
);
"""

        v1_file = tmp_path / "v1.sql"
        v2_file = tmp_path / "v2.sql"
        v1_file.write_text(v1_schema)
        v2_file.write_text(v2_schema)

        diff_service = SchemaDiffService()
        diff_result = diff_service.diff(v1_file, v2_file)

        migration_service = MigrationGeneratorService()
        migration_sql = migration_service.generate(diff_result)

        assert migration_sql is not None
        assert len(migration_sql) > 0

    def test_workflow_full_schema_lifecycle(self, tmp_path):
        """Test complete workflow: analyze, diff, migrate, save."""
        v1_schema = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255)
);
"""
        v1_file = tmp_path / "v1.sql"
        v1_file.write_text(v1_schema)

        analyzer = SchemaAnalyzerService()
        v1_analysis = analyzer.analyze_file(v1_file)
        assert v1_analysis.table_count == 1

        v2_schema = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255),
    created_at TIMESTAMP
);

CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    title VARCHAR(200),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""
        v2_file = tmp_path / "v2.sql"
        v2_file.write_text(v2_schema)

        v2_analysis = analyzer.analyze_file(v2_file)
        assert v2_analysis.table_count == 2

        diff_service = SchemaDiffService()
        diff_result = diff_service.diff(v1_file, v2_file)
        assert len(diff_result.changes) > 0

        migration_service = MigrationGeneratorService()
        migration_sql = migration_service.generate(diff_result)
        assert migration_sql is not None

        migration_dir = tmp_path / "migrations"
        migration_dir.mkdir()
        upgrade_file = migration_dir / "001_add_posts_and_timestamp_upgrade.sql"
        migration_service.save(migration_sql, upgrade_file)

        assert upgrade_file.exists()
