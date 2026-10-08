from datetime import date
from unittest.mock import MagicMock

import pytest

from app.services.report_service import ReportService


def test_doctor_revenue_rejects_invalid_date_range():
    db = MagicMock()
    service = ReportService(db)

    with pytest.raises(
        ValueError,
        match="Start date cannot be after end date."
    ):
        service.get_doctor_revenue(
            start_date=date(2026, 8, 24),
            end_date=date(2026, 8, 23)
        )


def test_treatment_usage_rejects_invalid_date_range():
    db = MagicMock()
    service = ReportService(db)

    with pytest.raises(
        ValueError,
        match="Start date cannot be after end date."
    ):
        service.get_treatment_usage(
            start_date=date(2026, 8, 24),
            end_date=date(2026, 8, 23)
        )


def test_insurance_report_rejects_invalid_date_range():
    db = MagicMock()
    service = ReportService(db)

    with pytest.raises(
        ValueError,
        match="Start date cannot be after end date."
    ):
        service.get_insurance_vs_out_of_pocket(
            start_date=date(2026, 8, 24),
            end_date=date(2026, 8, 23)
        )