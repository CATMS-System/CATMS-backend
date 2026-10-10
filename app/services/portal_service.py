# online access for patients: reception hands out a one time code, the patient
# uses it on the public activate page to choose their own username and password
import hashlib
import hmac
import secrets

import pymysql
from fastapi import HTTPException

from app.core.config import settings
from app.core.security import get_password_hash
from app.schemas.patient import PortalActivateRequest, PortalVerifyRequest
from app.services.common import transaction, write_audit

# no 0, O, 1, I or L so a printed code is hard to misread
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 10
INVITE_DAYS = 7
MAX_FAILED_ATTEMPTS = 5

# one message for every kind of wrong code, so nothing is leaked
INVALID_CODE_MESSAGE = "The NIC or activation code is not valid, or the code has expired"


def make_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


# the code is random and long, so a keyed hash is enough (the key is the app secret)
def hash_code(code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest()


# 5 chars, a dash, 5 chars is easier to read out and type
def format_code(code: str) -> str:
    return f"{code[:5]}-{code[5:]}"


# what the patient sees about their online access, used by the staff profile card
def get_portal_access(cursor, patient_id: int) -> dict:
    # left join because a patient without a login has no User_Account row
    cursor.execute(
        "SELECT u.Username FROM Patient p "
        "LEFT JOIN User_Account u ON u.Account_ID = p.Account_ID "
        "WHERE p.Patient_ID = %s",
        (patient_id,),
    )
    row = cursor.fetchone() or {}
    cursor.execute(
        "SELECT Invite_Type, Expires_At FROM Patient_Portal_Invite "
        "WHERE Patient_ID = %s AND Used_At IS NULL AND Revoked_At IS NULL AND Expires_At > NOW() "
        "ORDER BY Invite_ID DESC LIMIT 1",
        (patient_id,),
    )
    invite = cursor.fetchone()
    return {
        "has_account": row.get("Username") is not None,
        "username": row.get("Username"),
        "invite_pending": invite is not None,
        "invite_type": invite["Invite_Type"] if invite else None,
        "invite_expires_at": invite["Expires_At"] if invite else None,
    }


# no commit in here, the caller owns the transaction (registration uses it too)
def issue_invite(cursor, patient_id: int, created_by: int | None) -> dict:
    cursor.execute("SELECT Account_ID FROM Patient WHERE Patient_ID = %s FOR UPDATE", (patient_id,))
    patient = cursor.fetchone()
    if not patient:
        raise HTTPException(404, "Patient not found")

    # a patient with a login gets a reset code, a patient without one gets an activation code
    invite_type = "Activate"
    if patient["Account_ID"] is not None:
        cursor.execute(
            "SELECT System_Role FROM User_Account WHERE Account_ID = %s", (patient["Account_ID"],)
        )
        account = cursor.fetchone()
        if not account or account["System_Role"] != "Patient":
            raise HTTPException(409, "The login linked to this patient is not a patient account")
        invite_type = "Reset"

    # only the newest code works
    cursor.execute(
        "UPDATE Patient_Portal_Invite SET Revoked_At = NOW() "
        "WHERE Patient_ID = %s AND Used_At IS NULL AND Revoked_At IS NULL",
        (patient_id,),
    )

    code = make_code()
    cursor.execute(
        "INSERT INTO Patient_Portal_Invite (Patient_ID, Invite_Type, Code_Hash, Created_By, Expires_At) "
        "VALUES (%s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL %s DAY))",
        (patient_id, invite_type, hash_code(code), created_by, INVITE_DAYS),
    )
    invite_id = cursor.lastrowid
    cursor.execute("SELECT Expires_At FROM Patient_Portal_Invite WHERE Invite_ID = %s", (invite_id,))
    expires_at = cursor.fetchone()["Expires_At"]

    # the audit row never holds the code or its hash
    write_audit(
        cursor,
        account_id=created_by,
        table_name="Patient_Portal_Invite",
        record_id=invite_id,
        action="INSERT",
        new_value={"patient_id": patient_id, "invite_type": invite_type, "expires_at": expires_at},
    )
    return {
        "patient_id": patient_id,
        "invite_type": invite_type,
        "code": format_code(code),
        "expires_at": expires_at,
    }


def create_invite(conn: pymysql.Connection, patient_id: int, created_by: int | None) -> dict:
    with transaction(conn), conn.cursor() as cursor:
        return issue_invite(cursor, patient_id, created_by)


def revoke_invite(conn: pymysql.Connection, patient_id: int, account_id: int | None) -> None:
    with transaction(conn), conn.cursor() as cursor:
        cursor.execute("SELECT Patient_ID FROM Patient WHERE Patient_ID = %s", (patient_id,))
        if not cursor.fetchone():
            raise HTTPException(404, "Patient not found")
        cursor.execute(
            "UPDATE Patient_Portal_Invite SET Revoked_At = NOW() "
            "WHERE Patient_ID = %s AND Used_At IS NULL AND Revoked_At IS NULL",
            (patient_id,),
        )
        if cursor.rowcount == 0:
            raise HTTPException(404, "This patient has no pending code")
        write_audit(
            cursor,
            account_id=account_id,
            table_name="Patient_Portal_Invite",
            record_id=patient_id,
            action="UPDATE",
            new_value={"patient_id": patient_id, "revoked": True},
        )


# finds the open invite for this nic and checks the code
# returns (status, patient, invite), status is "ok" or "invalid"
# a wrong code adds one to Failed_Attempts, after 5 the invite is dead
def check_code(cursor, nic: str, code: str):
    cursor.execute("SELECT Patient_ID, Account_ID FROM Patient WHERE NIC = %s FOR UPDATE", (nic,))
    patient = cursor.fetchone()
    if not patient:
        return "invalid", None, None

    cursor.execute(
        "SELECT Invite_ID, Invite_Type, Code_Hash, Failed_Attempts FROM Patient_Portal_Invite "
        "WHERE Patient_ID = %s AND Used_At IS NULL AND Revoked_At IS NULL AND Expires_At > NOW() "
        "ORDER BY Invite_ID DESC LIMIT 1 FOR UPDATE",
        (patient["Patient_ID"],),
    )
    invite = cursor.fetchone()
    if not invite or invite["Failed_Attempts"] >= MAX_FAILED_ATTEMPTS:
        return "invalid", None, None

    # the invite type must still match the patient (login created or removed since)
    has_account = patient["Account_ID"] is not None
    if (invite["Invite_Type"] == "Activate") == has_account:
        return "invalid", None, None

    if not hmac.compare_digest(invite["Code_Hash"], hash_code(code)):
        cursor.execute(
            "UPDATE Patient_Portal_Invite SET Failed_Attempts = Failed_Attempts + 1 WHERE Invite_ID = %s",
            (invite["Invite_ID"],),
        )
        return "invalid", None, None

    return "ok", patient, invite


# first step of the page: tells the patient if they are activating or resetting
def verify_code(conn: pymysql.Connection, data: PortalVerifyRequest) -> dict:
    # the commit is kept even for a wrong code, so the attempt counter is saved
    with transaction(conn), conn.cursor() as cursor:
        status, patient, invite = check_code(cursor, data.nic, data.code)
        if status == "ok":
            username = None
            if invite["Invite_Type"] == "Reset":
                cursor.execute(
                    "SELECT Username FROM User_Account WHERE Account_ID = %s", (patient["Account_ID"],)
                )
                username = cursor.fetchone()["Username"]
            return {"invite_type": invite["Invite_Type"], "username": username}
    raise HTTPException(400, INVALID_CODE_MESSAGE)


def activate_account(conn: pymysql.Connection, data: PortalActivateRequest) -> dict:
    result = None
    with transaction(conn), conn.cursor() as cursor:
        status, patient, invite = check_code(cursor, data.nic, data.code)
        if status == "ok":
            result = _finish_activation(cursor, data, patient, invite)
    if result is None:
        raise HTTPException(400, INVALID_CODE_MESSAGE)
    return result


# runs after the code was accepted, any error here rolls everything back
def _finish_activation(cursor, data: PortalActivateRequest, patient: dict, invite: dict) -> dict:
    password_hash = get_password_hash(data.password)

    if invite["Invite_Type"] == "Reset":
        cursor.execute(
            "UPDATE User_Account SET Password_Hash = %s WHERE Account_ID = %s",
            (password_hash, patient["Account_ID"]),
        )
        cursor.execute(
            "SELECT Username FROM User_Account WHERE Account_ID = %s", (patient["Account_ID"],)
        )
        username = cursor.fetchone()["Username"]
        account_id = patient["Account_ID"]
        write_audit(
            cursor,
            account_id=account_id,
            table_name="User_Account",
            record_id=account_id,
            action="UPDATE",
            new_value={"username": username, "password_reset": True},
        )
    else:
        if not data.username:
            raise HTTPException(422, "Choose a username")
        # checked only after the code was accepted, so strangers cannot probe usernames
        cursor.execute("SELECT Account_ID FROM User_Account WHERE Username = %s", (data.username,))
        if cursor.fetchone():
            raise HTTPException(409, "That username is already taken")

        cursor.execute(
            "INSERT INTO User_Account (Username, Password_Hash, System_Role) VALUES (%s, %s, 'Patient')",
            (data.username, password_hash),
        )
        account_id = cursor.lastrowid
        # Account_ID IS NULL in the where part stops two requests linking the same patient
        cursor.execute(
            "UPDATE Patient SET Account_ID = %s WHERE Patient_ID = %s AND Account_ID IS NULL",
            (account_id, patient["Patient_ID"]),
        )
        if cursor.rowcount != 1:
            raise HTTPException(409, "This patient already has an online account")
        username = data.username
        write_audit(
            cursor,
            account_id=account_id,
            table_name="User_Account",
            record_id=account_id,
            action="INSERT",
            new_value={"username": username, "system_role": "Patient", "patient_id": patient["Patient_ID"]},
        )

    cursor.execute(
        "UPDATE Patient_Portal_Invite SET Used_At = NOW() WHERE Invite_ID = %s", (invite["Invite_ID"],)
    )
    return {"username": username, "invite_type": invite["Invite_Type"]}
