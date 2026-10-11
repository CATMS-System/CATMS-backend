# billing staff can only take payments and handle claims for their own branch
from fastapi.testclient import TestClient
from app.main import app


def headers_for(client, username):
    response = client.post(
        "/api/v1/auth/login", data={"username": username, "password": "Password123!"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_other_branch_billing_is_blocked(db):
    client = TestClient(app)
    kandy = headers_for(client, "billing_kandy")  # branch 2
    # invoice 1 and claim 1 belong to the Colombo branch (branch 1) in the seed data
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM Payment WHERE Invoice_ID = 1")
        payments_before = cursor.fetchone()["n"]
    payment = client.post(
        "/api/v1/billing/invoices/1/payments",
        json={"amount": "10.00", "payment_method": "Cash", "transaction_reference": "BRANCH-SCOPE-TEST"},
        headers=kandy,
    )
    assert payment.status_code == 403, payment.text
    claim = client.post(
        "/api/v1/billing/invoices/1/claims",
        json={"policy_id": 1, "claimed_amount": "10.00"},
        headers=kandy,
    )
    assert claim.status_code == 403, claim.text
    status = client.patch(
        "/api/v1/billing/claims/1/status", json={"new_status": "Rejected"}, headers=kandy
    )
    assert status.status_code == 403, status.text
    db.commit()  # fresh read
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM Payment WHERE Invoice_ID = 1")
        assert cursor.fetchone()["n"] == payments_before
