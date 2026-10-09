"""
Integration tests for Staff and Doctor creation:
- Creation of Doctor staff inserts records into User_Account, Staff, Doctor, and Doctor_Specialty.
- Validation rejects doctors without license number or consultation fee with 422.
- Duplicate doctor license numbers return 409 Conflict.
- Non-doctor staff creations insert User_Account and Staff without Doctor records.
"""

from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.db.connection import get_db_connection
from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum


@pytest.fixture
def auth_admin():
    mock_admin = UserAccount(
        Account_ID=1,
        Username="admin_tester",
        Password_Hash="",
        System_Role=SystemRoleEnum.Admin,
        Account_Status=AccountStatusEnum.Active,
    )
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: mock_admin
    yield mock_admin
    if previous is not None:
        app.dependency_overrides[get_current_user] = previous
    else:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def cleanup_created_staff():
    created_staff_ids = []
    yield created_staff_ids
    if created_staff_ids:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                for sid in created_staff_ids:
                    # Fetch account ID to clean up user account too
                    cur.execute("SELECT Account_ID FROM Staff WHERE Staff_ID = %s", (sid,))
                    row = cur.fetchone()
                    acc_id = row["Account_ID"] if row else None

                    # Cascade delete on Staff will remove Doctor and Doctor_Specialty
                    cur.execute("DELETE FROM Staff WHERE Staff_ID = %s", (sid,))
                    if acc_id:
                        cur.execute("DELETE FROM User_Account WHERE Account_ID = %s", (acc_id,))
            conn.commit()
        finally:
            conn.close()


def test_create_doctor_success_creates_doctor_and_specialties(auth_admin, cleanup_created_staff):
    """
    Verifies that creating staff with System_Role='Doctor' atomically creates
    User_Account, Staff, Doctor, and Doctor_Specialty rows.
    """
    with TestClient(app) as client:
        payload = {
            "First_Name": "Amara",
            "Last_Name": "Jayawardena",
            "Job_Title": "Cardiologist",
            "Contact_Number": "0771239988",
            "Email": "amara.cardio@example.com",
            "Employment_Status": "Active",
            "Branch_ID": 1,
            "System_Role": "Doctor",
            "License_Number": "SLMC-CARDIO-8899",
            "Standard_Consultation_Fee": "3500.00",
            "Specialty_IDs": [1],
        }

        response = client.post("/api/v1/staff", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        staff_id = data["Staff_ID"]
        cleanup_created_staff.append(staff_id)

        assert data["First_Name"] == "Amara"
        assert data["License_Number"] == "SLMC-CARDIO-8899"
        assert float(data["Standard_Consultation_Fee"]) == 3500.00
        assert data["Specialty_IDs"] == [1]

        # Verify database rows directly
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # 1. Staff table
                cur.execute("SELECT * FROM Staff WHERE Staff_ID = %s", (staff_id,))
                staff_row = cur.fetchone()
                assert staff_row is not None
                assert staff_row["First_Name"] == "Amara"

                # 2. Doctor table
                cur.execute("SELECT * FROM Doctor WHERE Doctor_ID = %s", (staff_id,))
                doctor_row = cur.fetchone()
                assert doctor_row is not None
                assert doctor_row["License_Number"] == "SLMC-CARDIO-8899"
                assert Decimal(str(doctor_row["Standard_Consultation_Fee"])) == Decimal("3500.00")

                # 3. Doctor_Specialty table
                cur.execute("SELECT * FROM Doctor_Specialty WHERE Doctor_ID = %s", (staff_id,))
                specialty_rows = cur.fetchall()
                assert len(specialty_rows) == 1
                assert specialty_rows[0]["Specialty_ID"] == 1

                # 4. User_Account table
                cur.execute("SELECT * FROM User_Account WHERE Account_ID = %s", (staff_row["Account_ID"],))
                acc_row = cur.fetchone()
                assert acc_row is not None
                assert acc_row["System_Role"] == "Doctor"
        finally:
            conn.close()


def test_create_doctor_missing_license_or_fee_returns_422(auth_admin):
    """
    Verifies that creating a doctor without license number or fee returns 422.
    """
    with TestClient(app) as client:
        # Missing license
        payload_no_license = {
            "First_Name": "Kasun",
            "Last_Name": "Perera",
            "Job_Title": "Pediatrician",
            "Contact_Number": "0771239911",
            "Email": "kasun.pedia@example.com",
            "Branch_ID": 1,
            "System_Role": "Doctor",
            "Standard_Consultation_Fee": "2500.00",
        }
        res1 = client.post("/api/v1/staff", json=payload_no_license)
        assert res1.status_code == 422
        assert "License number and standard consultation fee are required" in res1.json()["detail"]

        # Missing fee
        payload_no_fee = {
            "First_Name": "Kasun",
            "Last_Name": "Perera",
            "Job_Title": "Pediatrician",
            "Contact_Number": "0771239911",
            "Email": "kasun.pedia@example.com",
            "Branch_ID": 1,
            "System_Role": "Doctor",
            "License_Number": "SLMC-PEDIA-7766",
        }
        res2 = client.post("/api/v1/staff", json=payload_no_fee)
        assert res2.status_code == 422
        assert "License number and standard consultation fee are required" in res2.json()["detail"]


def test_create_doctor_duplicate_license_returns_409(auth_admin, cleanup_created_staff):
    """
    Verifies that attempting to register two doctors with the same license number returns 409 Conflict.
    """
    with TestClient(app) as client:
        payload1 = {
            "First_Name": "Rohan",
            "Last_Name": "Silva",
            "Job_Title": "General Practitioner",
            "Contact_Number": "0771112233",
            "Email": "rohan.gp1@example.com",
            "Branch_ID": 1,
            "System_Role": "Doctor",
            "License_Number": "SLMC-DUP-TEST-001",
            "Standard_Consultation_Fee": "2000.00",
        }
        res1 = client.post("/api/v1/staff", json=payload1)
        assert res1.status_code == 200
        cleanup_created_staff.append(res1.json()["Staff_ID"])

        # Second doctor with identical license
        payload2 = {
            "First_Name": "Sameera",
            "Last_Name": "Fernando",
            "Job_Title": "General Practitioner",
            "Contact_Number": "0771112244",
            "Email": "sameera.gp2@example.com",
            "Branch_ID": 1,
            "System_Role": "Doctor",
            "License_Number": "SLMC-DUP-TEST-001",
            "Standard_Consultation_Fee": "2000.00",
        }
        res2 = client.post("/api/v1/staff", json=payload2)
        assert res2.status_code == 409
        assert "already exists" in res2.json()["detail"]


def test_create_non_doctor_staff_does_not_insert_doctor(auth_admin, cleanup_created_staff):
    """
    Verifies that creating non-doctor staff (e.g. Receptionist) does not create Doctor rows.
    """
    with TestClient(app) as client:
        payload = {
            "First_Name": "Nalini",
            "Last_Name": "Gamage",
            "Job_Title": "Front Desk Receptionist",
            "Contact_Number": "0779988776",
            "Email": "nalini.desk@example.com",
            "Branch_ID": 1,
            "System_Role": "Receptionist",
        }
        res = client.post("/api/v1/staff", json=payload)
        assert res.status_code == 200
        staff_id = res.json()["Staff_ID"]
        cleanup_created_staff.append(staff_id)

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM Doctor WHERE Doctor_ID = %s", (staff_id,))
                doctor_row = cur.fetchone()
                assert doctor_row is None
        finally:
            conn.close()
