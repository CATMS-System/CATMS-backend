import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.db.connection import get_db_connection
from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_admin():
    mock_admin = UserAccount(
        Account_ID=1,
        Username="admin_alana",
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


def test_insurance_provider_and_policy_creation_writes_to_audit_log(client, auth_admin):
    conn = get_db_connection()
    created_provider_id = None
    created_policy_id = None

    try:
        # 1. Create Insurance Provider
        provider_data = {
            "provider_name": "Audit Test Insurance Corp",
            "contact_number": "+94 11 999 0001",
            "email": "audit_test@insurance.com",
            "street_address": "100 Galle Road",
            "city": "Colombo",
            "state_province": "Western Province",
            "postal_code": "00300",
        }
        resp = client.post("/api/v1/insurance/providers", json=provider_data)
        assert resp.status_code == 201, resp.text
        provider_resp = resp.json()
        created_provider_id = provider_resp["provider_id"]

        # Commit to reset snapshot and read committed rows
        conn.commit()
        # Verify Audit_Log entry for Insurance_Provider
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM Audit_Log 
                WHERE Table_Name = 'Insurance_Provider' AND Record_ID = %s 
                ORDER BY Audit_ID DESC LIMIT 1
                """,
                (str(created_provider_id),)
            )
            provider_audit = cur.fetchone()

        assert provider_audit is not None
        assert provider_audit["Account_ID"] == auth_admin.Account_ID
        assert provider_audit["Table_Name"] == "Insurance_Provider"
        assert provider_audit["Record_ID"] == str(created_provider_id)
        assert provider_audit["Action_Type"] == "INSERT"

        # 2. Attach Insurance Policy to Patient 1
        policy_data = {
            "provider_id": created_provider_id,
            "policy_number": "POL-AUDIT-9999",
            "policy_type": "Comprehensive",
            "start_date": "2026-01-01",
            "end_date": "2027-01-01",
            "default_coverage_percentage": 85.00,
        }
        resp_policy = client.post("/api/v1/patients/1/policies", json=policy_data)
        assert resp_policy.status_code == 201, resp_policy.text
        policy_resp = resp_policy.json()
        created_policy_id = policy_resp["policy_id"]

        # Commit to reset snapshot and read committed rows
        conn.commit()
        # Verify Audit_Log entry for Insurance_Policy
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM Audit_Log 
                WHERE Table_Name = 'Insurance_Policy' AND Record_ID = %s 
                ORDER BY Audit_ID DESC LIMIT 1
                """,
                (str(created_policy_id),)
            )
            policy_audit = cur.fetchone()

        assert policy_audit is not None
        assert policy_audit["Account_ID"] == auth_admin.Account_ID
        assert policy_audit["Table_Name"] == "Insurance_Policy"
        assert policy_audit["Record_ID"] == str(created_policy_id)
        assert policy_audit["Action_Type"] == "INSERT"

    finally:
        # Cleanup created records and their audit logs
        conn.commit()
        with conn.cursor() as cur:
            if created_policy_id:
                cur.execute("DELETE FROM Insurance_Policy WHERE Policy_ID = %s", (created_policy_id,))
                cur.execute("DELETE FROM Audit_Log WHERE Table_Name = 'Insurance_Policy' AND Record_ID = %s", (str(created_policy_id),))
            if created_provider_id:
                cur.execute("DELETE FROM Insurance_Provider WHERE Provider_ID = %s", (created_provider_id,))
                cur.execute("DELETE FROM Audit_Log WHERE Table_Name = 'Insurance_Provider' AND Record_ID = %s", (str(created_provider_id),))
            # Also clean up the temporary test records from our python test script
            cur.execute("DELETE FROM Insurance_Policy WHERE Policy_Number = 'P123'")
            cur.execute("DELETE FROM Insurance_Provider WHERE Provider_Name = 'Test12345'")
        conn.commit()
        conn.close()
