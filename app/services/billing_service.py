from decimal import Decimal

import pymysql
from pydantic import TypeAdapter, ValidationError

from app.schemas.billing import PaymentAmount
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.insurance_claim_repository import InsuranceClaimRepository

_payment_amount_adapter = TypeAdapter(PaymentAmount)


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

    def calculate_insurance_covered(self, invoice_id: int):
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

        return Decimal(result["Insurance_Covered"])


    def get_invoice_details(self, invoice_id: int):
        invoice = self.invoice_repository.get_by_id(invoice_id)
        if invoice is None:
            return None
        consultation_id = invoice["Consultation_ID"]
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT pt.Treatment_ID, t.Service_Code, t.Treatment_Name,
                       pt.Quantity, pt.Billed_Unit_Price,
                       pt.Quantity * pt.Billed_Unit_Price AS Line_Total
                FROM Prescribed_Treatment pt
                JOIN Treatment_Catalogue t ON pt.Treatment_ID = t.Treatment_ID
                WHERE pt.Consultation_ID = %s
                ORDER BY pt.Prescription_Item_ID
                """,
                (consultation_id,)
            )
            treatments = cursor.fetchall()
        summary = self.invoice_repository.get_summary(invoice_id)
        return {
            "invoice": invoice,
            "treatments": treatments,
            "consultation_fee": summary["Billed_Consultation_Fee"],
            "total_treatment_charges": summary["Total_Treatments_Fee"],
            "total_bill": summary["Invoice_Total"],
            "insurance_covered": summary["Insurance_Covered"],
            "patient_paid": summary["Patient_Paid"],
            "outstanding_balance": summary["Outstanding_Balance"],
        }

    def record_payment(
        self,
        invoice_id: int,
        amount,
        payment_method: str,
        transaction_reference: str
    ):
        try:
            amount = _payment_amount_adapter.validate_python(amount)
        except ValidationError as exc:
            if exc.errors()[0]["type"] == "greater_than":
                raise ValueError("Payment amount must be greater than zero.") from exc
            raise ValueError(
                "Payment amount must be exactly representable within DECIMAL(10, 2)."
            ) from exc

        try:
            # One transaction owns the procedure's invoice lock and response reads.
            self.db.begin()
            with self.db.cursor() as cursor:
                cursor.execute(
                    """
                    CALL sp_record_payment(
                        %s, %s, %s, %s,
                        @payment_id, @remaining_balance, @invoice_status
                    )
                    """,
                    (invoice_id, format(amount, "f"), payment_method, transaction_reference)
                )
                # CALL adds a final empty result set; consume all sets before SELECT.
                while cursor.nextset():
                    pass
                cursor.execute(
                    """
                    SELECT @payment_id AS payment_id,
                           @remaining_balance AS remaining_balance,
                           @invoice_status AS invoice_status
                    """
                )
                result = cursor.fetchone()

            payment = self.payment_repository.get_by_id(result["payment_id"])
            summary = self.invoice_repository.get_summary(invoice_id)
            if payment is None or summary is None:
                raise RuntimeError("Payment procedure returned incomplete results.")

            response = {
                "payment": payment,
                "total_bill": summary["Invoice_Total"],
                "insurance_covered": summary["Insurance_Covered"],
                "total_paid_before_payment": summary["Patient_Paid"] - payment["Amount"],
                "remaining_balance": Decimal(result["remaining_balance"]),
                "invoice_status": result["invoice_status"],
            }
            self.db.commit()
            return response

        except pymysql.MySQLError as exc:
            self.db.rollback()
            # SIGNAL SQLSTATE '45000' uses MySQL error 1644 for business errors.
            if exc.args and exc.args[0] == 1644:
                raise ValueError(exc.args[1]) from exc
            raise
        except Exception:
            self.db.rollback()
            raise

    def update_claim_status(
        self,
        claim_id: int,
        new_status: str,
        approved_amount=None
    ):
        if new_status != "Approved" and approved_amount is not None:
            raise ValueError("Approved amount is only allowed when approving a claim.")

        claim = self.insurance_claim_repository.get_by_id(claim_id)

        if claim is None:
            raise ValueError("Insurance claim not found.")

        current_status = claim["Claim_Status"]

        # Claims may be reviewed or decided directly; rejected/settled are terminal.
        allowed_transitions = {
            "Submitted": {"Under_Review", "Approved", "Rejected"},
            "Under_Review": {"Approved", "Rejected"},
            "Approved": {"Settled"},
            "Rejected": set(),
            "Settled": set(),
        }

        if not allowed_transitions.get(current_status):
            raise ValueError(
                f"Claim with status '{current_status}' cannot be changed."
            )

        if new_status not in allowed_transitions[current_status]:
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
