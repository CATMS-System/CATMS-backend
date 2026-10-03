from decimal import Decimal

from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    invoice_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0)
    payment_method: str
    transaction_reference: str


class ClaimCreate(BaseModel):
    invoice_id: int = Field(gt=0)
    policy_id: int = Field(gt=0)
    claimed_amount: Decimal = Field(gt=0)


class ClaimStatusUpdate(BaseModel):
    new_status: str
    approved_amount: Decimal | None = Field(default=None, gt=0)