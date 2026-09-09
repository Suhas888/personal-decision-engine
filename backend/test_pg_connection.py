import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# A dummy URL for testing
TEST_DB_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/pde_dev")

def check_connection():
    try:
        engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            val = result.scalar()
            if val == 1:
                print(f"SUCCESS: Connected to PostgreSQL at {TEST_DB_URL}")
                return True
            else:
                print("FAILED: SELECT 1 returned unexpected result.")
                return False
    except OperationalError as e:
        print(f"FAILED: Could not connect to PostgreSQL. Is it running? Error: {e}")
        return False
    except Exception as e:
        print(f"FAILED: Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = check_connection()
    sys.exit(0 if success else 1)
