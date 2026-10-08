from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field


class PaymentMethod(str, Enum):
    CASH = "Cash"
    CREDIT_CARD = "Credit_Card"
    DEBIT_CARD = "Debit_Card"
    BANK_TRANSFER = "Bank_Transfer"
    ONLINE = "Online"


def _validate_payment_precision(value: object) -> Decimal:
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Payment amount must be a valid decimal number.") from exc
    if not amount.is_finite():
        raise ValueError("Payment amount must be a finite decimal number.")
    if not amount.is_zero():
        # Inspect the exact coefficient; normalize/quantize can round under context.
        _, digits, exponent = amount.as_tuple()
        significant_digits = len(digits)
        while significant_digits and digits[significant_digits - 1] == 0:
            significant_digits -= 1
        trailing_zeros = len(digits) - significant_digits
        if exponent + trailing_zeros < -2:
            raise ValueError("Payment amount must have at most two decimal places.")
    return amount


PaymentAmount = Annotated[
    Decimal, Field(gt=0, max_digits=10, decimal_places=2),
    BeforeValidator(_validate_payment_precision),
]


class PaymentCreate(BaseModel):
    amount: PaymentAmount
    payment_method: PaymentMethod
    transaction_reference: str


class ClaimCreate(BaseModel):
    policy_id: int = Field(gt=0)
    claimed_amount: Decimal = Field(gt=0)


class ClaimStatusUpdate(BaseModel):
    new_status: str
    approved_amount: Decimal | None = Field(default=None, gt=0)
