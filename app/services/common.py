# helpers shared by the patient and insurance services
import json
import re
from contextlib import contextmanager
from typing import Any

import pymysql
from fastapi import HTTPException


# db columns look like Patient_ID but the schemas use patient_id
def lower_keys(row: Any) -> dict | None:
    if not row:
        return None
    return {key.lower(): value for key, value in row.items()}


def lower_rows(rows: Any) -> list[dict]:
    return [{key.lower(): value for key, value in row.items()} for row in rows]


# put a backslash before \ % _ so they are searched as normal characters
def escape_like(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace("%", "\\%")
    return text.replace("_", "\\_")

# turns a mysql error into an http error, returns None if we do not know the error
def convert_db_error(error: pymysql.MySQLError) -> HTTPException | None:
    error_code = error.args[0] if error.args else None
    message = str(error.args[1]) if len(error.args) > 1 else str(error)

    # 1062 = value already exists in a unique column
    if error_code == 1062:
        # the message names the key that broke
        if "NIC" in message:
            detail = "A patient with this NIC already exists"
        elif "uq_policy_provider_number" in message:
            detail = "This provider already has a policy with that policy number"
        elif "Provider_Name" in message:
            detail = "An insurance provider with this name already exists"
        elif "Email" in message:
            detail = "An insurance provider with this email already exists"
        else:
            detail = "Duplicate value for a unique field"
        return HTTPException(409, detail)

    # 1452 = foreign key points to a row that does not exist
    if error_code == 1452:
        return HTTPException(422, "A referenced record does not exist")

    # 3819 = a CHECK rule in the table was broken, rule name is inside quotes
    if error_code == 3819:
        found = re.search(r"'([^']+)'", message)
        rule = found.group(1) if found else "a check rule"
        return HTTPException(422, f"Value breaks database rule: {rule}")

    # 1048 null, 1264 and 1265 out of range or cut, 1366 wrong value, 1406 too long
    if error_code in (1048, 1264, 1265, 1366, 1406):
        return HTTPException(422, "A value is missing, too long or out of range")

    # unknown error, the caller raises it again
    return None

# use as: with transaction(conn):
# saves everything if there is no error, undoes everything if there is one
@contextmanager
def transaction(conn: pymysql.Connection):
    try:
        yield
        conn.commit()
    except HTTPException:
        # our own error (404, 409 ...), undo and pass it on
        conn.rollback()
        raise
    except pymysql.MySQLError as error:
        # database error, undo then try to make a clean http error
        conn.rollback()
        http_error = convert_db_error(error)
        if http_error:
            # "from error" keeps the original error in the traceback
            raise http_error from error
        raise
    except Exception:
        # any other bug, undo and pass it on
        conn.rollback()
        raise

# saves one row in Audit_Log, does nothing when there is no logged in user yet
def write_audit(
    cursor,
    account_id: int | None,
    table_name: str,
    record_id: int,
    action: str,
    old_value: dict | None = None,
    new_value: dict | None = None,
    branch_id: int | None = None,) -> None:
    if account_id is None:
        return

    # old and new values are saved as json text, dates are turned into strings
    old_json = json.dumps(old_value, default=str) if old_value is not None else None
    new_json = json.dumps(new_value, default=str) if new_value is not None else None

    cursor.execute(
        "INSERT INTO Audit_Log (Account_ID, Branch_ID, Table_Name, Record_ID, "
        "Action_Type, Old_Value, New_Value) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (account_id, branch_id, table_name, str(record_id), action, old_json, new_json),
    )
