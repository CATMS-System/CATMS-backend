"""
Doctor and Specialty API Endpoints (Option C: Plain PyMySQL).
Provides RESTful HTTP routes for physician directory lookup, filtering by branch
and medical specialty, profile detail retrieval, weekly schedule inspection,
and dynamic available appointment slot calculation.
"""

from datetime import date
from typing import List, Optional
import pymysql
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status

from app.api.deps import get_db
from app.schemas.doctor import (
    DoctorListItemResponse,
    DoctorDetailResponse,
    SpecialtyResponse,
    DoctorScheduleResponse,
    AvailableSlotResponse,
)
from app.services.doctor_service import (
    get_all_doctors,
    get_doctor_by_id,
    get_all_specialties,
    get_doctor_schedules,
    DoctorNotFoundError,
)
from app.services.appointment_service import get_doctor_available_slots

# Router for /api/v1/doctors
router = APIRouter()

# Router for /api/v1/specialties
specialties_router = APIRouter()


@specialties_router.get(
    "",
    response_model=List[SpecialtyResponse],
    summary="List all medical specialties",
    description="Retrieves all registered medical specialties with the number of practicing physicians.",
)
def list_specialties(
    conn: pymysql.Connection = Depends(get_db),
) -> List[SpecialtyResponse]:
    """
    Retrieves all medical specialties with doctor counts.
    """
    return get_all_specialties(conn)


@router.get(
    "",
    response_model=List[DoctorListItemResponse],
    summary="List doctors with optional filters",
    description="Retrieves doctors matching optional filters (branch_id, specialty_id, search across name and license).",
)
def list_doctors(
    branch_id: Optional[int] = Query(
        default=None,
        description="Filter doctors by home branch ID",
        ge=1,
    ),
    specialty_id: Optional[int] = Query(
        default=None,
        description="Filter doctors by medical specialty ID",
        ge=1,
    ),
    search: Optional[str] = Query(
        default=None,
        description="Search doctors by name or SLMC license number",
        min_length=1,
        max_length=100,
    ),
    conn: pymysql.Connection = Depends(get_db),
) -> List[DoctorListItemResponse]:
    """
    Retrieves doctors with joined branch information and comma-separated specialty titles.
    """
    return get_all_doctors(
        conn,
        branch_id=branch_id,
        specialty_id=specialty_id,
        search=search,
    )


@router.get(
    "/specialties",
    response_model=List[SpecialtyResponse],
    summary="List all medical specialties (alias under /doctors)",
    description="Convenience route to retrieve registered specialties under /api/v1/doctors/specialties.",
    tags=["Specialties", "Doctors"],
)
def list_doctor_specialties_alias(
    conn: pymysql.Connection = Depends(get_db),
) -> List[SpecialtyResponse]:
    """
    Alias endpoint for retrieving medical specialties.
    """
    return get_all_specialties(conn)


@router.get(
    "/{doctor_id}",
    response_model=DoctorDetailResponse,
    summary="Get doctor profile by ID",
    description="Retrieves the detailed profile of a single doctor including practicing specialties and branch info.",
)
def get_doctor(
    doctor_id: int = Path(..., description="Unique Doctor ID", ge=1),
    conn: pymysql.Connection = Depends(get_db),
) -> DoctorDetailResponse:
    """
    Retrieves full physician details by Doctor ID.
    Raises 404 NOT FOUND if the doctor does not exist.
    """
    try:
        return get_doctor_by_id(conn, doctor_id)
    except DoctorNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{doctor_id}/schedules",
    response_model=List[DoctorScheduleResponse],
    summary="Get weekly schedules for a doctor",
    description="Retrieves weekly working hours and branch assignments for a doctor.",
)
def get_doctor_weekly_schedules(
    doctor_id: int = Path(..., description="Unique Doctor ID", ge=1),
    branch_id: Optional[int] = Query(default=None, description="Optional branch ID filter", ge=1),
    conn: pymysql.Connection = Depends(get_db),
) -> List[DoctorScheduleResponse]:
    """
    Retrieves doctor weekly schedule blocks with branch location and shift duration.
    Raises 404 NOT FOUND if the doctor does not exist.
    """
    try:
        get_doctor_by_id(conn, doctor_id)
    except DoctorNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return get_doctor_schedules(conn, doctor_id=doctor_id, branch_id=branch_id)


@router.get(
    "/{doctor_id}/available-slots",
    response_model=List[AvailableSlotResponse],
    summary="Calculate available appointment slots for a doctor",
    description="Computes available booking time slots for a doctor on a specific date by checking working shifts against existing bookings.",
)
def get_available_slots(
    doctor_id: int = Path(..., description="Unique Doctor ID", ge=1),
    date: date = Query(..., description="Target appointment date (YYYY-MM-DD)"),
    duration_minutes: int = Query(
        default=30,
        description="Slot duration in minutes (e.g. 15, 20, 30)",
        ge=5,
        le=120,
    ),
    branch_id: Optional[int] = Query(default=None, description="Optional branch ID filter", ge=1),
    schedule_id: Optional[int] = Query(default=None, description="Optional schedule ID filter", ge=1),
    conn: pymysql.Connection = Depends(get_db),
) -> List[AvailableSlotResponse]:
    """
    Computes available appointment slots for a doctor on a given date.
    Excludes any slot that overlaps with an existing Scheduled, Confirmed, or Completed booking.
    Raises 404 NOT FOUND if the doctor does not exist.
    """
    try:
        return get_doctor_available_slots(
            conn,
            doctor_id=doctor_id,
            appointment_date=date,
            slot_duration_minutes=duration_minutes,
            branch_id=branch_id,
            schedule_id=schedule_id,
        )
    except DoctorNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
