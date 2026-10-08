# CATMS API Reference: Doctor & Appointment Services

## 1. Overview & Architecture

- **Base URL**: `http://localhost:8000/api/v1`
- **Interactive Documentation**: `http://localhost:8000/docs` (Swagger UI), `http://localhost:8000/redoc` (ReDoc)
- **Data Access Pattern**: Option C (FastAPI + Plain PyMySQL + DictCursor + Pydantic v2)
- **Default Port Configuration**: Backend on port `8000`, Frontend on port `5173`, MySQL on port `3306`

### Standard Error Response Format
All errors return standard JSON payloads with an informative `detail` string:
```json
{
  "detail": "Error description message"
}
```

---

## 2. Doctor & Specialty Endpoints

### 2.1 List Doctors
- **Route**: `GET /api/v1/doctors`
- **Description**: Retrieves active doctors with joined staff profile, branch name, and specialty list.
- **Query Parameters**:
  - `branch_id` *(optional, integer)*: Filter by clinic branch ID.
  - `specialty_id` *(optional, integer)*: Filter by medical specialty ID.
  - `search` *(optional, string)*: Case-insensitive search on doctor first or last name.
- **Response**: `200 OK`
```json
[
  {
    "Doctor_ID": 1,
    "Staff_ID": 3,
    "First_Name": "Alexander",
    "Last_Name": "Bennett",
    "Full_Name": "Alexander Bennett",
    "Email": "alexander.bennett@catms.lk",
    "Contact_Number": "+94 77 111 2233",
    "Branch_ID": 1,
    "Branch_Name": "Colombo Main Clinic",
    "License_Number": "SLMC-88321",
    "Standard_Consultation_Fee": 2500.0,
    "Specialties": ["Cardiology"]
  }
]
```

---

### 2.2 Get Doctor Profile
- **Route**: `GET /api/v1/doctors/{doctor_id}`
- **Description**: Returns detailed profile for a specific physician by primary key.
- **Path Parameters**:
  - `doctor_id` *(integer, required)*: Unique Doctor ID.
- **Response**: `200 OK` (Doctor profile) or `404 Not Found`.

---

### 2.3 Get Doctor Weekly Schedules
- **Route**: `GET /api/v1/doctors/{doctor_id}/schedules`
- **Description**: Retrieves recurring weekly shift blocks for the physician.
- **Query Parameters**:
  - `branch_id` *(optional, integer)*: Filter shifts by branch.
- **Response**: `200 OK`
```json
[
  {
    "Schedule_ID": 1,
    "Doctor_ID": 1,
    "Branch_ID": 1,
    "Branch_Name": "Colombo Main Clinic",
    "Day_Of_Week": "Monday",
    "Start_Time": "08:00:00",
    "End_Time": "12:00:00",
    "Shift_Duration_Minutes": 240,
    "Availability_Status": "Active"
  }
]
```

---

### 2.4 Compute Available Booking Slots
- **Route**: `GET /api/v1/doctors/{doctor_id}/available-slots`
- **Description**: Dynamically calculates open appointment intervals by slicing shift blocks and subtracting active bookings.
- **Query Parameters**:
  - `date` *(date, required)*: Target date (`YYYY-MM-DD`).
  - `duration_minutes` *(optional, integer, default: 30)*: Interval length (15 to 120 mins).
  - `branch_id` *(optional, integer)*: Restrict to specific branch.
- **Response**: `200 OK`
```json
[
  {
    "Start_Time": "09:30:00",
    "End_Time": "10:00:00",
    "Duration_Minutes": 30,
    "Branch_ID": 1,
    "Branch_Name": "Colombo Main Clinic",
    "Schedule_ID": 1,
    "Date": "2026-08-23"
  }
]
```

---

### 2.5 List Specialties Catalog
- **Route**: `GET /api/v1/specialties`
- **Description**: Returns all medical specialties with assigned doctor counts.
- **Response**: `200 OK`

