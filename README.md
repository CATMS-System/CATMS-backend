# CATMS Backend Service

Backend service for the Clinic Appointment and Treatment Management System (CATMS), built with Python FastAPI, SQLAlchemy, and MySQL (TiDB Cloud).

## Setup Instructions

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Environment Setup
Create and activate a virtual environment:

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configuration
Copy the environment template and configure your database credentials:

```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```

Open `.env` and fill in your database credentials:
- `DB_HOST`: Database host
- `DB_PORT`: Database port (default: 4000)
- `DB_USER`: Database username
- `DB_PASSWORD`: Database password
- `DB_NAME`: Database name (`CatMS`)

### 5. Verify Database Connection
Test connectivity to the database:

```bash
python test_connection.py
```

### 6. Documentation
Refer to `docs/` for additional technical documentation:
- `docs/database.md`: Database connectivity and SSL configuration guide.