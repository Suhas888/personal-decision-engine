from app.models.core import Base

print("=== SCHEMA AUDIT ===")
for table_name, table in Base.metadata.tables.items():
    print(f"Table: {table_name}")
    for col in table.columns:
        nullable = "NULL" if col.nullable else "NOT NULL"
        pk = "PK " if col.primary_key else ""
        fk = "FK" if col.foreign_keys else ""
        idx = "IDX" if col.index else ""
        # special check for timezone
        tz = " (tz=True)" if hasattr(col.type, "timezone") and col.type.timezone else ""
        print(f"  {col.name}: {col.type}{tz} | {nullable} | {pk}{fk} {idx}".strip())
    print("")
