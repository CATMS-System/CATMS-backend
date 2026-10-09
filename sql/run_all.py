"""
Database Migration and Seed Runner for CATMS.
Executes SQL scripts in order using PyMySQL connection settings from .env.
"""

import argparse
import os
import re
import sys
from pathlib import Path

import pymysql
import pymysql.cursors
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "CatMS")
DB_USE_SSL = os.getenv("DB_USE_SSL", "false").lower() in ("true", "1", "yes")


def get_db_connection(include_database: bool = True) -> pymysql.Connection:
    ssl_config = None
    if DB_USE_SSL:
        import certifi

        ssl_config = {"ca": certifi.where()}

    conn_params = {
        "host": DB_HOST,
        "port": DB_PORT,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "cursorclass": pymysql.cursors.DictCursor,
        "ssl": ssl_config,
        "autocommit": False,
        "connect_timeout": 10,
    }
    if include_database and DB_NAME:
        conn_params["database"] = DB_NAME

    return pymysql.connect(**conn_params)


def strip_full_line_comments(sql: str) -> str:
    """Strips full-line SQL comments (lines starting with -- after optional whitespace)."""
    return "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))


def is_executable_sql(sql: str) -> bool:
    cleaned = re.sub(r"(--[^\r\n]*|#[^\r\n]*)", "", sql)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    return bool(cleaned.strip())


def split_sql_statements(sql: str) -> list[str]:
    sql = strip_full_line_comments(sql)
    statements = []
    current = []
    in_single = False
    in_double = False
    in_backtick = False
    in_line_comment = False
    in_block_comment = False
    delimiter = ";"

    i = 0
    n = len(sql)
    while i < n:
        c = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        if in_single:
            current.append(c)
            if c == "\\":
                if i + 1 < n:
                    i += 1
                    current.append(sql[i])
            elif c == "'":
                if nxt == "'":
                    i += 1
                    current.append(sql[i])
                else:
                    in_single = False
        elif in_double:
            current.append(c)
            if c == "\\":
                if i + 1 < n:
                    i += 1
                    current.append(sql[i])
            elif c == '"':
                if nxt == '"':
                    i += 1
                    current.append(sql[i])
                else:
                    in_double = False
        elif in_backtick:
            current.append(c)
            if c == "`":
                in_backtick = False
        elif in_line_comment:
            current.append(c)
            if c == "\n":
                in_line_comment = False
        elif in_block_comment:
            current.append(c)
            if c == "*" and nxt == "/":
                current.append("/")
                i += 1
                in_block_comment = False
        else:
            if (c == "-" and nxt == "-" and (i + 2 >= n or sql[i + 2] in (" ", "\t", "\r", "\n"))) or c == "#":
                current.append(c)
                in_line_comment = True
            elif c == "/" and nxt == "*":
                current.append(c)
                current.append(nxt)
                i += 1
                in_block_comment = True
            elif c == "'":
                current.append(c)
                in_single = True
            elif c == '"':
                current.append(c)
                in_double = True
            elif c == "`":
                current.append(c)
                in_backtick = True
            else:
                buffer_prefix = "".join(current).strip()
                if not buffer_prefix and sql[i:].upper().startswith("DELIMITER "):
                    end_idx = sql.find("\n", i)
                    if end_idx == -1:
                        end_idx = n
                    delimiter = sql[i + 10:end_idx].strip()
                    i = end_idx
                    continue

                if sql[i:i + len(delimiter)] == delimiter:
                    stmt = "".join(current).strip()
                    if is_executable_sql(stmt):
                        statements.append(stmt)
                    current = []
                    i += len(delimiter) - 1
                else:
                    current.append(c)
        i += 1

    remaining = "".join(current).strip()
    if is_executable_sql(remaining):
        statements.append(remaining)

    return statements


def all_database_routine_files() -> list[Path]:
    return [
        BASE_DIR / "database/functions/fn_calculate_patient_balance.sql",
        BASE_DIR / "database/views/vw_Invoice_Summary.sql",
        BASE_DIR / "database/views/vw_audit_log_readable.sql",
        BASE_DIR / "database/views/vw_staff_directory.sql",
        BASE_DIR / "database/procedures/sp_book_appointment.sql",
        BASE_DIR / "database/procedures/sp_complete_consultation_and_generate_invoice.sql",
        BASE_DIR / "database/procedures/sp_force_password_reset.sql",
        BASE_DIR / "database/procedures/sp_record_payment.sql",
        BASE_DIR / "database/procedures/sp_transfer_branch_manager.sql",
        BASE_DIR / "database/triggers/trg_after_staff_update.sql",
        BASE_DIR / "database/triggers/trg_check_appointment_overlap.sql",
        BASE_DIR / "database/triggers/trg_audit_core_entities.sql",
    ]


def billing_sql_files() -> list[Path]:
    return [
        BASE_DIR / "database/functions/fn_calculate_patient_balance.sql",
        BASE_DIR / "database/views/vw_Invoice_Summary.sql",
        BASE_DIR / "database/procedures/sp_record_payment.sql",
    ]


def run_all(billing_only: bool = False, no_routines: bool = False, all_routines: bool = False) -> None:
    sql_dir = Path(__file__).resolve().parent
    if billing_only:
        sql_files = billing_sql_files()
    elif no_routines:
        sql_files = sorted(sql_dir.glob("*.sql"))
    else:
        # Default behavior: load schema and seed scripts, followed by all database routines and triggers
        sql_files = sorted(sql_dir.glob("*.sql")) + [
            f for f in all_database_routine_files() if f.is_file()
        ]

    if not sql_files:
        print("No .sql files found in sql directory.")
        return

    conn = None
    try:
        try:
            conn = get_db_connection(include_database=True)
        except pymysql.err.OperationalError as e:
            if len(e.args) > 0 and e.args[0] == 1049:
                conn = get_db_connection(include_database=False)
            else:
                print(f"Failed to connect to MySQL ({DB_HOST}:{DB_PORT}): {e}", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"Failed to connect to MySQL ({DB_HOST}:{DB_PORT}): {e}", file=sys.stderr)
            sys.exit(1)

        print(f"Connected to MySQL on {DB_HOST}:{DB_PORT}.")

        with conn.cursor() as cursor:
            for file_path in sql_files:
                content = file_path.read_text(encoding="utf-8")
                statements = split_sql_statements(content)
                print(f"Executing {file_path.name} ({len(statements)} statements)...")

                for stmt_idx, stmt in enumerate(statements, start=1):
                    try:
                        cursor.execute(stmt)
                    except Exception as err:
                        conn.rollback()
                        print(
                            f"\nERROR: Statement #{stmt_idx} failed in {file_path.name}:\n"
                            f"{err}\n\n"
                            f"Failing SQL:\n{stmt[:300]}...",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                conn.commit()
                print(f"Executed {file_path.name}: {len(statements)} statements ran successfully.")

        print("\nAll SQL files executed successfully.")
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--billing-only", action="store_true",
        help="Install billing function, view and procedure without schema/seed scripts."
    )
    parser.add_argument(
        "--no-routines", action="store_true",
        help="Install schema and seed scripts only, skipping stored routines and triggers."
    )
    parser.add_argument(
        "--all-routines", action="store_true",
        help="Legacy flag: install all database routines and triggers (now default behavior)."
    )
    args = parser.parse_args()
    run_all(billing_only=args.billing_only, no_routines=args.no_routines, all_routines=args.all_routines)

