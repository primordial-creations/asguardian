"""
Database Migration Generator Service.

Generates migration scripts from schema diffs.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from Asgard.Forseti.Database.models.database_models import (
    DatabaseConfig,
    SchemaDiffResult,
    ChangeType,
)

class MigrationGeneratorService:
    """
    Service for generating database migration scripts.

    Generates migration and rollback scripts from schema differences.

    Usage:
        service = MigrationGeneratorService()
        migration = service.generate(diff_result)
        service.save(migration, "migrations/001_update_schema.sql")
    """

    def __init__(self, config: Optional[DatabaseConfig] = None):
        """
        Initialize the migration generator service.

        Args:
            config: Optional configuration for generation behavior.
        """
        self.config = config or DatabaseConfig()

    def generate(
        self,
        diff_result: SchemaDiffResult,
        include_rollback: bool = True
    ) -> str:
        """
        Generate migration SQL from a diff result.

        Args:
            diff_result: Schema diff result.
            include_rollback: Include rollback statements as comments.

        Returns:
            Migration SQL script.
        """
        lines = []

        # Header
        lines.append("-- Migration Script")
        lines.append(f"-- Generated: {datetime.now().isoformat()}")
        if diff_result.source_schema:
            lines.append(f"-- Source: {diff_result.source_schema}")
        if diff_result.target_schema:
            lines.append(f"-- Target: {diff_result.target_schema}")
        lines.append(f"-- Changes: {diff_result.change_count}")
        lines.append("")
        # Group changes by type for better organization
        table_drops = []
        table_creates = []
        column_changes = []
        index_changes = []
        fk_changes = []

        for change in diff_result.changes:
            if change.change_type == ChangeType.DROP_TABLE:
                table_drops.append(change)
            elif change.change_type == ChangeType.ADD_TABLE:
                table_creates.append(change)
            elif change.change_type in [ChangeType.ADD_COLUMN, ChangeType.DROP_COLUMN, ChangeType.MODIFY_COLUMN]:
                column_changes.append(change)
            elif change.change_type in [ChangeType.ADD_INDEX, ChangeType.DROP_INDEX]:
                index_changes.append(change)
            elif change.change_type in [ChangeType.ADD_FOREIGN_KEY, ChangeType.DROP_FOREIGN_KEY]:
                fk_changes.append(change)

        # Drop foreign keys first (to allow table drops)
        if fk_changes:
            drop_fks = [c for c in fk_changes if c.change_type == ChangeType.DROP_FOREIGN_KEY]
            if drop_fks:
                lines.append("-- Drop Foreign Keys")
                for change in drop_fks:
                    if change.migration_sql:
                        lines.append(change.migration_sql)
                lines.append("")

        # Drop indexes
        if index_changes:
            drop_idxs = [c for c in index_changes if c.change_type == ChangeType.DROP_INDEX]
            if drop_idxs:
                lines.append("-- Drop Indexes")
                for change in drop_idxs:
                    if change.migration_sql:
                        lines.append(change.migration_sql)
                lines.append("")

        # Drop tables
        if table_drops:
            lines.append("-- Drop Tables")
            for change in table_drops:
                if change.migration_sql:
                    lines.append(change.migration_sql)
            lines.append("")

        # Create tables
        if table_creates:
            lines.append("-- Create Tables")
            for change in table_creates:
                if change.migration_sql:
                    lines.append(change.migration_sql)
                    lines.append("")

        # Column changes
        if column_changes:
            lines.append("-- Column Changes")
            for change in column_changes:
                if change.migration_sql:
                    lines.append(f"-- {change.change_type}: {change.table_name}.{change.object_name}")
                    lines.append(change.migration_sql)
            lines.append("")

        # Add indexes
        if index_changes:
            add_idxs = [c for c in index_changes if c.change_type == ChangeType.ADD_INDEX]
            if add_idxs:
                lines.append("-- Add Indexes")
                for change in add_idxs:
                    if change.migration_sql:
                        lines.append(change.migration_sql)
                lines.append("")

        # Add foreign keys last
        if fk_changes:
            add_fks = [c for c in fk_changes if c.change_type == ChangeType.ADD_FOREIGN_KEY]
            if add_fks:
                lines.append("-- Add Foreign Keys")
                for change in add_fks:
                    if change.migration_sql:
                        lines.append(change.migration_sql)
                lines.append("")

        # Rollback section
        if include_rollback:
            lines.append("")
            lines.append("-- " + "=" * 58)
            lines.append("-- ROLLBACK SCRIPT (commented out)")
            lines.append("-- " + "=" * 58)
            lines.append("")

            # Reverse order for rollback
            all_changes = (
                list(reversed(fk_changes)) +
                list(reversed(index_changes)) +
                list(reversed(column_changes)) +
                list(reversed(table_creates)) +
                list(reversed(table_drops))
            )

            for change in all_changes:
                if change.rollback_sql:
                    lines.append(f"-- {change.rollback_sql}")

        return "\n".join(lines)

    def generate_rollback(self, diff_result: SchemaDiffResult) -> str:
        """
        Generate rollback SQL from a diff result.

        Args:
            diff_result: Schema diff result.

        Returns:
            Rollback SQL script.
        """
        lines = []

        # Header
        lines.append("-- Rollback Script")
        lines.append(f"-- Generated: {datetime.now().isoformat()}")
        lines.append(f"-- Reverting changes from: {diff_result.source_schema}")
        lines.append("")

        # Reverse the changes
        for change in reversed(diff_result.changes):
            if change.rollback_sql:
                lines.append(f"-- Rollback: {change.change_type} {change.table_name}")
                lines.append(change.rollback_sql)
                lines.append("")

        return "\n".join(lines)

    def save(
        self,
        migration_sql: str,
        output_path: str | Path,
    ) -> None:
        """
        Save a migration script to a file.

        Args:
            migration_sql: Migration SQL content.
            output_path: Path to save the migration.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(migration_sql, encoding="utf-8")

    def generate_versioned_migration(
        self,
        diff_result: SchemaDiffResult,
        version: str,
        description: str = "schema_update"
    ) -> tuple[str, str]:
        """
        Generate versioned migration and rollback files.

        Args:
            diff_result: Schema diff result.
            version: Version string (e.g., "001", "20231215").
            description: Migration description.

        Returns:
            Tuple of (migration_filename, rollback_filename).
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        base_name = f"{version}_{timestamp}_{description}"

        migration_content = self.generate(diff_result, include_rollback=False)
        rollback_content = self.generate_rollback(diff_result)

        migration_file = f"{base_name}_up.sql"
        rollback_file = f"{base_name}_down.sql"

        return migration_content, rollback_content

    def generate_alembic_migration(
        self,
        diff_result: SchemaDiffResult,
        revision_id: str,
        description: str = "schema update"
    ) -> str:
        """
        Generate an Alembic-style migration script.

        Args:
            diff_result: Schema diff result.
            revision_id: Alembic revision ID.
            description: Migration description.

        Returns:
            Alembic migration Python script.
        """
        lines = []
        lines.append('"""')
        lines.append(description)
        lines.append("")
        lines.append(f"Revision ID: {revision_id}")
        lines.append(f"Create Date: {datetime.now().isoformat()}")
        lines.append('"""')
        lines.append("")
        lines.append(f'revision = "{revision_id}"')
        lines.append('down_revision = None')
        lines.append('branch_labels = None')
        lines.append('depends_on = None')
        lines.append("")
        lines.append("from alembic import op")
        lines.append("import sqlalchemy as sa")
        lines.append("")
        lines.append("")
        lines.append("def upgrade():")

        if not diff_result.changes:
            lines.append("    pass")
        else:
            for change in diff_result.changes:
                if change.migration_sql:
                    # Convert SQL to Alembic op.execute
                    sql = change.migration_sql.replace("'", "\\'")
                    lines.append(f"    op.execute('{sql}')")

        lines.append("")
        lines.append("")
        lines.append("def downgrade():")

        if not diff_result.changes:
            lines.append("    pass")
        else:
            for change in reversed(diff_result.changes):
                if change.rollback_sql:
                    sql = change.rollback_sql.replace("'", "\\'")
                    lines.append(f"    op.execute('{sql}')")

        return "\n".join(lines)
