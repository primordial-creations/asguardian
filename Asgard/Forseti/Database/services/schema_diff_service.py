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
from Asgard.Forseti.Database.services._schema_diff_helpers import (
    diff_tables,
    generate_markdown_report,
    generate_text_report,
)


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

        for table_name in source_tables:
            if table_name in target_tables:
                source_table = source_tables[table_name]
                target_table = target_tables[table_name]

                table_changes = diff_tables(
                    source_table,
                    target_table,
                    self.config.dialect,
                    self.config.case_sensitive,
                    self.config.include_indexes,
                    self.config.include_foreign_keys,
                )
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
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)
