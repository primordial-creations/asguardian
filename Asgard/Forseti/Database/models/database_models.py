"""
Database Models - Pydantic models for database schema handling.

These models represent database schema structures and diff results.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from Asgard.Forseti.Database.models._database_base_models import (
    ChangeType,
    ColumnDefinition,
    ColumnType,
    ConstraintDefinition,
    DatabaseConfig,
    ForeignKeyDefinition,
    IndexDefinition,
)


class TableDefinition(BaseModel):
    """Database table definition."""

    name: str = Field(description="Table name")
    schema_name: Optional[str] = Field(default=None, description="Schema/database name")
    columns: list[ColumnDefinition] = Field(
        default_factory=list,
        description="Table columns"
    )
    indexes: list[IndexDefinition] = Field(
        default_factory=list,
        description="Table indexes"
    )
    foreign_keys: list[ForeignKeyDefinition] = Field(
        default_factory=list,
        description="Foreign key constraints"
    )
    constraints: list[ConstraintDefinition] = Field(
        default_factory=list,
        description="Other constraints"
    )
    primary_key: list[str] = Field(
        default_factory=list,
        description="Primary key columns"
    )
    engine: Optional[str] = Field(default=None, description="Storage engine")
    charset: Optional[str] = Field(default=None, description="Character set")
    collation: Optional[str] = Field(default=None, description="Collation")
    comment: Optional[str] = Field(default=None, description="Table comment")

    def get_column(self, name: str) -> Optional[ColumnDefinition]:
        """Get a column by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def to_sql(self, dialect: str = "mysql") -> str:
        """Generate CREATE TABLE statement."""
        lines = [f"CREATE TABLE {self.name} ("]

        col_defs = []
        for col in self.columns:
            col_def = f"  {col.to_sql(dialect)}"
            col_defs.append(col_def)

        if self.primary_key and len(self.primary_key) > 1:
            pk_cols = ", ".join(self.primary_key)
            col_defs.append(f"  PRIMARY KEY ({pk_cols})")

        for fk in self.foreign_keys:
            col_defs.append(f"  {fk.to_sql(dialect)}")

        lines.append(",\n".join(col_defs))
        lines.append(")")

        options = []
        if self.engine:
            options.append(f"ENGINE={self.engine}")
        if self.charset:
            options.append(f"DEFAULT CHARSET={self.charset}")
        if options:
            lines[-1] += " " + " ".join(options)

        return "\n".join(lines)


class DatabaseSchema(BaseModel):
    """Complete database schema."""

    name: Optional[str] = Field(default=None, description="Database/schema name")
    tables: list[TableDefinition] = Field(
        default_factory=list,
        description="All tables"
    )
    extracted_at: datetime = Field(
        default_factory=datetime.now,
        description="Extraction timestamp"
    )
    source: Optional[str] = Field(
        default=None,
        description="Source (connection string or file)"
    )

    @property
    def table_count(self) -> int:
        """Return the number of tables."""
        return len(self.tables)

    def get_table(self, name: str) -> Optional[TableDefinition]:
        """Get a table by name."""
        for table in self.tables:
            if table.name == name:
                return table
        return None

    def get_all_foreign_keys(self) -> list[ForeignKeyDefinition]:
        """Get all foreign keys across all tables."""
        fks = []
        for table in self.tables:
            fks.extend(table.foreign_keys)
        return fks


class SchemaChange(BaseModel):
    """Represents a single schema change."""

    change_type: ChangeType = Field(description="Type of change")
    table_name: str = Field(description="Affected table")
    object_name: Optional[str] = Field(
        default=None,
        description="Affected object (column, index, etc.)"
    )
    old_definition: Optional[str] = Field(
        default=None,
        description="Old definition"
    )
    new_definition: Optional[str] = Field(
        default=None,
        description="New definition"
    )
    migration_sql: Optional[str] = Field(
        default=None,
        description="SQL to apply the change"
    )
    rollback_sql: Optional[str] = Field(
        default=None,
        description="SQL to rollback the change"
    )

    class Config:
        use_enum_values = True


class SchemaDiffResult(BaseModel):
    """Result of schema comparison."""

    source_schema: Optional[str] = Field(
        default=None,
        description="Source schema identifier"
    )
    target_schema: Optional[str] = Field(
        default=None,
        description="Target schema identifier"
    )
    is_identical: bool = Field(
        description="Whether schemas are identical"
    )
    changes: list[SchemaChange] = Field(
        default_factory=list,
        description="List of changes"
    )
    added_tables: list[str] = Field(
        default_factory=list,
        description="Tables added in target"
    )
    dropped_tables: list[str] = Field(
        default_factory=list,
        description="Tables removed in target"
    )
    modified_tables: list[str] = Field(
        default_factory=list,
        description="Tables modified in target"
    )
    compared_at: datetime = Field(
        default_factory=datetime.now,
        description="Comparison timestamp"
    )
    comparison_time_ms: float = Field(
        default=0.0,
        description="Time taken to compare"
    )

    @property
    def change_count(self) -> int:
        """Return the total number of changes."""
        return len(self.changes)

    @property
    def has_breaking_changes(self) -> bool:
        """Check if there are breaking changes."""
        breaking_types = {ChangeType.DROP_TABLE, ChangeType.DROP_COLUMN}
        return any(c.change_type in breaking_types for c in self.changes)


__all__ = [
    "ChangeType",
    "ColumnDefinition",
    "ColumnType",
    "ConstraintDefinition",
    "DatabaseConfig",
    "DatabaseSchema",
    "ForeignKeyDefinition",
    "IndexDefinition",
    "SchemaChange",
    "SchemaDiffResult",
    "TableDefinition",
]
