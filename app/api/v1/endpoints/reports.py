from datetime import date

import pymysql
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.services.report_service import ReportService


router = APIRouter()


@router.get("/branch-daily-summary")
def get_branch_daily_summary(
    report_date: date,
    branch_id: int | None = None,
    db: pymysql.Connection = Depends(get_db)
):
    report_service = ReportService(db)

    return report_service.get_branch_daily_summary(
        report_date=report_date,
        branch_id=branch_id
    )


@router.get("/doctor-revenue")
def get_doctor_revenue(
    start_date: date,
    end_date: date,
    branch_id: int | None = None,
    db: pymysql.Connection = Depends(get_db)
):
    report_service = ReportService(db)

    try:
        return report_service.get_doctor_revenue(
            start_date=start_date,
            end_date=end_date,
            branch_id=branch_id
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.get("/outstanding-balances")
def get_outstanding_balances(
    branch_id: int | None = None,
    db: pymysql.Connection = Depends(get_db)
):
    report_service = ReportService(db)

    return report_service.get_outstanding_balances(
        branch_id=branch_id
    )

@router.get("/treatment-usage")
def get_treatment_usage(
    start_date: date,
    end_date: date,
    branch_id: int | None = None,
    db: pymysql.Connection = Depends(get_db)
):
    report_service = ReportService(db)

    try:
        return report_service.get_treatment_usage(
            start_date=start_date,
            end_date=end_date,
            branch_id=branch_id
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.get("/insurance-vs-out-of-pocket")
def get_insurance_vs_out_of_pocket(
    start_date: date,
    end_date: date,
    branch_id: int | None = None,
    db: pymysql.Connection = Depends(get_db)
):
    report_service = ReportService(db)

    try:
        return report_service.get_insurance_vs_out_of_pocket(
            start_date=start_date,
            end_date=end_date,
            branch_id=branch_id
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )