# insurance providers and patient policies
import pymysql
from fastapi import HTTPException

from app.services.common import lower_keys, lower_rows

PROVIDER_COLS = (
    "Provider_ID, Provider_Name, Contact_Number, Email, "
    "Street_Address, City, State_Province, Postal_Code"
)


def get_provider(conn: pymysql.Connection, provider_id: int) -> dict:
    with conn.cursor() as cursor:
        cursor.execute(
            f"SELECT {PROVIDER_COLS} FROM Insurance_Provider WHERE Provider_ID = %s",
            (provider_id,),
        )
        row = lower_keys(cursor.fetchone())
    if not row:
        raise HTTPException(404, "Insurance provider not found")
    return row

def list_providers(conn: pymysql.Connection) -> list[dict]:
    with conn.cursor() as cursor:
        cursor.execute(f"SELECT {PROVIDER_COLS} FROM Insurance_Provider ORDER BY Provider_Name")
        return lower_rows(cursor.fetchall())