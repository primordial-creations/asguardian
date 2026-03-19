"""
Database Schema Diff Service.

Compares database schemas and identifies differences.
"""

import json
import time
from pathlib import Path
from typing import Optional

from Asgard.Forseti.Database.models.database_models import (
    DatabaseConfig,
    DatabaseSchema,
    SchemaDiffResult,
    SchemaChange,
    ChangeType,
)
from Asgard.Forseti.Database.services.schema_analyzer_service import SchemaAnalyzerService


class SchemaDiffService:
    """
    Service for comparing database schemas.

    Identifies differences between two schemas and generates change reports.

    Usage:
        service = SchemaDiffService()
        result = service.diff("schema_v1.sql", "schema_v2.sql")
        for change in result.changes:
            print(f"{change.change_type}: {change.table_name}")
    """

    def __init__(self, config: Optional[DatabaseConfig] = None):
        """
        Initialize the diff service.

        Args:
            config: Optional configuration for diff behavior.
        """
        self.config = config or DatabaseConfig()
        self.analyzer = SchemaAnalyzerService(config)

    def diff(
        self,
        source_path: str | Path,
        target_path: str | Path
    ) -> SchemaDiffResult:
        """
        Compare two schema files.

        Args:
            source_path: Path to the source (old) schema.
            target_path: Path to the target (new) schema.

        Returns:
            SchemaDiffResult with differences.
        """
        source_schema = self.analyzer.analyze_file(source_path)
        target_schema = self.analyzer.analyze_file(target_path)

        return self.diff_schemas(
            source_schema,
            target_schema,
            str(source_path),
            str(target_path)
        )

    def diff_schemas(
        self,
        source: DatabaseSchema,
        target: DatabaseSchema,
        source_name: Optional[str] = None,
        target_name: Optional[str] = None
    ) -> SchemaDiffResult:
        """
        Compare two database schemas.

        Args:
            source: Source (old) schema.
            target: Target (new) schema.
            source_name: Optional source identifier.
            target_name: Optional target identifier.

        Returns:
            SchemaDiffResult with differences.
        """
        start_time = time.time()
        changes: list[SchemaChange] = []
        added_tables: list[str] = []
        dropped_tables: list[str] = []
        modified_tables: list[str] = []

        source_tables = {t.name: t for t in source.tables}
        target_tables = {t.name: t for t in target.tables}

        if not self.config.case_sensitive:
            source_tables = {k.lower(): v for k, v in source_tables.items()}
            target_tables = {k.lower(): v for k, v in target_tables.items()}

        # Find added tables
        for table_name, table in target_tables.items():
            if table_name not in source_tables:
                added_tables.append(table.name)
                changes.append(SchemaChange(
                    change_type=ChangeType.ADD_TABLE,
                    table_name=table.name,
                    new_definition=table.to_sql(self.config.dialect),
                    migration_sql=table.to_sql(self.config.dialect) + ";",
                    rollback_sql=f"DROP TABLE {table.name};",
                ))

        # Find dropped tables
        for table_name, table in source_tables.items():
            if table_name not in target_tables:
                dropped_tables.append(table.name)
                changes.append(SchemaChange(
                    change_type=ChangeType.DROP_TABLE,
                    table_name=table.name,
                    old_definition=table.to_sql(self.config.dialect),
                    migration_sql=f"DROP TABLE {table.name};",
                    rollback_sql=table.to_sql(self.config.dialect) + ";",
                ))

        # Find modified tables
        for table_name in source_tables:
            if table_name in target_tables:
                source_table = source_tables[table_name]
                target_table = target_tables[table_name]

                table_changes = self._diff_tables(source_table, target_table)
                if table_changes:
                    modified_tables.append(source_table.name)
                    changes.extend(table_changes)

        comparison_time_ms = (time.time() - start_time) * 1000

        return SchemaDiffResult(
            source_schema=source_name,
            target_schema=target_name,
            is_identical=len(changes) == 0,
            changes=changes,
            added_tables=added_tables,
            dropped_tables=dropped_tables,
            modified_tables=modified_tables,
            comparison_time_ms=comparison_time_ms,
        )

    def _diff_tables(
        self,
        source_table,
        target_table
    ) -> list[SchemaChange]:
        """Compare two tables and return changes."""
        changes: list[SchemaChange] = []
        table_name = source_table.name

        # Compare columns
        source_cols = {c.name: c for c in source_table.columns}
        target_cols = {c.name: c for c in target_table.columns}

        if not self.config.case_sensitive:
            source_cols = {k.lower(): v for k, v in source_cols.items()}
            target_cols = {k.lower(): v for k, v in target_cols.items()}

        # Added columns
        for col_name, col in target_cols.items():
            if col_name not in source_cols:
                changes.append(SchemaChange(
                    change_type=ChangeType.ADD_COLUMN,
                    table_name=table_name,
                    object_name=col.name,
                    new_definition=col.to_sql(self.config.dialect),
                    migration_sql=f"ALTER TABLE {table_name} ADD COLUMN {col.to_sql(self.config.dialect)};",
                    rollback_sql=f"ALTER TABLE {table_name} DROP COLUMN {col.name};",
                ))

        # Dropped columns
        for col_name, col in source_cols.items():
            if col_name not in target_cols:
                changes.append(SchemaChange(
                    change_type=ChangeType.DROP_COLUMN,
                    table_name=table_name,
                    object_name=col.name,
                    old_definition=col.to_sql(self.config.dialect),
                    migration_sql=f"ALTER TABLE {table_name} DROP COLUMN {col.name};",
                    rollback_sql=f"ALTER TABLE {table_name} ADD COLUMN {col.to_sql(self.config.dialect)};",
                ))

        # Modified columns
        for col_name in source_cols:
            if col_name in target_cols:
                source_col = source_cols[col_name]
                target_col = target_cols[col_name]

                if self._columns_differ(source_col, target_col):
                    changes.append(SchemaChange(
                        change_type=ChangeType.MODIFY_COLUMN,
                        table_name=table_name,
                        object_name=source_col.name,
                        old_definition=source_col.to_sql(self.config.dialect),
                        new_definition=target_col.to_sql(self.config.dialect),
                        migration_sql=f"ALTER TABLE {table_name} MODIFY COLUMN {target_col.to_sql(self.config.dialect)};",
                        rollback_sql=f"ALTER TABLE {table_name} MODIFY COLUMN {source_col.to_sql(self.config.dialect)};",
                    ))

        # Compare indexes
        if self.config.include_indexes:
            source_idx = {i.name: i for i in source_table.indexes}
            target_idx = {i.name: i for i in target_table.indexes}

            for idx_name, idx in target_idx.items():
                if idx_name not in source_idx:
                    changes.append(SchemaChange(
                        change_type=ChangeType.ADD_INDEX,
                        table_name=table_name,
                        object_name=idx.name,
                        new_definition=idx.to_sql(self.config.dialect),
                        migration_sql=idx.to_sql(self.config.dialect) + ";",
                        rollback_sql=f"DROP INDEX {idx.name} ON {table_name};",
                    ))

            for idx_name, idx in source_idx.items():
                if idx_name not in target_idx:
                    changes.append(SchemaChange(
                        change_type=ChangeType.DROP_INDEX,
                        table_name=table_name,
                        object_name=idx.name,
                        old_definition=idx.to_sql(self.config.dialect),
                        migration_sql=f"DROP INDEX {idx.name} ON {table_name};",
                        rollback_sql=idx.to_sql(self.config.dialect) + ";",
                    ))

        # Compare foreign keys
        if self.config.include_foreign_keys:
            source_fks = {f.name: f for f in source_table.foreign_keys}
            target_fks = {f.name: f for f in target_table.foreign_keys}

            for fk_name, fk in target_fks.items():
                if fk_name not in source_fks:
                    changes.append(SchemaChange(
                        change_type=ChangeType.ADD_FOREIGN_KEY,
                        table_name=table_name,
                        object_name=fk.name,
                        new_definition=fk.to_sql(self.config.dialect),
                        migration_sql=f"ALTER TABLE {table_name} ADD {fk.to_sql(self.config.dialect)};",
                        rollback_sql=f"ALTER TABLE {table_name} DROP FOREIGN KEY {fk.name};",
                    ))

            for fk_name, fk in source_fks.items():
                if fk_name not in target_fks:
                    changes.append(SchemaChange(
                        change_type=ChangeType.DROP_FOREIGN_KEY,
                        table_name=table_name,
                        object_name=fk.name,
                        old_definition=fk.to_sql(self.config.dialect),
                        migration_sql=f"ALTER TABLE {table_name} DROP FOREIGN KEY {fk.name};",
                        rollback_sql=f"ALTER TABLE {table_name} ADD {fk.to_sql(self.config.dialect)};",
                    ))

        return changes

    def _columns_differ(self, source_col, target_col) -> bool:
        """Check if two columns differ."""
        if source_col.data_type != target_col.data_type:
            return True
        if source_col.length != target_col.length:
            return True
        if source_col.scale != target_col.scale:
            return True
        if source_col.nullable != target_col.nullable:
            return True
        if source_col.default_value != target_col.default_value:
            return True
        if source_col.is_auto_increment != target_col.is_auto_increment:
            return True
        return False

    def generate_report(
        self,
        result: SchemaDiffResult,
        format: str = "text"
    ) -> str:
        """
        Generate a diff report.

        Args:
            result: Diff result to report.
            format: Output format (text, json, markdown).

        Returns:
            Formatted report string.
        """
        if format == "json":
            return json.dumps(result.model_dump(), indent=2, default=str)
        elif format == "markdown":
            return self._generate_markdown_report(result)
        else:
            return self._generate_text_report(result)

    def _generate_text_report(self, result: SchemaDiffResult) -> str:
        """Generate a text format report."""
        lines = []
        lines.append("=" * 60)
        lines.append("Database Schema Diff Report")
        lines.append("=" * 60)
        lines.append(f"Source: {result.source_schema or 'N/A'}")
        lines.append(f"Target: {result.target_schema or 'N/A'}")
        lines.append(f"Identical: {'Yes' if result.is_identical else 'No'}")
        lines.append(f"Changes: {result.change_count}")
        lines.append(f"Time: {result.comparison_time_ms:.2f}ms")
        lines.append("-" * 60)

        if result.added_tables:
            lines.append(f"\nAdded Tables: {', '.join(result.added_tables)}")
        if result.dropped_tables:
            lines.append(f"Dropped Tables: {', '.join(result.dropped_tables)}")
        if result.modified_tables:
            lines.append(f"Modified Tables: {', '.join(result.modified_tables)}")

        if result.changes:
            lines.append("\nChanges:")
            for change in result.changes:
                obj = f".{change.object_name}" if change.object_name else ""
                lines.append(f"  [{change.change_type}] {change.table_name}{obj}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def _generate_markdown_report(self, result: SchemaDiffResult) -> str:
        """Generate a markdown format report."""
        lines = []
        lines.append("# Database Schema Diff Report\n")
        lines.append(f"- **Source**: {result.source_schema or 'N/A'}")
        lines.append(f"- **Target**: {result.target_schema or 'N/A'}")
        lines.append(f"- **Identical**: {'Yes' if result.is_identical else 'No'}")
        lines.append(f"- **Changes**: {result.change_count}")
        lines.append(f"- **Time**: {result.comparison_time_ms:.2f}ms\n")

        if result.added_tables:
            lines.append("## Added Tables\n")
            for table in result.added_tables:
                lines.append(f"- `{table}`")

        if result.dropped_tables:
            lines.append("\n## Dropped Tables\n")
            for table in result.dropped_tables:
                lines.append(f"- `{table}`")

        if result.modified_tables:
            lines.append("\n## Modified Tables\n")
            for table in result.modified_tables:
                lines.append(f"- `{table}`")

        if result.changes:
            lines.append("\n## All Changes\n")
            lines.append("| Type | Table | Object |")
            lines.append("|------|-------|--------|")
            for change in result.changes:
                lines.append(f"| {change.change_type} | {change.table_name} | {change.object_name or '-'} |")

        return "\n".join(lines)
