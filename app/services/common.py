# helpers shared by the patient and insurance services
from typing import Any


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