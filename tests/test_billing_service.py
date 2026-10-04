from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services.billing_service import BillingService


def make_service():
    db = MagicMock()
    service = BillingService(db)

    service.invoice_repository = MagicMock()
    service.payment_repository = MagicMock()
    service.insurance_claim_repository = MagicMock()

    return service


def test_payment_amount_must_be_greater_than_zero():
    service = make_service()

    with pytest.raises(
        ValueError,
        match="Payment amount must be greater than zero."
    ):
        service.record_payment(
            invoice_id=1,
            amount=Decimal("0.00"),
            payment_method="Cash",
            transaction_reference="TEST-001"
        )


def test_payment_rejects_missing_invoice():
    service = make_service()

    service.invoice_repository.get_by_id.return_value = None

    with pytest.raises(
        ValueError,
        match="Invoice not found."
    ):
        service.record_payment(
            invoice_id=999,
            amount=Decimal("100.00"),
            payment_method="Cash",
            transaction_reference="TEST-002"
        )


def test_payment_rejects_cancelled_invoice():
    service = make_service()

    service.invoice_repository.get_by_id.return_value = {
        "Invoice_ID": 1,
        "Consultation_ID": 10,
        "Invoice_Status": "Cancelled"
    }

    with pytest.raises(
        ValueError,
        match="Cannot make a payment for a cancelled invoice."
    ):
        service.record_payment(
            invoice_id=1,
            amount=Decimal("100.00"),
            payment_method="Cash",
            transaction_reference="TEST-003"
        )


def test_partial_payment_updates_invoice_to_partially_paid():
    service = make_service()

    service.invoice_repository.get_by_id.return_value = {
        "Invoice_ID": 1,
        "Consultation_ID": 10,
        "Invoice_Status": "Issued"
    }

    service.calculate_total_bill = MagicMock(
        return_value=Decimal("1000.00")
    )

    service.payment_repository.get_total_completed_for_invoice.return_value = (
        Decimal("200.00")
    )

    # Mock the query that calculates insurance coverage.
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "Insurance_Covered": Decimal("0.00")
    }

    service.db.cursor.return_value.__enter__.return_value = cursor

    service.payment_repository.create.return_value = {
        "Payment_ID": 1,
        "Invoice_ID": 1,
        "Amount": Decimal("300.00")
    }

    result = service.record_payment(
        invoice_id=1,
        amount=Decimal("300.00"),
        payment_method="Cash",
        transaction_reference="TEST-PARTIAL"
    )

    assert result["remaining_balance"] == Decimal("500.00")
    assert result["invoice_status"] == "Partially_Paid"

    service.invoice_repository.update_status.assert_called_once_with(
        1,
        "Partially_Paid"
    )

    service.db.commit.assert_called_once()


def test_full_payment_updates_invoice_to_paid():
    service = make_service()

    service.invoice_repository.get_by_id.return_value = {
        "Invoice_ID": 1,
        "Consultation_ID": 10,
        "Invoice_Status": "Partially_Paid"
    }

    service.calculate_total_bill = MagicMock(
        return_value=Decimal("1000.00")
    )

    service.payment_repository.get_total_completed_for_invoice.return_value = (
        Decimal("700.00")
    )

    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "Insurance_Covered": Decimal("0.00")
    }

    service.db.cursor.return_value.__enter__.return_value = cursor

    service.payment_repository.create.return_value = {
        "Payment_ID": 2,
        "Invoice_ID": 1,
        "Amount": Decimal("300.00")
    }

    result = service.record_payment(
        invoice_id=1,
        amount=Decimal("300.00"),
        payment_method="Cash",
        transaction_reference="TEST-FULL"
    )

    assert result["remaining_balance"] == Decimal("0.00")
    assert result["invoice_status"] == "Paid"

    service.invoice_repository.update_status.assert_called_once_with(
        1,
        "Paid"
    )

    service.db.commit.assert_called_once()


def test_payment_rejects_amount_greater_than_outstanding_balance():
    service = make_service()

    service.invoice_repository.get_by_id.return_value = {
        "Invoice_ID": 1,
        "Consultation_ID": 10,
        "Invoice_Status": "Partially_Paid"
    }

    service.calculate_total_bill = MagicMock(
        return_value=Decimal("1000.00")
    )

    service.payment_repository.get_total_completed_for_invoice.return_value = (
        Decimal("700.00")
    )

    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "Insurance_Covered": Decimal("0.00")
    }

    service.db.cursor.return_value.__enter__.return_value = cursor

    with pytest.raises(
        ValueError,
        match="Payment exceeds outstanding balance of 300.00."
    ):
        service.record_payment(
            invoice_id=1,
            amount=Decimal("400.00"),
            payment_method="Cash",
            transaction_reference="TEST-OVERPAY"
        )

    service.payment_repository.create.assert_not_called()
    service.invoice_repository.update_status.assert_not_called()



