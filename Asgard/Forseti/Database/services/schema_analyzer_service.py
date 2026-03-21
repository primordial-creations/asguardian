"""
Database Schema Analyzer Service.

Extracts schema information from databases and SQL files.
"""

import re
from pathlib import Path
from typing import Optional

from Asgard.Forseti.Database.models.database_models import (
    DatabaseConfig,
    DatabaseSchema,
    TableDefinition,
    ColumnDefinition,
    IndexDefinition,
    ForeignKeyDefinition,
)
from Asgard.Forseti.Database.utilities.database_utils import load_sql_file, parse_create_table
from Asgard.Forseti.Database.services._schema_analyzer_helpers import (
    extract_alter_foreign_keys,
    extract_standalone_indexes,
    parse_table,
)


class SchemaAnalyzerService:
    """
    Service for analyzing database schemas.

    Extracts schema information from SQL files or database connections.

    Usage:
        service = SchemaAnalyzerService()
        schema = service.analyze_file("schema.sql")
        for table in schema.tables:
            print(f"Table: {table.name}")
    """

    def __init__(self, config: Optional[DatabaseConfig] = None):
        """
        Initialize the analyzer service.

        Args:
            config: Optional configuration for analysis behavior.
        """
        self.config = config or DatabaseConfig()

    def analyze_file(self, file_path: str | Path) -> DatabaseSchema:
        """
        Analyze a SQL file to extract schema information.

        Args:
            file_path: Path to the SQL file.

        Returns:
            Extracted DatabaseSchema.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"SQL file not found: {file_path}")

        sql_content = load_sql_file(file_path)
        return self.analyze_sql(sql_content, str(file_path))

    def analyze_sql(
        self,
        sql_content: str,
        source_name: Optional[str] = None
    ) -> DatabaseSchema:
        """
        Analyze SQL content to extract schema information.

        Args:
            sql_content: SQL DDL content.
            source_name: Optional source identifier.

        Returns:
            Extracted DatabaseSchema.
        """
        tables: list[TableDefinition] = []

        create_table_pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"]?(\w+)[`"]?\s*\(([^;]+)\)'
        for match in re.finditer(create_table_pattern, sql_content, re.IGNORECASE | re.DOTALL):
            table_name = match.group(1)
            table_body = match.group(2)

            table = parse_table(table_name, table_body)
            if table:
                tables.append(table)

        if self.config.include_indexes:
            extract_standalone_indexes(sql_content, tables)

        if self.config.include_foreign_keys:
            extract_alter_foreign_keys(sql_content, tables)

        return DatabaseSchema(
            name=source_name,
            tables=tables,
            source=source_name,
        )

    def get_table_dependencies(self, schema: DatabaseSchema) -> dict[str, list[str]]:
        """
        Get table dependencies based on foreign keys.

        Args:
            schema: Database schema to analyze.

        Returns:
            Dictionary mapping table names to their dependencies.
        """
        dependencies: dict[str, list[str]] = {}

        for table in schema.tables:
            deps = []
            for fk in table.foreign_keys:
                if fk.reference_table != table.name:
                    deps.append(fk.reference_table)
            dependencies[table.name] = deps

        return dependencies

    def get_ordered_tables(self, schema: DatabaseSchema) -> list[str]:
        """
        Get tables in dependency order for creation.

        Args:
            schema: Database schema to analyze.

        Returns:
            List of table names in creation order.
        """
        dependencies = self.get_table_dependencies(schema)
        ordered: list[str] = []
        remaining = set(dependencies.keys())

        while remaining:
            ready = []
            for table in remaining:
                deps = dependencies.get(table, [])
                if all(d in ordered or d not in remaining for d in deps):
                    ready.append(table)

            if not ready:
                ordered.extend(sorted(remaining))
                break

            for table in sorted(ready):
                ordered.append(table)
                remaining.remove(table)

        return ordered
