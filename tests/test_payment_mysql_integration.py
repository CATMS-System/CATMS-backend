"""Opt-in Docker tests; create and remove only records owned by each fixture."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import pymysql
import pytest
from fastapi.testclient import TestClient
from fastapi.encoders import jsonable_encoder

from app.api.deps import get_db
from app.core.config import settings
from app.db.connection import get_db_connection
from app.main import app
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.billing import PaymentMethod
from app.services.billing_service import BillingService
from app.services.report_service import ReportService


pytestmark = pytest.mark.skipif(
    os.getenv("CATMS_RUN_MYSQL_TESTS") != "1",
    reason="Set CATMS_RUN_MYSQL_TESTS=1 to run disposable Docker MySQL tests.",
)


@pytest.fixture
def disposable_invoice():
    assert settings.DB_HOST in {"localhost", "127.0.0.1"}, "Use local Docker MySQL only"
    db = get_db_connection()
    appointment_id = consultation_id = invoice_id = None
    marker = f"CATMS-TEST-{uuid4().hex}"
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT VERSION() AS version")
            assert cursor.fetchone()["version"].startswith("8.0.")
            # Snapshot existing payment/invoice records to detect accidental changes.
            cursor.execute("SELECT * FROM Invoice ORDER BY Invoice_ID")
            existing_invoices = cursor.fetchall()
            cursor.execute("SELECT * FROM Payment ORDER BY Payment_ID")
            existing_payments = cursor.fetchall()
            cursor.execute("""
                SELECT a.Patient_ID, a.Doctor_ID, a.Branch_ID, ip.Policy_ID
                FROM Appointment a JOIN Insurance_Policy ip ON ip.Patient_ID = a.Patient_ID
                LIMIT 1
            """)
            parent = cursor.fetchone()
            assert parent, "Requires seeded appointment and insurance policy references"
            cursor.execute("""
                INSERT INTO Appointment
                    (Patient_ID, Doctor_ID, Branch_ID, Appointment_Date, Start_Time,
                     Appointment_Type, Status, Reason_For_Visit)
                VALUES (%s, %s, %s, CURRENT_DATE, '23:59:00', 'Walk_In', 'Completed', %s)
            """, (parent["Patient_ID"], parent["Doctor_ID"], parent["Branch_ID"], marker))
            appointment_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO Consultation (Appointment_ID, Diagnosis) VALUES (%s, %s)",
                (appointment_id, marker),
            )
            consultation_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO Invoice (Consultation_ID, Billed_Consultation_Fee, Invoice_Status)
                VALUES (%s, 1000.00, 'Issued')
            """, (consultation_id,))
            invoice_id = cursor.lastrowid
            cursor.execute("SELECT Treatment_ID FROM Treatment_Catalogue LIMIT 1")
            treatment_id = cursor.fetchone()["Treatment_ID"]
            cursor.execute("""
                INSERT INTO Prescribed_Treatment
                    (Consultation_ID, Treatment_ID, Quantity, Billed_Unit_Price)
                VALUES (%s, %s, 2, 50.00)
            """, (consultation_id, treatment_id))
            for status, amount in [("Approved", "200.00"), ("Rejected", "300.00")]:
                cursor.execute("""
                    INSERT INTO Insurance_Claim
                        (Invoice_ID, Policy_ID, Claimed_Amount, Approved_Amount, Claim_Status)
                    VALUES (%s, %s, 300.00, %s, %s)
                """, (invoice_id, parent["Policy_ID"], amount, status))
            for status, amount in [("Completed", "100.00"), ("Pending", "500.00")]:
                cursor.execute("""
                    INSERT INTO Payment
                        (Invoice_ID, Amount, Payment_Method, Payment_Status, Transaction_Reference)
                    VALUES (%s, %s, 'Cash', %s, %s)
                """, (invoice_id, amount, status, f"{marker}-{status}"))
        db.commit()
        yield db, invoice_id, marker
    finally:
        # Roll back failed test operations before cleaning up committed fixture rows.
        db.rollback()
        try:
            with db.cursor() as cursor:
                if invoice_id is not None:
                    cursor.execute("DELETE FROM Payment WHERE Invoice_ID = %s", (invoice_id,))
                    cursor.execute("DELETE FROM Insurance_Claim WHERE Invoice_ID = %s", (invoice_id,))
                    cursor.execute("DELETE FROM Invoice WHERE Invoice_ID = %s", (invoice_id,))
                if consultation_id is not None:
                    cursor.execute("DELETE FROM Prescribed_Treatment WHERE Consultation_ID = %s", (consultation_id,))
                    cursor.execute("DELETE FROM Consultation WHERE Consultation_ID = %s", (consultation_id,))
                if appointment_id is not None:
                    cursor.execute("DELETE FROM Appointment WHERE Appointment_ID = %s", (appointment_id,))
            db.commit()
            if invoice_id is not None:
                with db.cursor() as cursor:
                    cursor.execute("SELECT * FROM Invoice ORDER BY Invoice_ID")
                    assert cursor.fetchall() == existing_invoices
                    cursor.execute("SELECT * FROM Payment ORDER BY Payment_ID")
                    assert cursor.fetchall() == existing_payments
        finally:
            db.close()


