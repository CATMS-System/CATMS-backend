from fastapi import APIRouter, Depends, HTTPException
import pymysql

from app.schemas.billing import (
    PaymentCreate,
    ClaimCreate,
    ClaimStatusUpdate,
)
from app.api.deps import get_db
from app.repositories.invoice_repository import InvoiceRepository
from app.services.billing_service import BillingService


router = APIRouter()


@router.get("/invoices")
def get_invoices(
    db: pymysql.Connection = Depends(get_db)
):
    invoice_repository = InvoiceRepository(db)

    return invoice_repository.get_all()


@router.get("/invoices/{invoice_id}")
def get_invoice(
    invoice_id: int,
    db: pymysql.Connection = Depends(get_db)
):
    billing_service = BillingService(db)
    details = billing_service.get_invoice_details(invoice_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return details


@router.post("/invoices/{invoice_id}/payments")
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
            payment_method=payment_data.payment_method,
            transaction_reference=payment_data.transaction_reference
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post("/invoices/{invoice_id}/claims")
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


@router.patch("/claims/{claim_id}/status")
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