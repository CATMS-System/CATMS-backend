from datetime import date

import pymysql
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user, get_db, get_staff_branch_id, require_roles
from app.schemas.user import SystemRoleEnum, UserAccount
from app.services.report_service import ReportService


router = APIRouter(
    dependencies=[Depends(require_roles([
        SystemRoleEnum.Admin,
        SystemRoleEnum.Branch_Manager,
        SystemRoleEnum.Billing_Staff,
    ]))]
)


def enforce_report_branch(
    current_user: UserAccount,
    requested_branch_id: int | None,
    db: pymysql.Connection,
) -> int | None:
    if current_user.System_Role == SystemRoleEnum.Branch_Manager:
        manager_branch_id = get_staff_branch_id(db, current_user)
        if not manager_branch_id:
            raise HTTPException(
                status_code=403,
                detail="Branch manager has no assigned branch."
            )
        if requested_branch_id is not None and requested_branch_id != manager_branch_id:
            raise HTTPException(
                status_code=403,
                detail="Branch managers can only view reports for their own branch."
            )
        return manager_branch_id
    return requested_branch_id


@router.get("/branch-daily-summary")
def get_branch_daily_summary(
    report_date: date,
    branch_id: int | None = None,
    db: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    effective_branch_id = enforce_report_branch(current_user, branch_id, db)
    report_service = ReportService(db)

    return report_service.get_branch_daily_summary(
        report_date=report_date,
        branch_id=effective_branch_id,
    )


@router.get("/doctor-revenue")
def get_doctor_revenue(
    start_date: date,
    end_date: date,
    branch_id: int | None = None,
    db: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    effective_branch_id = enforce_report_branch(current_user, branch_id, db)
    report_service = ReportService(db)

    try:
        return report_service.get_doctor_revenue(
            start_date=start_date,
            end_date=end_date,
            branch_id=effective_branch_id,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.get("/outstanding-balances")
def get_outstanding_balances(
    branch_id: int | None = None,
    db: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    effective_branch_id = enforce_report_branch(current_user, branch_id, db)
    report_service = ReportService(db)

    return report_service.get_outstanding_balances(
        branch_id=effective_branch_id,
    )


@router.get("/treatment-usage")
def get_treatment_usage(
    start_date: date,
    end_date: date,
    branch_id: int | None = None,
    db: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    effective_branch_id = enforce_report_branch(current_user, branch_id, db)
    report_service = ReportService(db)

    try:
        return report_service.get_treatment_usage(
            start_date=start_date,
            end_date=end_date,
            branch_id=effective_branch_id,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.get("/insurance-vs-out-of-pocket")
def get_insurance_vs_out_of_pocket(
    start_date: date,
    end_date: date,
    branch_id: int | None = None,
    db: pymysql.Connection = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    effective_branch_id = enforce_report_branch(current_user, branch_id, db)
    report_service = ReportService(db)

    try:
        return report_service.get_insurance_vs_out_of_pocket(
            start_date=start_date,
            end_date=end_date,
            branch_id=effective_branch_id,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )