from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import pymysql

from app.services.billing_service import BillingService


def make_service():
    db = MagicMock()
    service = BillingService(db)

    service.invoice_repository = MagicMock()
    service.payment_repository = MagicMock()
    service.insurance_claim_repository = MagicMock()

    return service


@pytest.mark.parametrize("amount,message", [
    ("100.00", "Invoice not found."),
    ("100.00", "Cannot make a payment for a cancelled invoice."),
    ("400.00", "Payment exceeds outstanding balance of 300.00."),
    ("100.00", "This invoice has already been fully paid."),
])
def test_payment_procedure_validation_is_translated_to_value_error(amount, message):
    service = make_service()
    cursor = service.db.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = pymysql.err.OperationalError(1644, message)

    with pytest.raises(ValueError) as exc:
        service.record_payment(1, Decimal(amount), "Cash", "TEST-INVALID")

    assert str(exc.value) == message
    service.db.rollback.assert_called_once()
    service.db.commit.assert_not_called()
    service.payment_repository.create.assert_not_called()
    service.invoice_repository.update_status.assert_not_called()


@pytest.mark.parametrize("amount", [
    "800.004", "100.999", "0.001", "800.00000000000000000000000000000000001",
    "0", "-1", "NaN", "Infinity", "100000000",
])
def test_payment_service_rejects_invalid_amount_before_transaction(amount):
    service = make_service()
    service.db.cursor.return_value.__enter__.return_value.execute.side_effect = AssertionError(
        "Invalid amount reached the database"
    )
    with pytest.raises(ValueError, match="Payment amount"):
        service.record_payment(1, Decimal(amount), "Cash", "TEST-INVALID-AMOUNT")
    service.db.begin.assert_not_called()
    service.db.cursor.assert_not_called()
    service.db.commit.assert_not_called()


@pytest.mark.parametrize("amount", ["800", "800.5", "800.00", "800.0000", "8E2", "0.01"])
def test_payment_service_forwards_exact_decimal_text(amount):
    service = make_service()
    cursor = service.db.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = pymysql.err.OperationalError(1644, "test stop after CALL")
    with pytest.raises(ValueError, match="test stop after CALL"):
        service.record_payment(1, Decimal(amount), "Cash", "TEST-EXACT-AMOUNT")
    forwarded = cursor.execute.call_args.args[1][1]
    assert isinstance(forwarded, str)
    assert Decimal(forwarded) == Decimal(amount)
    assert "E" not in forwarded.upper()
    service.db.rollback.assert_called_once()


@pytest.mark.parametrize("remaining,paid_before,status", [
    ("500.00", "200.00", "Partially_Paid"),
    ("0.00", "700.00", "Paid"),
])
def test_payment_procedure_preserves_partial_and_full_payment_response(remaining, paid_before, status):
    service = make_service()
    cursor = service.db.cursor.return_value.__enter__.return_value
    cursor.nextset.side_effect = [True, True, None]
    cursor.fetchone.return_value = {
        "payment_id": 2, "remaining_balance": Decimal(remaining), "invoice_status": status,
    }
    payment = {"Payment_ID": 2, "Invoice_ID": 1, "Amount": Decimal("300.00")}
    service.payment_repository.get_by_id.return_value = payment
    service.invoice_repository.get_summary.return_value = {
        "Invoice_Total": Decimal("1000.00"), "Insurance_Covered": Decimal("0.00"),
        "Patient_Paid": Decimal(paid_before) + Decimal("300.00"),
    }

    result = service.record_payment(1, Decimal("300.00"), "Cash", "TEST-PAYMENT")

    assert result == {
        "payment": payment, "total_bill": Decimal("1000.00"),
        "insurance_covered": Decimal("0.00"), "total_paid_before_payment": Decimal(paid_before),
        "remaining_balance": Decimal(remaining), "invoice_status": status,
    }
    call_sql, parameters = cursor.execute.call_args_list[0].args
    assert "CALL sp_record_payment(" in call_sql
    assert parameters == (1, "300.00", "Cash", "TEST-PAYMENT")
    assert cursor.nextset.call_count == 3
    assert "SELECT @payment_id" in cursor.execute.call_args_list[1].args[0]
    service.payment_repository.get_by_id.assert_called_once_with(2)
    service.invoice_repository.get_summary.assert_called_once_with(1)
    service.payment_repository.create.assert_not_called()
    service.invoice_repository.update_status.assert_not_called()
    service.db.begin.assert_called_once()
    service.db.commit.assert_called_once()
    service.db.rollback.assert_not_called()


@pytest.mark.parametrize("failure_stage", ["call", "outputs", "payment", "summary", "commit"])
def test_payment_rolls_back_database_failures(failure_stage):
    service = make_service()
    cursor = service.db.cursor.return_value.__enter__.return_value
    cursor.nextset.return_value = None
    cursor.fetchone.return_value = {
        "payment_id": 2, "remaining_balance": Decimal("500"), "invoice_status": "Partially_Paid",
    }
    service.payment_repository.get_by_id.return_value = {"Amount": Decimal("300")}
    service.invoice_repository.get_summary.return_value = {
        "Invoice_Total": Decimal("1000"), "Insurance_Covered": Decimal("0"),
        "Patient_Paid": Decimal("500"),
    }
    error = pymysql.err.OperationalError(2013, "Lost connection")
    if failure_stage == "call":
        cursor.execute.side_effect = error
    elif failure_stage == "outputs":
        cursor.execute.side_effect = [None, error]
    elif failure_stage == "payment":
        service.payment_repository.get_by_id.side_effect = error
    elif failure_stage == "summary":
        service.invoice_repository.get_summary.side_effect = error
    else:
        service.db.commit.side_effect = error

    with pytest.raises(pymysql.err.OperationalError) as exc:
        service.record_payment(1, Decimal("300"), "Cash", "TEST-FAILURE")
    assert exc.value is error
    service.db.rollback.assert_called_once()
    if failure_stage != "commit":
        service.db.commit.assert_not_called()


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
