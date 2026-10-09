"""
Consultation Service.

Provides database operations and business logic for clinical consultations.
Service functions receive a PyMySQL connection (`pymysql.Connection`) as a parameter.
"""

from datetime import date, time, timedelta
from decimal import Decimal
import re
from typing import Any, Dict, List, Optional, Union
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
    Inserts into Consultation with formatted vitals in Clinical_Notes.
    Validates prescribed items against Treatment_Catalogue (422) and inserts into
    Prescribed_Treatment using authoritative standard unit prices.
    Completes appointment ('Completed') and generates 'Issued' Invoice via stored procedure
    `sp_complete_consultation_and_generate_invoice` (with fallback to inline SQL).
    Rolls back on any exception; commits on success.
    Returns consultation_id and invoice_id.
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
    items = (
        payload.items
        if hasattr(payload, "items")
        else payload.get("items", [])
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

            # 7. Validate and INSERT prescribed items
            prescribed_items_out: List[Dict[str, Any]] = []
            if items:
                for item in items:
                    treatment_id = (
                        item.treatment_id
                        if hasattr(item, "treatment_id")
                        else item["treatment_id"]
                    )
                    quantity = (
                        item.quantity
                        if hasattr(item, "quantity")
                        else item.get("quantity", 1)
                    )
                    instructions = (
                        item.instructions
                        if hasattr(item, "instructions")
                        else item.get("instructions")
                    )

                    # Query Treatment_Catalogue (must exist and be Active)
                    cursor.execute(
                        """
                        SELECT Treatment_ID, Service_Code, Treatment_Name, Standard_Unit_Price, Treatment_Status
                        FROM Treatment_Catalogue
                        WHERE Treatment_ID = %s
                        """,
                        (treatment_id,)
                    )
                    treatment = cursor.fetchone()
                    if not treatment:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Treatment ID {treatment_id} does not exist in the catalogue."
                        )
                    if treatment["Treatment_Status"] != "Active":
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Treatment ID {treatment_id} ('{treatment['Treatment_Name']}') is not active."
                        )

                    # Authoritative server-side price (never trust client-sent prices)
                    billed_unit_price = treatment["Standard_Unit_Price"]

                    cursor.execute(
                        """
                        INSERT INTO Prescribed_Treatment (
                            Consultation_ID,
                            Treatment_ID,
                            Quantity,
                            Billed_Unit_Price,
                            Instructions
                        ) VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            consultation_id,
                            treatment_id,
                            quantity,
                            billed_unit_price,
                            instructions,
                        )
                    )
                    prescription_item_id = cursor.lastrowid

                    prescribed_items_out.append({
                        "prescription_item_id": prescription_item_id,
                        "treatment_id": treatment_id,
                        "service_code": treatment["Service_Code"],
                        "treatment_name": treatment["Treatment_Name"],
                        "quantity": quantity,
                        "billed_unit_price": billed_unit_price,
                        "line_total": Decimal(str(quantity)) * billed_unit_price,
                        "instructions": instructions,
                    })

            # 8. Complete consultation and generate invoice via stored procedure
            # (marks Appointment Status='Completed' and generates 'Issued' Invoice)
            try:
                cursor.execute(
                    "CALL sp_complete_consultation_and_generate_invoice(%s, @invoice_id)",
                    (consultation_id,)
                )
                cursor.execute("SELECT @invoice_id AS invoice_id")
                inv_res = cursor.fetchone()
                invoice_id = inv_res["invoice_id"] if inv_res else None
            except pymysql.err.OperationalError as proc_err:
                # Fallback to inline SQL if stored procedure is not yet registered (error 1305)
                if len(proc_err.args) > 0 and proc_err.args[0] == 1305:
                    cursor.execute(
                        "UPDATE Appointment SET Status = 'Completed' WHERE Appointment_ID = %s",
                        (appointment_id,)
                    )
                    cursor.execute(
                        """
                        SELECT d.Standard_Consultation_Fee
                        FROM Appointment a
                        JOIN Doctor d ON a.Doctor_ID = d.Doctor_ID
                        WHERE a.Appointment_ID = %s
                        """,
                        (appointment_id,)
                    )
                    doc_row = cursor.fetchone()
                    fee = doc_row["Standard_Consultation_Fee"] if doc_row else Decimal("0.00")
                    cursor.execute(
                        """
                        INSERT INTO Invoice (
                            Consultation_ID,
                            Invoice_Date,
                            Billed_Consultation_Fee,
                            Invoice_Status
                        ) VALUES (%s, CURRENT_DATE, %s, 'Issued')
                        """,
                        (consultation_id, fee)
                    )
                    invoice_id = cursor.lastrowid
                else:
                    raise proc_err

            # Commit the single atomic transaction
            conn.commit()

            return {
                "consultation_id": consultation_id,
                "invoice_id": invoice_id,
                "appointment_id": appointment_id,
                "consultation_date": date.today(),
                "diagnosis": diagnosis,
                "clinical_notes": clinical_notes,
                "doctor_notes": doctor_notes,
                "follow_up_date": follow_up_date,
                "items": prescribed_items_out,
            }
    except Exception as e:
        conn.rollback()
        raise e


def format_time_hh_mm(val: Any) -> Optional[str]:
    """Converts a timedelta, time object, or time string to 'HH:MM' format."""
    if isinstance(val, timedelta):
        total_seconds = int(val.total_seconds())
        hours = (total_seconds // 3600) % 24
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    elif isinstance(val, time):
        return val.strftime("%H:%M")
    elif isinstance(val, str):
        return val[:5]
    return None


def parse_vitals_from_notes(clinical_notes: Optional[str]) -> Optional[VitalsIn]:
    """Attempts to extract structured vitals from seed-style clinical notes prefix."""
    if not clinical_notes or not clinical_notes.startswith("Vitals:"):
        return None
    try:
        prefix = clinical_notes.split(".", 1)[0]
        bp_match = re.search(r"BP\s+([0-9]+/[0-9]+)", prefix)
        hr_match = re.search(r"HR\s+([0-9]+)", prefix)
        temp_match = re.search(r"Temp\s+([0-9]+(?:\.[0-9]+)?)", prefix)
        spo2_match = re.search(r"SpO2\s+([0-9]+)%", prefix)
        weight_match = re.search(r"Weight\s+([0-9]+(?:\.[0-9]+)?)", prefix)

        bp = bp_match.group(1) if bp_match else None
        hr = int(hr_match.group(1)) if hr_match else None
        temp = float(temp_match.group(1)) if temp_match else None
        spo2 = int(spo2_match.group(1)) if spo2_match else None
        weight = float(weight_match.group(1)) if weight_match else None

        if any(v is not None for v in (bp, hr, temp, spo2, weight)):
            return VitalsIn(bp=bp, heart_rate=hr, temperature=temp, spo2=spo2, weight=weight)
    except Exception:
        pass
    return None


def get_consultation_by_id(
    conn: pymysql.Connection,
    consultation_id: int
) -> Dict[str, Any]:
    """
    Retrieves full clinical consultation details by ID via raw SQL joining Consultation,
    Appointment, Patient, Doctor/Staff, Invoice, and Prescribed_Treatment/Treatment_Catalogue.
    Converts any TIME column (e.g. Start_Time) from timedelta to 'HH:MM' string.
    Raises HTTP 404 if not found.
    """
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        query = """
        SELECT 
            c.Consultation_ID,
            c.Appointment_ID,
            c.Consultation_Date,
            c.Diagnosis,
            c.Clinical_Notes,
            c.Doctor_Notes,
            c.Follow_Up_Date,
            a.Appointment_Date,
            a.Start_Time,
            CONCAT(p.First_Name, ' ', p.Last_Name) AS Patient_Name,
            CONCAT(s.First_Name, ' ', s.Last_Name) AS Doctor_Name,
            i.Invoice_ID,
            pt.Prescription_Item_ID,
            pt.Treatment_ID,
            tc.Service_Code,
            tc.Treatment_Name,
            pt.Quantity,
            pt.Billed_Unit_Price,
            ROUND(pt.Quantity * pt.Billed_Unit_Price, 2) AS Line_Total,
            pt.Instructions
        FROM Consultation c
        JOIN Appointment a ON c.Appointment_ID = a.Appointment_ID
        JOIN Patient p ON a.Patient_ID = p.Patient_ID
        JOIN Doctor d ON a.Doctor_ID = d.Doctor_ID
        JOIN Staff s ON d.Doctor_ID = s.Staff_ID
        LEFT JOIN Invoice i ON c.Consultation_ID = i.Consultation_ID
        LEFT JOIN Prescribed_Treatment pt ON c.Consultation_ID = pt.Consultation_ID
        LEFT JOIN Treatment_Catalogue tc ON pt.Treatment_ID = tc.Treatment_ID
        WHERE c.Consultation_ID = %s
        ORDER BY pt.Prescription_Item_ID ASC
        """
        cursor.execute(query, (consultation_id,))
        rows = cursor.fetchall()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consultation {consultation_id} not found"
        )

    first_row = rows[0]

    # Convert any TIME column (such as Start_Time) from timedelta to "HH:MM"
    start_time_val = first_row.get("Start_Time")
    start_time_str = format_time_hh_mm(start_time_val) if start_time_val is not None else None

    # Collect prescribed items with line totals
    items_out: List[Dict[str, Any]] = []
    if first_row.get("Prescription_Item_ID") is not None:
        for r in rows:
            qty = r["Quantity"]
            unit_price = r["Billed_Unit_Price"]
            line_tot = r.get("Line_Total")
            if line_tot is None and qty is not None and unit_price is not None:
                line_tot = Decimal(str(qty)) * unit_price

            items_out.append({
                "prescription_item_id": r["Prescription_Item_ID"],
                "treatment_id": r["Treatment_ID"],
                "service_code": r["Service_Code"],
                "treatment_name": r["Treatment_Name"],
                "quantity": qty,
                "billed_unit_price": unit_price,
                "line_total": line_tot,
                "instructions": r.get("Instructions"),
            })

    # Optional vitals parse from notes
    vitals_obj = parse_vitals_from_notes(first_row.get("Clinical_Notes"))

    return {
        "consultation_id": first_row["Consultation_ID"],
        "appointment_id": first_row["Appointment_ID"],
        "consultation_date": first_row["Consultation_Date"],
        "diagnosis": first_row["Diagnosis"],
        "clinical_notes": first_row["Clinical_Notes"],
        "doctor_notes": first_row.get("Doctor_Notes"),
        "follow_up_date": first_row.get("Follow_Up_Date"),
        "patient_name": first_row["Patient_Name"],
        "doctor_name": first_row["Doctor_Name"],
        "appointment_date": first_row.get("Appointment_Date"),
        "start_time": start_time_str,
        "vitals": vitals_obj,
        "items": items_out,
        "invoice_id": first_row.get("Invoice_ID"),
    }


def get_patient_consultation_history(
    conn: pymysql.Connection,
    patient_id: int
) -> List[Dict[str, Any]]:
    """
    Retrieves chronological consultation history for a patient, ordered newest first.
    Includes consultation ID, date, diagnosis, doctor name, follow-up date, and count of
    prescribed treatment items.
    Raises 404 if the patient does not exist.
    """
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        # Verify patient exists
        cursor.execute("SELECT Patient_ID FROM Patient WHERE Patient_ID = %s", (patient_id,))
        patient = cursor.fetchone()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient {patient_id} not found"
            )

        query = """
        SELECT 
            c.Consultation_ID,
            c.Consultation_Date,
            c.Diagnosis,
            c.Follow_Up_Date,
            CONCAT(s.First_Name, ' ', s.Last_Name) AS Doctor_Name,
            COUNT(pt.Prescription_Item_ID) AS item_count
        FROM Consultation c
        JOIN Appointment a ON c.Appointment_ID = a.Appointment_ID
        JOIN Doctor d ON a.Doctor_ID = d.Doctor_ID
        JOIN Staff s ON d.Doctor_ID = s.Staff_ID
        LEFT JOIN Prescribed_Treatment pt ON c.Consultation_ID = pt.Consultation_ID
        WHERE a.Patient_ID = %s
        GROUP BY 
            c.Consultation_ID,
            c.Consultation_Date,
            c.Diagnosis,
            c.Follow_Up_Date,
            s.First_Name,
            s.Last_Name
        ORDER BY c.Consultation_Date DESC, c.Consultation_ID DESC
        """
        cursor.execute(query, (patient_id,))
        rows = cursor.fetchall()

    return [
        {
            "consultation_id": r["Consultation_ID"],
            "consultation_date": r["Consultation_Date"],
            "diagnosis": r["Diagnosis"],
            "doctor_name": r["Doctor_Name"],
            "follow_up_date": r["Follow_Up_Date"],
            "item_count": r["item_count"],
        }
        for r in rows
    ]