def test_claim_can_transition_from_submitted_to_approved():
    service = make_service()

    service.insurance_claim_repository.get_by_id.return_value = {
        "Claim_ID": 1,
        "Claim_Status": "Submitted",
        "Claimed_Amount": Decimal("1000.00")
    }

    service.insurance_claim_repository.update_status.return_value = {
        "Claim_ID": 1,
        "Claim_Status": "Approved",
        "Approved_Amount": Decimal("800.00")
    }

    result = service.update_claim_status(
        claim_id=1,
        new_status="Approved",
        approved_amount=Decimal("800.00")
    )

    assert result["Claim_Status"] == "Approved"

    service.insurance_claim_repository.update_status.assert_called_once_with(
        claim_id=1,
        status="Approved",
        approved_amount=Decimal("800.00")
    )

    service.db.commit.assert_called_once()


def test_claim_can_transition_from_approved_to_settled():
    service = make_service()

    service.insurance_claim_repository.get_by_id.return_value = {
        "Claim_ID": 1,
        "Claim_Status": "Approved",
        "Claimed_Amount": Decimal("1000.00"),
        "Approved_Amount": Decimal("800.00")
    }

    service.insurance_claim_repository.update_status.return_value = {
        "Claim_ID": 1,
        "Claim_Status": "Settled",
        "Approved_Amount": Decimal("800.00")
    }

    result = service.update_claim_status(
        claim_id=1,
        new_status="Settled"
    )

    assert result["Claim_Status"] == "Settled"

    service.insurance_claim_repository.update_status.assert_called_once_with(
        claim_id=1,
        status="Settled",
        approved_amount=None
    )

    service.db.commit.assert_called_once()


def test_claim_rejects_invalid_status_transition():
    service = make_service()

    service.insurance_claim_repository.get_by_id.return_value = {
        "Claim_ID": 1,
        "Claim_Status": "Submitted",
        "Claimed_Amount": Decimal("1000.00")
    }

    with pytest.raises(
        ValueError,
        match="Invalid claim status transition: Submitted -> Settled."
    ):
        service.update_claim_status(
            claim_id=1,
            new_status="Settled"
        )

    service.insurance_claim_repository.update_status.assert_not_called()


def test_generate_invoice_for_completed_consultation():
    service = make_service()

    service.invoice_repository.get_by_consultation_id.return_value = None

    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "Consultation_ID": 10,
        "Appointment_Status": "Completed",
        "Standard_Consultation_Fee": Decimal("2500.00")
    }

    service.db.cursor.return_value.__enter__.return_value = cursor

    service.invoice_repository.create.return_value = {
        "Invoice_ID": 5,
        "Consultation_ID": 10,
        "Billed_Consultation_Fee": Decimal("2500.00"),
        "Invoice_Status": "Issued"
    }

    result = service.generate_invoice(consultation_id=10)

    assert result["Invoice_Status"] == "Issued"
    assert result["Billed_Consultation_Fee"] == Decimal("2500.00")

    service.invoice_repository.create.assert_called_once_with(
        consultation_id=10,
        billed_consultation_fee=Decimal("2500.00"),
        invoice_status="Issued"
    )


def test_generate_invoice_rejects_duplicate_invoice():
    service = make_service()

    service.invoice_repository.get_by_consultation_id.return_value = {
        "Invoice_ID": 5,
        "Consultation_ID": 10
    }

    with pytest.raises(
        ValueError,
        match="An invoice already exists for this consultation."
    ):
        service.generate_invoice(consultation_id=10)

    service.invoice_repository.create.assert_not_called()


def test_generate_invoice_requires_completed_appointment():
    service = make_service()

    service.invoice_repository.get_by_consultation_id.return_value = None

    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "Consultation_ID": 10,
        "Appointment_Status": "Scheduled",
        "Standard_Consultation_Fee": Decimal("2500.00")
    }

    service.db.cursor.return_value.__enter__.return_value = cursor

    with pytest.raises(
        ValueError,
        match="Invoice can only be generated for a completed appointment."
    ):
        service.generate_invoice(consultation_id=10)

    service.invoice_repository.create.assert_not_called()