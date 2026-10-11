"""
Loads the schema, seed data and routines only when the database has no tables yet.
Used by the db-init service in docker-compose.full.yml so a fresh
`docker compose up` works, while a restart keeps the existing data.
"""
from run_all import get_db_connection, run_all


def main() -> None:
    conn = get_db_connection(include_database=True)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema = DATABASE()"
            )
            table_count = cursor.fetchone()["n"]
    finally:
        conn.close()
    if table_count:
        print(f"Database already has {table_count} tables, skipping setup.")
        return
    run_all()


if __name__ == "__main__":
    main()
