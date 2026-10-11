"""Patient invoice access regressions that never connect to a database."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.endpoints import billing
from app.main import app
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.user import AccountStatusEnum, SystemRoleEnum, UserAccount


@pytest.fixture
def patient_api(monkeypatch):
    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    user = UserAccount(
        Account_ID=11,
        Username="patient_tester",
        Password_Hash="",
        System_Role=SystemRoleEnum.Patient,
        Account_Status=AccountStatusEnum.Active,
    )
    service = MagicMock()
    monkeypatch.setattr(billing, "BillingService", lambda connection: service)
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with TestClient(app) as client:
            yield client, cursor, service
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.mark.parametrize("query", ["", "?patient_id=2", "?patient_id=2&branch_id=3"])
def test_patient_list_uses_account_patient_instead_of_requested_patient(patient_api, query):
    client, cursor, _ = patient_api
    cursor.fetchone.return_value = {"Patient_ID": 1}
    own_invoice = {"Invoice_ID": 101, "Patient_ID": 1, "Branch_ID": 3}
    other_invoice = {"Invoice_ID": 202, "Patient_ID": 2, "Branch_ID": 3}

    def select_invoices():
        sql, params = cursor.execute.call_args.args
        assert "Patient_ID = %s" in sql
        assert params[0] == 1
        return [row for row in [own_invoice, other_invoice] if row["Patient_ID"] == params[0]]

    cursor.fetchall.side_effect = select_invoices
    response = client.get("/api/v1/billing/invoices" + query)
    assert response.status_code == 200
    assert response.json() == [own_invoice]
    patient_lookup = cursor.execute.call_args_list[0]
    assert patient_lookup.args == (
        "SELECT Patient_ID FROM Patient WHERE Account_ID = %s", (11,)
    )
    if query.endswith("branch_id=3"):
        assert "Branch_ID = %s" in cursor.execute.call_args.args[0]
        assert cursor.execute.call_args.args[1] == (1, 3)


def test_patient_without_linked_patient_gets_empty_list(patient_api):
    client, cursor, _ = patient_api
    cursor.fetchone.return_value = None
    response = client.get("/api/v1/billing/invoices?patient_id=2")
    assert response.status_code == 200
    assert response.json() == []
    cursor.fetchall.assert_not_called()


@pytest.mark.parametrize("owner,status", [(1, 200), (2, 403)])
def test_patient_invoice_detail_checks_owner(patient_api, owner, status):
    client, cursor, service = patient_api
    details = {"invoice": {"Invoice_ID": 101}}
    service.get_invoice_details.return_value = details
    cursor.fetchone.side_effect = [
        {"Patient_ID": owner, "Branch_ID": 3},
        {"Patient_ID": 1},
    ]
    response = client.get("/api/v1/billing/invoices/101")
    assert response.status_code == status
    if status == 200:
        assert response.json() == details
    else:
        assert response.json()["detail"] == "Access denied: Cannot view another patient's invoice."
    assert cursor.execute.call_args_list[0].args[1] == (101,)
    assert cursor.execute.call_args_list[1].args[1] == (11,)


def test_invoice_routes_require_authentication(patient_api):
    client, cursor, service = patient_api
    app.dependency_overrides.pop(get_current_user)
    for url in ["/api/v1/billing/invoices", "/api/v1/billing/invoices/101"]:
        assert client.get(url).status_code == 401
    cursor.execute.assert_not_called()
    service.get_invoice_details.assert_not_called()


@pytest.mark.parametrize("patient_id,branch_id,where,params", [
    (1, None, "Patient_ID = %s", (1,)),
    (2, None, "Patient_ID = %s", (2,)),
    (1, 3, "Patient_ID = %s AND Branch_ID = %s", (1, 3)),
    (None, 3, "Branch_ID = %s", (3,)),
    (0, None, "Patient_ID = %s", (0,)),
])
def test_repository_parameterizes_patient_and_branch_filters(patient_id, branch_id, where, params):
    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [{"Invoice_ID": 101}]
    assert InvoiceRepository(db).get_all(patient_id=patient_id, branch_id=branch_id) == [{"Invoice_ID": 101}]
    sql, actual_params = cursor.execute.call_args.args
    assert " ".join(sql.split()) == (
        f"SELECT * FROM vw_Invoice_Summary WHERE {where} ORDER BY Invoice_ID"
    )
    assert actual_params == params
