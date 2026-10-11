# insurance claims are limited by the unpaid balance and by the policy,
# and approving a claim updates the invoice status
import random
import pytest
from fastapi.testclient import TestClient
from app.main import app


def billing_headers(client):
    response = client.post(
        "/api/v1/auth/login", data={"username": "billing_patel", "password": "Password123!"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# invoice for patient 1 (policy 1) at branch 1: fee 2500 + one ECG 5000 = 7500
# policy 1 covers 80% of the fee (2000) + 85% of the ECG (4250) = 6250
@pytest.fixture
def invoice_id(db):
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO Appointment (Patient_ID, Doctor_ID, Branch_ID, Appointment_Date, "
            "Start_Time, Duration_Minutes, Appointment_Type, Status, Reason_For_Visit) "
            "VALUES (1, 1, 1, '2099-03-03', '10:00:00', 15, 'Standard', 'Completed', "
            "'claim limit test')"
        )
        appointment_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO Consultation (Appointment_ID, Diagnosis) VALUES (%s, 'claim limit test')",
            (appointment_id,),
        )
        consultation_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO Prescribed_Treatment (Consultation_ID, Treatment_ID, Quantity, Billed_Unit_Price) "
            "VALUES (%s, 1, 1, 5000.00)",
            (consultation_id,),
        )
        cursor.execute(
            "INSERT INTO Invoice (Consultation_ID, Invoice_Date, Billed_Consultation_Fee, Invoice_Status) "
            "VALUES (%s, '2026-06-01', 2500.00, 'Issued')",
            (consultation_id,),
        )
        new_invoice_id = cursor.lastrowid
        db.commit()
        yield new_invoice_id
        with db.cursor() as cursor:
            cursor.execute("DELETE FROM Payment WHERE Invoice_ID = %s", (new_invoice_id,))
            cursor.execute("DELETE FROM Insurance_Claim WHERE Invoice_ID = %s", (new_invoice_id,))
            cursor.execute("DELETE FROM Invoice WHERE Invoice_ID = %s", (new_invoice_id,))
            cursor.execute("DELETE FROM Prescribed_Treatment WHERE Consultation_ID = %s", (consultation_id,))
            cursor.execute("DELETE FROM Consultation WHERE Consultation_ID = %s", (consultation_id,))
            cursor.execute("DELETE FROM Appointment WHERE Appointment_ID = %s", (appointment_id,))
        db.commit()


def invoice_status(db, invoice_id):
    db.commit()  # start a fresh read
    with db.cursor() as cursor:
        cursor.execute("SELECT Invoice_Status FROM Invoice WHERE Invoice_ID = %s", (invoice_id,))
        return cursor.fetchone()["Invoice_Status"]


def test_claim_limits_and_invoice_status(db, invoice_id):
    client = TestClient(app)
    headers = billing_headers(client)
    claims_url = f"/api/v1/billing/invoices/{invoice_id}/claims"
    too_much = client.post(claims_url, json={"policy_id": 1, "claimed_amount": "7000.00"}, headers=headers)
    assert too_much.status_code == 400, too_much.text
    assert "policy covers" in too_much.json()["detail"]
    claim = client.post(claims_url, json={"policy_id": 1, "claimed_amount": "6000.00"}, headers=headers)
    assert claim.status_code == 200, claim.text
    claim_id = claim.json()["Claim_ID"]
    # only 250 of the policy is left
    second = client.post(claims_url, json={"policy_id": 1, "claimed_amount": "1000.00"}, headers=headers)
    assert second.status_code == 400, second.text
    approved = client.patch(
        f"/api/v1/billing/claims/{claim_id}/status",
        json={"new_status": "Approved", "approved_amount": "6000.00"},
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    assert invoice_status(db, invoice_id) == "Partially_Paid"
    paid = client.post(
        f"/api/v1/billing/invoices/{invoice_id}/payments",
        json={
            "amount": "1500.00",
            "payment_method": "Cash",
            "transaction_reference": "CLAIMTEST-" + str(random.randint(100000, 999999)),
        },
        headers=headers,
    )
    assert paid.status_code == 200, paid.text
    assert invoice_status(db, invoice_id) == "Paid"
