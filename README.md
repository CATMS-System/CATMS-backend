# CATMS Backend Service

Welcome to the backend repository of the **Clinic Appointment and Treatment Management System (CATMS)**.

CATMS is a clinic management system created for outpatient healthcare centers in Sri Lanka. It helps manage multi-branch clinics, patient records, doctor schedules, appointments, clinical consultations, prescriptions, billing, insurance claims, and clinic reports.

This backend service is built with **Python**, **FastAPI**, and **MySQL 8.0**. It uses direct SQL queries with **PyMySQL** (Option C architecture) instead of an ORM to keep database operations fast, clear, and reliable.

---

## Table of Contents
1. [What This Repository Does](#what-this-repository-does)
2. [Live Demo & Cloud Hosting](#live-demo--cloud-hosting)
3. [How the Backend Connects to the Frontend](#how-the-backend-connects-to-the-frontend)
4. [Main Implemented Features](#main-implemented-features)
5. [Team Workload Distribution](#team-workload-distribution)
6. [Additional Features & Future Work](#additional-features--future-work)
7. [Technologies Used](#technologies-used)
8. [System Requirements](#system-requirements)
9. [Local Setup Without Docker](#local-setup-without-docker)
10. [Running with Docker Compose](#running-with-docker-compose)
11. [API URLs & Health Check](#api-urls--health-check)
12. [Database Setup & Demo Data](#database-setup--demo-data)
13. [Environment Configuration](#environment-configuration)
14. [Running Backend Tests](#running-backend-tests)
15. [Project Structure Overview](#project-structure-overview)
16. [Troubleshooting Common Issues](#troubleshooting-common-issues)
17. [Security Notes](#security-notes)

---

## What This Repository Does

The backend service handles all database operations, business calculations, and security checks for CATMS:
- **Direct Database Access (PyMySQL)**: Uses clear, plain SQL queries and transactions rather than heavy ORM layers.
- **Safe Database Operations**: Critical actions like booking appointments, completing visits, and recording payments use stored procedures (`sp_book_appointment`, `sp_complete_consultation_and_generate_invoice`, `sp_record_payment`) so operations succeed or fail cleanly as a single unit.
- **Overlap Prevention**: A MySQL trigger (`trg_check_appointment_overlap`) prevents double-booking doctors during conflicting time slots.
- **Audit Logging**: Important data changes are tracked in an audit table with readable views (`vw_audit_log_readable`) that display usernames and branch names.

---

## Live Demo & Cloud Hosting

A live demonstration of the full CATMS system is deployed and running on free-tier cloud infrastructure:

| Component | Provider / Hosting Type | Live URL | Description |
| :--- | :--- | :--- | :--- |
| **Frontend Web App** | Render Static Site | [https://catms-frontend.onrender.com](https://catms-frontend.onrender.com) | Interactive React client with trilingual support |
| **Backend API Root** | Render Web Service | [https://catms-backend.onrender.com](https://catms-backend.onrender.com) | FastAPI REST service root |
| **Interactive API Docs** | Render Web Service | [https://catms-backend.onrender.com/docs](https://catms-backend.onrender.com/docs) | Swagger UI for exploring and testing API endpoints |
| **Alternative API Docs** | Render Web Service | [https://catms-backend.onrender.com/redoc](https://catms-backend.onrender.com/redoc) | ReDoc API specifications |
| **Backend Health Check** | Render Web Service | [https://catms-backend.onrender.com/api/v1/health](https://catms-backend.onrender.com/api/v1/health) | Live service and cloud database health status |

> [!NOTE]
> **Free Tier Sleep Notice**: Free services on Render automatically spin down or sleep after 15 minutes of inactivity. When visiting the site or API after a period of idleness, the first request may take approximately 30–50 seconds while the web service spins back up. Subsequent requests respond immediately.

> [!CAUTION]
> **Educational & Demo Use Only**: This deployment is strictly for academic and demonstration purposes. It contains fictional sample data only and **must not be used with real patient data** or clinical records.

---

## How the Backend Connects to the Frontend

The backend runs on port `8000` and provides a REST API:

```text
  CATMS Frontend (React / Vite on port 5173)
                     |
                     |  HTTP requests with Bearer Token
                     v
  CATMS Backend  (FastAPI on port 8000)
                     |
                     |  PyMySQL connection (port 3306)
                     v
  MySQL 8.0 Database (Local or Docker container)
```

- **CORS Support**: The backend allows requests from the frontend at `http://localhost:5173`.
- **JWT Authentication**: Users log in at `/api/v1/auth/login` to receive an access token. The frontend sends this token in the `Authorization: Bearer <token>` header for protected API calls.
- **Friendly Errors**: Database errors (such as duplicate identity card numbers or booking collisions) are returned as clear HTTP 400 or 409 responses with helpful error text instead of internal server errors.

---

## Main Implemented Features

1. **Authentication & User Roles**:
   - Secure login with role-based permissions: `Admin`, `Branch_Manager`, `Doctor`, `Receptionist`, `Nurse`, `Billing_Staff`, and `Patient`.
   - Password change endpoint (`/api/v1/auth/change-password`).
2. **Branch & Staff Management**:
   - Manages multiple clinic branches (Colombo Main, Kandy, Galle, Kurunegala, Jaffna).
   - Staff directory with role assignments and branch transfers.
3. **Patient & Insurance Records**:
   - Patient registration with National Identity Card (NIC), contact numbers, and emergency contacts.
   - Cross-branch patient search by name, NIC, or phone.
   - Insurance provider management and policy linking with coverage percentages.
4. **Doctor Schedules & Appointments**:
   - Weekly doctor shift scheduling and available time slot calculations.
   - Scheduled bookings, emergency walk-ins, cancellations with audit reasons, and rescheduling.
   - Live waiting queue endpoint by branch (`/api/v1/appointments/queue`).
5. **Clinical Consultations & Prescriptions**:
   - Records patient vitals (blood pressure, heart rate, temperature, SpO2) and clinical diagnosis notes.
   - Itemized treatment prescriptions from an active catalogue with price snapshots.
   - Automatic invoice generation when a doctor completes a consultation.
6. **Invoicing, Payments & Claims**:
   - Calculates remaining patient dues and insurance coverage (`fn_policy_coverage`).
   - Insurance claim submission with status tracking (`Submitted`, `Under_Review`, `Approved`, `Rejected`, `Settled`).
   - Payment recording supporting cash, card, and bank transfers.
7. **Clinic Reports**:
   - Report 1: Appointments by branch and booking type (scheduled vs walk-in).
   - Report 2: Doctor revenue from consultations and treatments.
   - Report 3: Outstanding patient dues and unpaid balances.
   - Report 4: Treatment category usage.
   - Report 5: Insurance coverage compared to patient out-of-pocket payments.
8. **Full-Stack Containerization**:
   - Docker Compose can run MySQL 8.0, the backend, and the frontend together in one command using `docker-compose.full.yml`.
   - The frontend repository must be placed in a sibling folder named `CATMS-frontend` alongside `CATMS-backend` so Docker Compose can find and build the frontend container.

---

## Team Workload Distribution

As confirmed in the project document `TEAM_WORKLOAD_DISTRIBUTION.md`, the workload is divided among 5 team members across distinct full-stack functional areas:

* **Member 1: Core Foundation, Security & Clinic Administration (Coordinator)**:
  - Base architecture setup (FastAPI app factory, CORS, connection pooling, error handlers).
  - JWT authentication and role-based access dependencies (`get_current_user`, `require_roles`).
  - Endpoints and services for authentication (`/auth/login`, `/auth/me`), branches (`/branches`), staff (`/staff`), and audit logs (`/audit-logs`).
  - Database tables: `User_Account`, `Audit_Log`, `Branch`, `Staff`.
  - Lead reviewer for pull requests and system integration.
* **Member 2: Patient Registration & Insurance Management**:
  - Patient data models, validators (NIC, phone, date of birth), and registration endpoints.
  - Emergency contacts and cross-branch search endpoints (`/patients`).
  - Insurance provider management and policy linking (`/insurance/providers`, `/patients/{id}/policies`).
  - Database tables: `Patient`, `Emergency_Contact`, `Insurance_Provider`, `Insurance_Policy`.
* **Member 3: Doctor Availability & Appointment Lifecycle**:
  - Doctor specialty mapping and weekly scheduling grids (`/doctors`, `/specialties`).
  - Available time slot calculations and atomic booking stored procedure (`sp_book_appointment`).
  - Doctor appointment overlap prevention trigger (`trg_check_appointment_overlap`).
  - Endpoints for appointments, emergency walk-ins, rescheduling, cancellations, and waiting queues.
  - Database tables: `Doctor`, `Specialty`, `Doctor_Specialty`, `Doctor_Schedule`, `Appointment`.
* **Member 4: Clinical Consultations & Treatment Prescriptions**:
  - Treatment catalogue search, category filters, and policy coverage lookups (`/treatments`).
  - Consultation recording (vitals, clinical notes, diagnosis, follow-up date).
  - Multi-item prescription handling and atomic visit completion procedure (`sp_complete_consultation_and_generate_invoice`).
  - Database tables: `Treatment_Category`, `Treatment_Catalogue`, `Treatment_Policy_Eligibility`, `Consultation`, `Prescribed_Treatment`.
* **Member 5: Billing, Insurance Claims, Payments & Management Reports**:
  - Invoicing, balance calculation function (`fn_calculate_patient_balance`), and payment procedure (`sp_record_payment`).
  - Insurance claim filing, status workflows, and claim limit trigger (`trg_insurance_claim_rules`).
  - SQL implementations and API endpoints for all 5 analytical management reports (`/reports/*`).
  - Database tables: `Invoice`, `Insurance_Claim`, `Payment`.

---

## Additional Features & Future Work

### Implemented Enhancements
- **Clean Error Messaging**: Database signals and constraint checks return readable JSON messages for the UI instead of unhandled exceptions.
- **Random First Password**: Automatically creates a temporary initial password when registering new patients.
- **Real Names in Audit Log**: Uses the database view `vw_audit_log_readable` to display real staff usernames and branch names instead of generic placeholders.
- **Performance Indexes**: Added targeted database indexes in `sql/03_indexes.sql` for high-traffic appointment, date, and invoice searches.
- **Rich Seed Data Generator**: `sql/seed_demo_data.py` creates a realistic 60-day demo history with 40 patients and ~780 appointments.
- **Automated CI Workflow**: A GitHub Actions Continuous Integration (CI) workflow runs tests and checks against an automated MySQL 8.0 container on every push and pull request. (This workflow runs tests and builds only; it does not deploy the application).
- **Full-Stack Containerization**: Docker packages the backend and frontend as separate images. The `docker-compose.full.yml` file runs MySQL, the backend API, and the frontend together, and initializes the database on first startup. Run `docker compose -f docker-compose.full.yml up --build` from the backend repository. The frontend repository must be in a sibling folder.
- **Cloud Hosting & Live Deployment**: The complete project is deployed and accessible online using free-tier cloud infrastructure:
  - **Frontend**: Hosted as a **Render Static Site** at [https://catms-frontend.onrender.com](https://catms-frontend.onrender.com) with global CDN delivery.
  - **Backend API**: Runs as a **Render Web Service** (Python / FastAPI) at [https://catms-backend.onrender.com](https://catms-backend.onrender.com).
  - **Cloud Database**: Managed **MySQL 8.0** database hosted on **Aiven**, supporting all project schemas, views, stored procedures (`sp_book_appointment`, `sp_complete_consultation_and_generate_invoice`, `sp_record_payment`), and triggers (`trg_check_appointment_overlap`).
- **Responsive UI/UX**: The frontend adapts to phone, tablet, and desktop screens, with improved mobile navigation and layouts. Keyboard navigation, dialogs, and touch controls have also been made more accessible.

### Possible Future Improvements (Not Implemented Yet)
- **Email, SMS, and Push Notifications**: Sending automated reminders for appointment bookings and payment receipts is not implemented in the current code; all queue and appointment statuses are currently viewed directly in the application UI.
- **Online Payment Gateway**: Adding external payment processors like Stripe or PayHere.
- **File Uploads**: Attaching PDF or image lab reports directly to patient consultation records.
- **Recurring Shifts**: Automatically repeating doctor schedules across future weeks.

---

## Technologies Used

- **Python**: 3.11 or 3.12 (also tested on 3.14)
- **FastAPI**: Modern, high-performance web framework for APIs
- **PyMySQL**: Pure-Python MySQL client for direct SQL execution
- **MySQL 8.0**: Relational database server
- **Pydantic v2**: Request data validation and response schemas
- **PyJWT & Passlib**: Secure password hashing (bcrypt) and JWT tokens
- **Uvicorn**: Lightweight ASGI web server
- **Pytest**: Automated testing framework
- **Docker & Docker Compose**: Containerization for MySQL and full-stack deployment
- **Cloud Hosting**: Render (FastAPI Web Service) & Aiven (Managed MySQL 8.0 Database)

---

## System Requirements

To run the backend locally, you will need:
- **Git**
- **Python 3.11 or 3.12**
- **pip** (Python package installer)
- **MySQL 8.0** installed locally, OR **Docker Desktop** to run MySQL in a container

---

## Local Setup Without Docker

If you already have MySQL 8.0 running on your computer:

### 1. Clone the Repository
```bash
git clone https://github.com/CATMS-System/CATMS-backend.git
cd CATMS-backend
```

### 2. Create and Activate a Virtual Environment
**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On macOS or Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Create Your Environment File
Copy the example file to create `.env`:
```bash
cp .env.example .env
```
Open `.env` and set your local MySQL credentials:
```ini
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_local_password
DB_NAME=CatMS
DB_USE_SSL=false
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SECRET_KEY=careflow-secret-key-for-dev-jwt-tokens-2026
```

### 5. Set Up the Database
Make sure MySQL is running, then run the database script:
```bash
python sql/run_all.py
```
*(Optional)* If you want a fuller demo dataset with 40 patients and ~780 appointments for testing reports:
```bash
python sql/seed_demo_data.py
```

### 6. Start the Backend Server
```bash
python run.py
```
Or with Uvicorn:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Running with Docker Compose

You can use Docker Compose in two ways:

### Option 1: Run MySQL in Docker, Run Code Locally
This is the most common way to develop locally:
1. Start the MySQL container:
   ```bash
   docker compose up -d
   ```
2. Wait about 10 seconds for MySQL to be ready, then initialize the database:
   ```bash
   python sql/run_all.py
   ```
3. Start the backend:
   ```bash
   python run.py
   ```

### Option 2: Full-Stack Stack (MySQL + Backend + Frontend)
The repository includes a complete full-stack Compose setup in `docker-compose.full.yml`.

> **Important**: This Compose file expects the frontend repository to be located in a sibling folder named `CATMS-frontend`:
> ```text
> your-project-folder/
>   ├── CATMS-backend/      <-- Current directory
>   └── CATMS-frontend/     <-- Sibling directory
> ```

To start the full stack:
```bash
docker compose -f docker-compose.full.yml up --build
```

This starts:
1. MySQL 8.0 on port `3306` with automatic health checks.
2. A database initializer container that runs `sql/init_if_empty.py` to create tables and seed data automatically.
3. The FastAPI backend on `http://localhost:8000`.
4. The React frontend on `http://localhost:5173`.

> **Note on GitHub Codespaces**: If you test this project in GitHub Codespaces, keep in mind that Codespaces is a temporary cloud development and demo environment. It will shut down when inactive and does not provide permanent production hosting.

---

## API URLs & Health Check

When the backend is running, you can access these URLs in your browser:

| Resource | URL | Description |
| :--- | :--- | :--- |
| **API Home** | [http://localhost:8000/](http://localhost:8000/) | Welcome message and API links |
| **Interactive Docs (Swagger UI)** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive testing for all API endpoints |
| **Alternative Docs (ReDoc)** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Clean, readable API documentation |
| **Health Check** | [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health) | Checks API status and database connection |

A working health check returns:
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

## Database Setup & Demo Data

The database scripts in the `sql/` folder handle all database operations:

1. **`python sql/run_all.py`**:
   The main setup script. It creates:
   - Tables and constraints (`sql/01_schema.sql`)
   - Initial clinic branches, doctors, staff, and catalogue items (`sql/02_seed_data.sql`)
   - Stored functions, procedures, triggers, and views (`database/*`)
   - Query performance indexes (`sql/03_indexes.sql`)
2. **`python sql/seed_demo_data.py`**:
   Adds an optional realistic demo dataset containing 40 patients, appointments, invoices, and payments over the last 60 days.
3. **`python sql/init_if_empty.py`**:
   Checks if the database is empty and automatically runs `run_all.py`. Used by Docker Compose on first startup.

---

## Environment Configuration

Configuration values are defined in `app/core/config.py` and read from your `.env` file:

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `DB_HOST` | `localhost` | Database host (`127.0.0.1` or `mysql` in Docker) |
| `DB_PORT` | `3306` | MySQL port |
| `DB_USER` | `root` | Database username |
| `DB_PASSWORD` | `root` | Database password |
| `DB_NAME` | `CatMS` | Database name |
| `DB_USE_SSL` | `false` | Whether to use SSL for database connections |
| `SERVER_HOST` | `0.0.0.0` | IP address the API server listens on |
| `SERVER_PORT` | `8000` | Port the API server listens on |
| `SECRET_KEY` | *(dev fallback)* | Secret key used to sign and verify JWT login tokens |

> **Security Note**: Never commit your real `.env` file or passwords to Git. Always copy `.env.example` and keep your credentials private.

---

## Running Backend Tests

CATMS has a comprehensive automated test suite using `pytest`.

### Standard Test Run
Runs all unit and repository tests:
```bash
python -m pytest -q
```
*Expected: 444 tests pass (48 database integration tests are skipped by default to avoid altering your local database).*

### Full Test Run (With Live MySQL Integration Tests)
To run all 492 tests including the live database transaction tests in `tests/test_payment_mysql_integration.py`:

**In PowerShell:**
```powershell
$env:CATMS_RUN_MYSQL_TESTS = "1"
python -m pytest -q
```

**In Bash / Linux / macOS:**
```bash
CATMS_RUN_MYSQL_TESTS=1 python -m pytest -q
```
*Expected: All 492 tests pass.*

---

## Project Structure Overview

```text
CATMS-backend/
├── app/
│   ├── api/
│   │   ├── deps.py               # Shared auth & DB dependencies
│   │   └── v1/
│   │       ├── router.py         # Main API router & health check
│   │       └── endpoints/        # Modular API routes (appointments, billing, etc.)
│   ├── core/
│   │   ├── config.py             # Settings read from .env
│   │   └── security.py           # Password hashing & JWT tokens
│   ├── db/
│   │   └── connection.py         # PyMySQL connection factory
│   ├── repositories/             # Direct SQL database queries
│   ├── schemas/                  # Pydantic request and response models
│   ├── services/                 # Business logic and transaction handling
│   └── main.py                   # FastAPI setup and CORS configuration
├── database/
│   ├── functions/                # Stored functions (*.sql)
│   ├── procedures/               # Stored procedures (*.sql)
│   ├── triggers/                 # Database triggers (*.sql)
│   └── views/                    # Reporting database views (*.sql)
├── sql/
│   ├── 01_schema.sql             # Table creation and constraints
│   ├── 02_seed_data.sql          # Seed data for branches, staff, and doctors
│   ├── 03_indexes.sql            # Performance indexes
│   ├── init_if_empty.py          # Docker database initializer
│   ├── run_all.py                # Database setup runner
│   └── seed_demo_data.py         # Realistic demo data generator
├── tests/                        # Pytest automated test suites
├── Dockerfile                    # Backend Docker container definition
├── docker-compose.yml            # Database-only Docker service
├── docker-compose.full.yml       # Full-stack Docker Compose service
├── requirements.txt              # Python library dependencies
├── run.py                        # Local server startup script
└── README.md                     # This documentation file
```

---

## Troubleshooting Common Issues

- **Database Connection Refused**:
  Make sure your MySQL server is running. If using Docker, run `docker ps` to verify that `catms-mysql` is running on port `3306`.
- **Access Denied for User 'root'**:
  Check `DB_PASSWORD` in your `.env` file to ensure it matches your MySQL root password.
- **Why are 48 tests skipped?**:
  The 48 tests in `tests/test_payment_mysql_integration.py` perform real database writes and rollbacks. They are skipped by default to keep local data safe. Set `CATMS_RUN_MYSQL_TESTS=1` to run them.
- **Port 8000 is already in use**:
  Another application is using port 8000. Stop that program or change `SERVER_PORT=8001` in your `.env` file (remember to also update the proxy in the frontend's `vite.config.js`).

---

## Security Notes

- **Educational & Demo Use Only**: This project and its live cloud deployment are intended strictly for academic demonstration and evaluation. Never use this system or its cloud instances to store or process real patient medical records or personal health information (PHI).
- **Demo Credentials**: All seed accounts and sample passwords are for testing and academic demonstration only.
- **Production Use**: Before deploying to a real server:
  1. Set a strong, unique `SECRET_KEY` in `.env`.
  2. Use a secure database password and non-root database user.
  3. Ensure `.env` is never added to Git.
  4. Restrict CORS in `app/main.py` to your real frontend domain.
