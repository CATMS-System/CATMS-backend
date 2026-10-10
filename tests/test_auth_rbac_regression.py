"""
Security and RBAC Regression Test Suite.
Verifies:
1. Every domain route under /api/v1 (except public /auth/login and /health) returns 401 Unauthorized
   when accessed without an authentication Bearer token.
2. Endpoints protected with require_roles return 403 Forbidden when accessed by unauthorized roles.
"""

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.api.deps import get_current_user
from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum


def test_unauthenticated_requests_return_401_on_all_domain_routes():
    """
    Loops over all registered routes in the FastAPI application and verifies that
    requesting any endpoint without a valid Bearer authentication token returns HTTP 401 Unauthorized,
    except for explicit public endpoints (/api/v1/auth/login and /api/v1/health).
    """
    # Ensure no dependency overrides are active for clean unauthenticated test
    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.pop(get_current_user, None)

    try:
        with TestClient(app) as client:
            public_endpoints = {
                "/api/v1/health",
                "/api/v1/auth/login",
            }

            openapi_paths = app.openapi()["paths"]
            tested_routes_count = 0

            for path, path_item in openapi_paths.items():
                if not path.startswith("/api/v1"):
                    continue

                if path in public_endpoints:
                    continue

                # Substitute path parameters like {patient_id} or {invoice_id} with '1'
                target_path = path
                import re
                target_path = re.sub(r"\{[a-zA-Z0-9_]+\}", "1", target_path)

                for method in path_item.keys():
                    if method.lower() in {"parameters", "servers"}:
                        continue

                    response = client.request(method.upper(), target_path)
                    assert response.status_code == 401, (
                        f"Security regression: {method.upper()} {path} (called as {target_path}) "
                        f"did not reject unauthenticated request with 401! Returned status: {response.status_code}"
                    )
                    tested_routes_count += 1

            assert tested_routes_count > 0, "No API routes were found to test."
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def test_public_endpoints_accessible_without_token():
    """
    Verifies that /health and /auth/login are reachable without a token.
    """
    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.pop(get_current_user, None)

    try:
        with TestClient(app) as client:
            health_response = client.get("/api/v1/health")
            assert health_response.status_code != 401

            # Login without form body returns 422 validation error, not 401 auth error
            login_response = client.post("/api/v1/auth/login")
            assert login_response.status_code != 401
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def test_rbac_forbidden_for_unauthorized_roles():
    """
    Verifies that role guards reject unauthorized roles with HTTP 403 Forbidden.
    """
    client = TestClient(app)

    # 1. Patient trying to record a payment -> 403
    app.dependency_overrides[get_current_user] = lambda: UserAccount(
        Account_ID=10,
        Username="patient_user",
        Password_Hash="",
        System_Role=SystemRoleEnum.Patient,
        Account_Status=AccountStatusEnum.Active,
    )
    res = client.post("/api/v1/billing/invoices/1/payments", json={"amount": "100.00", "payment_method": "Cash"})
    assert res.status_code == 403
    assert "Operation not permitted" in res.json()["detail"]

    # 2. Receptionist trying to view reports -> 403
    app.dependency_overrides[get_current_user] = lambda: UserAccount(
        Account_ID=11,
        Username="reception_user",
        Password_Hash="",
        System_Role=SystemRoleEnum.Receptionist,
        Account_Status=AccountStatusEnum.Active,
    )
    res = client.get("/api/v1/reports/branch-daily-summary?report_date=2026-10-09")
    assert res.status_code == 403
    assert "Operation not permitted" in res.json()["detail"]

    # 3. Doctor trying to access audit logs -> 403
    app.dependency_overrides[get_current_user] = lambda: UserAccount(
        Account_ID=12,
        Username="doctor_user",
        Password_Hash="",
        System_Role=SystemRoleEnum.Doctor,
        Account_Status=AccountStatusEnum.Active,
    )
    res = client.get("/api/v1/audit-logs")
    assert res.status_code == 403
    assert "Operation not permitted" in res.json()["detail"]

    # 4. Patient trying to register a staff member -> 403
    app.dependency_overrides[get_current_user] = lambda: UserAccount(
        Account_ID=13,
        Username="patient_user",
        Password_Hash="",
        System_Role=SystemRoleEnum.Patient,
        Account_Status=AccountStatusEnum.Active,
    )
    res = client.post("/api/v1/staff", json={})
    assert res.status_code == 403

    app.dependency_overrides.clear()


def test_read_users_me_returns_enriched_profile():
    """Verifies that /auth/me enriches patient and staff profiles with database records."""
    client = TestClient(app)

    # 1. Patient user (Account 11 -> Patient 1)
    app.dependency_overrides[get_current_user] = lambda: UserAccount(
        Account_ID=11,
        Username="pat_johndoe",
        Password_Hash="",
        System_Role=SystemRoleEnum.Patient,
        Account_Status=AccountStatusEnum.Active,
    )
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["Account_ID"] == 11
    assert data["System_Role"] == "Patient"
    assert data["Patient_ID"] == 1
    assert data["First_Name"] == "John"
    assert data["Last_Name"] == "Doe"

    # 2. Doctor user (Account 2 -> Staff 1 / Doctor 1)
    app.dependency_overrides[get_current_user] = lambda: UserAccount(
        Account_ID=2,
        Username="dr_bennett",
        Password_Hash="",
        System_Role=SystemRoleEnum.Doctor,
        Account_Status=AccountStatusEnum.Active,
    )
    res2 = client.get("/api/v1/auth/me")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["Account_ID"] == 2
    assert data2["System_Role"] == "Doctor"
    assert data2["Doctor_ID"] == 1
    assert data2["Staff_ID"] == 1
    assert data2["Branch_ID"] == 1

    app.dependency_overrides.clear()
