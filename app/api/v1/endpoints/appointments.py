"""
Appointment API Endpoints (Option C: Plain PyMySQL).
Provides RESTful HTTP routes for booking standard appointments, creating emergency walk-ins,
retrieving appointment details, date-based schedule overviews, and daily status metrics.
"""

from datetime import date, datetime
from typing import List, Optional
import pymysql
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status

from app.api.deps import get_db, require_roles
from app.schemas.user import SystemRoleEnum
from app.schemas.appointment import (
    AppointmentCreate,
    WalkInAppointmentCreate,
    AppointmentReschedule,
    AppointmentCancel,
    AppointmentResponse,
    AppointmentStatusCountsResponse,
    QueueItemResponse,
)
from app.services.appointment_service import (
    book_appointment_atomic,
    get_appointment_by_id,
    get_appointments_by_date,
    get_appointment_status_counts,
    reschedule_appointment,
    cancel_appointment,
    get_daily_queue,
    AppointmentConflictError,
    AppointmentValidationError,
)

router = APIRouter()



@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book a standard scheduled appointment",
    description="Validates slot availability against doctor schedule and existing bookings, then atomically creates an appointment.",
    dependencies=[Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager, SystemRoleEnum.Receptionist, SystemRoleEnum.Doctor, SystemRoleEnum.Patient]))],
)
def create_appointment(
    payload: AppointmentCreate,
    conn: pymysql.Connection = Depends(get_db),
) -> AppointmentResponse:
    """
    Creates a new scheduled clinic appointment.
    Returns HTTP 409 Conflict if the requested slot overlaps with an existing active booking.
    Returns HTTP 400 Bad Request if patient, doctor, or branch validation fails.
    """
    try:
        appt_type_str = payload.appointment_type.value if hasattr(payload.appointment_type, "value") else str(payload.appointment_type)
        return book_appointment_atomic(
            conn=conn,
            patient_id=payload.patient_id,
            doctor_id=payload.doctor_id,
            branch_id=payload.branch_id,
            appointment_date=payload.appointment_date,
            start_time=payload.start_time,
            duration_minutes=payload.duration_minutes,
            appointment_type=appt_type_str,
            reason_for_visit=payload.reason_for_visit,
            schedule_id=payload.schedule_id,
        )
    except AppointmentConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except AppointmentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create appointment: {str(e)}",
        )


@router.post(
    "/walk-in",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register an emergency or unscheduled walk-in appointment",
    description="Creates an unscheduled walk-in appointment with Schedule_ID=NULL, Appointment_Type='Walk_In', and immediate Confirmed status.",
    dependencies=[Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager, SystemRoleEnum.Receptionist]))],
)
def create_walk_in_appointment(
    payload: WalkInAppointmentCreate,
    conn: pymysql.Connection = Depends(get_db),
) -> AppointmentResponse:
    """
    Creates an emergency/walk-in appointment record.
    Defaults date to current date and start_time to current time if omitted.
    """
    appt_date = payload.appointment_date or date.today()
    appt_time = payload.start_time or datetime.now().time().strftime("%H:%M:%S")

    # If triage urgency is given, prepend to reason for visit
    full_reason = payload.reason_for_visit
    if payload.triage_urgency and payload.triage_urgency != "Normal":
        full_reason = f"[{payload.triage_urgency} Urgency] {payload.reason_for_visit}"

    try:
        return book_appointment_atomic(
            conn=conn,
            patient_id=payload.patient_id,
            doctor_id=payload.doctor_id,
            branch_id=payload.branch_id,
            appointment_date=appt_date,
            start_time=appt_time,
            duration_minutes=payload.duration_minutes,
            appointment_type="Walk_In",
            reason_for_visit=full_reason,
            schedule_id=None,
        )
    except AppointmentConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except AppointmentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create walk-in appointment: {str(e)}",
        )


@router.get(
    "",
    response_model=List[AppointmentResponse],
    summary="List appointments with optional date, doctor, branch, and status filters",
    description="Retrieves clinic appointments matching query filters with joined patient, doctor, and branch details.",
    dependencies=[Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager, SystemRoleEnum.Receptionist, SystemRoleEnum.Doctor, SystemRoleEnum.Patient]))],
)
def list_appointments(
    date: Optional[date] = Query(default=None, description="Filter by appointment date (YYYY-MM-DD)"),
    doctor_id: Optional[int] = Query(default=None, description="Filter by Doctor ID", ge=1),
    branch_id: Optional[int] = Query(default=None, description="Filter by Branch ID", ge=1),
    status: Optional[str] = Query(default=None, description="Filter by appointment status (Scheduled, Confirmed, Completed, Cancelled, No_Show)"),
    conn: pymysql.Connection = Depends(get_db),
) -> List[AppointmentResponse]:
    """
    Queries appointments matching criteria, ordered by date and start time.
    """
    return get_appointments_by_date(
        conn=conn,
        appointment_date=date,
        doctor_id=doctor_id,
        branch_id=branch_id,
        status=status,
    )


