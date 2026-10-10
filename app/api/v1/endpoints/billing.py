from fastapi import APIRouter, Depends, HTTPException
import pymysql

from app.schemas.billing import (
    PaymentCreate,
    ClaimCreate,
    ClaimStatusUpdate,
)
from app.api.deps import get_db, require_roles, get_own_patient_id, get_staff_branch_id
from app.schemas.user import SystemRoleEnum, UserAccount
from app.repositories.invoice_repository import InvoiceRepository
from app.services.billing_service import BillingService


router = APIRouter()


@router.get(
    "/invoices",
)
def get_invoices(
    db: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(require_roles([SystemRoleEnum.Billing_Staff, SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager, SystemRoleEnum.Receptionist, SystemRoleEnum.Patient])),
):
    invoice_repository = InvoiceRepository(db)

    patient_id = None
    branch_id = None

    if current_user.System_Role == SystemRoleEnum.Patient:
        patient_id = get_own_patient_id(db, current_user)
        if not patient_id:
            return []
    elif current_user.System_Role in (SystemRoleEnum.Receptionist, SystemRoleEnum.Doctor, SystemRoleEnum.Branch_Manager):
        branch_id = get_staff_branch_id(db, current_user)

    return invoice_repository.get_all(patient_id=patient_id, branch_id=branch_id)


@router.get(
    "/invoices/{invoice_id}",
)
def get_invoice(
    invoice_id: int,
    db: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(require_roles([SystemRoleEnum.Billing_Staff, SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager, SystemRoleEnum.Receptionist, SystemRoleEnum.Patient])),
):
    billing_service = BillingService(db)
    details = billing_service.get_invoice_details(invoice_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    with db.cursor() as cursor:
        cursor.execute(
            """
            SELECT a.Patient_ID, a.Branch_ID
            FROM Invoice i
            JOIN Consultation c ON i.Consultation_ID = c.Consultation_ID
            JOIN Appointment a ON c.Appointment_ID = a.Appointment_ID
            WHERE i.Invoice_ID = %s
            """,
            (invoice_id,)
        )
        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    invoice_patient_id = row["Patient_ID"]
    invoice_branch_id = row["Branch_ID"]

    if current_user.System_Role == SystemRoleEnum.Patient:
        own_patient_id = get_own_patient_id(db, current_user)
        if not own_patient_id or own_patient_id != invoice_patient_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: Cannot view another patient's invoice.",
            )
    elif current_user.System_Role in (SystemRoleEnum.Receptionist, SystemRoleEnum.Doctor, SystemRoleEnum.Branch_Manager):
        staff_branch_id = get_staff_branch_id(db, current_user)
        if staff_branch_id and staff_branch_id != invoice_branch_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: Invoice belongs to a different branch.",
            )

    return details


@router.post(
    "/invoices/{invoice_id}/payments",
    dependencies=[Depends(require_roles([SystemRoleEnum.Billing_Staff, SystemRoleEnum.Admin]))],
)
def record_payment(
    invoice_id: int,
    payment_data: PaymentCreate,
    db: pymysql.Connection = Depends(get_db)
):
    billing_service = BillingService(db)

    try:
        result = billing_service.record_payment(
            invoice_id=invoice_id,
            amount=payment_data.amount,
            payment_method=payment_data.payment_method.value,
            transaction_reference=payment_data.transaction_reference
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post(
    "/invoices/{invoice_id}/claims",
    dependencies=[Depends(require_roles([SystemRoleEnum.Billing_Staff, SystemRoleEnum.Admin]))],
)
def submit_insurance_claim(
    invoice_id: int,
    claim_data: ClaimCreate,
    db: pymysql.Connection = Depends(get_db)
):
    billing_service = BillingService(db)

    try:
        claim = billing_service.submit_insurance_claim(
            invoice_id=invoice_id,
            policy_id=claim_data.policy_id,
            claimed_amount=claim_data.claimed_amount
        )

        return claim

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.patch(
    "/claims/{claim_id}/status",
    dependencies=[Depends(require_roles([SystemRoleEnum.Billing_Staff, SystemRoleEnum.Admin]))],
)
def update_claim_status(
    claim_id: int,
    status_data: ClaimStatusUpdate,
    db: pymysql.Connection = Depends(get_db)
):
    billing_service = BillingService(db)

    try:
        claim = billing_service.update_claim_status(
            claim_id=claim_id,
            new_status=status_data.new_status,
            approved_amount=status_data.approved_amount
        )

        return claim

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
