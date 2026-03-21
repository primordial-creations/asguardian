"""
Database Base Models - Enums, config, and simple definition models.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ChangeType(str, Enum):
    """Types of schema changes."""
    ADD_TABLE = "add_table"
    DROP_TABLE = "drop_table"
    ADD_COLUMN = "add_column"
    DROP_COLUMN = "drop_column"
    MODIFY_COLUMN = "modify_column"
    ADD_INDEX = "add_index"
    DROP_INDEX = "drop_index"
    ADD_FOREIGN_KEY = "add_foreign_key"
    DROP_FOREIGN_KEY = "drop_foreign_key"
    ADD_CONSTRAINT = "add_constraint"
    DROP_CONSTRAINT = "drop_constraint"
    RENAME_TABLE = "rename_table"
    RENAME_COLUMN = "rename_column"


class ColumnType(str, Enum):
    """Common SQL column types."""
    INTEGER = "INTEGER"
    BIGINT = "BIGINT"
    SMALLINT = "SMALLINT"
    DECIMAL = "DECIMAL"
    NUMERIC = "NUMERIC"
    FLOAT = "FLOAT"
    DOUBLE = "DOUBLE"
    REAL = "REAL"
    VARCHAR = "VARCHAR"
    CHAR = "CHAR"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    TIME = "TIME"
    DATETIME = "DATETIME"
    TIMESTAMP = "TIMESTAMP"
    BLOB = "BLOB"
    JSON = "JSON"
    UUID = "UUID"


class DatabaseConfig(BaseModel):
    """Configuration for database schema operations."""

    dialect: str = Field(
        default="mysql",
        description="SQL dialect (mysql, postgresql, sqlite, etc.)"
    )
    include_indexes: bool = Field(
        default=True,
        description="Include indexes in schema analysis"
    )
    include_foreign_keys: bool = Field(
        default=True,
        description="Include foreign keys in schema analysis"
    )
    include_constraints: bool = Field(
        default=True,
        description="Include constraints in schema analysis"
    )
    case_sensitive: bool = Field(
        default=False,
        description="Case-sensitive comparison of identifiers"
    )
    ignore_whitespace: bool = Field(
        default=True,
        description="Ignore whitespace differences"
    )


class ColumnDefinition(BaseModel):
    """Database column definition."""

    name: str = Field(description="Column name")
    data_type: str = Field(description="Column data type")
    length: Optional[int] = Field(default=None, description="Type length/precision")
    scale: Optional[int] = Field(default=None, description="Decimal scale")
    nullable: bool = Field(default=True, description="Allow NULL values")
    default_value: Optional[str] = Field(default=None, description="Default value")
    is_primary_key: bool = Field(default=False, description="Primary key flag")
    is_auto_increment: bool = Field(default=False, description="Auto-increment flag")
    is_unique: bool = Field(default=False, description="Unique constraint flag")
    comment: Optional[str] = Field(default=None, description="Column comment")
    collation: Optional[str] = Field(default=None, description="Column collation")

    def to_sql(self, dialect: str = "mysql") -> str:
        """Generate SQL column definition."""
        parts = [self.name, self.data_type]

        if self.length is not None:
            if self.scale is not None:
                parts[-1] = f"{self.data_type}({self.length},{self.scale})"
            else:
                parts[-1] = f"{self.data_type}({self.length})"

        if not self.nullable:
            parts.append("NOT NULL")

        if self.default_value is not None:
            parts.append(f"DEFAULT {self.default_value}")

        if self.is_auto_increment:
            if dialect == "postgresql":
                parts[1] = "SERIAL"
            else:
                parts.append("AUTO_INCREMENT")

        if self.is_primary_key:
            parts.append("PRIMARY KEY")

        if self.is_unique and not self.is_primary_key:
            parts.append("UNIQUE")

        return " ".join(parts)


class IndexDefinition(BaseModel):
    """Database index definition."""

    name: str = Field(description="Index name")
    table_name: str = Field(description="Table name")
    columns: list[str] = Field(description="Indexed columns")
    is_unique: bool = Field(default=False, description="Unique index flag")
    is_primary: bool = Field(default=False, description="Primary key index flag")
    index_type: Optional[str] = Field(default=None, description="Index type (BTREE, HASH, etc.)")

    def to_sql(self, dialect: str = "mysql") -> str:
        """Generate SQL index creation statement."""
        unique = "UNIQUE " if self.is_unique else ""
        columns = ", ".join(self.columns)
        return f"CREATE {unique}INDEX {self.name} ON {self.table_name} ({columns})"


class ForeignKeyDefinition(BaseModel):
    """Database foreign key definition."""

    name: str = Field(description="Constraint name")
    table_name: str = Field(description="Source table name")
    columns: list[str] = Field(description="Source columns")
    reference_table: str = Field(description="Referenced table")
    reference_columns: list[str] = Field(description="Referenced columns")
    on_delete: Optional[str] = Field(default=None, description="ON DELETE action")
    on_update: Optional[str] = Field(default=None, description="ON UPDATE action")

    def to_sql(self, dialect: str = "mysql") -> str:
        """Generate SQL foreign key constraint."""
        cols = ", ".join(self.columns)
        refs = ", ".join(self.reference_columns)
        sql = f"CONSTRAINT {self.name} FOREIGN KEY ({cols}) REFERENCES {self.reference_table} ({refs})"
        if self.on_delete:
            sql += f" ON DELETE {self.on_delete}"
        if self.on_update:
            sql += f" ON UPDATE {self.on_update}"
        return sql


class ConstraintDefinition(BaseModel):
    """Database constraint definition."""

    name: str = Field(description="Constraint name")
    table_name: str = Field(description="Table name")
    constraint_type: str = Field(description="Constraint type (CHECK, UNIQUE, etc.)")
    definition: str = Field(description="Constraint definition")
    columns: list[str] = Field(default_factory=list, description="Affected columns")