@router.get(
    "/metrics/status-counts",
    response_model=AppointmentStatusCountsResponse,
    summary="Get aggregated appointment status counts",
    description="Aggregates appointment status metrics for daily clinic operational oversight and queue displays.",
    dependencies=[Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager, SystemRoleEnum.Receptionist, SystemRoleEnum.Doctor]))],
)
def get_status_counts(
    date: Optional[date] = Query(default=None, description="Filter counts by appointment date (YYYY-MM-DD)"),
    branch_id: Optional[int] = Query(default=None, description="Filter counts by Branch ID", ge=1),
    doctor_id: Optional[int] = Query(default=None, description="Filter counts by Doctor ID", ge=1),
    conn: pymysql.Connection = Depends(get_db),
) -> AppointmentStatusCountsResponse:
    """
    Returns real-time status summary counts (Total, Scheduled, Confirmed, Completed, Cancelled, No_Show, Walk_In).
    """
    return get_appointment_status_counts(
        conn=conn,
        branch_id=branch_id,
        appointment_date=date,
        doctor_id=doctor_id,
    )


@router.get(
    "/queue",
    response_model=List[QueueItemResponse],
    summary="Get live clinic waiting queue",
    description="Retrieves the real-time active patient queue for a specific clinic branch and date, ordered chronologically with estimated wait times.",
    dependencies=[Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager, SystemRoleEnum.Receptionist, SystemRoleEnum.Doctor]))],
)
def get_clinic_queue(
    branch_id: int = Query(..., description="Clinic Branch ID", ge=1),
    date: Optional[date] = Query(default=None, description="Date of queue (YYYY-MM-DD); defaults to today"),
    conn: pymysql.Connection = Depends(get_db),
) -> List[QueueItemResponse]:
    """
    Returns active waiting queue for receptionist and doctor room oversight.
    """
    return get_daily_queue(
        conn=conn,
        branch_id=branch_id,
        queue_date=date,
    )


@router.get(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Get appointment details by ID",
    description="Retrieves a single appointment record with patient, doctor, and clinic details.",
    dependencies=[Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager, SystemRoleEnum.Receptionist, SystemRoleEnum.Doctor, SystemRoleEnum.Patient]))],
)
def get_appointment(
    appointment_id: int = Path(..., description="Unique Appointment ID", ge=1),
    conn: pymysql.Connection = Depends(get_db),
) -> AppointmentResponse:
    """
    Retrieves full details for a single appointment.
    Raises 404 NOT FOUND if the appointment does not exist.
    """
    appt = get_appointment_by_id(conn, appointment_id=appointment_id)
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment with ID {appointment_id} not found.",
        )
    return appt


@router.put(
    "/{appointment_id}/reschedule",
    response_model=AppointmentResponse,
    summary="Reschedule an appointment to a new date and time slot",
    description="Validates slot availability excluding current appointment, checks doctor schedule, and updates the appointment record.",
    dependencies=[Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager, SystemRoleEnum.Receptionist, SystemRoleEnum.Patient]))],
)
def reschedule_existing_appointment(
    payload: AppointmentReschedule,
    appointment_id: int = Path(..., description="Unique Appointment ID", ge=1),
    conn: pymysql.Connection = Depends(get_db),
) -> AppointmentResponse:
    """
    Reschedules an existing scheduled/confirmed appointment to a new date and time.
    Returns HTTP 409 Conflict if target slot collides with another booking.
    Returns HTTP 400 Bad Request if the appointment cannot be rescheduled.
    """
    try:
        return reschedule_appointment(
            conn=conn,
            appointment_id=appointment_id,
            new_date=payload.new_date,
            new_start_time=payload.new_start_time,
            duration_minutes=payload.duration_minutes,
            reschedule_reason=payload.reschedule_reason,
        )
    except AppointmentConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except AppointmentValidationError as e:
        if "does not exist" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reschedule appointment: {str(e)}",
        )


@router.put(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    summary="Cancel an appointment with a mandatory reason",
    description="Marks an appointment as Cancelled and records an audit cancellation reason.",
    dependencies=[Depends(require_roles([SystemRoleEnum.Admin, SystemRoleEnum.Branch_Manager, SystemRoleEnum.Receptionist, SystemRoleEnum.Doctor, SystemRoleEnum.Patient]))],
)
def cancel_existing_appointment(
    payload: AppointmentCancel,
    appointment_id: int = Path(..., description="Unique Appointment ID", ge=1),
    conn: pymysql.Connection = Depends(get_db),
) -> AppointmentResponse:
    """
    Cancels an active appointment with a required cancellation reason.
    Returns HTTP 400 Bad Request if already completed or cancelled.
    """
    try:
        return cancel_appointment(
            conn=conn,
            appointment_id=appointment_id,
            cancellation_reason=payload.cancellation_reason,
        )
    except AppointmentValidationError as e:
        if "does not exist" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel appointment: {str(e)}",
        )