@pytest.mark.parametrize("method", [method.value for method in PaymentMethod])
def test_real_procedure_partial_payment_and_view(disposable_invoice, method):
    db, invoice_id, marker = disposable_invoice
    result = BillingService(db).record_payment(invoice_id, Decimal("300"), method, marker)

    assert result["total_bill"] == Decimal("1100")
    assert result["insurance_covered"] == Decimal("200")
    assert result["total_paid_before_payment"] == Decimal("100")
    assert result["remaining_balance"] == Decimal("500")
    assert result["invoice_status"] == "Partially_Paid"
    payment = PaymentRepository(db).get_by_id(result["payment"]["Payment_ID"])
    assert payment["Amount"] == Decimal("300")
    assert payment["Payment_Method"] == method
    assert payment["Payment_Status"] == "Completed"
    assert InvoiceRepository(db).get_by_id(invoice_id)["Invoice_Status"] == "Partially_Paid"
    summary = InvoiceRepository(db).get_summary(invoice_id)
    assert summary["Total_Treatments_Fee"] == Decimal("100")
    assert summary["Patient_Paid"] == Decimal("400")
    assert summary["Outstanding_Balance"] == Decimal("500")


def test_real_full_payment_and_already_paid_rejection(disposable_invoice):
    db, invoice_id, marker = disposable_invoice
    service = BillingService(db)
    result = service.record_payment(invoice_id, Decimal("800"), "Cash", marker)
    assert result["remaining_balance"] == Decimal("0")
    assert result["invoice_status"] == "Paid"
    assert InvoiceRepository(db).get_by_id(invoice_id)["Invoice_Status"] == "Paid"
    with pytest.raises(ValueError, match="already been fully paid"):
        service.record_payment(invoice_id, Decimal("1"), "Cash", marker + "-again")
    assert InvoiceRepository(db).get_summary(invoice_id)["Patient_Paid"] == Decimal("900")


@pytest.mark.parametrize("amount,message", [
    ("0", "Payment amount must be greater than zero"),
    ("-1", "Payment amount must be greater than zero"),
    ("801", "Payment exceeds outstanding balance of 800.00"),
])
def test_real_invalid_amount_rolls_back(disposable_invoice, amount, message):
    db, invoice_id, marker = disposable_invoice
    with pytest.raises(ValueError, match=message):
        BillingService(db).record_payment(invoice_id, Decimal(amount), "Cash", marker)
    assert InvoiceRepository(db).get_by_id(invoice_id)["Invoice_Status"] == "Issued"
    assert InvoiceRepository(db).get_summary(invoice_id)["Patient_Paid"] == Decimal("100")


def test_real_duplicate_reference_rolls_back(disposable_invoice):
    db, invoice_id, marker = disposable_invoice
    with pytest.raises(pymysql.err.IntegrityError):
        BillingService(db).record_payment(invoice_id, Decimal("300"), "Cash", marker + "-Completed")
    assert InvoiceRepository(db).get_by_id(invoice_id)["Invoice_Status"] == "Issued"
    assert InvoiceRepository(db).get_summary(invoice_id)["Patient_Paid"] == Decimal("100")