---

## 3. Appointment Booking & Retrieval Endpoints

### 3.1 Book Standard Appointment
- **Route**: `POST /api/v1/appointments`
- **Description**: Atomically creates a scheduled appointment after verifying foreign keys and executing overlap validation.
- **Request Body**:
```json
{
  "patient_id": 1,
  "doctor_id": 1,
  "branch_id": 1,
  "appointment_date": "2026-11-20",
  "start_time": "10:00:00",
  "duration_minutes": 30,
  "appointment_type": "Standard",
  "reason_for_visit": "Bi-annual cardiac health review",
  "schedule_id": 1
}
```
- **Responses**:
  - `201 Created`: Appointment record successfully created (`Status: Scheduled`).
  - `400 Bad Request`: Invalid patient, doctor, or branch foreign key reference.
  - `409 Conflict`: Requested interval overlaps with an existing booking for the doctor.
  - `422 Unprocessable Entity`: Request body validation failed (e.g. invalid date format).

---

### 3.2 Register Emergency / Walk-In Appointment
- **Route**: `POST /api/v1/appointments/walk-in`
- **Description**: Fast-path creation for unscheduled patients. Automatically sets `Schedule_ID = NULL`, `Appointment_Type = 'Walk_In'`, and immediate `Status = 'Confirmed'`.
- **Request Body**:
```json
{
  "patient_id": 3,
  "doctor_id": 1,
  "branch_id": 1,
  "reason_for_visit": "Acute severe shortness of breath",
  "duration_minutes": 15,
  "triage_urgency": "Critical",
  "appointment_date": "2026-11-21",
  "start_time": "11:00:00"
}
```
- **Responses**:
  - `201 Created`: Walk-in created and confirmed.
  - `400 Bad Request`: Validation failure.
  - `409 Conflict`: Target doctor occupied at requested emergency time slot.

---

### 3.3 List Appointments with Filtering
- **Route**: `GET /api/v1/appointments`
- **Description**: Retrieves appointments matching search parameters, ordered chronologically.
- **Query Parameters**:
  - `date` *(optional, date)*: Filter by appointment date (`YYYY-MM-DD`).
  - `doctor_id` *(optional, integer)*: Filter by doctor ID.
  - `branch_id` *(optional, integer)*: Filter by branch ID.
  - `status` *(optional, string)*: Filter by status (`Scheduled`, `Confirmed`, `Completed`, `Cancelled`, `No_Show`).
- **Response**: `200 OK` (Array of appointment records).

---

### 3.4 Get Appointment Details
- **Route**: `GET /api/v1/appointments/{appointment_id}`
- **Description**: Retrieves full details for a single appointment including patient identity, doctor profile, and clinic branch.
- **Path Parameters**:
  - `appointment_id` *(integer, required)*: Unique Appointment ID.
- **Responses**:
  - `200 OK`: Full appointment record.
  - `404 Not Found`: Appointment not found.

---

## 4. Lifecycle Modification & Clinic Queue Endpoints

### 4.1 Reschedule Appointment
- **Route**: `PUT /api/v1/appointments/{appointment_id}/reschedule`
- **Description**: Moves an appointment to a new date and time slot. Validates doctor availability with self-exclusion (permits duration and start-time changes within same booking).
- **Path Parameters**:
  - `appointment_id` *(integer, required)*: Unique Appointment ID.
- **Request Body**:
```json
{
  "new_date": "2026-11-25",
  "new_start_time": "15:00:00",
  "duration_minutes": 30,
  "reschedule_reason": "Patient requested afternoon shift"
}
```
- **Responses**:
  - `200 OK`: Updated appointment record with audit reason appended.
  - `400 Bad Request`: Lifecycle violation (cannot reschedule `Cancelled` or `Completed` bookings).
  - `404 Not Found`: Appointment not found.
  - `409 Conflict`: Target slot collides with another booking for the doctor.

---

