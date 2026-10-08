from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from app.db.connection import get_db_connection
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.report_repository import ReportRepository
from app.services.billing_service import BillingService
from app.api.v1.endpoints.billing import get_invoice
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
    service.invoice_repository.get_summary = MagicMock(return_value={
        "Billed_Consultation_Fee": Decimal('100'), "Total_Treatments_Fee": Decimal('0'),
        "Invoice_Total": Decimal('100'), "Insurance_Covered": Decimal('80'),
        "Patient_Paid": Decimal('30'), "Outstanding_Balance": Decimal('-10'),
    })
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


def test_doctor_revenue_view_preserves_original_totals_and_branch_filters(db):
    start, end = date(2000, 1, 1), date(2100, 1, 1)
    # Independent calculation from base tables checks view integration compatibility.
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT d.Doctor_ID, CONCAT(s.First_Name, ' ', s.Last_Name) AS Doctor_Name,
                   b.Branch_ID, b.Branch_Name,
                   COUNT(i.Invoice_ID) AS Total_Invoices,
                   COUNT(DISTINCT c.Consultation_ID) AS Total_Consultations,
                   COALESCE(SUM(i.Billed_Consultation_Fee + COALESCE((
                       SELECT SUM(pt.Quantity * pt.Billed_Unit_Price)
                       FROM Prescribed_Treatment pt WHERE pt.Consultation_ID = c.Consultation_ID
                   ), 0)), 0) AS Gross_Revenue,
                   COALESCE(SUM(COALESCE((
                       SELECT SUM(p.Amount) FROM Payment p
                       WHERE p.Invoice_ID = i.Invoice_ID AND p.Payment_Status = 'Completed'
                   ), 0)), 0) AS Collected_Revenue
            FROM Invoice i
            JOIN Consultation c ON c.Consultation_ID = i.Consultation_ID
            JOIN Appointment a ON a.Appointment_ID = c.Appointment_ID
            JOIN Doctor d ON d.Doctor_ID = a.Doctor_ID
            JOIN Staff s ON s.Staff_ID = d.Doctor_ID
            JOIN Branch b ON b.Branch_ID = a.Branch_ID
            WHERE i.Invoice_Date BETWEEN %s AND %s
            GROUP BY d.Doctor_ID, s.First_Name, s.Last_Name, b.Branch_ID, b.Branch_Name
        """, (start, end))
        expected = cursor.fetchall()
    repository = ReportRepository(db)
    key = lambda row: (row["Doctor_ID"], row["Branch_ID"])
    assert sorted(repository.get_doctor_revenue(start, end), key=key) == sorted(expected, key=key)
    for branch_id in {row["Branch_ID"] for row in expected}:
        filtered = [row for row in expected if row["Branch_ID"] == branch_id]
        assert sorted(repository.get_doctor_revenue(start, end, branch_id), key=key) == sorted(filtered, key=key)
