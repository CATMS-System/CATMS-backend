"""
Integration tests for Billing API endpoints (M5-1).
Verifies:
1. Patient listing invoices scopes only to the caller's own invoices.
2. Patient can read their own invoice details (200 OK).
3. Patient attempting to read another patient's invoice receives 403 Forbidden.
4. Non-existent invoice returns 404 Not Found.
5. Staff roles without token receive 401 Unauthorized.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.schemas.user import UserAccount, SystemRoleEnum, AccountStatusEnum


client = TestClient(app)


def test_patient_reads_own_invoice_details():
    """Patient 1 (pat_johndoe, Account_ID=11, Patient_ID=1) reads Invoice 1 (John Doe's invoice)."""
    patient_user = UserAccount(
        Account_ID=11,
        Username="pat_johndoe",
        Password_Hash="",
        System_Role=SystemRoleEnum.Patient,
        Account_Status=AccountStatusEnum.Active,
    )
    app.dependency_overrides[get_current_user] = lambda: patient_user
    try:
        response = client.get("/api/v1/billing/invoices/1")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"
        data = response.json()
        assert "invoice" in data
        assert data["invoice"]["Invoice_ID"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_patient_reads_another_patients_invoice_returns_403():
    """Patient 1 (pat_johndoe, Account_ID=11, Patient_ID=1) attempts to read Invoice 2 (Clara Oswald's invoice)."""
    patient_user = UserAccount(
        Account_ID=11,
        Username="pat_johndoe",
        Password_Hash="",
        System_Role=SystemRoleEnum.Patient,
        Account_Status=AccountStatusEnum.Active,
    )
    app.dependency_overrides[get_current_user] = lambda: patient_user
    try:
        response = client.get("/api/v1/billing/invoices/2")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.json()}"
        assert "access denied" in response.json().get("detail", "").lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_patient_invoice_list_scopes_to_own_invoices():
    """Patient 1 (pat_johndoe, Account_ID=11, Patient_ID=1) listing invoices only sees their own invoices."""
    patient_user = UserAccount(
        Account_ID=11,
        Username="pat_johndoe",
        Password_Hash="",
        System_Role=SystemRoleEnum.Patient,
        Account_Status=AccountStatusEnum.Active,
    )
    app.dependency_overrides[get_current_user] = lambda: patient_user
    try:
        response = client.get("/api/v1/billing/invoices")
        assert response.status_code == 200
        invoices = response.json()
        assert isinstance(invoices, list)
        # All returned invoices must belong to Patient 1 (Invoice 1, etc.), never Invoice 2
        invoice_ids = [inv["Invoice_ID"] for inv in invoices]
        assert 1 in invoice_ids
        assert 2 not in invoice_ids
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_unauthenticated_request_to_invoices_returns_401():
    """Unauthenticated call to /invoices returns 401 Unauthorized."""
    response = client.get("/api/v1/billing/invoices")
    assert response.status_code == 401


def test_nonexistent_invoice_returns_404():
    """Admin requesting a non-existent invoice ID returns 404 Not Found."""
    admin_user = UserAccount(
        Account_ID=1,
        Username="admin_alana",
        Password_Hash="",
        System_Role=SystemRoleEnum.Admin,
        Account_Status=AccountStatusEnum.Active,
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        response = client.get("/api/v1/billing/invoices/999999")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_branch_manager_can_read_own_branch_invoice():
    """Branch Manager for Branch 1 (mgr_vance, Account_ID=6) can read Invoice 1 (Branch 1)."""
    manager_user = UserAccount(
        Account_ID=6,
        Username="mgr_vance",
        Password_Hash="",
        System_Role=SystemRoleEnum.Branch_Manager,
        Account_Status=AccountStatusEnum.Active,
    )
    app.dependency_overrides[get_current_user] = lambda: manager_user
    try:
        response = client.get("/api/v1/billing/invoices/1")
        assert response.status_code == 200
        data = response.json()
        assert "invoice" in data
        assert data["invoice"]["Invoice_ID"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_branch_manager_cannot_read_other_branch_invoice():
    """Branch Manager for Branch 1 (mgr_vance, Account_ID=6) reading Invoice 2 (Branch 2) receives 403."""
    manager_user = UserAccount(
        Account_ID=6,
        Username="mgr_vance",
        Password_Hash="",
        System_Role=SystemRoleEnum.Branch_Manager,
        Account_Status=AccountStatusEnum.Active,
    )
    app.dependency_overrides[get_current_user] = lambda: manager_user
    try:
        response = client.get("/api/v1/billing/invoices/2")
        assert response.status_code == 403
        assert "Branch managers can only view invoices for their own branch" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_branch_manager_invoice_list_scopes_to_own_branch():
    """Branch Manager for Branch 1 listing invoices only sees invoices from Branch 1."""
    manager_user = UserAccount(
        Account_ID=6,
        Username="mgr_vance",
        Password_Hash="",
        System_Role=SystemRoleEnum.Branch_Manager,
        Account_Status=AccountStatusEnum.Active,
    )
    app.dependency_overrides[get_current_user] = lambda: manager_user
    try:
        response = client.get("/api/v1/billing/invoices")
        assert response.status_code == 200
        invoices = response.json()
        assert isinstance(invoices, list)
        invoice_ids = [inv["Invoice_ID"] for inv in invoices]
        assert 1 in invoice_ids
        assert 2 not in invoice_ids
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_branch_manager_cannot_list_other_branch_invoices():
    """Branch Manager for Branch 1 requesting branch_id=2 invoices receives 403."""
    manager_user = UserAccount(
        Account_ID=6,
        Username="mgr_vance",
        Password_Hash="",
        System_Role=SystemRoleEnum.Branch_Manager,
        Account_Status=AccountStatusEnum.Active,
    )
    app.dependency_overrides[get_current_user] = lambda: manager_user
    try:
        response = client.get("/api/v1/billing/invoices?branch_id=2")
        assert response.status_code == 403
        assert "Branch managers can only view invoices for their own branch" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_branch_manager_without_assigned_branch_cannot_list_invoices():
    """Branch Manager without assigned branch receives 403 when listing invoices."""
    manager_user = UserAccount(
        Account_ID=9999,
        Username="unassigned_mgr",
        Password_Hash="",
        System_Role=SystemRoleEnum.Branch_Manager,
        Account_Status=AccountStatusEnum.Active,
    )
    app.dependency_overrides[get_current_user] = lambda: manager_user
    try:
        response = client.get("/api/v1/billing/invoices")
        assert response.status_code == 403
        assert "Branch manager has no assigned branch" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_billing_staff_can_read_own_branch_invoice():
    """Billing Staff for Branch 1 (billing_patel, Account_ID=7) can read Invoice 1 (Branch 1)."""
    billing_user = UserAccount(
        Account_ID=7,
        Username="billing_patel",
        Password_Hash="",
        System_Role=SystemRoleEnum.Billing_Staff,
        Account_Status=AccountStatusEnum.Active,
    )
    app.dependency_overrides[get_current_user] = lambda: billing_user
    try:
        response = client.get("/api/v1/billing/invoices/1")
        assert response.status_code == 200
        data = response.json()
        assert "invoice" in data
        assert data["invoice"]["Invoice_ID"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_billing_staff_cannot_read_other_branch_invoice():
    """Billing Staff for Branch 1 (billing_patel, Account_ID=7) reading Invoice 2 (Branch 2) receives 403."""
    billing_user = UserAccount(
        Account_ID=7,
        Username="billing_patel",
        Password_Hash="",
        System_Role=SystemRoleEnum.Billing_Staff,
        Account_Status=AccountStatusEnum.Active,
    )
    app.dependency_overrides[get_current_user] = lambda: billing_user
    try:
        response = client.get("/api/v1/billing/invoices/2")
        assert response.status_code == 403
        assert "Billing staff can only view invoices for their own branch" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_billing_staff_invoice_list_scopes_to_own_branch():
    """Billing Staff for Branch 1 listing invoices only sees invoices from Branch 1."""
    billing_user = UserAccount(
        Account_ID=7,
        Username="billing_patel",
        Password_Hash="",
        System_Role=SystemRoleEnum.Billing_Staff,
        Account_Status=AccountStatusEnum.Active,
    )
    app.dependency_overrides[get_current_user] = lambda: billing_user
    try:
        response = client.get("/api/v1/billing/invoices")
        assert response.status_code == 200
        invoices = response.json()
        assert isinstance(invoices, list)
        invoice_ids = [inv["Invoice_ID"] for inv in invoices]
        assert 1 in invoice_ids
        assert 2 not in invoice_ids
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_billing_staff_cannot_list_other_branch_invoices():
    """Billing Staff for Branch 1 requesting branch_id=2 invoices receives 403."""
    billing_user = UserAccount(
        Account_ID=7,
        Username="billing_patel",
        Password_Hash="",
        System_Role=SystemRoleEnum.Billing_Staff,
        Account_Status=AccountStatusEnum.Active,
    )
    app.dependency_overrides[get_current_user] = lambda: billing_user
    try:
        response = client.get("/api/v1/billing/invoices?branch_id=2")
        assert response.status_code == 403
        assert "Billing staff can only view invoices for their own branch" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)
