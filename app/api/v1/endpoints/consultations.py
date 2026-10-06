"""
Clinical Consultation Endpoints.

Handles HTTP routes for recording clinical consultations, prescribing treatments,
and querying patient consultation history.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
import pymysql

from app.api.deps import get_db
from app.schemas.consultation import (
    ConsultationCreate,
    ConsultationCreateResponse,
    ConsultationHistoryItem,
    ConsultationOut,
)
from app.services.consultation_service import (
    create_consultation,
    get_consultation_by_id,
    get_patient_consultation_history,
)

router = APIRouter()


@router.post("", response_model=ConsultationCreateResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ConsultationCreateResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def record_consultation(
    payload: ConsultationCreate,
    conn: pymysql.Connection = Depends(get_db)
) -> ConsultationCreateResponse:
    """
    Record a new clinical consultation, prescribe itemized treatments,
    mark the appointment as 'Completed', and generate an 'Issued' invoice.

    - **appointment_id**: Must exist in 'Scheduled' or 'Confirmed' status with no prior consultation.
    - **diagnosis**: Required non-empty clinical diagnosis.
    - **items**: Itemized treatments validated against the Treatment Catalogue.
    - **vitals**: Formatted and prepended to Clinical_Notes.

    Maps service errors to HTTP 404 (not found), 409 (conflict / duplicate / invalid status),
    and 422 (un-processable entity / catalogue validation).
    """
    try:
        result = create_consultation(conn, payload)
        return ConsultationCreateResponse(
            consultation_id=result["consultation_id"],
            invoice_id=result["invoice_id"]
        )
    except HTTPException:
        # Re-raise explicit HTTP exceptions (404, 409, 422) as raised by service layer
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except pymysql.err.IntegrityError as e:
        errno = e.args[0] if len(e.args) > 0 else 0
        errmsg = str(e)
        if errno == 1062:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Duplicate record already exists ({errmsg})"
            )
        elif errno == 1452:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Referenced record not found ({errmsg})"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Data integrity error: {errmsg}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while creating consultation: {str(e)}"
        )


@router.get("/patient/{patient_id}", response_model=List[ConsultationHistoryItem], status_code=status.HTTP_200_OK)
def read_patient_consultation_history(
    patient_id: int,
    conn: pymysql.Connection = Depends(get_db)
) -> List[ConsultationHistoryItem]:
    """
    Retrieve chronological consultation history for a patient, ordered newest first.
    Returns a list of ConsultationHistoryItem summaries with prescribed item counts.
    Raises 404 if the patient is not found.
    """
    history = get_patient_consultation_history(conn, patient_id)
    return [ConsultationHistoryItem(**item) for item in history]


@router.get("/{consultation_id}", response_model=ConsultationOut, status_code=status.HTTP_200_OK)
def read_consultation(
    consultation_id: int,
    conn: pymysql.Connection = Depends(get_db)
) -> ConsultationOut:
    """
    Retrieve full consultation details by ID via raw SQL joining Consultation,
    Appointment, Patient, Doctor/Staff, Invoice, and Prescribed_Treatment/Treatment_Catalogue.
    Returns ConsultationOut with items and line totals.
    Raises 404 if consultation does not exist.
    """
    data = get_consultation_by_id(conn, consultation_id)
    return ConsultationOut(**data)