@pytest.mark.parametrize("case,message", [
    ("missing", "Invoice not found"),
    ("cancelled", "Cannot make a payment for a cancelled invoice"),
    ("zero_balance", "already been fully paid"),
])
def test_real_invoice_validation(disposable_invoice, case, message):
    db, invoice_id, marker = disposable_invoice
    target = invoice_id
    with db.cursor() as cursor:
        if case == "missing":
            target = -1
            cursor.execute("SELECT Invoice_ID FROM Invoice WHERE Invoice_ID = %s", (target,))
            assert cursor.fetchone() is None
        elif case == "cancelled":
            cursor.execute("UPDATE Invoice SET Invoice_Status = 'Cancelled' WHERE Invoice_ID = %s", (invoice_id,))
        else:
            # A zero balance must reject payment even if the status is still Issued.
            cursor.execute("""
                UPDATE Insurance_Claim SET Claimed_Amount = 1000, Approved_Amount = 1000
                WHERE Invoice_ID = %s AND Claim_Status = 'Approved'
            """, (invoice_id,))
    db.commit()
    with pytest.raises(ValueError, match=message):
        BillingService(db).record_payment(target, Decimal("1"), "Cash", marker)
    assert InvoiceRepository(db).get_summary(invoice_id)["Patient_Paid"] == Decimal("100")


def test_real_payment_eligibility_remains_balance_based(disposable_invoice):
    db, invoice_id, marker = disposable_invoice
    with db.cursor() as cursor:
        cursor.execute("UPDATE Invoice SET Invoice_Status = 'Paid' WHERE Invoice_ID = %s", (invoice_id,))
    db.commit()
    result = BillingService(db).record_payment(invoice_id, Decimal("300"), "Cash", marker)
    assert result["invoice_status"] == "Partially_Paid"
    assert result["remaining_balance"] == Decimal("500")


def test_real_response_read_failure_rolls_back_payment_and_invoice(disposable_invoice):
    db, invoice_id, marker = disposable_invoice
    service = BillingService(db)
    with patch.object(service.invoice_repository, "get_summary", side_effect=RuntimeError("read failure")):
        with pytest.raises(RuntimeError, match="read failure"):
            service.record_payment(invoice_id, Decimal("300"), "Cash", marker)
    assert InvoiceRepository(db).get_by_id(invoice_id)["Invoice_Status"] == "Issued"
    assert InvoiceRepository(db).get_summary(invoice_id)["Patient_Paid"] == Decimal("100")


