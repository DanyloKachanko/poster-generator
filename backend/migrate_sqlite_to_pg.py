"""
One-time migration: SQLite → PostgreSQL.

Usage:
  1. Start PostgreSQL: docker-compose up db
  2. Run: python migrate_sqlite_to_pg.py [sqlite_path]

Default SQLite path: ./poster_generator.db
"""

import sys
import os
import sqlite3
import asyncio
import asyncpg

SQLITE_PATH = sys.argv[1] if len(sys.argv) > 1 else "poster_generator.db"
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://poster:poster@localhost:5432/poster_generator",
)

# Tables to migrate in dependency order
TABLES = [
    "generations",
    "generated_images",
    "credit_usage",
    "product_analytics",
    "etsy_tokens",
    "scheduled_products",
    "used_presets",
    "schedule_settings",
]


async def migrate():
    if not os.path.exists(SQLITE_PATH):
        print(f"SQLite file not found: {SQLITE_PATH}")
        sys.exit(1)

    print(f"Source: {SQLITE_PATH}")
    print(f"Target: {DATABASE_URL}")

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    pg_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)

    # Create tables first (import schema from database module)
    from database import SCHEMA
    async with pg_pool.acquire() as conn:
        await conn.execute(SCHEMA)
    print("PostgreSQL schema created.")

    for table in TABLES:
        try:
            cursor = sqlite_conn.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            print(f"  {table}: table not found in SQLite, skipping")
            continue

        if not rows:
            print(f"  {table}: 0 rows (empty)")
            continue

        columns = [desc[0] for desc in cursor.description]
        # Skip 'id' column — let PostgreSQL SERIAL handle it
        cols_no_id = [c for c in columns if c != "id"]

        placeholders = ", ".join(f"${i+1}" for i in range(len(cols_no_id)))
        col_names = ", ".join(cols_no_id)
        insert_sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

        count = 0
        async with pg_pool.acquire() as conn:
            for row in rows:
                values = [row[c] for c in cols_no_id]
                try:
                    await conn.execute(insert_sql, *values)
                    count += 1
                except Exception as e:
                    print(f"  {table}: error inserting row: {e}")

        print(f"  {table}: {count}/{len(rows)} rows migrated")

    # Reset sequences to max(id) + 1 for SERIAL columns
    async with pg_pool.acquire() as conn:
        for table in TABLES:
            try:
                max_id = await conn.fetchval(f"SELECT MAX(id) FROM {table}")
                if max_id is not None:
                    seq_name = f"{table}_id_seq"
                    await conn.execute(f"SELECT setval('{seq_name}', {max_id})")
                    print(f"  {table}_id_seq reset to {max_id}")
            except Exception:
                pass  # Table may not have a sequence (e.g. etsy_tokens, schedule_settings)

    await pg_pool.close()
    sqlite_conn.close()
    print("\nMigration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())
