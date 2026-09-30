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

### 8. Documentation
Refer to `docs/` for additional technical documentation:
- `docs/database.md`: Database connectivity, Option C query standards, and connection lifecycle.