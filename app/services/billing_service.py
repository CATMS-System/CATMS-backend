from decimal import Decimal

import pymysql

from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.insurance_claim_repository import InsuranceClaimRepository

class BillingService:

    def __init__(self, db: pymysql.Connection):
        self.db = db
        self.invoice_repository = InvoiceRepository(db)
        self.payment_repository = PaymentRepository(db)
        self.insurance_claim_repository = InsuranceClaimRepository(db)

    def generate_invoice(self, consultation_id: int):
        # Do not create the same invoice twice.
        existing_invoice = self.invoice_repository.get_by_consultation_id(
            consultation_id
        )

        if existing_invoice:
            raise ValueError(
                "An invoice already exists for this consultation."
            )

        # Find the consultation, appointment and doctor's consultation fee.
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    c.Consultation_ID,
                    a.Status AS Appointment_Status,
                    d.Standard_Consultation_Fee
                FROM Consultation c
                JOIN Appointment a
                    ON c.Appointment_ID = a.Appointment_ID
                JOIN Doctor d
                    ON a.Doctor_ID = d.Doctor_ID
                WHERE c.Consultation_ID = %s
                """,
                (consultation_id,)
            )

            consultation = cursor.fetchone()

        if consultation is None:
            raise ValueError("Consultation not found.")

        if consultation["Appointment_Status"] != "Completed":
            raise ValueError(
                "Invoice can only be generated for a completed appointment."
            )

        consultation_fee = consultation["Standard_Consultation_Fee"]

        invoice = self.invoice_repository.create(
            consultation_id=consultation_id,
            billed_consultation_fee=consultation_fee,
            invoice_status="Issued"
        )

        return invoice

    def calculate_treatment_total(self, consultation_id: int):
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(
                    SUM(Quantity * Billed_Unit_Price),
                    0
                ) AS Treatment_Total
                FROM Prescribed_Treatment
                WHERE Consultation_ID = %s
                """,
                (consultation_id,)
            )

            result = cursor.fetchone()

        return result["Treatment_Total"]

    def calculate_total_bill(self, consultation_id: int):
        invoice = self.invoice_repository.get_by_consultation_id(
            consultation_id
        )

        if invoice is None:
            raise ValueError("Invoice not found.")

        consultation_fee = invoice["Billed_Consultation_Fee"]
        treatment_total = self.calculate_treatment_total(consultation_id)

        return Decimal(consultation_fee) + Decimal(treatment_total)

    def record_payment(
        self,
        invoice_id: int,
        amount,
        payment_method: str,
        transaction_reference: str
    ):
        amount = Decimal(amount)

        # Payment must be positive.
        if amount <= 0:
            raise ValueError(
                "Payment amount must be greater than zero."
            )

        # Find invoice.
        invoice = self.invoice_repository.get_by_id(invoice_id)

        if invoice is None:
            raise ValueError("Invoice not found.")

        if invoice["Invoice_Status"] == "Cancelled":
            raise ValueError(
                "Cannot make a payment for a cancelled invoice."
            )

        consultation_id = invoice["Consultation_ID"]

        # Full bill = consultation fee + treatment charges.
        total_bill = self.calculate_total_bill(consultation_id)

        # Previous completed payments.
        total_paid = Decimal(
            self.payment_repository.get_total_completed_for_invoice(
                invoice_id
            )
        )

        # Approved/settled insurance coverage.
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(
                    SUM(Approved_Amount),
                    0
                ) AS Insurance_Covered
                FROM Insurance_Claim
                WHERE Invoice_ID = %s
                  AND Claim_Status IN ('Approved', 'Settled')
                """,
                (invoice_id,)
            )

            result = cursor.fetchone()

        insurance_covered = Decimal(
            result["Insurance_Covered"]
        )

        # Work out what is still owed.
        outstanding = (
            total_bill
            - total_paid
            - insurance_covered
        )

        if outstanding <= 0:
            raise ValueError(
                "This invoice has already been fully paid."
            )

        if amount > outstanding:
            raise ValueError(
                f"Payment exceeds outstanding balance of "
                f"{outstanding:.2f}."
            )

        try:
            # Insert payment.
            payment = self.payment_repository.create(
                invoice_id=invoice_id,
                amount=amount,
                payment_method=payment_method,
                transaction_reference=transaction_reference,
                payment_status="Completed"
            )

            remaining_balance = outstanding - amount

            # Determine invoice status.
            if remaining_balance == 0:
                new_status = "Paid"
            else:
                new_status = "Partially_Paid"

            # Update invoice status.
            self.invoice_repository.update_status(
                invoice_id,
                new_status
            )

            # Save both operations together.
            self.db.commit()

            return {
                "payment": payment,
                "total_bill": total_bill,
                "insurance_covered": insurance_covered,
                "total_paid_before_payment": total_paid,
                "remaining_balance": remaining_balance,
                "invoice_status": new_status
            }

        except Exception:
            # Undo both operations if anything fails.
            self.db.rollback()
            raise

    def update_claim_status(
        self,
        claim_id: int,
        new_status: str,
        approved_amount=None
    ):
        claim = self.insurance_claim_repository.get_by_id(claim_id)

        if claim is None:
            raise ValueError("Insurance claim not found.")

        current_status = claim["Claim_Status"]

        # Allowed workflow:
        # Submitted -> Approved -> Settled
        allowed_transitions = {
            "Submitted": "Approved",
            "Approved": "Settled"
        }

        if current_status not in allowed_transitions:
            raise ValueError(
                f"Claim with status '{current_status}' cannot be changed."
            )

        expected_status = allowed_transitions[current_status]

        if new_status != expected_status:
            raise ValueError(
                f"Invalid claim status transition: "
                f"{current_status} -> {new_status}."
            )

        # Approval requires an approved amount.
        if new_status == "Approved":
            if approved_amount is None:
                raise ValueError(
                    "Approved amount is required when approving a claim."
                )

            approved_amount = Decimal(approved_amount)

            if approved_amount <= 0:
                raise ValueError(
                    "Approved amount must be greater than zero."
                )

            claimed_amount = Decimal(claim["Claimed_Amount"])

            if approved_amount > claimed_amount:
                raise ValueError(
                    "Approved amount cannot exceed claimed amount."
                )

        try:
            updated_claim = self.insurance_claim_repository.update_status(
                claim_id=claim_id,
                status=new_status,
                approved_amount=approved_amount
            )

            self.db.commit()

            return updated_claim

        except Exception:
            self.db.rollback()
            raise

    def submit_insurance_claim(
        self,
        invoice_id: int,
        policy_id: int,
        claimed_amount
    ):
        claimed_amount = Decimal(claimed_amount)

        if claimed_amount <= 0:
            raise ValueError(
                "Claimed amount must be greater than zero."
            )

        # Check that the invoice exists.
        invoice = self.invoice_repository.get_by_id(invoice_id)

        if invoice is None:
            raise ValueError("Invoice not found.")

        if invoice["Invoice_Status"] == "Cancelled":
            raise ValueError(
                "Cannot submit a claim for a cancelled invoice."
            )

        # Calculate the complete bill.
        total_bill = self.calculate_total_bill(
            invoice["Consultation_ID"]
        )

        # Do not allow a claim larger than the bill.
        if claimed_amount > total_bill:
            raise ValueError(
                f"Claimed amount cannot exceed total bill of "
                f"{total_bill:.2f}."
            )

        # Check that the insurance policy exists.
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    ip.*,
                    a.Patient_ID AS Invoice_Patient_ID
                FROM Insurance_Policy ip
                JOIN Appointment a
                    ON a.Patient_ID = ip.Patient_ID
                JOIN Consultation c
                    ON c.Appointment_ID = a.Appointment_ID
                JOIN Invoice i
                    ON i.Consultation_ID = c.Consultation_ID
                WHERE ip.Policy_ID = %s
                AND i.Invoice_ID = %s
                """,
                (policy_id, invoice_id)
            )
            policy = cursor.fetchone()

        if policy is None:
            raise ValueError(
                "Insurance policy not found or does not belong to this patient."
            )

        if policy["Policy_Status"] != "Active":
            raise ValueError("Insurance policy is not active.")

        invoice_date = invoice["Invoice_Date"]

        if not (
            policy["Start_Date"] <= invoice_date <= policy["End_Date"]
        ):
            raise ValueError(
                "Insurance policy was not valid on the invoice date."
            )

        try:
            claim = self.insurance_claim_repository.create(
                invoice_id=invoice_id,
                policy_id=policy_id,
                claimed_amount=claimed_amount,
                approved_amount=Decimal("0.00"),
                claim_status="Submitted"
            )

            self.db.commit()

            return claim

        except Exception:
            self.db.rollback()
            raise