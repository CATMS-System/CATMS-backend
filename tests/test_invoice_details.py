from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from app.db.connection import get_db_connection
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.report_repository import ReportRepository
from app.services.billing_service import BillingService
from app.api.v1.billing import get_invoice
from fastapi import HTTPException


@pytest.fixture
def db():
    connection = get_db_connection()
    try:
        yield connection
    finally:
        connection.close()


def test_invoice_list_branches_follow_appointment(db):
    rows = InvoiceRepository(db).get_all()
    with db.cursor() as cursor:
        cursor.execute("""SELECT i.*, b.Branch_ID, b.Branch_Name FROM Invoice i
            JOIN Consultation c ON c.Consultation_ID = i.Consultation_ID
            JOIN Appointment a ON a.Appointment_ID = c.Appointment_ID
            JOIN Branch b ON b.Branch_ID = a.Branch_ID ORDER BY i.Invoice_ID""")
        assert rows == cursor.fetchall()
    assert rows, "This integration test requires seeded invoices"
    assert all(row["Branch_ID"] and row["Branch_Name"] for row in rows)


def test_invoice_details_billed_treatments_and_summary(db):
    invoices = InvoiceRepository(db).get_all()
    assert invoices
    saw_treatment = False
    for invoice in invoices:
        details = BillingService(db).get_invoice_details(invoice["Invoice_ID"])
        assert details["invoice"] == InvoiceRepository(db).get_by_id(invoice["Invoice_ID"])
        with db.cursor() as cursor:
            cursor.execute("""SELECT pt.Treatment_ID, t.Service_Code, t.Treatment_Name,
                pt.Quantity, pt.Billed_Unit_Price, pt.Quantity * pt.Billed_Unit_Price AS Line_Total
                FROM Prescribed_Treatment pt JOIN Treatment_Catalogue t ON t.Treatment_ID = pt.Treatment_ID
                WHERE pt.Consultation_ID = %s ORDER BY pt.Prescription_Item_ID""", (invoice["Consultation_ID"],))
            assert details["treatments"] == cursor.fetchall()
            cursor.execute("""SELECT COALESCE(SUM(Approved_Amount), 0) AS coverage
                FROM Insurance_Claim WHERE Invoice_ID = %s AND Claim_Status IN ('Approved', 'Settled')""", (invoice["Invoice_ID"],))
            assert details["insurance_covered"] == cursor.fetchone()["coverage"]
            cursor.execute("""SELECT COALESCE(SUM(Amount), 0) AS paid FROM Payment
                WHERE Invoice_ID = %s AND Payment_Status = 'Completed'""", (invoice["Invoice_ID"],))
            assert details["patient_paid"] == cursor.fetchone()["paid"]
        saw_treatment |= bool(details["treatments"])
        treatment_total = sum((item["Quantity"] * item["Billed_Unit_Price"] for item in details["treatments"]), Decimal('0'))
        assert details["total_treatment_charges"] == treatment_total
        assert details["consultation_fee"] == invoice["Billed_Consultation_Fee"]
        assert details["total_bill"] == invoice["Billed_Consultation_Fee"] + treatment_total
        assert details["outstanding_balance"] == details["total_bill"] - details["insurance_covered"] - details["patient_paid"]
    assert saw_treatment, "This integration test requires seeded prescribed treatments"


def test_details_preserve_negative_balance_and_empty_treatments():
    db = MagicMock()
    service = BillingService(db)
    service.invoice_repository.get_by_id = MagicMock(return_value={"Invoice_ID": 1, "Consultation_ID": 2, "Billed_Consultation_Fee": Decimal('100')})
    db.cursor.return_value.__enter__.return_value.fetchall.return_value = []
    service.calculate_treatment_total = MagicMock(return_value=Decimal('0'))
    service.calculate_insurance_covered = MagicMock(return_value=Decimal('80'))
    service.payment_repository.get_total_completed_for_invoice = MagicMock(return_value=Decimal('30'))
    details = service.get_invoice_details(1)
    assert details["treatments"] == []
    assert details["outstanding_balance"] == Decimal('-10')
    db.commit.assert_not_called()


def test_missing_invoice_keeps_404():
    db = MagicMock()
    db.cursor.return_value.__enter__.return_value.fetchone.return_value = None
    with pytest.raises(HTTPException) as exc:
        get_invoice(999, db)
    assert exc.value.status_code == 404


def test_doctor_consultation_count_uses_existing_invoice_scope(db):
    start, end = date(2000, 1, 1), date(2100, 1, 1)
    rows = ReportRepository(db).get_doctor_revenue(start, end)
    assert rows
    for row in rows:
        with db.cursor() as cursor:
            cursor.execute("""SELECT COUNT(DISTINCT c.Consultation_ID) AS consultations,
                COUNT(i.Invoice_ID) AS invoices FROM Invoice i
                JOIN Consultation c ON c.Consultation_ID = i.Consultation_ID
                JOIN Appointment a ON a.Appointment_ID = c.Appointment_ID
                WHERE i.Invoice_Date BETWEEN %s AND %s AND a.Doctor_ID = %s AND a.Branch_ID = %s""",
                (start, end, row["Doctor_ID"], row["Branch_ID"]))
            counts = cursor.fetchone()
        assert row["Total_Consultations"] == counts["consultations"]
        assert row["Total_Invoices"] == counts["invoices"]
        filtered = ReportRepository(db).get_doctor_revenue(start, end, row["Branch_ID"])
        assert row in filtered
    assert not ReportRepository(db).get_doctor_revenue(date(1900, 1, 1), date(1900, 1, 1))