def test_real_api_overpayment_returns_400(disposable_invoice):
    db, invoice_id, marker = disposable_invoice
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.post(
                f"{settings.API_V1_STR}/billing/invoices/{invoice_id}/payments",
                json={"amount": "801", "payment_method": "Cash", "transaction_reference": marker},
            )
        assert response.status_code == 400
        assert response.json()["detail"] == "Payment exceeds outstanding balance of 800.00."
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_real_concurrent_payments_cannot_overpay(disposable_invoice):
    db, invoice_id, marker = disposable_invoice
    barrier = Barrier(2)

    def pay(index):
        connection = get_db_connection()
        try:
            barrier.wait(timeout=10)
            try:
                return BillingService(connection).record_payment(
                    invoice_id, Decimal("600"), "Cash", f"{marker}-{index}"
                )
            except ValueError as exc:
                return str(exc)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(pay, [1, 2]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert "Payment exceeds outstanding balance of 200.00." in results
    db.rollback()  # Start a fresh read snapshot after concurrent commits.
    assert InvoiceRepository(db).get_summary(invoice_id)["Outstanding_Balance"] == Decimal("200")


def test_real_view_preserves_negative_balance(disposable_invoice):
    db, invoice_id, _ = disposable_invoice
    with db.cursor() as cursor:
        cursor.execute("""
            UPDATE Insurance_Claim SET Claimed_Amount = 1200, Approved_Amount = 1200
            WHERE Invoice_ID = %s AND Claim_Status = 'Approved'
        """, (invoice_id,))
    db.commit()
    assert InvoiceRepository(db).get_summary(invoice_id)["Outstanding_Balance"] == Decimal("-200")
    assert BillingService(db).get_invoice_details(invoice_id)["outstanding_balance"] == Decimal("-200")


def test_real_billing_and_all_report_routes(disposable_invoice):
    db, invoice_id, marker = disposable_invoice
    # Use a valid invoice date for an existing policy; change only the disposable invoice.
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT ip.Policy_ID, ip.Start_Date, a.Branch_ID, CURRENT_DATE AS Today
            FROM Invoice i
            JOIN Consultation c ON c.Consultation_ID = i.Consultation_ID
            JOIN Appointment a ON a.Appointment_ID = c.Appointment_ID
            JOIN Insurance_Policy ip ON ip.Patient_ID = a.Patient_ID
            WHERE i.Invoice_ID = %s AND ip.Policy_Status = 'Active'
            LIMIT 1
        """, (invoice_id,))
        policy = cursor.fetchone()
        assert policy, "Requires an active seeded insurance policy"
        cursor.execute("UPDATE Invoice SET Invoice_Date = %s WHERE Invoice_ID = %s",
                       (policy["Start_Date"], invoice_id))
    db.commit()
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    billing_base = f"{settings.API_V1_STR}/billing"
    try:
        with TestClient(app) as client:
            response = client.get(f"{billing_base}/invoices")
            assert response.status_code == 200
            assert any(row["Invoice_ID"] == invoice_id for row in response.json())
            response = client.get(f"{billing_base}/invoices/{invoice_id}")
            assert response.status_code == 200
            assert response.json()["outstanding_balance"] == 800

            response = client.post(f"{billing_base}/invoices/{invoice_id}/claims",
                                   json={"policy_id": policy["Policy_ID"], "claimed_amount": "50"})
            assert response.status_code == 200
            claim = response.json()
            assert claim["Claim_Status"] == "Submitted"
            for status in ["Under_Review", "Approved", "Settled"]:
                payload = {"new_status": status}
                if status == "Approved":
                    payload["approved_amount"] = "50"
                response = client.patch(f"{billing_base}/claims/{claim['Claim_ID']}/status", json=payload)
                assert response.status_code == 200
                assert response.json()["Claim_Status"] == status
            assert response.json()["Settlement_Date"] is not None

            response = client.post(f"{billing_base}/invoices/{invoice_id}/payments", json={
                "amount": "300", "payment_method": "Cash", "transaction_reference": marker,
            })
            assert response.status_code == 200
            assert response.json()["remaining_balance"] == 450
            assert response.json()["invoice_status"] == "Partially_Paid"

            service = ReportService(db)
            start, end = date(2000, 1, 1), date(2100, 1, 1)
            reports = [
                ("branch-daily-summary", {"report_date": policy["Today"].isoformat()},
                 service.get_branch_daily_summary(policy["Today"], policy["Branch_ID"])),
                ("doctor-revenue", {"start_date": start.isoformat(), "end_date": end.isoformat()},
                 service.get_doctor_revenue(start, end, policy["Branch_ID"])),
                ("outstanding-balances", {}, service.get_outstanding_balances(policy["Branch_ID"])),
                ("treatment-usage", {"start_date": start.isoformat(), "end_date": end.isoformat()},
                 service.get_treatment_usage(start, end, policy["Branch_ID"])),
                ("insurance-vs-out-of-pocket", {"start_date": start.isoformat(), "end_date": end.isoformat()},
                 service.get_insurance_vs_out_of_pocket(start, end, policy["Branch_ID"])),
            ]
            for path, parameters, expected in reports:
                response = client.get(f"{settings.API_V1_STR}/reports/{path}",
                                      params={**parameters, "branch_id": policy["Branch_ID"]})
                assert response.status_code == 200
                assert response.json() == jsonable_encoder(expected)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.mark.parametrize("amount", ["800", "800.5", "800.00", "800.0000", "8E2", "0.01"])
def test_real_api_records_exact_cent_amounts(disposable_invoice, amount):
    db, invoice_id, marker = disposable_invoice
    with db.cursor() as cursor:
        cursor.execute("UPDATE Invoice SET Billed_Consultation_Fee = 1200 WHERE Invoice_ID = %s", (invoice_id,))
    db.commit()
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.post(f"{settings.API_V1_STR}/billing/invoices/{invoice_id}/payments", json={
                "amount": amount, "payment_method": "Cash", "transaction_reference": marker,
            })
        assert response.status_code == 200
        payment_id = response.json()["payment"]["Payment_ID"]
        assert PaymentRepository(db).get_by_id(payment_id)["Amount"] == Decimal(amount)
        assert InvoiceRepository(db).get_summary(invoice_id)["Outstanding_Balance"] == Decimal("1000") - Decimal(amount)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.mark.parametrize("amount", ["800.004", "100.999", "0.001", "0", "-1"])
def test_real_api_invalid_precision_returns_422_without_writes(disposable_invoice, amount):
    db, invoice_id, marker = disposable_invoice
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.post(f"{settings.API_V1_STR}/billing/invoices/{invoice_id}/payments", json={
                "amount": amount, "payment_method": "Cash", "transaction_reference": marker,
            })
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "amount"]
        assert InvoiceRepository(db).get_by_id(invoice_id)["Invoice_Status"] == "Issued"
        assert InvoiceRepository(db).get_summary(invoice_id)["Patient_Paid"] == Decimal("100")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.mark.parametrize("amount", [
    "800.004", "100.999", "0.001", "800." + "0" * 40 + "1",
    "0", "-1", "not-a-number", None, "100000000",
])
def test_real_direct_sql_rejects_invalid_amount_without_rounding(disposable_invoice, amount):
    db, invoice_id, marker = disposable_invoice
    db.begin()
    try:
        with db.cursor() as cursor:
            with pytest.raises(pymysql.MySQLError) as exc:
                cursor.execute("""
                    CALL sp_record_payment(%s, %s, %s, %s,
                        @payment_id, @remaining_balance, @invoice_status)
                """, (invoice_id, amount, "Cash", marker))
            assert exc.value.args[0] == 1644
    finally:
        db.rollback()
    assert InvoiceRepository(db).get_by_id(invoice_id)["Invoice_Status"] == "Issued"
    assert InvoiceRepository(db).get_summary(invoice_id)["Patient_Paid"] == Decimal("100")


@pytest.mark.parametrize("amount", ["800", "800.5", "800.00", "800.0000", "0.01"])
def test_real_direct_sql_accepts_exact_cent_amounts(disposable_invoice, amount):
    db, invoice_id, marker = disposable_invoice
    with db.cursor() as cursor:
        cursor.execute("UPDATE Invoice SET Billed_Consultation_Fee = 1200 WHERE Invoice_ID = %s", (invoice_id,))
    db.commit()
    db.begin()
    try:
        with db.cursor() as cursor:
            cursor.execute("""
                CALL sp_record_payment(%s, %s, %s, %s,
                    @payment_id, @remaining_balance, @invoice_status)
            """, (invoice_id, amount, "Cash", marker))
            while cursor.nextset():
                pass
            cursor.execute("SELECT @payment_id AS Payment_ID")
            payment_id = cursor.fetchone()["Payment_ID"]
        db.commit()
    except Exception:
        db.rollback()
        raise
    assert PaymentRepository(db).get_by_id(payment_id)["Amount"] == Decimal(amount)


@pytest.mark.parametrize("current,new", [
    ("Submitted", "Under_Review"), ("Submitted", "Rejected"),
    ("Under_Review", "Rejected"), ("Approved", "Settled"),
])
def test_real_non_approval_amount_rejected_and_null_remains_valid(disposable_invoice, current, new):
    db, invoice_id, _ = disposable_invoice
    initial_amount = Decimal("100") if current == "Approved" else Decimal("0")
    with db.cursor() as cursor:
        cursor.execute("SELECT Policy_ID FROM Insurance_Claim WHERE Invoice_ID = %s LIMIT 1", (invoice_id,))
        policy_id = cursor.fetchone()["Policy_ID"]
        cursor.execute("""
            INSERT INTO Insurance_Claim
                (Invoice_ID, Policy_ID, Claimed_Amount, Approved_Amount, Claim_Status)
            VALUES (%s, %s, 300, %s, %s)
        """, (invoice_id, policy_id, initial_amount, current))
        claim_id = cursor.lastrowid
    db.commit()
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            path = f"{settings.API_V1_STR}/billing/claims/{claim_id}/status"
            response = client.patch(path, json={"new_status": new, "approved_amount": "400"})
            assert response.status_code == 400
            assert response.json()["detail"] == "Approved amount is only allowed when approving a claim."
            with db.cursor() as cursor:
                cursor.execute("SELECT Claim_Status, Approved_Amount FROM Insurance_Claim WHERE Claim_ID = %s", (claim_id,))
                assert cursor.fetchone() == {"Claim_Status": current, "Approved_Amount": initial_amount}
            response = client.patch(path, json={"new_status": new, "approved_amount": None})
            assert response.status_code == 200
            assert response.json()["Claim_Status"] == new
            if new == "Settled":
                assert response.json()["Settlement_Date"] is not None
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
