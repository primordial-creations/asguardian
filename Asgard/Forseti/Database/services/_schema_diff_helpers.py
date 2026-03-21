"""
Database Schema Diff Helpers.

Helper functions for SchemaDiffService.
"""

from Asgard.Forseti.Database.models.database_models import (
    ChangeType,
    SchemaChange,
    SchemaDiffResult,
)


def columns_differ(source_col, target_col) -> bool:
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


def diff_tables(
    source_table,
    target_table,
    dialect: str,
    case_sensitive: bool,
    include_indexes: bool,
    include_foreign_keys: bool,
) -> list[SchemaChange]:
    """Compare two tables and return changes."""
    changes: list[SchemaChange] = []
    table_name = source_table.name

    source_cols = {c.name: c for c in source_table.columns}
    target_cols = {c.name: c for c in target_table.columns}

    if not case_sensitive:
        source_cols = {k.lower(): v for k, v in source_cols.items()}
        target_cols = {k.lower(): v for k, v in target_cols.items()}

    for col_name, col in target_cols.items():
        if col_name not in source_cols:
            changes.append(SchemaChange(
                change_type=ChangeType.ADD_COLUMN,
                table_name=table_name,
                object_name=col.name,
                new_definition=col.to_sql(dialect),
                migration_sql=f"ALTER TABLE {table_name} ADD COLUMN {col.to_sql(dialect)};",
                rollback_sql=f"ALTER TABLE {table_name} DROP COLUMN {col.name};",
            ))

    for col_name, col in source_cols.items():
        if col_name not in target_cols:
            changes.append(SchemaChange(
                change_type=ChangeType.DROP_COLUMN,
                table_name=table_name,
                object_name=col.name,
                old_definition=col.to_sql(dialect),
                migration_sql=f"ALTER TABLE {table_name} DROP COLUMN {col.name};",
                rollback_sql=f"ALTER TABLE {table_name} ADD COLUMN {col.to_sql(dialect)};",
            ))

    for col_name in source_cols:
        if col_name in target_cols:
            source_col = source_cols[col_name]
            target_col = target_cols[col_name]

            if columns_differ(source_col, target_col):
                changes.append(SchemaChange(
                    change_type=ChangeType.MODIFY_COLUMN,
                    table_name=table_name,
                    object_name=source_col.name,
                    old_definition=source_col.to_sql(dialect),
                    new_definition=target_col.to_sql(dialect),
                    migration_sql=f"ALTER TABLE {table_name} MODIFY COLUMN {target_col.to_sql(dialect)};",
                    rollback_sql=f"ALTER TABLE {table_name} MODIFY COLUMN {source_col.to_sql(dialect)};",
                ))

    if include_indexes:
        source_idx = {i.name: i for i in source_table.indexes}
        target_idx = {i.name: i for i in target_table.indexes}

        for idx_name, idx in target_idx.items():
            if idx_name not in source_idx:
                changes.append(SchemaChange(
                    change_type=ChangeType.ADD_INDEX,
                    table_name=table_name,
                    object_name=idx.name,
                    new_definition=idx.to_sql(dialect),
                    migration_sql=idx.to_sql(dialect) + ";",
                    rollback_sql=f"DROP INDEX {idx.name} ON {table_name};",
                ))

        for idx_name, idx in source_idx.items():
            if idx_name not in target_idx:
                changes.append(SchemaChange(
                    change_type=ChangeType.DROP_INDEX,
                    table_name=table_name,
                    object_name=idx.name,
                    old_definition=idx.to_sql(dialect),
                    migration_sql=f"DROP INDEX {idx.name} ON {table_name};",
                    rollback_sql=idx.to_sql(dialect) + ";",
                ))

    if include_foreign_keys:
        source_fks = {f.name: f for f in source_table.foreign_keys}
        target_fks = {f.name: f for f in target_table.foreign_keys}

        for fk_name, fk in target_fks.items():
            if fk_name not in source_fks:
                changes.append(SchemaChange(
                    change_type=ChangeType.ADD_FOREIGN_KEY,
                    table_name=table_name,
                    object_name=fk.name,
                    new_definition=fk.to_sql(dialect),
                    migration_sql=f"ALTER TABLE {table_name} ADD {fk.to_sql(dialect)};",
                    rollback_sql=f"ALTER TABLE {table_name} DROP FOREIGN KEY {fk.name};",
                ))

        for fk_name, fk in source_fks.items():
            if fk_name not in target_fks:
                changes.append(SchemaChange(
                    change_type=ChangeType.DROP_FOREIGN_KEY,
                    table_name=table_name,
                    object_name=fk.name,
                    old_definition=fk.to_sql(dialect),
                    migration_sql=f"ALTER TABLE {table_name} DROP FOREIGN KEY {fk.name};",
                    rollback_sql=f"ALTER TABLE {table_name} ADD {fk.to_sql(dialect)};",
                ))

    return changes


def generate_text_report(result: SchemaDiffResult) -> str:
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


def generate_markdown_report(result: SchemaDiffResult) -> str:
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
