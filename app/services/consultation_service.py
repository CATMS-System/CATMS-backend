"""
Consultation Service.

Provides database operations and business logic for clinical consultations.
Service functions receive a PyMySQL connection (`pymysql.Connection`) as a parameter.
"""

from datetime import date
from typing import Any, Dict, Optional, Union
from fastapi import HTTPException, status
import pymysql
import pymysql.cursors

from app.schemas.consultation import ConsultationCreate, VitalsIn


def format_clinical_notes_with_vitals(
    vitals: Optional[Union[VitalsIn, Dict[str, Any]]],
    clinical_notes: Optional[str]
) -> Optional[str]:
    """
    Prepends patient vital signs to clinical notes in CATMS seed data format:
    e.g. 'Vitals: BP 138/88 mmHg, HR 76 bpm, Temp 36.8 C, SpO2 98%, Weight 74 kg. Doctor notes...'
    """
    vitals_parts = []
    if vitals:
        bp = getattr(vitals, "bp", None) if not isinstance(vitals, dict) else vitals.get("bp")
        hr = getattr(vitals, "heart_rate", None) if not isinstance(vitals, dict) else vitals.get("heart_rate")
        temp = getattr(vitals, "temperature", None) if not isinstance(vitals, dict) else vitals.get("temperature")
        spo2 = getattr(vitals, "spo2", None) if not isinstance(vitals, dict) else vitals.get("spo2")
        weight = getattr(vitals, "weight", None) if not isinstance(vitals, dict) else vitals.get("weight")

        if bp:
            bp_str = str(bp).strip()
            vitals_parts.append(f"BP {bp_str}" if "mmHg" in bp_str else f"BP {bp_str} mmHg")
        if hr is not None:
            vitals_parts.append(f"HR {hr} bpm")
        if temp is not None:
            temp_str = f"{temp:g}" if isinstance(temp, (int, float)) else str(temp)
            vitals_parts.append(f"Temp {temp_str} C")
        if spo2 is not None:
            vitals_parts.append(f"SpO2 {spo2}%")
        if weight is not None:
            weight_str = f"{weight:g}" if isinstance(weight, (int, float)) else str(weight)
            vitals_parts.append(f"Weight {weight_str} kg")

    vitals_prefix = f"Vitals: {', '.join(vitals_parts)}." if vitals_parts else None

    if vitals_prefix and clinical_notes and clinical_notes.strip():
        return f"{vitals_prefix} {clinical_notes.strip()}"
    elif vitals_prefix:
        return vitals_prefix
    elif clinical_notes and clinical_notes.strip():
        return clinical_notes.strip()
    return None


def create_consultation(
    conn: pymysql.Connection,
    payload: Union[ConsultationCreate, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Initiates clinical consultation creation for an appointment under a pessimistic lock.
    Validates appointment existence (404), active booking status (409), and ensures no
    duplicate consultation exists (409).
    Inserts into Consultation with formatted vitals in Clinical_Notes and commits.
    """
    appointment_id = (
        payload.appointment_id
        if hasattr(payload, "appointment_id")
        else payload["appointment_id"]
    )
    diagnosis = (
        payload.diagnosis
        if hasattr(payload, "diagnosis")
        else payload["diagnosis"]
    )
    raw_clinical_notes = (
        payload.clinical_notes
        if hasattr(payload, "clinical_notes")
        else payload.get("clinical_notes")
    )
    doctor_notes = (
        payload.doctor_notes
        if hasattr(payload, "doctor_notes")
        else payload.get("doctor_notes")
    )
    follow_up_date = (
        payload.follow_up_date
        if hasattr(payload, "follow_up_date")
        else payload.get("follow_up_date")
    )
    vitals = (
        payload.vitals
        if hasattr(payload, "vitals")
        else payload.get("vitals")
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

            # 5. Format Clinical_Notes with prepended vitals
            clinical_notes = format_clinical_notes_with_vitals(vitals, raw_clinical_notes)

            # 6. INSERT into Consultation
            cursor.execute(
                """
                INSERT INTO Consultation (
                    Appointment_ID,
                    Consultation_Date,
                    Diagnosis,
                    Clinical_Notes,
                    Doctor_Notes,
                    Follow_Up_Date
                ) VALUES (%s, CURRENT_DATE, %s, %s, %s, %s)
                """,
                (
                    appointment_id,
                    diagnosis,
                    clinical_notes,
                    doctor_notes,
                    follow_up_date,
                )
            )
            consultation_id = cursor.lastrowid

            # Commit the transaction here for now
            conn.commit()

            return {
                "consultation_id": consultation_id,
                "appointment_id": appointment_id,
                "consultation_date": date.today(),
                "diagnosis": diagnosis,
                "clinical_notes": clinical_notes,
                "doctor_notes": doctor_notes,
                "follow_up_date": follow_up_date,
            }
    except Exception as e:
        conn.rollback()
        raise e