### 4.2 Cancel Appointment
- **Route**: `PUT /api/v1/appointments/{appointment_id}/cancel`
- **Description**: Marks appointment as `Cancelled` and stores mandatory audit cancellation reason.
- **Path Parameters**:
  - `appointment_id` *(integer, required)*: Unique Appointment ID.
- **Request Body**:
```json
{
  "cancellation_reason": "Patient called to cancel due to family emergency"
}
```
- **Responses**:
  - `200 OK`: Cancelled appointment record with `Status: Cancelled`.
  - `400 Bad Request`: Appointment already cancelled or completed.
  - `404 Not Found`: Appointment not found.
  - `422 Unprocessable Entity`: Cancellation reason shorter than 3 characters.

---

### 4.3 Aggregated Appointment Status Metrics
- **Route**: `GET /api/v1/appointments/metrics/status-counts`
- **Description**: Returns live operational counts across all statuses for reception dashboard oversight.
- **Query Parameters**:
  - `date` *(optional, date)*: Filter metrics by date.
  - `branch_id` *(optional, integer)*: Filter metrics by clinic branch.
  - `doctor_id` *(optional, integer)*: Filter metrics by doctor.
- **Response**: `200 OK`
```json
{
  "Total": 14,
  "Scheduled": 4,
  "Confirmed": 3,
  "Completed": 5,
  "Cancelled": 1,
  "No_Show": 1,
  "Walk_In": 2
}
```

---

### 4.4 Live Clinic Waiting Queue
- **Route**: `GET /api/v1/appointments/queue`
- **Description**: Real-time queue for reception desk and doctor consultation room display. Ordered chronologically (`Start_Time ASC, Appointment_ID ASC`).
- **Query Parameters**:
  - `branch_id` *(integer, required)*: Clinic branch ID.
  - `date` *(optional, date)*: Target queue date (defaults to current date).
- **Response**: `200 OK`
```json
[
  {
    "Queue_Number": 1,
    "Appointment_ID": 10,
    "Patient_ID": 1,
    "Patient_Name": "John Doe",
    "Patient_Phone": "+94 77 123 4567",
    "Doctor_ID": 1,
    "Doctor_Name": "Alexander Bennett",
    "Branch_ID": 1,
    "Branch_Name": "Colombo Main Clinic",
    "Appointment_Date": "2026-11-28",
    "Start_Time": "10:00:00",
    "Duration_Minutes": 20,
    "Appointment_Type": "Standard",
    "Status": "Scheduled",
    "Reason_For_Visit": "Cardiology Review",
    "Estimated_Wait_Minutes": 0
  },
  {
    "Queue_Number": 2,
    "Appointment_ID": 11,
    "Patient_ID": 2,
    "Patient_Name": "Jane Smith",
    "Patient_Phone": "+94 71 987 6543",
    "Doctor_ID": 1,
    "Doctor_Name": "Alexander Bennett",
    "Branch_ID": 1,
    "Branch_Name": "Colombo Main Clinic",
    "Appointment_Date": "2026-11-28",
    "Start_Time": "10:30:00",
    "Duration_Minutes": 25,
    "Appointment_Type": "Walk_In",
    "Status": "Confirmed",
    "Reason_For_Visit": "[High Urgency] Chest tightness",
    "Estimated_Wait_Minutes": 20
  }
]
```

---

## 5. Summary of HTTP Status Codes

| Code | Status | Usage |
|:---|:---|:---|
| `200` | OK | Successful retrieval or update operation |
| `201` | Created | Successfully booked standard or walk-in appointment |
| `400` | Bad Request | Business rule or foreign key validation failure |
| `404` | Not Found | Requested entity (Doctor, Appointment) does not exist |
| `409` | Conflict | Overlapping appointment collision detected for doctor |
| `422` | Unprocessable Entity | Pydantic payload schema or constraint validation error |
| `500` | Server Error | Internal server or database execution exception |


