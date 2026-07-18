"""
SQL (Database module) -> IR adapter.

Closes the DB->API loop RESEARCH_12 emphasizes: maps a parsed
`TableDefinition` (Database/services/schema_analyzer_service.py) onto
IRRecord. `VARCHAR(n)` -> STRING with capacity note folded into the type
class (capacity comparison itself lives in the type matrix, which only
needs the class), `DECIMAL(p,s)` -> DECIMAL, nullable columns map directly.
"""

from typing import Any

from Asgard.Forseti.Alignment.models.ir_models import (
    IRField,
    IRRecord,
    IRType,
    SourceRef,
    TypeClass,
)
from Asgard.Forseti.Alignment.services._lexical_helpers import tokenize

_SQL_TYPE_MAP: dict[str, TypeClass] = {
    "INTEGER": TypeClass.INT32,
    "INT": TypeClass.INT32,
    "SMALLINT": TypeClass.INT32,
    "BIGINT": TypeClass.INT64,
    "DECIMAL": TypeClass.DECIMAL,
    "NUMERIC": TypeClass.DECIMAL,
    "FLOAT": TypeClass.FLOAT32,
    "DOUBLE": TypeClass.FLOAT64,
    "REAL": TypeClass.FLOAT32,
    "VARCHAR": TypeClass.STRING,
    "CHAR": TypeClass.STRING,
    "TEXT": TypeClass.STRING,
    "BOOLEAN": TypeClass.BOOL,
    "BOOL": TypeClass.BOOL,
    "DATE": TypeClass.DATE,
    "TIME": TypeClass.STRING,
    "DATETIME": TypeClass.DATETIME,
    "TIMESTAMP": TypeClass.DATETIME,
    "BLOB": TypeClass.BYTES,
    "JSON": TypeClass.ANY,
    "UUID": TypeClass.UUID,
}


def _sql_type_to_ir(data_type: str) -> IRType:
    normalized = data_type.strip().upper()
    return IRType(type_class=_SQL_TYPE_MAP.get(normalized, TypeClass.ANY))


def sql_table_to_ir_record(table: Any, file: str = "", path: str = "/") -> IRRecord:
    """Build an IRRecord from a parsed `TableDefinition`."""
    fields: list[IRField] = []
    for column in table.columns:
        ir_type = _sql_type_to_ir(column.data_type)
        nullable = bool(column.nullable) and not column.is_primary_key
        fields.append(
            IRField(
                raw_name=column.name,
                lexical_tokens=tokenize(column.name),
                type=ir_type,
                nullable=nullable,
                required=not nullable,
                default=column.default_value,
                doc=column.comment,
                source=SourceRef(file=file, format="sql", path=f"{path}/{column.name}"),
            )
        )
    return IRRecord(name=table.name, fields=fields, source=SourceRef(file=file, format="sql", path=path))
