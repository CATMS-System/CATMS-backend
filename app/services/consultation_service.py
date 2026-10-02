"""
Consultation Service.

Provides database operations and business logic for clinical consultations.
Service functions receive a PyMySQL connection (`pymysql.Connection`) as a parameter.
"""

from typing import Any, Dict, Union
from fastapi import HTTPException, status
import pymysql
import pymysql.cursors

from app.schemas.consultation import ConsultationCreate


def create_consultation(
    conn: pymysql.Connection,
    payload: Union[ConsultationCreate, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Initiates clinical consultation creation for an appointment under a pessimistic lock.
    Validates appointment existence (404), active booking status (409), and ensures no
    duplicate consultation exists (409).
    """
    appointment_id = (
        payload.appointment_id
        if hasattr(payload, "appointment_id")
        else payload["appointment_id"]
    )

    try:
        conn.begin()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. SELECT Appointment FOR UPDATE to acquire pessimistic row lock
            cursor.execute(
                """
                SELECT Appointment_ID, Patient_ID, Doctor_ID, Branch_ID, Appointment_Date, Status
                FROM Appointment
                WHERE Appointment_ID = %s
                FOR UPDATE
                """,
                (appointment_id,)
            )
            appointment = cursor.fetchone()

            # 2. Raise 404 if missing
            if not appointment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Appointment {appointment_id} not found"
                )

            # 3. Raise 409 unless Status is 'Scheduled' or 'Confirmed'
            appt_status = appointment.get("Status")
            if appt_status not in ("Scheduled", "Confirmed"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot create consultation for appointment {appointment_id} with status '{appt_status}'. Must be 'Scheduled' or 'Confirmed'."
                )

            # 4. Raise 409 if a Consultation already exists for it
            cursor.execute(
                """
                SELECT Consultation_ID
                FROM Consultation
                WHERE Appointment_ID = %s
                """,
                (appointment_id,)
            )
            existing_consultation = cursor.fetchone()
            if existing_consultation:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A consultation (ID: {existing_consultation['Consultation_ID']}) already exists for appointment {appointment_id}."
                )

            # Early return after initial validation check (no insert yet)
            conn.commit()
            return {
                "message": "Appointment validated successfully for consultation creation",
                "appointment_id": appointment["Appointment_ID"],
                "status": appointment["Status"],
                "patient_id": appointment["Patient_ID"],
                "doctor_id": appointment["Doctor_ID"],
            }
    except Exception as e:
        conn.rollback()
        raise e
