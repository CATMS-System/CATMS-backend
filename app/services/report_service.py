from datetime import date
import pymysql

from app.repositories.report_repository import ReportRepository


class ReportService:

    def __init__(self, db: pymysql.Connection):
        self.db = db
        self.report_repository = ReportRepository(db)

    def get_branch_daily_summary(
        self,
        report_date: date,
        branch_id=None
    ):
        return self.report_repository.get_branch_daily_summary(
            report_date=report_date,
            branch_id=branch_id
        )

    def get_doctor_revenue(
        self,
        start_date: date,
        end_date: date,
        branch_id=None
    ):
        self._validate_date_range(start_date, end_date)

        return self.report_repository.get_doctor_revenue(
            start_date=start_date,
            end_date=end_date,
            branch_id=branch_id
        )

    def get_outstanding_balances(
        self,
        branch_id=None
    ):
        return self.report_repository.get_outstanding_balances(
            branch_id=branch_id
        )

    def get_treatment_usage(
        self,
        start_date: date,
        end_date: date,
        branch_id=None
    ):
        self._validate_date_range(start_date, end_date)

        return self.report_repository.get_treatment_usage(
            start_date=start_date,
            end_date=end_date,
            branch_id=branch_id
        )

    def get_insurance_vs_out_of_pocket(
        self,
        start_date: date,
        end_date: date,
        branch_id=None
    ):
        self._validate_date_range(start_date, end_date)

        return self.report_repository.get_insurance_vs_out_of_pocket(
            start_date=start_date,
            end_date=end_date,
            branch_id=branch_id
        )

    def _validate_date_range(
        self,
        start_date: date,
        end_date: date
    ):
        if start_date > end_date:
            raise ValueError(
                "Start date cannot be after end date."
            )