from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db, get_current_user
from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum
from app.core.config import settings
from app.main import app


BILLING_ROUTES = {
    "/invoices": "get",
    "/invoices/{invoice_id}": "get",
    "/invoices/{invoice_id}/payments": "post",
    "/invoices/{invoice_id}/claims": "post",
    "/claims/{claim_id}/status": "patch",
}
REPORT_ROUTES = [
    "/branch-daily-summary", "/doctor-revenue", "/outstanding-balances",
    "/treatment-usage", "/insurance-vs-out-of-pocket",
]


@pytest.fixture
def client():
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: UserAccount(
        Account_ID=1,
        Username="admin_tester",
        Password_Hash="",
        System_Role=SystemRoleEnum.Admin,
        Account_Status=AccountStatusEnum.Active,
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_openapi_registers_domain_prefixes_without_legacy_billing_routes(client):
    response = client.get(f"{settings.API_V1_STR}/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    operation_ids = []
    for path, method in BILLING_ROUTES.items():
        route = paths[f"{settings.API_V1_STR}/billing{path}"]
        assert set(route) == {method}
        assert route[method]["tags"] == ["Billing"]
        operation_ids.append(route[method]["operationId"])
        assert f"{settings.API_V1_STR}{path}" not in paths
    for path in REPORT_ROUTES:
        route = paths[f"{settings.API_V1_STR}/reports{path}"]
        assert set(route) == {"get"}
        assert route["get"]["tags"] == ["Reports"]
        operation_ids.append(route["get"]["operationId"])
    assert len(operation_ids) == len(set(operation_ids))
    assert f"{settings.API_V1_STR}/health" in paths
    assert client.get("/docs").status_code == 200


@pytest.mark.parametrize("path,method", BILLING_ROUTES.items())
def test_legacy_billing_routes_are_not_registered(client, path, method):
    path = path.replace("{invoice_id}", "1").replace("{claim_id}", "1")
    assert client.request(method, f"{settings.API_V1_STR}{path}").status_code == 404


def test_invoice_listing_uses_billing_prefix(client):
    rows = [{"Invoice_ID": 1, "Invoice_Status": "Issued"}]
    with patch("app.api.v1.endpoints.billing.InvoiceRepository") as repository:
        repository.return_value.get_all.return_value = rows
        response = client.get(f"{settings.API_V1_STR}/billing/invoices")
    assert response.status_code == 200
    assert response.json() == rows


def test_invoice_details_use_billing_prefix(client):
    details = {"invoice": {"Invoice_ID": 1}, "treatments": [], "total_bill": 100}
    with patch("app.api.v1.endpoints.billing.BillingService") as service:
        service.return_value.get_invoice_details.return_value = details
        response = client.get(f"{settings.API_V1_STR}/billing/invoices/1")
        service.return_value.get_invoice_details.assert_called_once_with(1)
    assert response.status_code == 200
    assert response.json() == details


def test_claim_creation_uses_billing_prefix(client):
    claim = {"Claim_ID": 9, "Claim_Status": "Submitted"}
    with patch("app.api.v1.endpoints.billing.BillingService") as service:
        service.return_value.submit_insurance_claim.return_value = claim
        response = client.post(
            f"{settings.API_V1_STR}/billing/invoices/1/claims",
            json={"policy_id": 3, "claimed_amount": "200"},
        )
        arguments = service.return_value.submit_insurance_claim.call_args.kwargs
        assert arguments["invoice_id"] == 1
        assert arguments["policy_id"] == 3
        assert str(arguments["claimed_amount"]) == "200"
    assert response.status_code == 200
    assert response.json() == claim


@pytest.mark.parametrize("path,service_method,parameters", [
    ("branch-daily-summary", "get_branch_daily_summary", {"report_date": "2026-10-08"}),
    ("doctor-revenue", "get_doctor_revenue", {"start_date": "2026-10-01", "end_date": "2026-10-08"}),
    ("outstanding-balances", "get_outstanding_balances", {}),
    ("treatment-usage", "get_treatment_usage", {"start_date": "2026-10-01", "end_date": "2026-10-08"}),
    ("insurance-vs-out-of-pocket", "get_insurance_vs_out_of_pocket", {"start_date": "2026-10-01", "end_date": "2026-10-08"}),
])
def test_all_management_reports_keep_reports_prefix(client, path, service_method, parameters):
    rows = [{"Branch_ID": 5}]
    with patch("app.api.v1.endpoints.reports.ReportService") as service:
        method = getattr(service.return_value, service_method)
        method.return_value = rows
        response = client.get(
            f"{settings.API_V1_STR}/reports/{path}", params={**parameters, "branch_id": 5}
        )
        assert method.call_args.kwargs["branch_id"] == 5
        for name, value in parameters.items():
            assert method.call_args.kwargs[name].isoformat() == value
    assert response.status_code == 200
    assert response.json() == rows
