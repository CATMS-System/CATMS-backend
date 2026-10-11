from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.schemas.billing import PaymentCreate, PaymentMethod


ALLOWED_METHODS = ["Cash", "Credit_Card", "Debit_Card", "Bank_Transfer", "Online"]
INVALID_METHODS = ["Cheque", "cash", "Credit Card", "Cash ", "", None, 1]
PAYMENT_URL = f"{settings.API_V1_STR}/billing/invoices/1/payments"


def payment_payload(method):
    return {
        "amount": "100.00",
        "payment_method": method,
        "transaction_reference": "TEST-PAYMENT",
    }


@pytest.fixture
def payment_api():
    from app.api.deps import get_current_user
    from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum
    mock_user = UserAccount(
        Account_ID=1,
        Username="billing_tester",
        Password_Hash="",
        System_Role=SystemRoleEnum.Billing_Staff,
        Account_Status=AccountStatusEnum.Active,
    )
    db = MagicMock()
    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        with patch("app.api.v1.endpoints.billing.BillingService") as service_class:
            with TestClient(app) as client:
                yield client, service_class, db
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def test_payment_method_enum_matches_database_values():
    assert [method.value for method in PaymentMethod] == ALLOWED_METHODS


@pytest.mark.parametrize("method", ALLOWED_METHODS)
def test_payment_schema_accepts_allowed_methods(method):
    payment = PaymentCreate(**payment_payload(method))

    assert payment.payment_method is PaymentMethod(method)
    assert payment.model_dump(mode="json")["payment_method"] == method
    assert payment.amount == Decimal("100.00")


@pytest.mark.parametrize("method", INVALID_METHODS)
def test_payment_schema_rejects_invalid_methods(method):
    with pytest.raises(ValidationError) as exc:
        PaymentCreate(**payment_payload(method))

    assert exc.value.errors()[0]["loc"] == ("payment_method",)


@pytest.mark.parametrize("method", ALLOWED_METHODS)
def test_payment_api_preserves_valid_request_format(payment_api, method):
    client, service_class, db = payment_api
    service_class.return_value.record_payment.return_value = {
        "payment": {"Payment_Method": method},
        "invoice_status": "Partially_Paid",
    }

    response = client.post(
        PAYMENT_URL,
        json=payment_payload(method),
    )

    assert response.status_code == 200
    assert response.json()["payment"]["Payment_Method"] == method
    service_class.assert_called_once_with(db)
    service_class.return_value.record_payment.assert_called_once_with(
        invoice_id=1,
        amount=Decimal("100.00"),
        payment_method=method,
        transaction_reference="TEST-PAYMENT",
    )
    passed_method = service_class.return_value.record_payment.call_args.kwargs[
        "payment_method"
    ]
    assert type(passed_method) is str


@pytest.mark.parametrize("method", INVALID_METHODS)
def test_payment_api_returns_422_before_processing_invalid_methods(payment_api, method):
    client, service_class, db = payment_api

    response = client.post(
        PAYMENT_URL, json=payment_payload(method)
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "payment_method"]
    service_class.assert_not_called()
    db.commit.assert_not_called()


def test_payment_api_requires_payment_method(payment_api):
    client, service_class, _ = payment_api
    payload = payment_payload("Cash")
    del payload["payment_method"]

    response = client.post(PAYMENT_URL, json=payload)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "payment_method"]
    service_class.assert_not_called()


@pytest.mark.parametrize("amount", ["800", "800.5", "800.00", "800.0000", "8E2", "0.01"])
def test_payment_api_accepts_exact_cent_amounts(payment_api, amount):
    client, service_class, _ = payment_api
    service_class.return_value.record_payment.return_value = {"invoice_status": "Paid"}
    payload = {**payment_payload("Cash"), "amount": amount}
    payment = PaymentCreate(**payload)
    assert payment.amount == Decimal(amount)

    response = client.post(PAYMENT_URL, json=payload)

    assert response.status_code == 200
    assert service_class.return_value.record_payment.call_args.kwargs["amount"] == Decimal(amount)


@pytest.mark.parametrize("amount", [
    "800.004", "100.999", "0.001", "800.00000000000000000000000000000000001",
    "0", "-1", "NaN", "Infinity", "100000000",
])
def test_payment_api_rejects_invalid_amounts_before_service(payment_api, amount):
    client, service_class, db = payment_api
    payload = {**payment_payload("Cash"), "amount": amount}
    with pytest.raises(ValidationError):
        PaymentCreate(**payload)

    response = client.post(PAYMENT_URL, json=payload)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "amount"]
    service_class.assert_not_called()
    db.commit.assert_not_called()
