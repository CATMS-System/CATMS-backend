# CATMS Backend Service

Welcome to the backend repository of the **Clinic Appointment and Treatment Management System (CATMS)**. 

CATMS is an end-to-end outpatient healthcare platform designed for multi-branch clinics in Sri Lanka. It manages everything from patient intake and doctor scheduling to clinical consultations, electronic prescriptions, insurance claims, billing, and executive analytics.

This service is built with **Python**, **FastAPI**, and **MySQL 8.0** using **Option C (Plain PyMySQL)** for high-performance direct SQL queries, transactions, and stored routines.

---

## Table of Contents
1. [Overview & Architecture](#overview--architecture)
2. [How Backend & Frontend Connect](#how-backend--frontend-connect)
3. [Main Implemented Features](#main-implemented-features)
4. [Team Workload Distribution](#team-workload-distribution)
5. [Additional & Future Features](#additional--future-features)
6. [Technologies Used](#technologies-used)
7. [System Requirements](#system-requirements)
8. [Local Setup (Without Docker)](#local-setup-without-docker)
9. [Running with Docker Compose](#running-with-docker-compose)
10. [URLs & Health Check](#urls--health-check)
11. [Database Initialization & Seeding](#database-initialization--seeding)
12. [Environment Configuration](#environment-configuration)
13. [Running Tests](#running-tests)
14. [Project Structure](#project-structure)
15. [Troubleshooting](#troubleshooting)
16. [Security Guidelines](#security-guidelines)

---

## Overview & Architecture

The CATMS backend manages all business logic, data persistence, and security enforcement. Rather than relying on heavy ORM abstractions, the system uses plain **PyMySQL** connection pooling with custom SQL queries, transactions, stored procedures, and triggers. This ensures data integrity, strict concurrency control, and lightning-fast responses.

Key architectural highlights:
- **Option C Plain PyMySQL**: Clean separation between database connection handling, repository queries, and service-layer business rules.
- **Atomic Operations**: Critical workflows like appointment booking (`sp_book_appointment`), consultation completion with initial invoicing (`sp_complete_consultation_and_generate_invoice`), and payment recording (`sp_record_payment`) execute atomically in MySQL.
- **Database Triggers**: Schedule collision prevention trigger (`trg_check_appointment_overlap`) prevents double-booking a physician across overlapping time blocks.
- **Auditing**: Core entity changes are captured in `Audit_Log` with readable views (`vw_audit_log_readable`).

---

## How Backend & Frontend Connect

The backend exposes a REST API at `http://localhost:8000/api/v1/`.

```
  +--------------------------+          HTTP / JSON          +-------------------------+
  |      CATMS Frontend      |  -------------------------->  |      CATMS Backend      |
  | (React / Vite on :5173)  |  <--------------------------  |   (FastAPI on :8000)    |
  +--------------------------+         Bearer Token          +-------------------------+
                                                                          |
                                                                   PyMySQL / TCP
                                                                          v
                                                             +-------------------------+
                                                             |     MySQL 8.0 Database  |
                                                             |     (Local / Docker)    |
                                                             +-------------------------+
```

- **CORS**: Configured in `app/main.py` to allow requests from `http://localhost:5173`.
- **Authentication**: Stateful JSON Web Tokens (JWT). When a user logs in via `/api/v1/auth/login`, the backend issues an access token. The frontend sends this token in the `Authorization: Bearer <token>` header on subsequent requests.
- **Error Handling**: Database integrity errors (duplicate NICs, foreign key conflicts, and trigger business rule signals) return clear 400/409 HTTP responses with descriptive messages for the frontend to display.

---

## Main Implemented Features

1. **Authentication & RBAC**:
   - Secure login with role enforcement: `Admin`, `Branch_Manager`, `Doctor`, `Receptionist`, `Nurse`, `Billing_Staff`, and `Patient`.
   - Password change endpoint (`/api/v1/auth/change-password`) with validation rules.
2. **Branch & Staff Administration**:
   - Multi-branch organization (Colombo Main, Kandy, Galle, Kurunegala, Jaffna).
   - Staff member directory with role assignments and branch transfers.
3. **Patient & Insurance Lifecycle**:
   - Patient registration with National Identity Card (NIC), phone, and emergency contact details.
   - Cross-branch patient search by name, NIC, or contact number.
   - Insurance provider management and policy linking with coverage percentages and deductibles.
4. **Doctor Schedules & Appointments**:
   - Weekly doctor shift allocation and dynamic open-slot calculation.
   - Scheduled appointment booking, emergency walk-in fast track, cancellation auditing, and rescheduling.
   - Live waiting queue endpoint by branch (`/api/v1/appointments/queue`).
5. **Clinical Consultations & Prescriptions**:
   - Clinical intake with vitals (blood pressure, heart rate, temperature, SpO2) and clinical notes.
   - Itemized treatment prescriptions with standard pricing snapshots.
   - Automatic invoice generation upon consultation completion.
6. **Billing, Payments & Insurance Claims**:
   - Detailed patient invoice balances with insurance copay calculations (`fn_policy_coverage`).
   - Insurance claim submission, status transitions (`Submitted`, `Under_Review`, `Approved`, `Rejected`, `Settled`), and claim limits enforcement.
   - Payment processing with cash, card, and bank transfer support.
7. **Operational Management Reports**:
   - Report 1: Daily and date-range appointments grouped by branch and booking type.
   - Report 2: Doctor revenue generated by consultations and treatments.
   - Report 3: Outstanding patient dues and unsettled balances.
   - Report 4: Treatment category utilization and clinical popularity.
   - Report 5: Insurance claim coverage vs. out-of-pocket patient payment ratio.

---

## Team Workload Distribution

The CATMS system was built by a collaborative 5-member team following the project workload specification:

* **Member 1 (Coordinator) – Core Foundation, Security & Clinic Administration**:
  - Foundational FastAPI setup, Plain PyMySQL connection pooling, CORS, and unified error handling.
  - JWT token generation, verification, and role-based access control (`require_roles`).
  - Endpoints and services for authentication (`/auth/login`, `/auth/me`), branches (`/branches`), staff (`/staff`), and audit logs (`/audit-logs`).
  - Lead reviewer for cross-module integration and database schema alignment.
* **Member 2 – Patient Registration & Insurance Management**:
  - Patient lifecycle schema, validators (NIC, phone, date of birth), and CRUD operations.
  - Emergency contact persistence and cross-branch search queries.
  - Insurance provider management and patient insurance policy linking.
  - Unit and integration tests for patient schemas, policies, and API endpoints.
* **Member 3 – Doctor Availability & Appointment Lifecycle**:
  - Doctor specialty mapping and weekly scheduling grids.
  - Dynamic slot availability engine and atomic booking stored procedure (`sp_book_appointment`).
  - Doctor appointment collision prevention trigger (`trg_check_appointment_overlap`).
  - Endpoints for appointments, emergency walk-ins, rescheduling, cancellations, and live waiting queues.
* **Member 4 – Clinical Consultations & Treatment Prescriptions**:
  - Treatment catalogue search, category filters, and policy coverage lookups.
  - Clinical consultation recording (vitals, diagnosis, doctor notes, follow-up date).
  - Multi-item prescription handling and atomic consultation completion procedure (`sp_complete_consultation_and_generate_invoice`).
* **Member 5 – Billing, Insurance Claims, Payments & Management Reports**:
  - Invoicing, balance calculation function (`fn_calculate_patient_balance`), and atomic payment recording (`sp_record_payment`).
  - Insurance claim filing, status workflows, and rule enforcement trigger (`trg_insurance_claim_rules`).
  - SQL implementations and API endpoints for all 5 mandatory analytical management reports.

---

## Additional & Future Features

### Features Already Implemented
- **Multilingual Error Responses**: Descriptive error messages that translate cleanly into the frontend UI without exposing raw database dumps.
- **Random First Password**: Automatic generation of temporary passwords for new patients (Fix C-2).
- **Readable Audit Trails**: `vw_audit_log_readable` joins real account names and affected branch labels instead of showing generic placeholders (Fix M-6).
- **Busiest Query Indexes**: Performance indexing in `sql/03_indexes.sql` targeting high-traffic appointment, invoice, and payment lookups.
- **Rich Seed Data Generator**: `sql/seed_demo_data.py` populates a realistic 60-day historical clinic dataset with 40 patients and ~780 appointments.
- **Automated CI Workflow**: GitHub Actions workflow testing the full database schema and test suite against an automated MySQL 8.0 container service.

### Possible Future Improvements (Not Yet Implemented)
- **SMS & Email Notifications**: Automated reminder messages for upcoming appointments and payment receipts.
- **Online Payment Gateways**: Integration with payment processors (e.g., Stripe, PayHere) for online portal payments.
- **Lab & Radiology Attachments**: Support for uploading and attaching digital lab report PDFs or images to consultations.
- **Recurring Doctor Shifts**: Bi-weekly or monthly automated schedule generation.

---

## Technologies Used

- **Language**: Python 3.11+ / Python 3.12
- **Framework**: FastAPI (Asynchronous Web Framework)
- **Database Driver**: PyMySQL (Direct SQL Execution)
- **Database Server**: MySQL 8.0
- **Validation**: Pydantic v2
- **Authentication**: PyJWT, passlib with bcrypt
- **Server Runner**: Uvicorn
- **Testing**: pytest

---

## System Requirements

Before you begin, ensure you have the following installed:
- **Git**
- **Python 3.11 or 3.12**
- **pip** (Python package installer)
- **Docker Desktop** (optional, but recommended for running MySQL easily)

---

## Local Setup (Without Docker)

Follow these steps if you have a local MySQL 8.0 server installed directly on your machine.

### Step 1: Clone and Navigate
```bash
git clone https://github.com/CATMS-System/CATMS-backend.git
cd CATMS-backend
```

### Step 2: Create a Virtual Environment
**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure the Environment File
Copy the sample environment file to create your local `.env`:
```bash
cp .env.example .env
```
Open `.env` in your text editor and adjust the database credentials to match your local MySQL configuration:
```ini
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_local_mysql_password
DB_NAME=CatMS
DB_USE_SSL=false
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SECRET_KEY=careflow-secret-key-for-dev-jwt-tokens-2026
```

### Step 5: Initialize the Database
Ensure your local MySQL service is running. Run the setup script to create the `CatMS` database, tables, triggers, views, stored procedures, and base seed records:
```bash
python sql/run_all.py
```

*(Optional)* To populate a rich demo dataset for testing reports and dashboards, run:
```bash
python sql/seed_demo_data.py
```

### Step 6: Start the Backend Service
```bash
python run.py
```
Or directly with Uvicorn:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Running with Docker Compose

You have two convenient Docker options:

### Option A: Database Only via Docker (Recommended for Local Development)
If you want to run MySQL in a container while editing and running Python code locally on your host machine:

1. Start the MySQL container:
   ```bash
   docker compose up -d
   ```
2. Wait a few seconds for MySQL to become healthy, then run the database migration script:
   ```bash
   python sql/run_all.py
   ```
3. Start the Python server locally:
   ```bash
   python run.py
   ```

### Option B: Full-Stack Stack (Database + Backend + Frontend)
The repository includes a complete full-stack Compose configuration in `docker-compose.full.yml`.

> **Note on Folder Structure**: This file expects the frontend repository to be located in a sibling folder named `CATMS-frontend` alongside this directory:
> ```text
> parent-folder/
>   ├── CATMS-backend/      <-- Current directory
>   └── CATMS-frontend/     <-- Sibling directory
> ```

To run the complete full-stack environment:
```bash
docker compose -f docker-compose.full.yml up --build
```

This single command will:
1. Start the MySQL 8.0 database container and perform health checks.
2. Run `sql/init_if_empty.py` to automatically load the schema and seed data on first boot.
3. Start the FastAPI backend container on `http://localhost:8000`.
4. Build and serve the React frontend container with Nginx on `http://localhost:5173`.

---

## URLs & Health Check

When the backend service is running, the following endpoints are available:

| Resource | URL | Description |
| :--- | :--- | :--- |
| **API Root** | [http://localhost:8000/](http://localhost:8000/) | Service welcome message and link directory |
| **Interactive Docs (Swagger)** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive API exploration and testing |
| **Alternative Docs (ReDoc)** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Clean formatted API documentation |
| **Health Check** | [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health) | Verifies API runtime and database connectivity |

A healthy response from `/api/v1/health` looks like:
```json
{
  "status": "healthy",
  "database": "connected",
  "query_result": {
    "status": 1
  }
}
```

---

## Database Initialization & Seeding

The database setup scripts are organized in the `sql/` directory:

1. **`python sql/run_all.py`**:
   The primary runner. It executes:
   - `sql/01_schema.sql` (Creates all 19 normalized tables, foreign keys, and check constraints)
   - `sql/02_seed_data.sql` (Inserts branches, roles, specialties, doctors, staff, catalogue items, and baseline users)
   - `database/functions/*.sql` (Installs custom functions like `fn_policy_coverage` and `fn_calculate_patient_balance`)
   - `database/procedures/*.sql` (Installs stored procedures: `sp_book_appointment`, `sp_complete_consultation_and_generate_invoice`, `sp_record_payment`, etc.)
   - `database/triggers/*.sql` (Installs business triggers: `trg_check_appointment_overlap`, `trg_insurance_claim_rules`, `trg_audit_core_entities`)
   - `database/views/*.sql` (Installs views: `vw_audit_log_readable`, `vw_Invoice_Summary`, `vw_staff_directory`)
   - `sql/03_indexes.sql` (Applies performance indexing on appointment dates and billing lookups)

2. **`python sql/seed_demo_data.py`**:
   Generates a realistic test dataset containing 40 patients and ~780 appointments spanning the previous 60 days and the next 14 days. Ideal for demoing the reporting dashboards.

3. **`python sql/init_if_empty.py`**:
   Inspects the database; if tables are missing, it triggers `run_all.py`. Used automatically by the Docker Compose `db-init` container.

---

## Environment Configuration

Configuration is managed via Pydantic settings in `app/core/config.py` and loaded from your `.env` file.

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DB_HOST` | `localhost` | Database hostname (`127.0.0.1` or `mysql` in Docker) |
| `DB_PORT` | `3306` | MySQL port |
| `DB_USER` | `root` | Database username |
| `DB_PASSWORD` | `root` | Database password |
| `DB_NAME` | `CatMS` | Target database schema name |
| `DB_USE_SSL` | `false` | Whether to enable SSL connection |
| `SERVER_HOST` | `0.0.0.0` | Backend bind address |
| `SERVER_PORT` | `8000` | Port for the FastAPI server |
| `SECRET_KEY` | *(dev fallback)* | Secret key used to sign and verify JWT authentication tokens |

> **Important**: Never commit real passwords, secret keys, or private `.env` files to git. Always use `.env.example` as a template.

---

## Running Tests

CATMS includes an extensive suite of automated tests verifying schema constraints, API endpoints, role permissions, and stored routines.

### Standard Test Run
To run all unit and repository tests (excluding tests requiring a dedicated disposable database):
```bash
python -m pytest -q
```

### Full Test Suite (Including Live MySQL Integration Tests)
To enable the 48 MySQL transaction and stored procedure integration tests (`tests/test_payment_mysql_integration.py`):

**In PowerShell:**
```powershell
$env:CATMS_RUN_MYSQL_TESTS = "1"
python -m pytest -q
```

**In Bash / Linux / macOS:**
```bash
CATMS_RUN_MYSQL_TESTS=1 python -m pytest -q
```

*Expected output: All 492 tests pass.*

---

## Project Structure

```text
CATMS-backend/
├── app/
│   ├── api/
│   │   ├── deps.py               # Shared auth & DB dependencies
│   │   └── v1/
│   │       ├── router.py         # Main API router & health check
│   │       └── endpoints/        # Modular domain route handlers
│   ├── core/
│   │   ├── config.py             # Environment settings & configuration
│   │   └── security.py           # Password hashing & JWT token management
│   ├── db/
│   │   └── connection.py         # PyMySQL connection factory
│   ├── repositories/             # Direct SQL data access queries
│   ├── schemas/                  # Pydantic request and response models
│   ├── services/                 # Business logic, validations, & transactions
│   └── main.py                   # FastAPI application initialization & CORS
├── database/
│   ├── functions/                # Stored functions (*.sql)
│   ├── procedures/               # Stored procedures (*.sql)
│   ├── triggers/                 # Collision & business triggers (*.sql)
│   └── views/                    # Readable reporting views (*.sql)
├── sql/
│   ├── 01_schema.sql             # Table definitions & constraints
│   ├── 02_seed_data.sql          # Seed clinics, staff, & default users
│   ├── 03_indexes.sql            # Performance indexes
│   ├── init_if_empty.py          # Automatic initializer for Docker
│   ├── run_all.py                # Database rebuild & routine runner
│   └── seed_demo_data.py         # Realistic demo data generator
├── tests/                        # Automated pytest test suites
├── Dockerfile                    # Backend container definition
├── docker-compose.yml            # Database-only Docker service
├── docker-compose.full.yml       # Complete multi-service stack
├── requirements.txt              # Python project dependencies
├── run.py                        # Local server entry point
└── README.md                     # This documentation file
```

---

## Troubleshooting

- **`Can't connect to MySQL server on 'localhost'`**:
  Ensure your MySQL container or local service is running. If using Docker, run `docker ps` to verify `catms-mysql` is healthy on port `3306`.
- **`Access denied for user 'root'@'...'`**:
  Check `DB_PASSWORD` in your `.env` file to ensure it matches the password configured in your MySQL server.
- **`48 tests skipped`**:
  Integration tests in `test_payment_mysql_integration.py` perform real database transactions and are intentionally skipped unless the environment variable `CATMS_RUN_MYSQL_TESTS=1` is set.
- **Port 8000 already in use**:
  Another application is using port 8000. Stop that process, or set `SERVER_PORT=8001` in `.env` (and update the proxy in the frontend's `vite.config.js`).

---

## Security Guidelines

- **Demo Credentials Only**: The seed accounts provided in this codebase are intended solely for academic review and demonstration purposes.
- **Production Deployments**: Before deploying to a production server:
  1. Generate a strong, random `SECRET_KEY` (at least 32 characters long).
  2. Use secure, strong database passwords.
  3. Ensure `.env` is never committed to source control.
  4. Restrict CORS origins in `app/main.py` to your production domain.
