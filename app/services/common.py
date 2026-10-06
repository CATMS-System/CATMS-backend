"""Small helpers shared by the Member 2 services """

import json
import re
from contextlib import contextmanager
from typing import Any

import pymysql
from fastapi import HTTPException

def lower_keys(row: Any) -> dict | None:
    """DB columns are Pascal_Case (Patient_ID), the API/schemas use
    snake_case (patient_id), Lowercasing maps every column name exactly"""
    return {k.lower(): v for k, v in row.items()} if row else None

def lower_rows(rows) -> list[dict]:
    return [{k.lower(): v for k, v in r.items()} for r in rows]

def escape_like(value: str) -> str:
    """Escapes LIKE wildcards so a user typing '%' or '_' searches for those
    literal characters instead of matching everything """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")