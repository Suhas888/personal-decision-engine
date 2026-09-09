import sys
import os
from sqlalchemy import create_engine, text
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app.config import settings

engine = create_engine(settings.DATABASE_URL)

with engine.connect() as conn:
    print("=== ALEMBIC VERSION ===")
    try:
        ver = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        print(f"alembic_version: {ver[0]}")
    except Exception as e:
        print("Error reading alembic_version:", e)

    print("\n=== SCHEMA, COLUMNS, TYPES, NULLABILITY ===")
    tables = [
        'users', 'command_confirmations', 'dynamic_constraints', 'fixed_events', 
        'plans', 'preferences', 'refresh_sessions', 'tasks', 'user_profiles', 
        'plan_history', 'schedule_blocks', 'task_dependencies'
    ]
    for table in tables:
        print(f"\nTABLE: {table}")
        cols = conn.execute(text(f"""
            SELECT column_name, data_type, is_nullable, column_default 
            FROM information_schema.columns 
            WHERE table_name = '{table}' 
            ORDER BY ordinal_position
        """)).fetchall()
        for c in cols:
            print(f"  {c[0]}: {c[1]} (Nullable: {c[2]}) Default: {c[3]}")

    print("\n=== FOREIGN KEYS & CASCADES ===")
    fks = conn.execute(text("""
        SELECT
            tc.table_name, kcu.column_name, 
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            rc.delete_rule
        FROM 
            information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
            JOIN information_schema.referential_constraints AS rc
              ON rc.constraint_name = tc.constraint_name
        WHERE constraint_type = 'FOREIGN KEY'
        ORDER BY tc.table_name, kcu.column_name;
    """)).fetchall()
    for fk in fks:
        print(f"  {fk[0]}.{fk[1]} -> {fk[2]}.{fk[3]} ON DELETE {fk[4]}")

    print("\n=== UNIQUE CONSTRAINTS (Not PKs) ===")
    unqs = conn.execute(text("""
        SELECT tc.table_name, tc.constraint_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        WHERE tc.constraint_type = 'UNIQUE'
        ORDER BY tc.table_name, tc.constraint_name;
    """)).fetchall()
    for uq in unqs:
        print(f"  {uq[0]} : {uq[1]} ({uq[2]})")

    print("\n=== INDEXES ===")
    idxs = conn.execute(text("""
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname;
    """)).fetchall()
    for idx in idxs:
        print(f"  {idx[0]} : {idx[1]}")
