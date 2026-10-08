from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.repositories.insurance_claim_repository import InsuranceClaimRepository
from app.services.billing_service import BillingService


STATUSES = ["Submitted", "Under_Review", "Approved", "Rejected", "Settled"]
PERMITTED = {
    ("Submitted", "Under_Review"),
    ("Submitted", "Approved"),
    ("Submitted", "Rejected"),
    ("Under_Review", "Approved"),
    ("Under_Review", "Rejected"),
    ("Approved", "Settled"),
}
TRANSITIONS = [(current, new) for current in STATUSES for new in STATUSES + ["Unknown"]]
CLAIM_URL = f"{settings.API_V1_STR}/billing/claims/1/status"


@pytest.fixture
def service():
    service = BillingService(MagicMock())
    service.insurance_claim_repository = MagicMock()
    return service


def configure_claim(service, current):
    service.insurance_claim_repository.get_by_id.return_value = {
        "Claim_ID": 1,
        "Claim_Status": current,
        "Claimed_Amount": Decimal("1000.00"),
        "Approved_Amount": Decimal("800.00") if current == "Approved" else Decimal("0"),
    }


def assert_no_update(service):
    service.insurance_claim_repository.update_status.assert_not_called()
    service.db.commit.assert_not_called()


@pytest.mark.parametrize("current,new", TRANSITIONS)
def test_service_claim_transition_matrix(service, current, new):
    configure_claim(service, current)
    amount = Decimal("800.00") if new == "Approved" else None
    updated = {"Claim_ID": 1, "Claim_Status": new}
    service.insurance_claim_repository.update_status.return_value = updated

    if (current, new) in PERMITTED:
        assert service.update_claim_status(1, new, amount) == updated
        service.insurance_claim_repository.update_status.assert_called_once_with(
            claim_id=1, status=new, approved_amount=amount
        )
        service.db.commit.assert_called_once()
        service.db.rollback.assert_not_called()
    else:
        with pytest.raises(ValueError, match="cannot be changed|Invalid claim status transition"):
            service.update_claim_status(1, new, amount)
        assert_no_update(service)


@pytest.fixture
def claim_api(service):
    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: service.db
    try:
        with patch("app.api.v1.endpoints.billing.BillingService", return_value=service):
            with TestClient(app) as client:
                yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.mark.parametrize("current,new", TRANSITIONS)
def test_api_claim_transition_matrix(claim_api, service, current, new):
    configure_claim(service, current)
    service.insurance_claim_repository.update_status.return_value = {
        "Claim_ID": 1, "Claim_Status": new
    }
    payload = {"new_status": new}
    if new == "Approved":
        payload["approved_amount"] = "800.00"

    response = claim_api.patch(CLAIM_URL, json=payload)

    if (current, new) in PERMITTED:
        assert response.status_code == 200
        assert response.json()["Claim_Status"] == new
        service.db.commit.assert_called_once()
    else:
        assert response.status_code == 400
        detail = response.json()["detail"]
        if current in {"Rejected", "Settled"}:
            assert detail == f"Claim with status '{current}' cannot be changed."
        else:
            assert detail == f"Invalid claim status transition: {current} -> {new}."
        assert_no_update(service)


def test_service_rejects_nonexistent_claim(service):
    service.insurance_claim_repository.get_by_id.return_value = None
    with pytest.raises(ValueError, match="Insurance claim not found"):
        service.update_claim_status(1, "Under_Review")
    assert_no_update(service)


def test_api_nonexistent_claim_returns_400(claim_api, service):
    service.insurance_claim_repository.get_by_id.return_value = None
    response = claim_api.patch(CLAIM_URL, json={"new_status": "Under_Review"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Insurance claim not found."
    assert_no_update(service)


@pytest.mark.parametrize("current", ["Submitted", "Under_Review"])
@pytest.mark.parametrize("amount", [None, Decimal("0"), Decimal("-1"), Decimal("1001")])
def test_approval_preserves_amount_validation(service, current, amount):
    configure_claim(service, current)
    with pytest.raises(ValueError, match="Approved amount"):
        service.update_claim_status(1, "Approved", amount)
    assert_no_update(service)


@pytest.mark.parametrize("current,new", sorted(PERMITTED - {
    ("Submitted", "Approved"), ("Under_Review", "Approved"),
}))
@pytest.mark.parametrize("amount", [Decimal("50"), Decimal("400"), Decimal("1001")])
def test_service_rejects_approval_amount_on_non_approval_transition(service, current, new, amount):
    configure_claim(service, current)
    with pytest.raises(ValueError, match="only allowed when approving"):
        service.update_claim_status(1, new, amount)
    service.insurance_claim_repository.get_by_id.assert_not_called()
    assert_no_update(service)


@pytest.mark.parametrize("current,new", sorted(PERMITTED - {
    ("Submitted", "Approved"), ("Under_Review", "Approved"),
}))
@pytest.mark.parametrize("amount", ["50", "400", "1001"])
def test_api_rejects_approval_amount_on_non_approval_transition(claim_api, service, current, new, amount):
    configure_claim(service, current)
    response = claim_api.patch(CLAIM_URL, json={"new_status": new, "approved_amount": amount})
    assert response.status_code == 400
    assert response.json()["detail"] == "Approved amount is only allowed when approving a claim."
    assert_no_update(service)


@pytest.mark.parametrize("current,new", sorted(PERMITTED - {
    ("Submitted", "Approved"), ("Under_Review", "Approved"),
}))
def test_non_approval_transition_accepts_explicit_null(claim_api, service, current, new):
    configure_claim(service, current)
    service.insurance_claim_repository.update_status.return_value = {"Claim_Status": new}
    response = claim_api.patch(CLAIM_URL, json={"new_status": new, "approved_amount": None})
    assert response.status_code == 200
    service.insurance_claim_repository.update_status.assert_called_once_with(
        claim_id=1, status=new, approved_amount=None,
    )


@pytest.mark.parametrize("current", ["Submitted", "Under_Review"])
@pytest.mark.parametrize("amount,expected_status", [(None, 400), ("0", 422), ("-1", 422), ("1001", 400)])
def test_api_preserves_approval_amount_limits(claim_api, service, current, amount, expected_status):
    configure_claim(service, current)
    response = claim_api.patch(CLAIM_URL, json={"new_status": "Approved", "approved_amount": amount})
    assert response.status_code == expected_status
    assert_no_update(service)


def test_claim_update_failure_rolls_back(service):
    configure_claim(service, "Submitted")
    service.insurance_claim_repository.update_status.side_effect = RuntimeError("DB failure")
    with pytest.raises(RuntimeError, match="DB failure"):
        service.update_claim_status(1, "Under_Review")
    service.db.rollback.assert_called_once()
    service.db.commit.assert_not_called()


@pytest.mark.parametrize("status", ["Under_Review", "Rejected", "Settled"])
def test_repository_preserves_status_updates_and_settlement_date(status):
    db = MagicMock()
    repository = InsuranceClaimRepository(db)
    repository.get_by_id = MagicMock(return_value={"Claim_Status": status})
    cursor = db.cursor.return_value.__enter__.return_value

    assert repository.update_status(1, status)["Claim_Status"] == status

    sql, parameters = cursor.execute.call_args.args
    if status == "Settled":
        assert "Settlement_Date = %s" in sql
        assert parameters == (status, date.today(), 1)
    else:
        assert "Settlement_Date" not in sql
        assert "Approved_Amount" not in sql
        assert parameters == (status, 1)
