# CATMS Backend Service

Backend service for the Clinic Appointment and Treatment Management System (CATMS), built with Python FastAPI and MySQL 8.0 (local via Docker) using **Option C (Plain PyMySQL)**.

## Setup Instructions

### 1. Prerequisites
- Python 3.11+
- Git
- Docker Desktop

### 2. Start the Database
Install and start Docker Desktop, then start the MySQL 8.0 container:

```bash
docker-compose up -d
```

Wait about 15 seconds for MySQL to initialize, then run the database migration and seed script:

```bash
python sql/run_all.py
```

The full runner recreates tables and loads seed data; use it only for a fresh or
disposable database. It then installs the billing balance function, invoice summary
view, and payment procedure in dependency order.

To install or update only those billing SQL objects on an existing Docker database:

```bash
python sql/run_all.py --billing-only
```

This replaces the billing function/procedure and updates the view without changing
tables or seed records. Deploy these objects before running the updated backend.
`sp_record_payment` must be called inside a caller-owned transaction: begin, call,
consume result sets, read its three OUT values, then commit; roll back on any failure.
The procedure locks the invoice until commit and does not start or commit a transaction.
Its amount input is plain decimal text (the service sends `format(amount, "f")`).
It validates precision before converting to `DECIMAL(10, 2)`, so callers cannot
silently round fractional cents. API payments must be positive, fit the existing
database monetary range, and be exactly representable with two decimal places;
trailing zeros are accepted. Claim status updates may supply a non-null
`approved_amount` only when the target status is `Approved`.

Run the backend suite with disposable Docker payment tests enabled (PowerShell):

```powershell
$env:CATMS_RUN_MYSQL_TESTS = "1"
python -m pytest -q
```

These tests require the local seeded MySQL 8.0 database. They create their own
appointment, consultation, invoice, treatment, claim, and payment records, then
remove only those records and verify existing invoices/payments are unchanged.

### 3. Environment Setup
Create and activate a virtual environment:

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configuration
Copy the environment template and configure your database credentials:

```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```

Open `.env` and fill in your database credentials:
- `DB_HOST`: Database host (e.g. `localhost`)
- `DB_PORT`: Database port (default: `3306`)
- `DB_USER`: Database username
- `DB_PASSWORD`: Database password
- `DB_NAME`: Database name (`CatMS`)
- `SERVER_HOST`: Backend host (default: `0.0.0.0`)
- `SERVER_PORT`: Backend port (default: `8000`)

### 6. Verify Database Connection
Test connectivity to the database:

```bash
python test_connection.py
```
Or run the Option C test:
```bash
python tests/test_health.py
```

### 7. Run the Backend Service
Start the FastAPI server on port `8000`:

```bash
python run.py
```
Or directly with Uvicorn:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- API Base URL: `http://localhost:8000`
- Interactive Swagger Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/v1/health`

Billing and report routers live in `app/api/v1/endpoints/` and are registered in
`app/api/v1/router.py`. Billing uses `/api/v1/billing` for invoice listing/details,
payments, claims, and claim status updates. Management reports use `/api/v1/reports`.
The earlier `/api/v1/invoices` and `/api/v1/claims` routes are no longer registered;
deploy the frontend billing API update together with this backend change.

### 8. Documentation
Refer to `docs/` for additional technical documentation:
- `docs/database.md`: Database connectivity, Option C query standards, and connection lifecycle.
